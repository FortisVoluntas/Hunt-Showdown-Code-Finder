#!/usr/bin/env python3
# hunt_codes_gui_used.py
# Einmaliger Suchdurchlauf -> GUI mit Codes, Copy-Buttons + "Benutzt"-Liste (persistiert, wird beim nächsten Lauf ignoriert)
#
# Anforderungen (pip):
#   requests
#   beautifulsoup4
#   python-dateutil
#
# Hinweis für Windows-Doppelklick:
# - Wenn ein Fehler passiert (z.B. fehlendes Modul), zeigt dieses Script eine Fehlermeldung an
#   und schreibt zusätzlich ein error.log in den Konfigurationsordner.

from __future__ import annotations

import os
import re
import sys
import time
import traceback
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set

# ------------------ Konfiguration ------------------
USER_AGENT = "Mozilla/5.0 (compatible; FortisCodeFinder/1.0; +https://example.org/)"
HEADERS = {"User-Agent": USER_AGENT}
REQUEST_DELAY = 1.0  # Sekunden zwischen Requests (freundlich)
REDDIT_SUBREDDIT = "HuntShowdown"
REDDIT_QUERY = "code OR giveaway OR redeem"
REDDIT_LIMIT = 75
MAX_AGE_DAYS = 14  # nur Einträge jünger oder gleich dieser Zahl verwenden

# Format deiner Keys (z.B. EG77-2PJY-M68D-33Y1)
CODE_REGEX = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b", re.IGNORECASE)

# Optional: eigene URLs, die einmal abgefragt werden sollen (als strings)
CUSTOM_URLS: List[str] = [
    # "https://example.com/hunt-showdown-codes",
]


# ------------------ Abhängigkeiten mit klaren Fehlermeldungen ------------------

def _require_deps():
    """Importiert Abhängigkeiten und wirft bei Fehlern eine verständliche Exception."""
    try:
        import tkinter as tk  # noqa
        import tkinter.scrolledtext as scrolled  # noqa
        from tkinter import ttk, messagebox  # noqa
    except Exception as e:
        raise RuntimeError(
            "tkinter ist nicht verfügbar. Unter Windows ist es normalerweise in der Standard-Python-Installation enthalten.\n"
            "Wenn du eine 'embeddable' Python-Version nutzt oder tkinter abgewählt hast, installiere Python neu (python.org) "
            "und achte darauf, dass 'tcl/tk and IDLE' mit installiert wird."
        ) from e

    try:
        import requests  # noqa
    except Exception as e:
        raise RuntimeError(
            "Python-Modul 'requests' fehlt.\n"
            "Installiere es mit:\n"
            "  py -m pip install requests"
        ) from e

    try:
        from bs4 import BeautifulSoup  # noqa
    except Exception as e:
        raise RuntimeError(
            "Python-Modul 'beautifulsoup4' fehlt.\n"
            "Installiere es mit:\n"
            "  py -m pip install beautifulsoup4"
        ) from e

    try:
        from dateutil import parser as dateparser  # noqa
    except Exception as e:
        raise RuntimeError(
            "Python-Modul 'python-dateutil' fehlt.\n"
            "Installiere es mit:\n"
            "  py -m pip install python-dateutil"
        ) from e

    # Rückgabe der wirklich verwendeten Module (damit Linters ruhig sind)
    import tkinter as tk  # type: ignore
    import tkinter.scrolledtext as scrolled  # type: ignore
    from tkinter import ttk, messagebox  # type: ignore
    import requests  # type: ignore
    from bs4 import BeautifulSoup  # type: ignore
    from dateutil import parser as dateparser  # type: ignore
    return tk, scrolled, ttk, messagebox, requests, BeautifulSoup, dateparser


# ------------------ Persistente "Benutzt"-Liste ------------------

def get_config_dir() -> Path:
    """
    Windows:  %APPDATA%\\FortisCodeFinder
    Linux:    $XDG_CONFIG_HOME/fortis_code_finder  oder ~/.config/fortis_code_finder
    macOS:    wie Linux (XDG falls gesetzt, sonst ~/.config) – bewusst schlicht gehalten
    """
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if not appdata:
            # Fallback (sollte selten nötig sein)
            appdata = str(Path.home() / "AppData" / "Roaming")
        base = Path(appdata) / "FortisCodeFinder"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            base = Path(xdg) / "fortis_code_finder"
        else:
            base = Path.home() / ".config" / "fortis_code_finder"

    base.mkdir(parents=True, exist_ok=True)
    return base


def get_used_codes_path() -> Path:
    return get_config_dir() / "used_codes.txt"


def load_used_codes(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    used: Set[str] = set()
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip().upper()
            if s:
                used.add(s)
    except Exception:
        # Falls Datei kaputt ist o.Ä.: nicht crashen, einfach leer starten
        return set()
    return used


def append_used_code(path: Path, code: str) -> None:
    code = code.strip().upper()
    if not code:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(code + "\n")


def write_error_log(exc: BaseException) -> Path:
    cfg = get_config_dir()
    log_path = cfg / "error.log"
    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(datetime.now().isoformat() + "\n")
            f.write("Python: " + sys.version.replace("\n", " ") + "\n")
            f.write("Platform: " + sys.platform + "\n")
            f.write(traceback.format_exc() + "\n")
    except Exception:
        # Notfalls: nichts weiter tun
        pass
    return log_path


# ------------------ Datentyp ------------------

@dataclass
class FoundCode:
    code: str
    url: str
    source: str
    date: Optional[str]
    snippet: str


# ------------------ Hilfsfunktionen ------------------

def is_within_max_age(date_iso: Optional[str], max_days: int = MAX_AGE_DAYS, dateparser=None) -> bool:
    """
    date_iso: ISO-formatiertes Datum/Zeit-String (idealerweise mit TZ).
    Rückgabe: True, wenn date_iso innerhalb der letzten max_days (inklusive) liegt.
    """
    if not date_iso:
        return False
    try:
        dt = dateparser.parse(date_iso)
        if dt.tzinfo is None:
            # annehmen UTC, falls keine TZ angegeben
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age = now - dt.astimezone(timezone.utc)
        return age <= timedelta(days=max_days)
    except Exception:
        return False


# ------------------ Netzwerk / Parsing ------------------

def fetch_reddit_search(requests, subreddit: str = REDDIT_SUBREDDIT, query: str = REDDIT_QUERY, limit: int = REDDIT_LIMIT):
    url = f"https://www.reddit.com/r/{subreddit}/search.json?q={requests.utils.quote(query)}&restrict_sr=1&sort=new&limit={limit}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    results = []
    for child in data.get("data", {}).get("children", []):
        post = child.get("data", {})
        title = post.get("title", "") or ""
        selftext = post.get("selftext", "") or ""
        combined = (title + "\n" + selftext).strip()
        created_utc = post.get("created_utc")
        dt = None
        if created_utc is not None:
            dt = datetime.fromtimestamp(float(created_utc), tz=timezone.utc).isoformat()
        url_post = "https://reddit.com" + post.get("permalink", "")
        results.append({"source": "reddit", "url": url_post, "text": combined, "date": dt})
    time.sleep(REQUEST_DELAY)
    return results


def fetch_generic_url(requests, BeautifulSoup, dateparser, url: str):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    # Datumsermittlung (best effort)
    dt = None
    ttag = soup.find("time")
    if ttag and ttag.has_attr("datetime"):
        try:
            dt = dateparser.parse(ttag["datetime"]).astimezone(timezone.utc).isoformat()
        except Exception:
            dt = None
    if not dt:
        for meta_name in ("article:published_time", "og:updated_time", "date", "publishdate", "pubdate"):
            m = soup.find("meta", {"property": meta_name}) or soup.find("meta", {"name": meta_name})
            if m and m.has_attr("content"):
                try:
                    dt = dateparser.parse(m["content"]).astimezone(timezone.utc).isoformat()
                    break
                except Exception:
                    dt = None
    time.sleep(REQUEST_DELAY)
    return {"source": url, "url": url, "text": soup.get_text("\n", strip=True), "date": dt}


def extract_codes_from_item(item, dateparser) -> List[FoundCode]:
    """
    Extrahiert Codes aus item, prüft das Datum (nur <= MAX_AGE_DAYS erlaubt).
    Falls item['date'] fehlt oder älter als MAX_AGE_DAYS, werden keine Codes aus diesem Item zurückgegeben.
    """
    date_iso = item.get("date")
    if not is_within_max_age(date_iso, MAX_AGE_DAYS, dateparser=dateparser):
        return []

    text = (item.get("text") or "")
    found: List[FoundCode] = []
    for m in CODE_REGEX.finditer(text):
        code = m.group(0).upper()
        snippet_start = max(0, m.start() - 80)
        snippet_end = min(len(text), m.end() + 80)
        snippet = text[snippet_start:snippet_end].replace("\n", " ")
        found.append(FoundCode(
            code=code,
            url=item.get("url") or "",
            source=item.get("source") or "",
            date=date_iso,
            snippet=snippet
        ))
    return found


def dedupe_and_sort(found_list: List[FoundCode], dateparser) -> List[FoundCode]:
    unique: Dict[str, FoundCode] = {}
    for f in found_list:
        if f.code not in unique:
            unique[f.code] = f

    items = list(unique.values())

    def sort_key(x: FoundCode):
        d = x.date
        if not d:
            return datetime.fromtimestamp(0, tz=timezone.utc)
        try:
            return dateparser.parse(d)
        except Exception:
            return datetime.fromtimestamp(0, tz=timezone.utc)

    items.sort(key=sort_key, reverse=True)
    return items


# ------------------ GUI ------------------

class CodeFinderGUI:
    def __init__(self, root, results: List[FoundCode], used_path: Path, used_set: Set[str], tk, scrolled, ttk, messagebox):
        self.root = root
        self.tk = tk
        self.scrolled = scrolled
        self.ttk = ttk
        self.messagebox = messagebox

        self.root.title(f"Hunt Code Finder — Einmaliger Durchlauf (letzte {MAX_AGE_DAYS} Tage)")
        self.root.geometry("1024x650")
        self.root.minsize(900, 600)

        self.results = results
        self.used_path = used_path
        self.used_set = used_set

        frm = ttk.Frame(root, padding=8)
        frm.pack(fill="both", expand=True)

        top_label = ttk.Label(
            frm,
            text=f"Gefundene mögliche Codes (≤ {MAX_AGE_DAYS} Tage), ohne 'Benutzt': {len(results)}",
            font=("Segoe UI", 11, "bold")
        )
        top_label.pack(anchor="w", pady=(0, 6))

        hint = ttk.Label(
            frm,
            text=f"'Benutzt'-Liste: {used_path}",
            font=("Segoe UI", 8),
            foreground="gray"
        )
        hint.pack(anchor="w", pady=(0, 8))

        canvas = tk.Canvas(frm)
        scrollbar = ttk.Scrollbar(frm, orient="vertical", command=canvas.yview)
        self.scrollable = ttk.Frame(canvas)

        self.scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        if not results:
            ttk.Label(
                self.scrollable,
                text=f"Keine möglichen Codes gefunden (nur Einträge der letzten {MAX_AGE_DAYS} Tage werden angezeigt).\n"
                     f"Wenn du Codes erwartet hast: Prüfe ggf. error.log (Konfig-Ordner) oder starte per Konsole, um Fehlermeldungen zu sehen.",
                foreground="gray"
            ).pack(anchor="w", pady=8)
        else:
            for idx, r in enumerate(results, 1):
                self._add_code_entry(idx, r)

        bottom = ttk.Frame(frm)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Button(bottom, text="Konfig-Ordner öffnen", command=self.open_config_dir).pack(side="left", padx=8)
    def _add_code_entry(self, idx: int, item: FoundCode):
        box = self.ttk.Frame(self.scrollable, relief="groove", padding=6)
        box.pack(fill="x", pady=6)

        header = self.ttk.Frame(box)
        header.pack(fill="x")
        self.ttk.Label(header, text=f"#{idx}: {item.code}", font=("Segoe UI", 10, "bold")).pack(side="left")

        btn_frame = self.ttk.Frame(header)
        btn_frame.pack(side="right")

        self.ttk.Button(btn_frame, text="Kopieren", command=lambda c=item.code: self.copy_single(c)).pack(side="left", padx=4)
        self.ttk.Button(btn_frame, text="Öffnen", command=lambda u=item.url: webbrowser.open(u)).pack(side="left", padx=4)

        used_btn = self.ttk.Button(btn_frame, text="Benutzt", command=lambda c=item.code: self.mark_used(c))
        used_btn.pack(side="left")

        info = f"Datum (UTC): {item.date or '(nicht gefunden)'}   Quelle: {item.url}"
        info_lbl = self.ttk.Label(box, text=info, font=("Segoe UI", 8), foreground="gray", wraplength=980, justify="left")
        info_lbl.pack(anchor="w", pady=(4, 0))

        txt = self.scrolled.ScrolledText(box, height=3, wrap="word")
        txt.pack(fill="x", pady=(6, 0))
        txt.insert("1.0", item.snippet or "")
        txt.configure(state="disabled")

        # Falls in used_set (sollte bei Filterung nicht passieren), Button direkt deaktivieren
        if item.code.upper() in self.used_set:
            used_btn.configure(text="Benutzt ✓", state="disabled")

        # Referenz speichern, damit wir diesen Button später deaktivieren können
        # (einfacher: Widget im Closure suchen ist lästig -> wir mapen Code->Button)
        if not hasattr(self, "_used_buttons"):
            self._used_buttons = {}
        self._used_buttons[item.code.upper()] = used_btn

    def mark_used(self, code: str):
        code_u = code.strip().upper()
        if not code_u:
            return
        if code_u in self.used_set:
            # Schon markiert
            btn = getattr(self, "_used_buttons", {}).get(code_u)
            if btn:
                btn.configure(text="Benutzt ✓", state="disabled")
            return

        try:
            append_used_code(self.used_path, code_u)
            self.used_set.add(code_u)
            btn = getattr(self, "_used_buttons", {}).get(code_u)
            if btn:
                btn.configure(text="Benutzt ✓", state="disabled")
            self.messagebox.showinfo("Benutzt", f"Code '{code_u}' wurde in die Benutzt-Liste eingetragen.\n"
                                              f"Er wird beim nächsten Durchlauf ignoriert.")
        except Exception as e:
            self.messagebox.showerror("Fehler", f"Eintragen fehlgeschlagen: {e}")

    def copy_single(self, code: str):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            self.messagebox.showinfo("Kopiert", f"Code '{code}' in Zwischenablage kopiert.")
        except Exception as e:
            self.messagebox.showerror("Fehler", f"Kopieren fehlgeschlagen: {e}")

    def copy_all(self):
        codes = [r.code for r in self.results]
        if not codes:
            self.messagebox.showinfo("Keine Codes", "Keine Codes zum Kopieren vorhanden.")
            return
        text = "\n".join(codes)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.messagebox.showinfo("Kopiert", f"{len(codes)} Codes in Zwischenablage kopiert.")
        except Exception as e:
            self.messagebox.showerror("Fehler", f"Kopieren fehlgeschlagen: {e}")

    def open_config_dir(self):
        cfg = str(get_config_dir())
        try:
            if sys.platform.startswith("win"):
                os.startfile(cfg)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{cfg}"')
            else:
                os.system(f'xdg-open "{cfg}"')
        except Exception as e:
            self.messagebox.showerror("Fehler", f"Ordner konnte nicht geöffnet werden: {e}")


# ------------------ Main Flow ------------------

def run_search_one_time(requests, BeautifulSoup, dateparser, used_set: Set[str]) -> List[FoundCode]:
    findings: List[FoundCode] = []

    try:
        reddit_items = fetch_reddit_search(requests)
        for it in reddit_items:
            findings.extend(extract_codes_from_item(it, dateparser))
    except Exception as e:
        # Reddit kann blocken/Rate-Limit/etc. -> nicht crashen, nur ignorieren
        print("Reddit-Suche fehlgeschlagen:", e)

    for url in CUSTOM_URLS:
        try:
            item = fetch_generic_url(requests, BeautifulSoup, dateparser, url)
            findings.extend(extract_codes_from_item(item, dateparser))
        except Exception as e:
            print("Fehler beim Abrufen", url, ":", e)

    results = dedupe_and_sort(findings, dateparser)

    # "Benutzt" herausfiltern (für den nächsten Durchlauf)
    filtered = [r for r in results if r.code.upper() not in used_set]
    return filtered


def show_fatal_error(msg: str, log_path: Optional[Path] = None):
    # Minimaler TK-Fehlerdialog (auch wenn wir noch keine App haben)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        if log_path:
            msg = msg + f"\n\nDetails: {log_path}"
        messagebox.showerror("Fehler", msg)
        root.destroy()
    except Exception:
        # Fallback: Konsole
        if log_path:
            msg = msg + f"\nDetails: {log_path}"
        print(msg, file=sys.stderr)


def main():
    tk = scrolled = ttk = messagebox = requests = BeautifulSoup = dateparser = None  # type: ignore

    try:
        tk, scrolled, ttk, messagebox, requests, BeautifulSoup, dateparser = _require_deps()

        used_path = get_used_codes_path()
        used_set = load_used_codes(used_path)

        print("Starte einmaligen Suchdurchlauf (nur Einträge <= MAX_AGE_DAYS)...")
        results = run_search_one_time(requests, BeautifulSoup, dateparser, used_set)
        print(f"Fertig. Gefundene mögliche Codes (letzte {MAX_AGE_DAYS} Tage, ohne Benutzt): {len(results)}")

        root = tk.Tk()
        app = CodeFinderGUI(root, results, used_path, used_set, tk, scrolled, ttk, messagebox)
        root.mainloop()

    except Exception as e:
        log_path = write_error_log(e)
        show_fatal_error(str(e), log_path=log_path)


if __name__ == "__main__":
    main()
