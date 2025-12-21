# Hunt Code Finder by Fortis (Windows EXE)

Eine kleine Windows-App (Standalone **.exe**) mit GUI, die nach möglichen **Hunt: Showdown**-Codes sucht, Treffer auf die **letzten 14 Tage** begrenzt und Codes per Klick als **„Benutzt“** markiert, damit sie beim nächsten Durchlauf **ignoriert** werden.

> Unofficial/inoffiziell. Keine Verbindung zu Crytek oder Reddit.

---

## ✅ Systemanforderungen

- Windows 10/11 (64-bit)

**Keine Installation nötig:**  
Die EXE ist portable – einfach starten.

---

## 🚀 Start

1. `HuntCodeFinder.exe` herunterladen
2. Doppelklick zum Starten

Beim ersten Start kann Windows SmartScreen warnen (unbekannter Herausgeber). Das ist normal bei nicht-signierten EXEs.

---

## 🔍 Was macht die App?

- Einmaliger Suchlauf nach möglichen Codes (kein Hintergrunddienst)
- Filter: nur Inhalte der letzten **14 Tage**
- Erkennung von Codes im Format:
  - `XXXX-XXXX-XXXX-XXXX`

Zu jedem Treffer gibt es Buttons:

- **Kopieren** → Code in die Zwischenablage
- **Öffnen** → Quelle im Browser öffnen
- **Benutzt** → Code wird gespeichert und künftig ignoriert

---

## 🧾 „Benutzt“-Liste (wird gespeichert)

Wenn du einen Code als **„Benutzt“** markierst, wird er in einer Liste gespeichert und beim nächsten Start **nicht mehr angezeigt**.

**Speicherort (Windows):**
- `%APPDATA%\FortisCodeFinder\used_codes.txt`

### Reset / Wieder anzeigen
- `used_codes.txt` löschen, oder einzelne Zeilen entfernen.

---

## 🧯 Fehlerdiagnose (wenn die App nicht startet)

Wenn beim Start etwas schiefgeht, schreibt die App ein Log.

**Log-Datei:**
- `%APPDATA%\FortisCodeFinder\error.log`

Wenn du Hilfe brauchst: Inhalt von `error.log` kopieren und als Issue posten.

---

## ⚠️ Hinweise / Einschränkungen

- Die App greift auf öffentlich verfügbare Inhalte zu; Suchquellen können Rate-Limits haben.
- Gefundene Codes sind nur **Muster-Treffer** – keine Garantie, dass sie gültig sind.
- Je nach Internet/Quelle kann es vorkommen, dass keine Treffer angezeigt werden.

---

## 📦 Download

- Releases: Lade die aktuelle `HuntCodeFinder.exe` aus dem **Releases**-Bereich herunter.


---

## 📝 Lizenz

Hier deine Lizenz eintragen (z. B. MIT) und die Datei `LICENSE` hinzufügen.

---

## 🙏 Credits

- Python / Tkinter (als Grundlage für das gepackte Programm)
- Requests / BeautifulSoup / python-dateutil

- Tested by Greenie, Lynara and Grendelwendell
