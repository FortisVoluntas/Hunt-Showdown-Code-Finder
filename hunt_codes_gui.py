#!/usr/bin/env python3
# hunt_codes_gui.py  —  Hunt: Showdown Code Finder
# by Fortis Voluntas
#
# Anforderungen (pip):
#   requests  beautifulsoup4  python-dateutil

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

# ─────────────────────────── Konfiguration ────────────────────────────────────
USER_AGENT         = "HuntCodeFinder/1.0"
HEADERS            = {"User-Agent": USER_AGENT}
REQUEST_DELAY      = 1.0
REDDIT_SUBREDDIT   = "HuntShowdown"
REDDIT_QUERY       = "code OR giveaway OR redeem"
REDDIT_LIMIT       = 75
MAX_AGE_DAYS       = 14

CODE_REGEX = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b", re.IGNORECASE)

CUSTOM_URLS: List[str] = []

PAYPAL_URL = "https://paypal.me/fortisvoluntas"


# ─────────────────────────── Lokalisierung ────────────────────────────────────

STRINGS: Dict[str, Dict[str, str]] = {
    "de": {
        "window_title":    "Hunt: Showdown  —  Code Finder",
        "header_sub":      "BOUNTIES GEFUNDEN",
        "max_age_label":   "MAX ALTER",
        "days":            "TAGE",
        "btn_copy":        "⎘  Kopieren",
        "btn_open":        "↗  Öffnen",
        "btn_used":        "✓  Benutzt",
        "btn_used_done":   "✓  Benutzt",
        "btn_config":      "📁  Konfig-Ordner",
        "btn_info":        "ℹ  Info",
        "used_path_label": "Benutzt-Liste",
        "no_codes":        "Keine Codes gefunden (letzte {days} Tage).\n\nPrüfe das error.log im Konfig-Ordner.",
        "copied_title":    "Kopiert",
        "copied_msg":      "Code '{code}' in Zwischenablage kopiert.",
        "used_title":      "Benutzt markiert",
        "used_msg":        "Code '{code}' wurde eingetragen.\nBeim nächsten Durchlauf ignoriert.",
        "err_copy":        "Kopieren fehlgeschlagen",
        "err_used":        "Eintragen fehlgeschlagen",
        "err_folder":      "Ordner konnte nicht geöffnet werden",
        "lang_toggle":     "EN",
        "date_unknown":    "Datum unbekannt",
        # ── About dialog ──────────────────────────────────────────────────────
        "about_title":     "ÜBER DIESES TOOL",
        "about_dev_label": "ENTWICKLER",
        "about_dev":       "Fortis Voluntas",
        "about_body": (
            "Ich bin Hobby-Entwickler — mein eigentliches Steckenpferd ist 3D-Design.\n\n"
            "Dieses Tool und alle meine kleinen Projekte entstehen als Freizeitbeschäftigung,\n"
            "die ich aufgrund einer Erkrankung im Rückenmark für mich gefunden habe.\n\n"
            "Wer meine Arbeit unterstützen möchte, kann gerne eine kleine Spende dalassen —\n"
            "das bedeutet mir wirklich viel. ♥"
        ),
        "about_donate_label": "UNTERSTÜTZEN",
        "about_donate_btn":   "☕  Spenden via PayPal",
        "about_close":        "Schließen",
    },
    "en": {
        "window_title":    "Hunt: Showdown  —  Code Finder",
        "header_sub":      "BOUNTIES FOUND",
        "max_age_label":   "MAX AGE",
        "days":            "DAYS",
        "btn_copy":        "⎘  Copy",
        "btn_open":        "↗  Open",
        "btn_used":        "✓  Mark Used",
        "btn_used_done":   "✓  Used",
        "btn_config":      "📁  Config Folder",
        "btn_info":        "ℹ  Info",
        "used_path_label": "Used list",
        "no_codes":        "No codes found (last {days} days).\n\nCheck error.log in the config folder.",
        "copied_title":    "Copied",
        "copied_msg":      "Code '{code}' copied to clipboard.",
        "used_title":      "Marked as used",
        "used_msg":        "Code '{code}' has been saved.\nIt will be ignored on the next run.",
        "err_copy":        "Copy failed",
        "err_used":        "Could not save",
        "err_folder":      "Could not open folder",
        "lang_toggle":     "DE",
        "date_unknown":    "Date unknown",
        # ── About dialog ──────────────────────────────────────────────────────
        "about_title":     "ABOUT THIS TOOL",
        "about_dev_label": "DEVELOPER",
        "about_dev":       "Fortis Voluntas",
        "about_body": (
            "I'm a hobby developer — my main passion is 3D design.\n\n"
            "This tool and all my little projects are a pastime I found for myself\n"
            "while dealing with a spinal cord condition.\n\n"
            "If you'd like to support my work, a small donation means\n"
            "the world to me. ♥"
        ),
        "about_donate_label": "SUPPORT",
        "about_donate_btn":   "☕  Donate via PayPal",
        "about_close":        "Close",
    },
}


# ─────────────────────────── Persistenz ───────────────────────────────────────

def get_config_dir() -> Path:
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        base = Path(appdata) / "FortisCodeFinder"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) / "fortis_code_finder" if xdg else Path.home() / ".config" / "fortis_code_finder"
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
        pass
    return log_path


# ─────────────────────────── Datentyp ─────────────────────────────────────────

@dataclass
class FoundCode:
    code:    str
    url:     str
    source:  str
    date:    Optional[str]
    snippet: str


# ─────────────────────────── Hilfsfunktionen ──────────────────────────────────

def is_within_max_age(date_iso: Optional[str], max_days: int = MAX_AGE_DAYS, dateparser=None) -> bool:
    if not date_iso:
        return False
    try:
        dt = dateparser.parse(date_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)) <= timedelta(days=max_days)
    except Exception:
        return False


# ─────────────────────────── Netzwerk / Parsing ───────────────────────────────

def fetch_reddit_search(requests, subreddit=REDDIT_SUBREDDIT, query=REDDIT_QUERY, limit=REDDIT_LIMIT):
    import xml.etree.ElementTree as ET
    import html as _html

    NS = "http://www.w3.org/2005/Atom"
    results = []

    urls = [
        # Keyword-Suche — findet Code-Posts auch wenn sie älter sind
        (f"https://www.reddit.com/r/{subreddit}/search.rss"
         f"?q={requests.utils.quote(query)}&restrict_sr=1&sort=new&limit={limit}"),
        # /new.rss — findet Posts von heute sofort, ohne Suchindex-Verzögerung
        f"https://www.reddit.com/r/{subreddit}/new.rss?limit={limit}",
    ]

    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            root = ET.fromstring(r.text)
            for entry in root.findall(f"{{{NS}}}entry"):
                title      = entry.findtext(f"{{{NS}}}title", "") or ""
                link_el    = entry.find(f"{{{NS}}}link")
                href       = link_el.get("href", "") if link_el is not None else ""
                updated    = entry.findtext(f"{{{NS}}}updated", "") or ""
                content_raw = entry.findtext(f"{{{NS}}}content", "") or ""
                # Unescape HTML entities, then strip tags
                content_txt = re.sub(r"<[^>]+>", " ", _html.unescape(content_raw))
                combined    = (title + "\n" + content_txt).strip()
                results.append({"source": "reddit", "url": href, "text": combined, "date": updated})
            time.sleep(REQUEST_DELAY)
        except Exception as e:
            print(f"RSS-Fehler ({url[:60]}): {e}")

    return results


def fetch_generic_url(requests, BeautifulSoup, dateparser, url: str):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
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
    date_iso = item.get("date")
    if not is_within_max_age(date_iso, MAX_AGE_DAYS, dateparser=dateparser):
        return []
    text  = item.get("text") or ""
    found: List[FoundCode] = []
    for m in CODE_REGEX.finditer(text):
        code = m.group(0).upper()
        s    = max(0, m.start() - 80)
        e    = min(len(text), m.end() + 80)
        snippet = text[s:e].replace("\n", " ")
        found.append(FoundCode(
            code=code, url=item.get("url") or "",
            source=item.get("source") or "",
            date=date_iso, snippet=snippet,
        ))
    return found


def dedupe_and_sort(found_list: List[FoundCode], dateparser) -> List[FoundCode]:
    unique: Dict[str, FoundCode] = {}
    for f in found_list:
        if f.code not in unique:
            unique[f.code] = f
    items = list(unique.values())

    def sort_key(x: FoundCode):
        if not x.date:
            return datetime.fromtimestamp(0, tz=timezone.utc)
        try:
            return dateparser.parse(x.date)
        except Exception:
            return datetime.fromtimestamp(0, tz=timezone.utc)

    items.sort(key=sort_key, reverse=True)
    return items


# ══════════════════════════════════════════════════════════════════════════════
#  GUI  —  Hunt: Showdown 1896 Palette
#  Abgeleitet aus dem Bayou-Artwork: Tief-Blauschwarz, kühles Off-White, kein Gold
# ══════════════════════════════════════════════════════════════════════════════
#
#  BG        #0C0E11   Bayou-Nacht (Haupthintergrund)
#  BG_HDR    #0F1215   Header/Footer
#  BG_CARD   #141820   Karten-Hintergrund
#  BG_SNIP   #090B0D   Snippet-Textbox
#  SEP       #1E252E   Trennlinien
#  SEP_ACC   #2C3D4A   Akzent-Trennlinie (Nebel-Teal)
#  ACCENT    #D0D8E0   Off-White (HUNT-Logo-Weiß)  ← Primär-Akzent
#  ACCENT_LT #EEF2F6   Helles Weiß (Code-Anzeige)
#  ACCENT_DK #1E2D38   Dunkler Akzent (Button-BG)
#  RED       #6B1212   Blutrot  (Benutzt-Button)
#  RED_LT    #9B3030   Helleres Rot
#  TEXT      #A0ACB4   Kühles Grau-Weiß  (Fließtext)
#  TEXT_DIM  #384450   Gedimmtes Blau-Grau  (Hints/Meta)
#  TEXT_MID  #607080   Mittleres Blau-Grau  (sekundärer Text)

BG        = "#0C0E11"
BG_HDR    = "#0F1215"
BG_CARD   = "#141820"
BG_SNIP   = "#090B0D"
SEP       = "#1E252E"
SEP_ACC   = "#2C3D4A"
ACCENT    = "#D0D8E0"
ACCENT_LT = "#EEF2F6"
ACCENT_DK = "#1E2D38"
RED       = "#6B1212"
RED_LT    = "#9B3030"
TEXT      = "#A0ACB4"
TEXT_DIM  = "#384450"
TEXT_MID  = "#607080"

F_TITLE  = ("Impact",      18)
F_SUB    = ("Courier New",  8)
F_BODY   = ("Courier New",  9)
F_DIM    = ("Courier New",  8)
F_CODE   = ("Courier New", 13, "bold")
F_NUM    = ("Courier New",  8)
F_BTN    = ("Courier New",  9, "bold")
F_LANG   = ("Courier New", 10, "bold")

BG_IMG_PATH = "background.jpg"   # Dateiname im Config-Ordner

BG_IMAGE_B64 = (
    "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"
    "PLvIAAKtmFKsAAE82GXkACv/2Q=="
)


class CodeFinderGUI:
    def __init__(self, root, results, used_path, used_set, tk, scrolled, ttk, messagebox):
        self.root        = root
        self.tk          = tk
        self.ttk         = ttk
        self.messagebox  = messagebox
        self.results     = results
        self.used_path   = used_path
        self.used_set    = used_set
        self._used_buttons: Dict[str, object] = {}
        self._lang = "de"

        self._lbl_sub:      object = None
        self._lbl_path_key: object = None
        self._btn_config:   object = None
        self._btn_info:     object = None
        self._lang_btn:     object = None
        self._scroll_inner: object = None
        self._canvas:       object = None
        self._cwin:         int    = 0
        self._hdr_canvas:   object = None
        self._hdr_bg_photo: object = None   # Pillow PhotoImage — keep reference!
        self._hdr_bg_img    = None           # raw PIL image

        root.title(STRINGS["de"]["window_title"])
        root.geometry("1080x720")
        root.minsize(900, 580)
        root.configure(bg=BG)

        self._load_bg_image()
        self._setup_ttk_style()
        self._build_ui()

    # ── Background image ──────────────────────────────────────────────────────

    def _load_bg_image(self):
        try:
            from PIL import Image
            import base64, io
            # Eigenes Bild aus Config-Ordner hat Vorrang
            bg_path = get_config_dir() / BG_IMG_PATH
            if bg_path.exists():
                self._hdr_bg_img = Image.open(bg_path)
            else:
                # Eingebettetes Bild aus BG_IMAGE_B64
                data = base64.b64decode(BG_IMAGE_B64)
                self._hdr_bg_img = Image.open(io.BytesIO(data))
        except Exception:
            pass   # Kein Bild — Fallback auf Farbe

    # ── TTK Style ─────────────────────────────────────────────────────────────

    def _setup_ttk_style(self):
        self._sb_style = None   # None = use default ttk scrollbar
        try:
            s = self.ttk.Style()
            s.theme_use("clam")
            s.configure("Hunt.Vertical.TScrollbar",
                        background=BG_CARD, troughcolor=BG,
                        arrowcolor=ACCENT, darkcolor=SEP, lightcolor=SEP,
                        gripcount=0)
            s.map("Hunt.Vertical.TScrollbar",
                  background=[("active", ACCENT_DK)])
            self._sb_style = "Hunt.Vertical.TScrollbar"
        except Exception:
            pass   # Fall back to OS default scrollbar — still functional

    # ── Button factory ─────────────────────────────────────────────────────────

    def _btn(self, parent, text, cmd, variant="accent"):
        palettes = {
            "accent": (ACCENT_DK, ACCENT_LT, ACCENT,   BG),
            "dim":    (SEP,       TEXT_MID,  ACCENT_DK, TEXT),
            "red":    (RED,       "#C08080",  RED_LT,   BG),
            "lang":   (BG_HDR,    ACCENT,    ACCENT_DK, BG),
            "info":   (SEP,       ACCENT,    ACCENT_DK, BG),
        }
        bg, fg, abg, afg = palettes.get(variant, palettes["accent"])
        return self.tk.Button(
            parent, text=text, command=cmd,
            bg=bg, fg=fg, activebackground=abg, activeforeground=afg,
            relief="flat", bd=0, padx=10, pady=5,
            font=F_BTN, cursor="hand2",
        )

    # ── Build main layout ──────────────────────────────────────────────────────

    def _build_ui(self):
        tk  = self.tk
        ttk = self.ttk
        T   = STRINGS[self._lang]

        # ══ HEADER mit Hintergrundbild ════════════════════════════════════════
        HDR_H = 110
        self._hdr_canvas = tk.Canvas(
            self.root, height=HDR_H, highlightthickness=0, bd=0, bg=BG_HDR,
        )
        self._hdr_canvas.pack(fill="x")
        self._hdr_canvas.bind("<Configure>", self._redraw_header)

        # Widgets auf dem Canvas als Fenster-Elemente
        ctrl_frame = tk.Frame(self._hdr_canvas, bg="")  # bg wird in _redraw_header gesetzt
        ctrl_frame.configure(bg=BG_HDR)

        tk.Label(ctrl_frame, text="LANG", bg=BG_HDR, fg=TEXT_DIM, font=F_DIM).pack(side="left", padx=(0, 6))
        self._lang_btn = self._btn(ctrl_frame, T["lang_toggle"], self._toggle_lang, "lang")
        self._lang_btn.configure(font=F_LANG, padx=12, pady=4,
                                 highlightthickness=1, highlightbackground=ACCENT_DK)
        self._lang_btn.pack(side="left")
        self._hdr_canvas.create_window(1060, 55, window=ctrl_frame, anchor="e", tags="ctrl")

        sub_frame = tk.Frame(self._hdr_canvas, bg=BG_HDR)
        self._lbl_sub = sub_frame   # Referenz für _toggle_lang
        self._sub_frame = sub_frame
        self._build_sub_labels(sub_frame, T)
        self._hdr_canvas.create_window(24, 82, window=sub_frame, anchor="w", tags="sub")

        # Trennlinie unter Header
        tk.Frame(self.root, bg=SEP_ACC, height=1).pack(fill="x")
        tk.Frame(self.root, bg=SEP,     height=1).pack(fill="x")

        # ══ FOOTER ════════════════════════════════════════════════════════════
        footer = tk.Frame(self.root, bg=BG_HDR, padx=16, pady=7)
        footer.pack(side="bottom", fill="x")

        tk.Frame(footer, bg=SEP_ACC, height=1).pack(fill="x", pady=(0, 7))
        tk.Frame(footer, bg=SEP,     height=1).pack(fill="x", pady=(0, 6))

        path_row = tk.Frame(footer, bg=BG_HDR)
        path_row.pack(fill="x")

        self._lbl_path_key = tk.Label(path_row,
                                      text=T["used_path_label"] + ":",
                                      bg=BG_HDR, fg=TEXT_DIM, font=F_DIM)
        self._lbl_path_key.pack(side="left", padx=(0, 5))

        tk.Label(path_row, text=str(self.used_path),
                 bg=BG_HDR, fg=TEXT_DIM, font=F_DIM).pack(side="left")

        # Right side of footer: Info button + Config button
        self._btn_info = self._btn(path_row, T["btn_info"], self.show_about, "info")
        self._btn_info.pack(side="right", padx=(6, 0))

        self._btn_config = self._btn(path_row, T["btn_config"], self.open_config_dir, "dim")
        self._btn_config.pack(side="right", padx=(0, 6))

        # ══ SCROLL AREA ═══════════════════════════════════════════════════════
        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0, bd=0)
        _sb_kw = {"orient": "vertical", "command": self._canvas.yview}
        if self._sb_style:
            _sb_kw["style"] = self._sb_style
        sb = ttk.Scrollbar(wrap, **_sb_kw)

        self._scroll_inner = tk.Frame(self._canvas, bg=BG)
        self._cwin = self._canvas.create_window((0, 0), window=self._scroll_inner, anchor="nw")

        self._scroll_inner.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfig(self._cwin, width=e.width),
        )
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._canvas.bind_all("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(int(-1 * e.delta / 120), "units"))
        self._canvas.bind_all("<Button-4>",
            lambda e: self._canvas.yview_scroll(-1, "units"))
        self._canvas.bind_all("<Button-5>",
            lambda e: self._canvas.yview_scroll(1, "units"))

        self._build_cards()

    # ── Header redraw (Hintergrundbild + Titel-Text) ───────────────────────────

    def _redraw_header(self, event=None):
        c   = self._hdr_canvas
        w   = c.winfo_width()  or 1080
        h   = c.winfo_height() or 110

        c.delete("bg", "title")

        if self._hdr_bg_img is not None:
            try:
                from PIL import Image, ImageEnhance, ImageTk
                img = self._hdr_bg_img
                # Skalieren: Breite = Fensterbreite, Höhe proportional
                scale    = w / img.width
                new_h    = int(img.height * scale)
                resized  = img.resize((w, new_h), Image.LANCZOS)
                # Bildmitte zeigen — HUNT-Logo ist mittig vorpositioniert
                crop_y   = max(0, (new_h - h) // 2)
                cropped  = resized.crop((0, crop_y, w, crop_y + h))
                # Abdunkeln
                darkened = ImageEnhance.Brightness(cropped).enhance(0.38)
                self._hdr_bg_photo = ImageTk.PhotoImage(darkened)
                c.create_image(0, 0, image=self._hdr_bg_photo, anchor="nw", tags="bg")
            except Exception:
                c.configure(bg=BG_HDR)
        else:
            c.configure(bg=BG_HDR)

        # Titel-Text über dem Bild
        c.create_text(24, 28, text="HUNT: SHOWDOWN 1896",
                      fill=ACCENT_LT, font=F_TITLE, anchor="w", tags="title")
        c.create_text(24, 50, text="— CODE FINDER",
                      fill=ACCENT, font=("Courier New", 9), anchor="w", tags="title")

        # Alle anderen Canvas-Items nach vorne
        c.tag_raise("sub")
        c.tag_raise("ctrl")

    # ── Sub-Label-Zeile (Zahlen in Weiß, Labels gedimmt) ──────────────────────

    def _build_sub_labels(self, frame, T):
        for w in frame.winfo_children():
            w.destroy()
        bg = BG_HDR
        F  = ("Courier New", 8)
        FB = ("Courier New", 8, "bold")

        tk = self.tk
        tk.Label(frame, text=T["header_sub"] + ": ", bg=bg, fg=ACCENT_LT, font=F).pack(side="left")
        tk.Label(frame, text=str(len(self.results)),  bg=bg, fg=ACCENT_LT, font=FB).pack(side="left")
        tk.Label(frame, text="   ·   ",              bg=bg, fg=TEXT_MID,  font=F).pack(side="left")
        tk.Label(frame, text=T["max_age_label"] + ": ", bg=bg, fg=ACCENT_LT, font=F).pack(side="left")
        tk.Label(frame, text=str(MAX_AGE_DAYS),       bg=bg, fg=ACCENT_LT, font=FB).pack(side="left")
        tk.Label(frame, text=" " + T["days"],         bg=bg, fg=ACCENT_LT, font=F).pack(side="left")

    # ── Card list ──────────────────────────────────────────────────────────────

    def _build_cards(self):
        tk = self.tk
        T  = STRINGS[self._lang]

        for w in self._scroll_inner.winfo_children():
            w.destroy()
        self._used_buttons.clear()

        if not self.results:
            tk.Label(
                self._scroll_inner,
                text=T["no_codes"].format(days=MAX_AGE_DAYS),
                bg=BG, fg=TEXT_DIM, font=("Courier New", 10), justify="center",
            ).pack(pady=60)
            return

        for idx, r in enumerate(self.results, 1):
            self._add_code_card(idx, r)

    # ── Single code card ───────────────────────────────────────────────────────

    def _add_code_card(self, idx: int, item: FoundCode):
        tk = self.tk
        T  = STRINGS[self._lang]

        already_used = item.code.upper() in self.used_set
        strip_color  = RED_LT if already_used else ACCENT

        outer = tk.Frame(self._scroll_inner, bg=SEP)
        outer.pack(fill="x", padx=16, pady=6)

        tk.Frame(outer, bg=strip_color, width=3).pack(side="left", fill="y")

        card = tk.Frame(outer, bg=BG_CARD, padx=18, pady=14)
        card.pack(side="left", fill="both", expand=True)

        # ── Kopfzeile: Nummer + Label + Buttons ───────────────────────────────
        top = tk.Frame(card, bg=BG_CARD)
        top.pack(fill="x", pady=(0, 8))

        num_bg = tk.Frame(top, bg=ACCENT_DK, padx=7, pady=3)
        num_bg.pack(side="left")
        tk.Label(num_bg, text=f"#{idx:02d}", bg=ACCENT_DK, fg=ACCENT,
                 font=F_NUM).pack()

        tk.Label(top, text="  BOUNTY CODE",
                 bg=BG_CARD, fg=TEXT_DIM, font=("Courier New", 7, "bold")).pack(side="left")

        if already_used:
            tk.Label(top, text="  ✓ REDEEMED",
                     bg=BG_CARD, fg=RED_LT, font=("Courier New", 7, "bold")).pack(side="left")

        btns = tk.Frame(top, bg=BG_CARD)
        btns.pack(side="right")

        self._btn(btns, T["btn_open"],
                  lambda u=item.url: webbrowser.open(u), "dim").pack(side="left", padx=(0, 4))

        if already_used:
            b_used = self._btn(btns, T["btn_used_done"], lambda: None, "red")
            b_used.configure(state="disabled", fg=TEXT_DIM)
        else:
            b_used = self._btn(btns, T["btn_used"],
                               lambda c=item.code: self.mark_used(c), "red")
        b_used.pack(side="left")
        self._used_buttons[item.code.upper()] = b_used

        # ── Code-Anzeige groß ─────────────────────────────────────────────────
        code_frame = tk.Frame(card, bg=BG_SNIP, padx=16, pady=12)
        code_frame.pack(fill="x")

        code_color = TEXT_DIM if already_used else ACCENT_LT

        # Code-Gruppen einzeln darstellen, durch · getrennt
        parts = item.code.split("-")
        seg_row = tk.Frame(code_frame, bg=BG_SNIP)
        seg_row.pack(side="left")

        for i, part in enumerate(parts):
            if i > 0:
                tk.Label(seg_row, text="-",
                         bg=BG_SNIP, fg=ACCENT,
                         font=("Courier New", 17, "bold")).pack(side="left", padx=1)
            tk.Label(seg_row, text=part,
                     bg=BG_SNIP, fg=code_color,
                     font=("Courier New", 17, "bold")).pack(side="left")

        # Copy-Button direkt neben dem Code
        self._btn(code_frame, T["btn_copy"],
                  lambda c=item.code: self.copy_single(c), "accent").pack(side="right")

        # ── Meta-Zeile ────────────────────────────────────────────────────────
        tk.Frame(card, bg=SEP, height=1).pack(fill="x", pady=(10, 6))

        meta = tk.Frame(card, bg=BG_CARD)
        meta.pack(fill="x")

        date_str = (item.date or T["date_unknown"])[:19].replace("T", "  ")
        url_disp = item.url if len(item.url) <= 72 else item.url[:69] + "…"

        tk.Label(meta, text="DATE",       bg=BG_CARD, fg=ACCENT,   font=F_DIM).pack(side="left")
        tk.Label(meta, text=f"  {date_str}",  bg=BG_CARD, fg=TEXT_MID, font=F_DIM).pack(side="left")
        tk.Label(meta, text="     URL",   bg=BG_CARD, fg=ACCENT,   font=F_DIM).pack(side="left")
        tk.Label(meta, text=f"  {url_disp}",  bg=BG_CARD, fg=TEXT_DIM, font=F_DIM).pack(side="left")

        # ── Snippet ───────────────────────────────────────────────────────────
        if item.snippet and item.snippet.strip():
            tk.Frame(card, bg=SEP, height=1).pack(fill="x", pady=(6, 5))
            snip = tk.Text(
                card, height=2, wrap="word",
                bg=BG_SNIP, fg=TEXT_MID, font=F_DIM,
                relief="flat", bd=0, padx=10, pady=6,
                selectbackground=ACCENT_DK, insertbackground=ACCENT,
            )
            snip.pack(fill="x")
            snip.insert("1.0", item.snippet.strip())
            snip.configure(state="disabled")

    # ── About / Info dialog ────────────────────────────────────────────────────

    def show_about(self):
        tk = self.tk
        T  = STRINGS[self._lang]

        dlg = tk.Toplevel(self.root)
        dlg.title(T["about_title"])
        dlg.resizable(False, False)
        dlg.configure(bg=BG)
        dlg.grab_set()  # modal

        # Center relative to main window
        self.root.update_idletasks()
        rx = self.root.winfo_x() + self.root.winfo_width()  // 2
        ry = self.root.winfo_y() + self.root.winfo_height() // 2
        dlg.geometry(f"480x360+{rx - 240}+{ry - 180}")

        # ── Top accent bar ────────────────────────────────────────────────────
        tk.Frame(dlg, bg=ACCENT, height=1).pack(fill="x")

        # ── Title bar ─────────────────────────────────────────────────────────
        title_bar = tk.Frame(dlg, bg=BG_HDR, padx=20, pady=12)
        title_bar.pack(fill="x")

        tk.Frame(title_bar, bg=ACCENT, width=3, height=22).pack(side="left", padx=(0, 10))
        tk.Label(title_bar, text=T["about_title"],
                 bg=BG_HDR, fg=TEXT, font=F_TITLE).pack(side="left")

        tk.Frame(dlg, bg=SEP,     height=1).pack(fill="x")
        tk.Frame(dlg, bg=SEP_ACC, height=1).pack(fill="x")

        # ── Body ──────────────────────────────────────────────────────────────
        body = tk.Frame(dlg, bg=BG, padx=24, pady=18)
        body.pack(fill="both", expand=True)

        # Developer row
        dev_row = tk.Frame(body, bg=BG)
        dev_row.pack(fill="x", pady=(0, 4))

        tk.Label(dev_row, text=T["about_dev_label"],
                 bg=BG, fg=ACCENT, font=F_DIM).pack(side="left")
        tk.Label(dev_row, text="   " + T["about_dev"],
                 bg=BG, fg=ACCENT_LT, font=("Impact", 13)).pack(side="left")

        tk.Frame(body, bg=SEP, height=1).pack(fill="x", pady=(6, 12))

        # Description text
        tk.Label(body, text=T["about_body"],
                 bg=BG, fg=TEXT_MID, font=F_BODY,
                 justify="left", anchor="w", wraplength=432).pack(fill="x")

        tk.Frame(body, bg=SEP, height=1).pack(fill="x", pady=(14, 10))

        # Donate section
        donate_row = tk.Frame(body, bg=BG)
        donate_row.pack(fill="x")

        tk.Label(donate_row, text=T["about_donate_label"],
                 bg=BG, fg=ACCENT, font=F_DIM).pack(side="left", padx=(0, 12))

        # PayPal link — styled as a clickable label
        pp_lbl = tk.Label(donate_row,
                          text=T["about_donate_btn"],
                          bg=ACCENT_DK, fg=ACCENT_LT,
                          font=F_BTN, padx=12, pady=5,
                          cursor="hand2")
        pp_lbl.pack(side="left")
        pp_lbl.bind("<Button-1>", lambda e: webbrowser.open(PAYPAL_URL))
        pp_lbl.bind("<Enter>",    lambda e: pp_lbl.configure(bg=ACCENT, fg=BG))
        pp_lbl.bind("<Leave>",    lambda e: pp_lbl.configure(bg=ACCENT_DK, fg=ACCENT_LT))

        # PayPal URL hint
        tk.Label(donate_row, text=f"  {PAYPAL_URL}",
                 bg=BG, fg=TEXT_DIM, font=F_DIM).pack(side="left")

        # ── Footer: close button ──────────────────────────────────────────────
        tk.Frame(dlg, bg=SEP_ACC, height=1).pack(fill="x")
        tk.Frame(dlg, bg=SEP,     height=1).pack(fill="x")

        foot = tk.Frame(dlg, bg=BG_HDR, padx=16, pady=8)
        foot.pack(fill="x")

        close_btn = self._btn(foot, T["about_close"], dlg.destroy, "dim")
        close_btn.pack(side="right")

    # ── Language toggle ────────────────────────────────────────────────────────

    def _sub_text(self, T):
        return (f"{T['header_sub']}: {len(self.results)}"
                f"   |   {T['max_age_label']}: {MAX_AGE_DAYS} {T['days']}")

    def _toggle_lang(self):
        self._lang = "en" if self._lang == "de" else "de"
        T = STRINGS[self._lang]
        self.root.title(T["window_title"])
        self._build_sub_labels(self._sub_frame, T)
        self._lang_btn.configure(text=T["lang_toggle"])
        self._lbl_path_key.configure(text=T["used_path_label"] + ":")
        self._btn_config.configure(text=T["btn_config"])
        self._btn_info.configure(text=T["btn_info"])
        self._build_cards()

    # ── Actions ────────────────────────────────────────────────────────────────

    def mark_used(self, code: str):
        T      = STRINGS[self._lang]
        code_u = code.strip().upper()
        if not code_u:
            return
        if code_u in self.used_set:
            btn = self._used_buttons.get(code_u)
            if btn:
                btn.configure(text=T["btn_used_done"], state="disabled", fg=TEXT_DIM)
            return
        try:
            append_used_code(self.used_path, code_u)
            self.used_set.add(code_u)
            btn = self._used_buttons.get(code_u)
            if btn:
                btn.configure(text=T["btn_used_done"], state="disabled", fg=TEXT_DIM)
            self.messagebox.showinfo(T["used_title"], T["used_msg"].format(code=code_u))
        except Exception as e:
            self.messagebox.showerror(T["err_used"], str(e))

    def copy_single(self, code: str):
        T = STRINGS[self._lang]
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            self.messagebox.showinfo(T["copied_title"], T["copied_msg"].format(code=code))
        except Exception as e:
            self.messagebox.showerror(T["err_copy"], str(e))

    def open_config_dir(self):
        T   = STRINGS[self._lang]
        cfg = str(get_config_dir())
        try:
            if sys.platform.startswith("win"):
                os.startfile(cfg)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{cfg}"')
            else:
                os.system(f'xdg-open "{cfg}"')
        except Exception as e:
            self.messagebox.showerror(T["err_folder"], str(e))


# ─────────────────────────── Abhängigkeiten ───────────────────────────────────

def _require_deps():
    try:
        import tkinter as tk
        import tkinter.scrolledtext as scrolled
        from tkinter import ttk, messagebox
    except Exception as e:
        raise RuntimeError(
            "tkinter ist nicht verfügbar.\n"
            "Installiere Python neu (python.org) und aktiviere 'tcl/tk and IDLE'."
        ) from e
    try:
        import requests
    except Exception as e:
        raise RuntimeError("Modul 'requests' fehlt.  →  py -m pip install requests") from e
    try:
        from bs4 import BeautifulSoup
    except Exception as e:
        raise RuntimeError("Modul 'beautifulsoup4' fehlt.  →  py -m pip install beautifulsoup4") from e
    try:
        from dateutil import parser as dateparser
    except Exception as e:
        raise RuntimeError("Modul 'python-dateutil' fehlt.  →  py -m pip install python-dateutil") from e

    # Pillow — optional, nur für Hintergrundbild
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        pass   # Ohne Pillow: kein Hintergrundbild, kein Fehler

    import tkinter as tk
    import tkinter.scrolledtext as scrolled
    from tkinter import ttk, messagebox
    import requests
    from bs4 import BeautifulSoup
    from dateutil import parser as dateparser
    return tk, scrolled, ttk, messagebox, requests, BeautifulSoup, dateparser


# ─────────────────────────── Main Flow ────────────────────────────────────────

def run_search_one_time(requests, BeautifulSoup, dateparser, used_set: Set[str]) -> List[FoundCode]:
    findings: List[FoundCode] = []
    try:
        for it in fetch_reddit_search(requests):
            findings.extend(extract_codes_from_item(it, dateparser))
    except Exception as e:
        print("Reddit-Suche fehlgeschlagen:", e)
    for url in CUSTOM_URLS:
        try:
            item = fetch_generic_url(requests, BeautifulSoup, dateparser, url)
            findings.extend(extract_codes_from_item(item, dateparser))
        except Exception as e:
            print("Fehler beim Abrufen", url, ":", e)
    results  = dedupe_and_sort(findings, dateparser)
    filtered = [r for r in results if r.code.upper() not in used_set]
    return filtered


def show_fatal_error(msg: str, log_path: Optional[Path] = None):
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        if log_path:
            msg = msg + f"\n\nDetails: {log_path}"
        messagebox.showerror("Fehler / Error", msg)
        root.destroy()
    except Exception:
        if log_path:
            msg = msg + f"\nDetails: {log_path}"
        print(msg, file=sys.stderr)


def main():
    try:
        tk, scrolled, ttk, messagebox, requests, BeautifulSoup, dateparser = _require_deps()

        used_path = get_used_codes_path()
        used_set  = load_used_codes(used_path)

        print("Starte Suchdurchlauf …")
        results = run_search_one_time(requests, BeautifulSoup, dateparser, used_set)
        print(f"Fertig. Codes (letzte {MAX_AGE_DAYS} Tage, ohne Benutzt): {len(results)}")

        root = tk.Tk()
        CodeFinderGUI(root, results, used_path, used_set, tk, scrolled, ttk, messagebox)
        root.mainloop()

    except Exception as e:
        log_path = write_error_log(e)
        show_fatal_error(str(e), log_path=log_path)


if __name__ == "__main__":
    main()
