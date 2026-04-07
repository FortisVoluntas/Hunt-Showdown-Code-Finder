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
USER_AGENT         = "Mozilla/5.0 (compatible; FortisCodeFinder/1.0; +https://example.org/)"
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
    url = (
        f"https://www.reddit.com/r/{subreddit}/search.json"
        f"?q={requests.utils.quote(query)}&restrict_sr=1&sort=new&limit={limit}"
    )
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    results = []
    for child in data.get("data", {}).get("children", []):
        post     = child.get("data", {})
        title    = post.get("title", "") or ""
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
#  GUI  —  Hunt: Showdown  Authentic Palette
# ══════════════════════════════════════════════════════════════════════════════
#
#  BG        #0A0A0A   Reines Schwarz  (Haupthintergrund)
#  BG_HDR    #111111   Header/Footer-Leiste
#  BG_CARD   #171717   Karten-Hintergrund
#  BG_SNIP   #0D0D0D   Snippet-Textbox
#  SEP       #2C2C2C   Trennlinien / subtile Borders
#  SEP_GOLD  #5C4A10   Gold-getönte Trennlinie
#  GOLD      #B8941E   Gedämpftes Hunt-Gold  ← Primär-Akzent
#  GOLD_LT   #D4AF37   Helleres Gold (Code-Anzeige)
#  GOLD_DK   #6B5510   Dunkles Gold (Buttons inaktiv)
#  RED       #7A1515   Blutrot  (Benutzt-Button)
#  TEXT      #C0BEB8   Kühles Off-White  (Fließtext)
#  TEXT_DIM  #555550   Gedimmtes Grau  (Hints/Meta)
#  TEXT_MID  #888880   Mittleres Grau  (sekundärer Text)

BG        = "#0A0A0A"
BG_HDR    = "#111111"
BG_CARD   = "#171717"
BG_SNIP   = "#0D0D0D"
SEP       = "#2C2C2C"
SEP_GOLD  = "#5C4A10"
GOLD      = "#B8941E"
GOLD_LT   = "#D4AF37"
GOLD_DK   = "#6B5510"
RED       = "#7A1515"
TEXT      = "#C0BEB8"
TEXT_DIM  = "#555550"
TEXT_MID  = "#888880"

F_TITLE  = ("Impact",      14)
F_SUB    = ("Courier New",  8)
F_BODY   = ("Courier New",  9)
F_DIM    = ("Courier New",  8)
F_CODE   = ("Courier New", 13, "bold")
F_NUM    = ("Courier New",  8)
F_BTN    = ("Courier New",  9, "bold")
F_LANG   = ("Courier New", 10, "bold")


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

        root.title(STRINGS["de"]["window_title"])
        root.geometry("1080x720")
        root.minsize(900, 580)
        root.configure(bg=BG)

        self._setup_ttk_style()
        self._build_ui()

    # ── TTK Style ─────────────────────────────────────────────────────────────

    def _setup_ttk_style(self):
        self._sb_style = None   # None = use default ttk scrollbar
        try:
            s = self.ttk.Style()
            s.theme_use("clam")
            s.configure("Hunt.Vertical.TScrollbar",
                        background=BG_CARD, troughcolor=BG,
                        arrowcolor=GOLD, darkcolor=SEP, lightcolor=SEP,
                        gripcount=0)
            s.map("Hunt.Vertical.TScrollbar",
                  background=[("active", GOLD_DK)])
            self._sb_style = "Hunt.Vertical.TScrollbar"
        except Exception:
            pass   # Fall back to OS default scrollbar — still functional

    # ── Button factory ─────────────────────────────────────────────────────────

    def _btn(self, parent, text, cmd, variant="gold"):
        palettes = {
            "gold":  (GOLD_DK,  GOLD_LT,  GOLD,      BG),
            "dim":   (SEP,      TEXT_MID, GOLD_DK,   TEXT),
            "red":   (RED,      "#C08080", "#A32020", BG),
            "lang":  (BG_HDR,   GOLD,     GOLD_DK,   BG),
            "info":  (SEP,      GOLD,     GOLD_DK,   BG),
        }
        bg, fg, abg, afg = palettes.get(variant, palettes["gold"])
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

        # ══ HEADER ════════════════════════════════════════════════════════════
        hdr = tk.Frame(self.root, bg=BG_HDR)
        hdr.pack(fill="x")

        tk.Frame(hdr, bg=GOLD, height=1).pack(fill="x")

        inner = tk.Frame(hdr, bg=BG_HDR, padx=20, pady=10)
        inner.pack(fill="x")

        left = tk.Frame(inner, bg=BG_HDR)
        left.pack(side="left")

        tk.Frame(left, bg=GOLD, width=3, height=28).pack(side="left", padx=(0, 10))

        title_block = tk.Frame(left, bg=BG_HDR)
        title_block.pack(side="left")

        tk.Label(title_block, text="HUNT: SHOWDOWN  —  CODE FINDER",
                 bg=BG_HDR, fg=TEXT, font=F_TITLE).pack(anchor="w")

        self._lbl_sub = tk.Label(title_block, text=self._sub_text(T),
                                 bg=BG_HDR, fg=TEXT_DIM, font=F_SUB)
        self._lbl_sub.pack(anchor="w", pady=(1, 0))

        right = tk.Frame(inner, bg=BG_HDR)
        right.pack(side="right")

        tk.Label(right, text="LANG", bg=BG_HDR, fg=TEXT_DIM, font=F_DIM).pack(side="left", padx=(0, 6))
        self._lang_btn = self._btn(right, T["lang_toggle"], self._toggle_lang, "lang")
        self._lang_btn.configure(font=F_LANG, padx=12, pady=4,
                                 highlightthickness=1, highlightbackground=GOLD_DK)
        self._lang_btn.pack(side="left")

        tk.Frame(hdr, bg=SEP,      height=1).pack(fill="x")
        tk.Frame(hdr, bg=SEP_GOLD, height=1).pack(fill="x")

        # ══ FOOTER ════════════════════════════════════════════════════════════
        footer = tk.Frame(self.root, bg=BG_HDR, padx=16, pady=7)
        footer.pack(side="bottom", fill="x")

        tk.Frame(footer, bg=SEP_GOLD, height=1).pack(fill="x", pady=(0, 7))
        tk.Frame(footer, bg=SEP,      height=1).pack(fill="x", pady=(0, 6))

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

        outer = tk.Frame(self._scroll_inner, bg=SEP)
        outer.pack(fill="x", padx=16, pady=5)

        # Left accent strip: gold = active, red = used
        strip_color = RED if already_used else GOLD
        tk.Frame(outer, bg=strip_color, width=2).pack(side="left", fill="y")

        card = tk.Frame(outer, bg=BG_CARD, padx=14, pady=10)
        card.pack(side="left", fill="both", expand=True)

        # Row 1: index | CODE | buttons
        row1 = tk.Frame(card, bg=BG_CARD)
        row1.pack(fill="x")

        num_bg = tk.Frame(row1, bg=GOLD_DK, padx=5, pady=2)
        num_bg.pack(side="left", padx=(0, 10))
        tk.Label(num_bg, text=f"#{idx:02d}", bg=GOLD_DK, fg=GOLD_LT, font=F_NUM).pack()

        code_color = TEXT_DIM if already_used else GOLD_LT
        tk.Label(row1, text=item.code, bg=BG_CARD, fg=code_color, font=F_CODE).pack(side="left")

        btns = tk.Frame(row1, bg=BG_CARD)
        btns.pack(side="right")

        self._btn(btns, T["btn_copy"],
                  lambda c=item.code: self.copy_single(c), "gold").pack(side="left", padx=(0, 4))
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

        # Separator
        tk.Frame(card, bg=SEP, height=1).pack(fill="x", pady=(8, 5))

        # Row 2: meta
        date_str = item.date or T["date_unknown"]
        url_disp = item.url if len(item.url) <= 88 else item.url[:85] + "…"

        meta_row = tk.Frame(card, bg=BG_CARD)
        meta_row.pack(fill="x", pady=(0, 6))

        tk.Label(meta_row, text="DATE",   bg=BG_CARD, fg=GOLD,    font=F_DIM).pack(side="left")
        tk.Label(meta_row, text=f"  {date_str}", bg=BG_CARD, fg=TEXT_MID, font=F_DIM).pack(side="left")
        tk.Label(meta_row, text="   SOURCE", bg=BG_CARD, fg=GOLD, font=F_DIM).pack(side="left")
        tk.Label(meta_row, text=f"  {url_disp}", bg=BG_CARD, fg=TEXT_DIM,
                 font=F_DIM, wraplength=700, anchor="w", justify="left").pack(side="left")

        # Row 3: snippet
        snip = self.tk.Text(
            card, height=2, wrap="word",
            bg=BG_SNIP, fg=TEXT_MID, font=F_DIM,
            relief="flat", bd=0, padx=8, pady=5,
            selectbackground=GOLD_DK, insertbackground=GOLD,
        )
        snip.pack(fill="x")
        snip.insert("1.0", item.snippet or "")
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

        # ── Top gold bar ──────────────────────────────────────────────────────
        tk.Frame(dlg, bg=GOLD, height=1).pack(fill="x")

        # ── Title bar ─────────────────────────────────────────────────────────
        title_bar = tk.Frame(dlg, bg=BG_HDR, padx=20, pady=12)
        title_bar.pack(fill="x")

        tk.Frame(title_bar, bg=GOLD, width=3, height=22).pack(side="left", padx=(0, 10))
        tk.Label(title_bar, text=T["about_title"],
                 bg=BG_HDR, fg=TEXT, font=F_TITLE).pack(side="left")

        tk.Frame(dlg, bg=SEP,      height=1).pack(fill="x")
        tk.Frame(dlg, bg=SEP_GOLD, height=1).pack(fill="x")

        # ── Body ──────────────────────────────────────────────────────────────
        body = tk.Frame(dlg, bg=BG, padx=24, pady=18)
        body.pack(fill="both", expand=True)

        # Developer row
        dev_row = tk.Frame(body, bg=BG)
        dev_row.pack(fill="x", pady=(0, 4))

        tk.Label(dev_row, text=T["about_dev_label"],
                 bg=BG, fg=GOLD, font=F_DIM).pack(side="left")
        tk.Label(dev_row, text="   " + T["about_dev"],
                 bg=BG, fg=GOLD_LT, font=("Impact", 13)).pack(side="left")

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
                 bg=BG, fg=GOLD, font=F_DIM).pack(side="left", padx=(0, 12))

        # PayPal link — styled as a clickable label
        pp_lbl = tk.Label(donate_row,
                          text=T["about_donate_btn"],
                          bg=GOLD_DK, fg=GOLD_LT,
                          font=F_BTN, padx=12, pady=5,
                          cursor="hand2")
        pp_lbl.pack(side="left")
        pp_lbl.bind("<Button-1>", lambda e: webbrowser.open(PAYPAL_URL))
        pp_lbl.bind("<Enter>",    lambda e: pp_lbl.configure(bg=GOLD, fg=BG))
        pp_lbl.bind("<Leave>",    lambda e: pp_lbl.configure(bg=GOLD_DK, fg=GOLD_LT))

        # PayPal URL hint
        tk.Label(donate_row, text=f"  {PAYPAL_URL}",
                 bg=BG, fg=TEXT_DIM, font=F_DIM).pack(side="left")

        # ── Footer: close button ──────────────────────────────────────────────
        tk.Frame(dlg, bg=SEP_GOLD, height=1).pack(fill="x")
        tk.Frame(dlg, bg=SEP,      height=1).pack(fill="x")

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
        self._lbl_sub.configure(text=self._sub_text(T))
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
