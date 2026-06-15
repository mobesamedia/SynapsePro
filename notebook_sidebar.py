from __future__ import annotations

import base64
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import urllib.request
from typing import Optional

from aqt import mw
from aqt.qt import (
    QDockWidget, Qt, QVBoxLayout, QHBoxLayout,
    QWidget, QFileDialog, QUrl, QKeySequence, QShortcut,
    QPushButton, QLabel,
)
from aqt.webview import AnkiWebView, AnkiWebViewKind
from aqt.utils import tooltip, showInfo, askUser

try:
    from .locales import _
except ImportError:
    def _(text):  # type: ignore
        return text

ADDON_NAME_FOR_BRIDGE = "notion_mini"
DB_FILENAME = "notebook.sqlite"
DOCK_TITLE = "Notebook"
HTML_DIR = "web_notebook"

# ──────────────────────────────────────────────
# HTML i18n injection
# ──────────────────────────────────────────────

def _build_i18n_script(tool_name: str) -> str:
    """Return a <script> tag that sets window.__SYNAPSE_I18N__ for the current language.

    Structured per-tool so each HTML file only gets the strings it uses.
    The applyI18n() function embedded in each HTML file reads these on
    DOMContentLoaded and applies them via data-i18n / data-i18n-placeholder.
    """
    STRINGS: dict = {
        "notebook": {
            "search_placeholder": _("Search in this page..."),
            "close":              _("Close"),
            "new_page":           _("New Page"),
            "apply":              _("Apply"),
            "cancel":             _("Cancel"),
            "delete":             _("Delete"),
            "duplicate":          _("Duplicate"),
            "convert":            _("Convert"),
            "add_icon":           _("Add Icon"),
            "remove_icon":        _("Remove Icon"),
            "block_text":         _("Text"),
            "block_h1":           _("Heading 1"),
            "block_h2":           _("Heading 2"),
            "block_list":         _("List"),
            "block_todo":         _("To-Do"),
            "block_quote":        _("Quote"),
            "block_callout":      _("Callout"),
            "block_code":         _("Code"),
            "block_toggle":       _("Toggle"),
            "block_divider":      _("Divider"),
            "block_table":        _("Table"),
            "paste_tip":          _("Tip: Paste images (Ctrl+V) supported"),
            "saved":              _("Saved"),
            "saving":             _("Saving..."),
            "untitled":           _("Untitled"),
            "delete_page_confirm":  _("Delete this page?"),
            "delete_table_confirm": _("Delete table?"),
            "table_add_row":      _("+ Row"),
            "table_add_col":      _("+ Col"),
            "placeholder_slash":        _("Type '/' for commands"),
            "placeholder_callout":      _("Type something..."),
            "placeholder_toggle":       _("Toggle title"),
            "placeholder_toggle_body":  _("Add content here..."),
            "time_just_now":  _("just now"),
            "time_m_ago":     _("m ago"),
            "time_h_ago":     _("h ago"),
            "time_d_ago":     _("d ago"),
            "no_results":     _("No results for"),
        },
        "todo": {
            "title":           _("Todo"),
            "filter_all":      _("All"),
            "filter_open":     _("Open"),
            "filter_done":     _("Done"),
            "add_placeholder": _("Add a task\u2026"),
            "add_btn":         _("+ Add"),
            "tag_placeholder": _("Tag (optional)"),
            "section_open":    _("Open"),
            "section_done":    _("Done"),
            "empty":           _("No tasks yet."),
            "empty_sub":       _("Add one above!"),
            "saved":           _("Saved"),
            "done_of":         _("{done} / {total} done"),
        },
        "pdf": {
            "search_placeholder":  _("Search PDFs\u2026"),
            "add_btn":             _("Add PDF"),
            "back":                _("Back"),
            "loading":             _("Loading PDF\u2026"),
            "error_msg":           _("Could not render PDF."),
            "open_sys":            _("Open in system viewer"),
            "empty_msg":           _("No PDFs yet."),
            "empty_sub":           _("Add one to get started."),
            "saved":               _("Saved"),
            "already_in_list":     _("Already in list"),
            "pdf_added":           _("PDF added"),
            "removed":             _("Removed"),
            "moved_to_folder":     _("Moved to folder"),
            "removed_from_folder": _("Removed from folder"),
            "relink_btn":          _("Relink file"),
            "relinked":            _("File relinked"),
            "view_inline":         _("View inline"),
            "move_to_folder":      _("Move to folder"),
            "open_externally":     _("Open externally"),
            "remove":              _("Remove"),
            "notice_title":        _("PDF Viewer only"),
            "notice_body":         _("PDFs can be viewed but not edited here."
                                     " Keep your files at their original paths;"
                                     " moving or deleting them will break the link."),
        },
    }
    strings = STRINGS.get(tool_name, {})
    strings_json = json.dumps(strings, ensure_ascii=False)
    return f'<script id="synapse-i18n">window.__SYNAPSE_I18N__={strings_json};</script>'
VACUUM_THRESHOLD_MB  = 5
MAX_PDF_INLINE_MB    = 30   # warn before loading PDFs larger than this

TOOL_FILES = {
    "notebook": "index.html",
    "todo":     "todo.html",
    "pdf":      "pdf_viewer.html",
}

# ──────────────────────────────────────────────
# PDF.js offline bundling
# ──────────────────────────────────────────────

PDFJS_VERSION = "3.11.174"
_PDFJS_CDN    = f"https://cdnjs.cloudflare.com/ajax/libs/pdf.js/{PDFJS_VERSION}"
_PDFJS_FILES  = ["pdf.min.js", "pdf.worker.min.js"]


def _pdfjs_dir() -> str:
    return os.path.join(addon_dir(), HTML_DIR, "pdfjs")


def _ensure_pdfjs_async() -> None:
    """Download PDF.js files to local cache in a background thread (runs once)."""
    def _download() -> None:
        d = _pdfjs_dir()
        os.makedirs(d, exist_ok=True)
        for fname in _PDFJS_FILES:
            dest = os.path.join(d, fname)
            if os.path.exists(dest):
                continue
            tmp = dest + ".tmp"
            try:
                urllib.request.urlretrieve(f"{_PDFJS_CDN}/{fname}", tmp)
                os.replace(tmp, dest)
                print(f"SynapsePro: cached {fname}")
            except Exception as exc:
                print(f"SynapsePro: could not download {fname}: {exc}")
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    threading.Thread(target=_download, daemon=True).start()


def _pdfjs_local_scripts() -> tuple[str, str]:
    """Return (main_inline_tag, worker_code_json) if both local files are ready.

    main_inline_tag  – a <script>…</script> block inlining pdf.min.js
    worker_code_json – a JSON string of pdf.worker.min.js content, safe to embed
                       inside a <script> tag (</  is escaped to <\/)
    Returns ('', '') if local files are not yet available.
    """
    d = _pdfjs_dir()
    main_path   = os.path.join(d, "pdf.min.js")
    worker_path = os.path.join(d, "pdf.worker.min.js")
    if not (os.path.exists(main_path) and os.path.exists(worker_path)):
        return "", ""
    try:
        with open(main_path, "r", encoding="utf-8") as fh:
            main_js = fh.read()
        with open(worker_path, "r", encoding="utf-8") as fh:
            worker_js = fh.read()
        # Escape </ so the content cannot prematurely close a <script> tag
        safe_main   = main_js.replace("</", "<\\/")
        worker_json = json.dumps(worker_js).replace("</", "<\\/")
        return f"<script>{safe_main}</script>", worker_json
    except Exception as exc:
        print(f"SynapsePro: could not read PDF.js local files: {exc}")
        return "", ""


# ──────────────────────────────────────────────
# Nav-Bar HTML (injected into every tool page)
# ──────────────────────────────────────────────
_NAV_STYLE = """
<style id="synapse-nav-style">
  #synapse-tool-nav {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 42px;
    padding: 0 10px;
    background: var(--header-bg, #f2f2f2);
    border-bottom: 1px solid var(--border, rgba(0,0,0,0.08));
    flex-shrink: 0;
    z-index: 200;
  }
  .snav-btn {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 5px 12px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--text, #37352f);
    font-size: 13px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    cursor: pointer;
    transition: background 0.15s;
    white-space: nowrap;
  }
  .snav-btn:hover {
    background: var(--hover-bg, #efefef);
  }
  .snav-btn.snav-active {
    background: var(--hover-bg, #efefef);
    font-weight: 600;
  }
  .snav-btn svg {
    width: 15px;
    height: 15px;
    opacity: 0.75;
    flex-shrink: 0;
  }
  .snav-spacer { flex: 1; }
  .snav-fs-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--text, #37352f);
    cursor: pointer;
    transition: background 0.15s;
    flex-shrink: 0;
  }
  .snav-fs-btn:hover { background: var(--hover-bg, #efefef); }
  .snav-fs-btn svg { width: 15px; height: 15px; opacity: 0.65; }
</style>
"""

_NAV_ICONS = {
    "notebook": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>""",
    "todo":     """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>""",
    "pdf":      """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>""",
}

_NAV_LABELS = {
    "notebook": "Notebook",
    "todo":     "Todo",
    "pdf":      "PDF",
}


_FS_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="15 3 21 3 21 9"/>'
    '<polyline points="9 21 3 21 3 15"/>'
    '<line x1="21" y1="3" x2="14" y2="10"/>'
    '<line x1="3" y1="21" x2="10" y2="14"/>'
    '</svg>'
)


def _build_nav_html(active_tool: str) -> str:
    buttons = ""
    for key in ("notebook", "todo", "pdf"):
        active_cls = " snav-active" if key == active_tool else ""
        icon  = _NAV_ICONS[key]
        label = _NAV_LABELS[key]
        buttons += (
            f'<button class="snav-btn{active_cls}" '
            f'onclick="pycmd(\'{ADDON_NAME_FOR_BRIDGE}:switch:{key}\')">'
            f'{icon}{label}</button>'
        )
    fs_btn = (
        f'<span class="snav-spacer"></span>'
        f'<button class="snav-fs-btn" title="Fullscreen" '
        f'onclick="pycmd(\'{ADDON_NAME_FOR_BRIDGE}:fullscreen\')">'
        f'{_FS_ICON}</button>'
    )
    return f'<div id="synapse-tool-nav">{buttons}{fs_btn}</div>'


def _inject_nav(html: str, active_tool: str) -> str:
    """Insert nav bar + style right after the opening <body> tag."""
    nav_block = _NAV_STYLE + _build_nav_html(active_tool)
    # Match <body> or <body ...>
    new_html = re.sub(r'(<body[^>]*>)', r'\1' + nav_block, html, count=1,
                      flags=re.IGNORECASE)
    if new_html == html:
        # Fallback: prepend to html
        new_html = nav_block + html
    return new_html


# ──────────────────────────────────────────────
# Helpers to make body a flex column so the nav
# bar sits above each tool without overlap.
# ──────────────────────────────────────────────
_BODY_COLUMN_STYLE = """
<style id="synapse-body-column">
  body { display: flex !important; flex-direction: column !important; }
  #app { flex: 1 !important; min-height: 0 !important; }
</style>
"""


def _inject_body_column(html: str) -> str:
    """Ensure body is flex-column so the injected nav is a real row."""
    new_html = re.sub(r'(<head[^>]*>)', r'\1' + _BODY_COLUMN_STYLE, html,
                      count=1, flags=re.IGNORECASE)
    if new_html == html:
        new_html = _BODY_COLUMN_STYLE + html
    return new_html


# ──────────────────────────────────────────────
# Database helpers
# ──────────────────────────────────────────────

_dock: Optional[QDockWidget] = None


def addon_dir() -> str:
    return os.path.dirname(__file__)


def db_path() -> str:
    if mw.pm.profileFolder():
        return os.path.join(mw.pm.profileFolder(), DB_FILENAME)
    return os.path.join(addon_dir(), DB_FILENAME)


def ensure_db() -> None:
    path = db_path()
    con = sqlite3.connect(path)
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                body TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                body TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS pdfs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                body TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)
        con.commit()
    finally:
        con.close()


# ── Notes (Notebook) ──────────────────────────

def load_latest_note() -> str:
    ensure_db()
    try:
        con = sqlite3.connect(db_path())
        row = con.execute(
            "SELECT body FROM notes ORDER BY updated_at DESC, id DESC LIMIT 1"
        ).fetchone()
        con.close()
        return row[0] if row else "[]"
    except Exception as e:
        print(f"Notebook Load Error: {e}")
        return "[]"


def save_note(body: str) -> None:
    ensure_db()
    path = db_path()
    try:
        con = sqlite3.connect(path)
        con.execute(
            "INSERT INTO notes(body, updated_at) VALUES(?, strftime('%s','now'))", (body,)
        )
        con.execute(
            "DELETE FROM notes WHERE id NOT IN "
            "(SELECT id FROM notes ORDER BY updated_at DESC LIMIT 20)"
        )
        con.commit()
        con.close()
        _maybe_vacuum(path)
    except Exception as e:
        print(f"Notebook Save Error: {e}")


# ── Todos ─────────────────────────────────────

def load_latest_todos() -> str:
    ensure_db()
    try:
        con = sqlite3.connect(db_path())
        row = con.execute(
            "SELECT body FROM todos ORDER BY updated_at DESC, id DESC LIMIT 1"
        ).fetchone()
        con.close()
        return row[0] if row else "[]"
    except Exception as e:
        print(f"Todo Load Error: {e}")
        return "[]"


def save_todos(body: str) -> None:
    ensure_db()
    path = db_path()
    try:
        con = sqlite3.connect(path)
        con.execute(
            "INSERT INTO todos(body, updated_at) VALUES(?, strftime('%s','now'))", (body,)
        )
        con.execute(
            "DELETE FROM todos WHERE id NOT IN "
            "(SELECT id FROM todos ORDER BY updated_at DESC LIMIT 20)"
        )
        con.commit()
        con.close()
        _maybe_vacuum(path)
    except Exception as e:
        print(f"Todo Save Error: {e}")


# ── PDFs ──────────────────────────────────────

def load_pdf_list() -> str:
    ensure_db()
    try:
        con = sqlite3.connect(db_path())
        row = con.execute(
            "SELECT body FROM pdfs ORDER BY updated_at DESC, id DESC LIMIT 1"
        ).fetchone()
        con.close()
        return row[0] if row else "[]"
    except Exception as e:
        print(f"PDF Load Error: {e}")
        return "[]"


def load_pdf_list_enriched() -> str:
    """Like load_pdf_list() but adds a transient ``_exists`` bool to every entry.

    Python checks os.path.isfile() for each stored path so the UI can show
    a "missing file" indicator without a separate async bridge round-trip.
    The ``_exists`` flag is stripped again by the save handler so it is never
    persisted back to the database.
    """
    raw = load_pdf_list()
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "pdfs" in data:
            for entry in data["pdfs"]:
                entry["_exists"] = os.path.isfile(entry.get("path", ""))
        return json.dumps(data)
    except Exception:
        return raw


def save_pdf_list(body: str) -> None:
    ensure_db()
    path = db_path()
    try:
        con = sqlite3.connect(path)
        con.execute(
            "INSERT INTO pdfs(body, updated_at) VALUES(?, strftime('%s','now'))", (body,)
        )
        con.execute(
            "DELETE FROM pdfs WHERE id NOT IN "
            "(SELECT id FROM pdfs ORDER BY updated_at DESC LIMIT 20)"
        )
        con.commit()
        con.close()
        _maybe_vacuum(path)
    except Exception as e:
        print(f"PDF Save Error: {e}")


def _maybe_vacuum(path: str) -> None:
    try:
        if os.path.exists(path) and os.path.getsize(path) > (VACUUM_THRESHOLD_MB * 1024 * 1024):
            con = sqlite3.connect(path)
            con.execute("VACUUM")
            con.close()
    except Exception:
        pass


# ── Misc ──────────────────────────────────────

def export_data():
    data = load_latest_note()
    save_title  = _("Export Notebook")
    save_filter = _("JSON (*.json)")
    path, _filter = QFileDialog.getSaveFileName(
        mw, save_title, "notebook_export.json", save_filter
    )
    if path:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
            tooltip(_("Notebook exported successfully!"))
        except Exception as e:
            showInfo(_("Export failed: {}").format(e))


def _open_file_externally(file_path: str) -> None:
    """Open a file with the OS default application."""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", file_path])
        elif sys.platform == "win32":
            os.startfile(file_path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", file_path])
    except Exception as e:
        showInfo(_("Could not open file: {}").format(e))


# ──────────────────────────────────────────────
# Fullscreen window
# ──────────────────────────────────────────────

class NotebookFullscreenWindow(QWidget):
    """Standalone fullscreen window that borrows the web view from the dock."""

    def __init__(self, panel: "NotebookPanel", web_view: AnkiWebView, parent=None) -> None:
        super().__init__(parent)
        self.panel    = panel
        self.web_view = web_view
        self.setWindowTitle(_("SynapsePro – Notebook"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(web_view)

        # ESC closes fullscreen
        esc = QShortcut(QKeySequence("Escape"), self)
        esc.activated.connect(self.close)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.panel.exit_fullscreen(self.web_view)
        event.accept()


# ──────────────────────────────────────────────
# NotebookPanel  –  the main Qt widget
# ──────────────────────────────────────────────

class NotebookPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._layout)
        self.web: Optional[AnkiWebView] = None
        self.is_initialized    = False
        self.current_tool      = "notebook"
        self.is_in_fullscreen  = False
        self.fullscreen_window: Optional[NotebookFullscreenWindow] = None
        self._current_pdf_path = ""
        # Store a reference to the parent dock for fullscreen toggling
        self.parent_dock: Optional[QDockWidget] = (
            parent if isinstance(parent, QDockWidget) else None
        )

    # ── Loading ───────────────────────────────

    def load_content(self):
        """Create the WebView and load current tool. Called when dock becomes visible."""
        if self.web:
            self._reload_current_tool()
            return

        self.web = AnkiWebView(kind=AnkiWebViewKind.DEFAULT)
        self.web.set_bridge_command(self._on_bridge_cmd, self)
        self._layout.addWidget(self.web)

        self._load_tool(self.current_tool)
        self.is_initialized = True

    def unload_content(self):
        """Destroy the WebView to free RAM (called when dock is hidden)."""
        if self.is_in_fullscreen:
            return  # Don't unload while fullscreen window is open
        self._current_pdf_path = ""
        if self.web:
            self._layout.removeWidget(self.web)
            self.web.deleteLater()
            self.web = None
            self.is_initialized = False

    def enter_fullscreen(self) -> None:
        if not self.web or self.is_in_fullscreen:
            return
        self.is_in_fullscreen = True

        # Detach web view from dock layout
        self._layout.removeWidget(self.web)
        self.web.setParent(None)  # type: ignore[arg-type]

        # Hide the dock
        if self.parent_dock:
            self.parent_dock.hide()

        # Show in standalone fullscreen window
        self.fullscreen_window = NotebookFullscreenWindow(self, self.web)
        self.fullscreen_window.showFullScreen()

    def exit_fullscreen(self, web_view_ref: AnkiWebView) -> None:
        self.is_in_fullscreen  = False
        self.fullscreen_window = None

        # Reattach web view to dock panel
        self._layout.addWidget(web_view_ref)
        self.web = web_view_ref

        # Show the dock again
        if self.parent_dock:
            self.parent_dock.show()
            self.parent_dock.raise_()

    def _load_tool(self, tool_name: str) -> None:
        """Read the tool's HTML file, inject nav bar, and display it."""
        if not self.web:
            return
        self.current_tool = tool_name
        file_name = TOOL_FILES.get(tool_name, "index.html")
        html_path = os.path.join(addon_dir(), HTML_DIR, file_name)

        if not os.path.exists(html_path):
            self.web.setHtml(
                f"<h2 style='font-family:sans-serif;padding:20px'>"
                f"Error: {HTML_DIR}/{file_name} not found</h2>"
            )
            return

        with open(html_path, "r", encoding="utf-8") as fh:
            html = fh.read()

        html = _inject_body_column(html)
        html = _inject_nav(html, tool_name)

        # ── Preload initial data to avoid a visual flash ──────────────
        # Instead of loading the page with default state and then calling
        # loadContent() 150 ms later (which causes a visible layout shift),
        # we embed the data directly so the page can initialise correctly
        # on first render.
        if tool_name == "notebook":
            preload_data = load_latest_note()
            preload_js   = json.dumps(preload_data)
            preload_tag  = f'<script id="synapse-preload">window.__SYNAPSE_PRELOAD__={preload_js};</script>'
            # Use a lambda replacement so that JSON backslash-escapes (e.g. \u, \n)
            # inside preload_tag are never interpreted as regex replacement tokens.
            html = re.sub(r'</head>', lambda m: preload_tag + m.group(0), html,
                          count=1, flags=re.IGNORECASE)
        elif tool_name == "todo":
            preload_data = load_latest_todos()
            preload_js   = json.dumps(preload_data)
            preload_tag  = (
                f'<script id="synapse-preload">'
                f'window.__SYNAPSE_TODO_PRELOAD__={preload_js};'
                f'</script>'
            )
            html = re.sub(r'</head>', lambda m: preload_tag + m.group(0), html,
                          count=1, flags=re.IGNORECASE)
        elif tool_name == "pdf":
            preload_data = load_pdf_list_enriched()
            preload_js   = json.dumps(preload_data)

            # Try to use locally cached PDF.js (offline support + avoids cross-origin
            # worker restriction that can occur with setHtml() pages).
            pdfjs_main_tag, worker_json = _pdfjs_local_scripts()
            if pdfjs_main_tag:
                _CDN_TAG = (
                    '<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/'
                    f'{PDFJS_VERSION}/pdf.min.js"></script>'
                )
                html = html.replace(_CDN_TAG, pdfjs_main_tag, 1)
                preload_tag = (
                    f'<script id="synapse-preload">'
                    f'window.__SYNAPSE_PDF_PRELOAD__={preload_js};'
                    f'window.__PDFJS_WORKER_CODE__={worker_json};'
                    f'</script>'
                )
            else:
                preload_tag = (
                    f'<script id="synapse-preload">'
                    f'window.__SYNAPSE_PDF_PRELOAD__={preload_js};'
                    f'</script>'
                )
            html = re.sub(r'</head>', lambda m: preload_tag + m.group(0), html,
                          count=1, flags=re.IGNORECASE)

        # ── Inject i18n translations ──────────────────────────────────
        i18n_tag = _build_i18n_script(tool_name)
        html = re.sub(r'</head>', lambda m: i18n_tag + m.group(0), html,
                      count=1, flags=re.IGNORECASE)

        self.web.setHtml(html)

    def _reload_current_tool(self) -> None:
        """Re-fetch data for whichever tool is visible."""
        if self.current_tool == "notebook":
            self.reload_from_db()
        elif self.current_tool == "todo":
            self._reload_todos()
        elif self.current_tool == "pdf":
            self._reload_pdfs()

    # ── Data reload helpers ───────────────────

    def reload_from_db(self) -> None:
        if not self.web:
            return
        body = load_latest_note()
        json_str = json.dumps(body)
        self.web.eval(f"if(window.loadContent) window.loadContent({json_str});")

    def _reload_todos(self) -> None:
        if not self.web:
            return
        body = load_latest_todos()
        json_str = json.dumps(body)
        self.web.eval(f"if(window.loadTodos) window.loadTodos({json_str});")

    def _reload_pdfs(self) -> None:
        if not self.web:
            return
        body     = load_pdf_list_enriched()
        json_str = json.dumps(body)
        self.web.eval(f"if(window.loadPdfs) window.loadPdfs({json_str});")

    # ── Bridge command handler ────────────────

    def _on_bridge_cmd(self, cmd: str) -> None:
        prefix = f"{ADDON_NAME_FOR_BRIDGE}:"
        if not cmd.startswith(prefix):
            return
        payload = cmd[len(prefix):]

        # ── Tab switching ──────────────────────
        if payload.startswith("switch:"):
            tool = payload[len("switch:"):]
            if tool in TOOL_FILES:
                self._load_tool(tool)
            return

        # ── Fullscreen ────────────────────────
        if payload == "fullscreen":
            if self.is_in_fullscreen:
                if self.fullscreen_window:
                    self.fullscreen_window.close()  # triggers exit_fullscreen via closeEvent
            else:
                self.enter_fullscreen()
            return

        # ── Notebook commands ──────────────────
        if payload == "load":
            self.reload_from_db()
        elif payload.startswith("save:"):
            body = payload[len("save:"):]
            save_note(body)
            if self.web:
                self.web.eval("if(window.onSaved) window.onSaved();")
        elif payload == "export":
            export_data()

        # ── Todo commands ──────────────────────
        elif payload == "todo:load":
            self._reload_todos()
        elif payload.startswith("todo:save:"):
            body = payload[len("todo:save:"):]
            save_todos(body)
            if self.web:
                self.web.eval("if(window.onTodoSaved) window.onTodoSaved();")

        # ── PDF commands ───────────────────────
        elif payload == "pdf:load":
            self._reload_pdfs()
        elif payload.startswith("pdf:save:"):
            body = payload[len("pdf:save:"):]
            # Strip transient _exists flags before persisting
            try:
                data = json.loads(body)
                if isinstance(data, dict) and "pdfs" in data:
                    for entry in data["pdfs"]:
                        entry.pop("_exists", None)
                body = json.dumps(data)
            except Exception:
                pass
            save_pdf_list(body)
            if self.web:
                self.web.eval("if(window.onPdfSaved) window.onPdfSaved();")
        elif payload == "pdf:add":
            self._add_pdf_dialog()
        elif payload.startswith("pdf:open:"):
            file_path = payload[len("pdf:open:"):]
            _open_file_externally(file_path)
        elif payload.startswith("pdf:render:"):
            file_path = payload[len("pdf:render:"):]
            self._render_pdf_inline(file_path)
        elif payload == "pdf:back":
            self._current_pdf_path = ""
            self._load_tool("pdf")
        elif payload.startswith("pdf:relink:"):
            pdf_id = payload[len("pdf:relink:"):]
            self._relink_pdf_dialog(pdf_id)

    def _add_pdf_dialog(self) -> None:
        """Open a file-chooser and pass the chosen path back to JavaScript."""
        dialog_title  = _("Select PDF")
        dialog_filter = _("PDF Files (*.pdf)")
        path, _filter = QFileDialog.getOpenFileName(
            mw, dialog_title, "", dialog_filter
        )
        if path and self.web:
            json_path = json.dumps(path)
            self.web.eval(f"if(window.onPdfAdded) window.onPdfAdded({json_path});")

    def _relink_pdf_dialog(self, pdf_id: str) -> None:
        """Let the user pick a new file path for a missing PDF entry."""
        dialog_title  = _("Relink PDF")
        dialog_filter = _("PDF Files (*.pdf)")
        path, _filter = QFileDialog.getOpenFileName(
            mw, dialog_title, "", dialog_filter
        )
        if path and self.web:
            id_json   = json.dumps(pdf_id)
            path_json = json.dumps(path)
            self.web.eval(
                f"if(window.onPdfRelinked) window.onPdfRelinked({id_json}, {path_json});"
            )

    def _render_pdf_inline(self, file_path: str) -> None:
        """Render a PDF inline via PDF.js running inside pdf_viewer.html."""
        if not self.web:
            return

        # ── File existence check ──────────────────────────────────────
        if not os.path.isfile(file_path):
            name_json = json.dumps(os.path.basename(file_path))
            err_json  = json.dumps(
                _("File not found – it may have been moved or deleted:\n{}").format(file_path)
            )
            # Show the viewer panel with an inline error instead of a blocking popup
            self.web.eval(
                f"if(window.showViewer) window.showViewer({name_json}, '');"
                f"if(window.showViewerError) window.showViewerError({err_json});"
            )
            return

        # ── File size guard ───────────────────────────────────────────
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > MAX_PDF_INLINE_MB:
            msg = _(
                "This PDF is {size:.1f} MB. Loading it into the sidebar may be slow "
                "or use a lot of memory.\n\nContinue anyway?"
            ).format(size=file_size_mb)
            if not askUser(msg):
                return

        self._current_pdf_path = file_path

        # ── Read + encode ─────────────────────────────────────────────
        try:
            with open(file_path, "rb") as fh:
                pdf_bytes = fh.read()
        except Exception as exc:
            err_json  = json.dumps(_("Could not read PDF: {}").format(exc))
            name_json = json.dumps(os.path.basename(file_path))
            self.web.eval(
                f"if(window.showViewer) window.showViewer({name_json}, '');"
                f"if(window.showViewerError) window.showViewerError({err_json});"
            )
            return

        b64       = base64.b64encode(pdf_bytes).decode("ascii")
        name_json = json.dumps(os.path.basename(file_path))
        path_json = json.dumps(file_path)

        # Pass data via window globals – avoids issues with very large eval strings.
        self.web.eval(
            f"window.__PDF_B64__={json.dumps(b64)};"
            f"window.__PDF_NAME__={name_json};"
            f"window.__PDF_PATH__={path_json};"
            f"if(window.renderFromGlobals) window.renderFromGlobals();"
        )


# ──────────────────────────────────────────────
# Dock management
# ──────────────────────────────────────────────

def _ensure_dock() -> QDockWidget:
    global _dock

    if _dock is not None:
        return _dock

    dock_name = "IntegratedNotebookSidebarDock_Mobesa_v1"
    _dock = QDockWidget(_(DOCK_TITLE), mw)
    _dock.setObjectName(dock_name)
    _dock.setAllowedAreas(
        Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
    )

    empty_title_bar = QWidget()
    _dock.setTitleBarWidget(empty_title_bar)

    panel = NotebookPanel(_dock)
    _dock.setWidget(panel)
    _dock.setMinimumWidth(320)

    _dock.visibilityChanged.connect(_on_visibility_changed)

    mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, _dock)
    return _dock


def _on_visibility_changed(visible: bool):
    global _dock
    if not _dock:
        return
    panel = _dock.widget()
    if isinstance(panel, NotebookPanel):
        if visible:
            panel.load_content()
        else:
            panel.unload_content()


# ── Integration Functions (called from __init__.py) ──

def setup_notebook_sidebar():
    # Kick off a background download of PDF.js so the viewer works offline
    # after the first run (or after the cache is cleared).
    _ensure_pdfjs_async()


def toggle_notebook_dock():
    dock = _ensure_dock()
    if dock.isVisible():
        dock.hide()
    else:
        dock.show()
        dock.raise_()


def cleanup_notebook_sidebar():
    global _dock
    if _dock:
        panel = _dock.widget()
        if isinstance(panel, NotebookPanel):
            panel.unload_content()
    _dock = None
