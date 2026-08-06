from __future__ import annotations

import base64
import html
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
from typing import Callable, Optional

import aqt
from anki.collection import AddNoteRequest
from anki.consts import MODEL_STD
from aqt import mw
from aqt.operations import CollectionOp
from aqt.qt import (
    QApplication,
    QDockWidget, Qt, QVBoxLayout, QHBoxLayout,
    QWidget, QFileDialog, QUrl, QKeySequence, QShortcut,
    QPushButton, QLabel, QTimer,
)
from aqt.webview import AnkiWebView, AnkiWebViewKind
from aqt.utils import tooltip, showInfo, askUser

try:
    from .locales import _
except ImportError:
    def _(text):  # type: ignore
        return text

from . import embedded_window

ADDON_NAME_FOR_BRIDGE = "notion_mini"
DB_FILENAME = "notebook.sqlite"
DOCK_TITLE = "Notebook"
HTML_DIR = "web_notebook"


def _json_for_script(value, *, ensure_ascii: bool = True) -> str:
    """Serialize data for an inline script without allowing </script> breaks."""
    return json.dumps(value, ensure_ascii=ensure_ascii).replace("</", "<\\/")

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
            "document_title":    _("Notebook"),
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
            "custom_icon_placeholder": _("Own icon or text…"),
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
            "block_pagelink":     _("Link to page"),
            "paste_tip":          _("Tip: Paste images (Ctrl+V) supported"),
            "saved":              _("Saved"),
            "saving":             _("Saving..."),
            "save_failed":        _("Save failed — your changes are still open."),
            "untitled":           _("Untitled"),
            "delete_page_confirm":  _("Delete this page?"),
            "delete_table_confirm": _("Delete table?"),
            "table_add_row":      _("+ Row"),
            "table_add_col":      _("+ Col"),
            "placeholder_slash":        _("Type '/' for commands"),
            "placeholder_callout":      _("Type something..."),
            "placeholder_toggle":       _("Toggle title"),
            "placeholder_toggle_body":  _("Add content here..."),
            "pinned":               _("Pinned"),
            "pin":                  _("Pin"),
            "unpin":                _("Unpin"),
            "new_folder":           _("New Folder"),
            "folder_name_prompt":   _("Folder name:"),
            "rename_folder":        _("Rename folder:"),
            "delete_folder_confirm": _("Delete folder? Pages inside will be kept."),
            "move_to_folder":       _("Move to folder"),
            "no_folder":            _("No folder"),
            "time_just_now":  _("just now"),
            "time_m_ago":     _("m ago"),
            "time_h_ago":     _("h ago"),
            "time_d_ago":     _("d ago"),
            "no_results":     _("No results for"),
            "page_title_placeholder": _("Page Title"),
            "page_picker_placeholder": _("Search or create a page…"),
            "remove_cover": _("Remove cover"),
            "new_page_named": _("New page: \"{title}\""),
            "create_new_page": _("Create new page"),
            "page_not_found": _("Page not found"),
            "link_title": _("Link (Ctrl+K)"),
            "cover_title": _("Cover for learning"),
            "recover_covers_title": _("Cover all revealed terms again"),
        },
        "todo": {
            "title":           _("Todo"),
            "delete":          _("Delete"),
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
            "save_failed":     _("Save failed — your changes are still open."),
            "done_of":         _("{done} / {total} done"),
        },
        "pdf": {
            "title":               _("PDF"),
            "zoom_out":            _("Zoom out"),
            "zoom_in":             _("Zoom in"),
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
            "notice_title":        _("PDF study viewer"),
            "notice_body":         _("Select text in text-based PDFs to copy it or prepare an Anki card. Scanned PDFs require OCR."),
            "copy_selection":      _("Copy"),
            "card_front":          _("Card front"),
            "card_back":           _("Card back"),
            "open_in_anki":        _("Open in Anki"),
            "clear_draft":         _("Clear"),
            "front_saved":         _("Front saved"),
            "back_saved":          _("Back saved"),
            "draft_front":         _("Front"),
            "draft_back":          _("Back side"),
            "select_text_first":   _("Select some PDF text first."),
            "discard_draft":       _("Discard the unfinished card draft?"),
            "card_creator":        _("Card Creator"),
            "creator_subtitle":    _("Build multiple cards while reading"),
            "creator_sidebar_hint": _("Tip: Card Creator works best in fullscreen."),
            "front_placeholder":   _("Question or prompt"),
            "back_placeholder":    _("Answer or explanation"),
            "add_card":            _("Add card"),
            "update_card":         _("Update card"),
            "new_card":            _("New card"),
            "include_source":      _("Add PDF source to the back"),
            "source_hint":         _("Adds the file name and selected page numbers in small text."),
            "source_short":        _("Source"),
            "cards_ready":         _("{count} cards ready"),
            "cards_label":         _("Cards"),
            "deck_name":           _("Deck name"),
            "deck_placeholder":    _("Choose an existing deck or enter a new name"),
            "finish_session":      _("Create cards"),
            "finish_cards":        _("Finish · Create {count} cards"),
            "discard_session":     _("Discard session"),
            "discard_session_confirm": _("Discard this unfinished Card Creator session?"),
            "edit":                _("Edit"),
            "remove_card":         _("Remove card"),
            "creator_empty":       _("No cards collected yet."),
            "creator_empty_sub":   _("Enter text manually or select text in the PDF."),
            "front_required":      _("Enter a front side first."),
            "deck_required":       _("Choose or enter a deck name."),
            "creating_cards":      _("Creating cards…"),
            "duplicate_card":      _("This card is already in the session."),
            "card_too_long":       _("This card contains too much text."),
            "too_many_cards":      _("This session already contains 500 cards."),
            "close":               _("Close"),
            "save_failed":         _("Save failed — your changes are still open."),
            "folder_name_prompt":  _("Folder name:"),
            "rename_folder":       _("Rename folder:"),
            "all":                 _("All"),
            "unfiled":             _("Unfiled"),
            "new_folder":          _("New Folder"),
            "no_folder":           _("No folder"),
            "no_folders":          _("No folders yet."),
            "empty_in_folder":     _("No PDFs in \"{folder}\" yet."),
            "file_missing":        _("File missing"),
            "delete_folder_named": _("Delete folder \"{name}\"? {count} PDF file(s) will become unfiled."),
            "loading_short":       _("Loading…"),
            "page_error":          _("Page {page}: {error}"),
            "selected_text_copied": _("Selected text copied"),
            "copy_text_failed":    _("Could not copy text"),
            "cards_created":       _("Cards created"),
            "cards_create_failed": _("Could not create cards"),
        },
    }
    strings = dict(STRINGS.get(tool_name, {}))
    strings.update({
        "error_title": _("SynapsePro error"),
        "error_show": _("Show details"),
        "error_hide": _("Hide details"),
        "error_copy": _("Copy error"),
        "error_copied": _("Copied!"),
        "error_dismiss": _("Dismiss"),
        "error_unexpected": _("Unexpected error"),
        "error_unexpected_async": _("Unexpected error (async)"),
        "error_safe": _("Your data is safe. Please screenshot the details and send them to help.synapse.pro@gmail.com."),
        "error_no_stack": _("(no stack trace available)"),
    })
    strings_json = _json_for_script(strings, ensure_ascii=False)
    return f'<script id="synapse-i18n">window.__SYNAPSE_I18N__={strings_json};</script>'
MAX_PDF_INLINE_MB    = 30   # warn before loading PDFs larger than this
MAX_PDF_HARD_MB      = 100  # avoid multi-hundred-MB reads/base64 copies
MAX_PDF_CARD_CHARS   = 50_000
MAX_PDF_COPY_CHARS   = 200_000
MAX_PDF_BATCH_CARDS  = 500
MAX_PDF_BATCH_CHARS  = 1_000_000
MAX_PDF_DECK_SUGGESTIONS = 2_000
MAX_FINAL_SAVE_ATTEMPTS = 3

TOOL_FILES = {
    "notebook": "index.html",
    "todo":     "todo.html",
    "pdf":      "pdf_viewer.html",
}

# ──────────────────────────────────────────────
# PDF.js offline bundling
# ──────────────────────────────────────────────

PDFJS_VERSION = "3.11.174"
_PDFJS_FILES  = ["pdf.min.js", "pdf.worker.min.js"]


def _pdfjs_dir() -> str:
    return os.path.join(addon_dir(), HTML_DIR, "pdfjs")


def _ensure_pdfjs_async() -> None:
    """Verify that the pinned, bundled PDF.js files are available."""
    existing_dir = _pdfjs_dir()
    if all(os.path.exists(os.path.join(existing_dir, name))
           for name in _PDFJS_FILES):
        return
    print("SynapsePro: bundled PDF.js files are missing; PDF viewer disabled.")


def _pdfjs_local_scripts() -> tuple[str, str]:
    """Return (main_inline_tag, worker_code_json) if both local files are ready.

    main_inline_tag  – a <script>…</script> block inlining pdf.min.js
    worker_code_json – a JSON string of pdf.worker.min.js content, safe to embed
                       inside a <script> tag (</ is escaped with a backslash)
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

# Icon shown while IN fullscreen: arrows pointing inwards ("exit fullscreen").
# Same glyph as the Mindmap tool so all features look identical.
_FS_ICON_EXIT = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="4 14 10 14 10 20"/>'
    '<polyline points="20 10 14 10 14 4"/>'
    '<line x1="10" y1="14" x2="3" y2="21"/>'
    '<line x1="21" y1="3" x2="14" y2="10"/>'
    '</svg>'
)

# Icon for "open in a separate window" (a window with a title bar)
_WIN_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="3" y="3" width="18" height="18" rx="2"/>'
    '<line x1="3" y1="9" x2="21" y2="9"/>'
    '</svg>'
)

# Icon shown while the embedded view is active: the same window frame with a
# small dash inside (matches the Mindmap tool's "close window" state).
_WIN_ICON_CLOSE = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="3" y="3" width="18" height="18" rx="2"/>'
    '<line x1="3" y1="9" x2="21" y2="9"/>'
    '<line x1="9" y1="15" x2="15" y2="15"/>'
    '</svg>'
)


def _build_nav_html(active_tool: str, fs_active: bool = False,
                    win_active: bool = False) -> str:
    buttons = ""
    for key in ("notebook", "todo", "pdf"):
        active_cls = " snav-active" if key == active_tool else ""
        icon  = _NAV_ICONS[key]
        label = _(_NAV_LABELS[key])
        buttons += (
            f'<button class="snav-btn{active_cls}" '
            f'onclick="pycmd(\'{ADDON_NAME_FOR_BRIDGE}:switch:{key}\')">'
            f'{icon}{label}</button>'
        )
    win_title = _("Close Window") if win_active else _("New Window")
    fs_title  = _("Exit Fullscreen") if fs_active else _("Fullscreen")
    win_icon  = _WIN_ICON_CLOSE if win_active else _WIN_ICON
    fs_icon   = _FS_ICON_EXIT if fs_active else _FS_ICON
    fs_btn = (
        f'<span class="snav-spacer"></span>'
        f'<button id="snav-win-btn" class="snav-fs-btn" title="{win_title}" '
        f'onclick="pycmd(\'{ADDON_NAME_FOR_BRIDGE}:window\')">'
        f'{win_icon}</button>'
        f'<button id="snav-fs-btn" class="snav-fs-btn" title="{fs_title}" '
        f'onclick="pycmd(\'{ADDON_NAME_FOR_BRIDGE}:fullscreen\')">'
        f'{fs_icon}</button>'
    )
    return f'<div id="synapse-tool-nav">{buttons}{fs_btn}</div>'


def _build_nav_toggle_script() -> str:
    """JS helpers that swap the fullscreen / window icons at runtime.

    Mirrors the Mindmap tool's __synapseSetFullscreen / __synapseSetWindow
    contract so Python can toggle the button state without a page reload.
    """
    icons = {
        "fs":       _FS_ICON,
        "fsExit":   _FS_ICON_EXIT,
        "win":      _WIN_ICON,
        "winClose": _WIN_ICON_CLOSE,
    }
    return (
        '<script id="synapse-nav-toggle">'
        f'var __SNAV_ICONS__ = {json.dumps(icons)};'
        'window.__synapseSetFullscreen = function(active, t) {'
        '  var btn = document.getElementById("snav-fs-btn");'
        '  if (!btn) return;'
        '  btn.innerHTML = active ? __SNAV_ICONS__.fsExit : __SNAV_ICONS__.fs;'
        '  if (t) btn.title = active ? t.fullscreen_exit : t.fullscreen_enter;'
        '};'
        'window.__synapseSetWindow = function(active, t) {'
        '  var btn = document.getElementById("snav-win-btn");'
        '  if (!btn) return;'
        '  btn.innerHTML = active ? __SNAV_ICONS__.winClose : __SNAV_ICONS__.win;'
        '  if (t) btn.title = active ? t.window_exit : t.window_open;'
        '};'
        '</script>'
    )


def _inject_nav(html: str, active_tool: str, fs_active: bool = False,
                win_active: bool = False) -> str:
    """Insert nav bar + style right after the opening <body> tag."""
    nav_block = (_NAV_STYLE
                 + _build_nav_html(active_tool, fs_active, win_active)
                 + _build_nav_toggle_script())
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
  /* Wide mode (embedded / fullscreen): the note column is capped at 800px
     for the narrow sidebar. In a large window that leaves too much empty
     space, so we widen it while still keeping comfortable side margins. */
  body.synapse-wide .content-container {
    max-width: none !important;
    padding-left: 10% !important;
    padding-right: 10% !important;
  }
  /* Wide mode: the top bars stay flush with the window edges (small fixed
     padding), so the nav buttons sit fully left and the window/fullscreen
     and sidebar buttons sit fully right. Only the note column below keeps
     its comfortable side margins. */
  body.synapse-wide #synapse-tool-nav {
    padding: 0 10px;
    height: 46px;
  }
  body.synapse-wide .header-bar {
    padding: 0 15px;
  }
</style>
"""


def _inject_body_column(html: str) -> str:
    """Ensure body is flex-column so the injected nav is a real row."""
    new_html = re.sub(r'(<head[^>]*>)', r'\1' + _BODY_COLUMN_STYLE, html,
                      count=1, flags=re.IGNORECASE)
    if new_html == html:
        new_html = _BODY_COLUMN_STYLE + html
    return new_html


def _add_wide_class(html: str) -> str:
    """Tag <body> with 'synapse-wide' (used for embedded / fullscreen views).

    Applied at load time so switching tools while already in a wide view keeps
    the widened note column. Live toggling (without reload) is handled via JS.
    """
    def repl(match: "re.Match[str]") -> str:
        tag = match.group(0)
        m_cls = re.search(r'class=(["\'])(.*?)\1', tag, flags=re.IGNORECASE)
        if m_cls:
            quote = m_cls.group(1)
            value = m_cls.group(2)
            new_attr = f'class={quote}{value} synapse-wide{quote}'
            return tag[:m_cls.start()] + new_attr + tag[m_cls.end():]
        return tag[:-1] + ' class="synapse-wide">'

    return re.sub(r'<body[^>]*>', repl, html, count=1, flags=re.IGNORECASE)


def _apply_night_mode(html: str) -> str:
    """Tell the page Anki's theme, exactly like the mindmap tool does.

    The tool pages must not rely on ``prefers-color-scheme``: Chromium derives
    that from the OS (on macOS Anki's dark switch flips the whole app's native
    appearance, so it happened to match — on Windows it never follows Anki).
    Instead we tag <html> with 'nightMode' — every tool's boot script already
    copies that to <body>, where all dark CSS rules hook in — and expose an
    explicit ``window.__SYNAPSE_NIGHT__`` flag for JS-side checks.
    """
    try:
        night = bool(mw and mw.pm.night_mode())
    except Exception:
        night = False

    flag_tag = ('<script id="synapse-night">window.__SYNAPSE_NIGHT__='
                + ("true" if night else "false") + ';</script>')
    new_html = re.sub(r'(<head[^>]*>)', lambda m: m.group(1) + flag_tag, html,
                      count=1, flags=re.IGNORECASE)
    if new_html == html:
        new_html = flag_tag + html
    html = new_html
    if not night:
        return html

    def repl(match: "re.Match[str]") -> str:
        tag = match.group(0)
        m_cls = re.search(r'class=(["\'])(.*?)\1', tag, flags=re.IGNORECASE)
        if m_cls:
            quote = m_cls.group(1)
            value = m_cls.group(2)
            new_attr = f'class={quote}{value} nightMode{quote}'
            return tag[:m_cls.start()] + new_attr + tag[m_cls.end():]
        return tag[:-1] + ' class="nightMode">'

    return re.sub(r'<html[^>]*>', repl, html, count=1, flags=re.IGNORECASE)


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


def _ensure_db_at(path: str, timeout: float = 5.0) -> None:
    con = sqlite3.connect(path, timeout=timeout)
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


def ensure_db() -> None:
    _ensure_db_at(db_path())


# ── Snapshot persistence ───────────────────────

def _snapshot_recovery_path(table: str, database_path: Optional[str] = None) -> str:
    database_path = database_path or db_path()
    return os.path.join(
        os.path.dirname(database_path), f"synapsepro_{table}_recovery.json"
    )


def _write_snapshot_recovery(
    table: str, body: str, database_path: Optional[str] = None
) -> bool:
    """Atomically preserve a valid snapshot when SQLite is temporarily unavailable."""
    path = _snapshot_recovery_path(table, database_path)
    tmp_path = f"{path}.tmp"
    try:
        data = json.loads(body)
        payload = {"version": 1, "table": table, "body": data}
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        return True
    except Exception as exc:
        print(f"Notebook {table} recovery save failed: {exc}")
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        return False


def _load_snapshot_recovery(
    table: str, database_path: Optional[str] = None
) -> Optional[str]:
    try:
        with open(
            _snapshot_recovery_path(table, database_path), "r", encoding="utf-8"
        ) as handle:
            payload = json.load(handle)
        if (
            isinstance(payload, dict)
            and payload.get("version") == 1
            and payload.get("table") == table
        ):
            body = json.dumps(payload.get("body"), ensure_ascii=False, separators=(",", ":"))
            return body if _valid_snapshot(table, body) else None
    except FileNotFoundError:
        pass
    except Exception as exc:
        print(f"Notebook {table} recovery load failed: {exc}")
    return None


def _clear_snapshot_recovery(
    table: str, committed_body: str, database_path: Optional[str] = None
) -> None:
    path = _snapshot_recovery_path(table, database_path)
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError:
        # A locked recovery file must never remain stale. Refreshing it with the
        # just-committed body keeps either source safe to load next time.
        _write_snapshot_recovery(table, committed_body, database_path)

def _load_latest_snapshot(
    table: str, fallback: str, database_path: Optional[str] = None
) -> str:
    """Load one known snapshot table without leaking a SQLite connection."""
    database_path = database_path or db_path()
    recovery = _load_snapshot_recovery(table, database_path)
    if recovery is not None:
        return recovery
    con: Optional[sqlite3.Connection] = None
    try:
        _ensure_db_at(database_path)
        con = sqlite3.connect(database_path, timeout=5)
        row = con.execute(
            f"SELECT body FROM {table} ORDER BY updated_at DESC, id DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else fallback
    except Exception as e:
        print(f"Notebook {table} Load Error: {e}")
        return fallback
    finally:
        if con is not None:
            con.close()


def _valid_snapshot(table: str, body: str) -> bool:
    """Reject truncated/corrupt bridge payloads before they become the latest row."""
    try:
        data = json.loads(body)
    except (TypeError, ValueError):
        return False
    if table == "notes":
        return isinstance(data, list) or (
            isinstance(data, dict) and isinstance(data.get("pages"), list)
        )
    if table == "todos":
        return isinstance(data, list)
    if table == "pdfs":
        return isinstance(data, list) or (
            isinstance(data, dict) and isinstance(data.get("pdfs"), list)
        )
    return False


def _save_snapshot(
    table: str,
    body: str,
    database_path: Optional[str] = None,
    sqlite_timeout: float = 5.0,
) -> bool:
    """Transactionally store a validated snapshot and retain 20 recovery rows."""
    if not _valid_snapshot(table, body):
        print(f"Notebook {table} Save Error: invalid JSON snapshot rejected")
        return False

    con: Optional[sqlite3.Connection] = None
    database_path = database_path or db_path()
    try:
        _ensure_db_at(database_path, timeout=sqlite_timeout)
        con = sqlite3.connect(database_path, timeout=sqlite_timeout)
        with con:
            con.execute(
                f"INSERT INTO {table}(body, updated_at) "
                "VALUES(?, strftime('%s','now'))",
                (body,),
            )
            con.execute(
                f"DELETE FROM {table} WHERE id NOT IN "
                f"(SELECT id FROM {table} "
                "ORDER BY updated_at DESC, id DESC LIMIT 20)"
            )
        _clear_snapshot_recovery(table, body, database_path)
        return True
    except Exception as e:
        print(f"Notebook {table} Save Error: {e}")
        if _write_snapshot_recovery(table, body, database_path):
            print(f"Notebook {table}: latest snapshot stored in recovery file")
            return True
        return False
    finally:
        if con is not None:
            con.close()


# ── Notes (Notebook) ──────────────────────────

def load_latest_note() -> str:
    return _load_latest_snapshot("notes", "[]")


def save_note(body: str) -> bool:
    return _save_snapshot("notes", body)


# ── Todos ─────────────────────────────────────

def load_latest_todos() -> str:
    return _load_latest_snapshot("todos", "[]")


def save_todos(body: str) -> bool:
    return _save_snapshot("todos", body)


# ── PDFs ──────────────────────────────────────

def load_pdf_list() -> str:
    return _load_latest_snapshot("pdfs", "[]")


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


def save_pdf_list(body: str) -> bool:
    return _save_snapshot("pdfs", body)


def _pdf_deck_names() -> list[str]:
    """Return normal Anki decks for the Card Creator's searchable input."""
    try:
        if not mw or not getattr(mw, "col", None):
            return []
        names = {
            item.name
            for item in mw.col.decks.all_names_and_ids(include_filtered=False)
            if getattr(item, "name", "")
        }
        # A datalist with tens of thousands of DOM options can noticeably stall
        # a narrow WebView. Any omitted deck can still be entered manually.
        return sorted(names, key=str.casefold)[:MAX_PDF_DECK_SUGGESTIONS]
    except Exception as exc:
        print(f"Notebook could not load deck names for PDF Card Creator: {exc}")
        return []


# ── Serialized background writer ──────────────

class _PendingSnapshotWrite:
    def __init__(
        self,
        table: str,
        body: str,
        database_path: str,
        callback: Callable[[bool], None],
    ) -> None:
        self.table = table
        self.body = body
        self.database_path = database_path
        self.callbacks = [callback]


class _NotebookBackgroundWriter:
    """One lazy worker that serializes and coalesces our private SQLite writes.

    An in-flight write is never replaced. Only a not-yet-started write for the
    same profile and table is updated to the newest snapshot; every requester is
    still notified once that newest durable snapshot has completed.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[tuple[str, str], _PendingSnapshotWrite] = {}
        self._thread: Optional[threading.Thread] = None

    def submit(
        self,
        table: str,
        body: str,
        database_path: str,
        callback: Callable[[bool], None],
    ) -> None:
        if table not in {"notes", "todos", "pdfs"}:
            self._deliver([callback], False)
            return

        key = (database_path, table)
        with self._lock:
            pending = self._pending.get(key)
            if pending is None:
                self._pending[key] = _PendingSnapshotWrite(
                    table, body, database_path, callback
                )
            else:
                # Coalesce only work the thread has not started yet. The callbacks
                # remain in request order, matching the JavaScript save revisions.
                pending.body = body
                pending.callbacks.append(callback)
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(
                    target=self._run,
                    name="SynapseProNotebookWriter",
                    # A short-lived non-daemon worker is intentional: on a normal
                    # Anki exit Python waits for an in-flight durable write instead
                    # of terminating it halfway through. The thread exits as soon
                    # as the queue is empty, so it never keeps an idle app alive.
                    daemon=False,
                )
                self._thread.start()

    def _run(self) -> None:
        while True:
            with self._lock:
                if not self._pending:
                    self._thread = None
                    return
                key = next(iter(self._pending))
                job = self._pending.pop(key)

            # This database is owned by the add-on, not by Anki's Collection.
            # A fresh connection is created and closed entirely on this thread.
            saved = _save_snapshot(
                job.table,
                job.body,
                database_path=job.database_path,
                sqlite_timeout=1.0,
            )
            self._deliver(job.callbacks, saved)

    @staticmethod
    def _deliver(callbacks: list[Callable[[bool], None]], saved: bool) -> None:
        def on_main() -> None:
            for callback in callbacks:
                try:
                    callback(saved)
                except Exception as exc:
                    print(f"Notebook background save callback failed: {exc}")

        try:
            if mw and getattr(mw, "taskman", None):
                mw.taskman.run_on_main(on_main)
            else:
                print("Notebook background save completed without a main-thread dispatcher")
        except Exception as exc:
            # The durable write has already completed. During process shutdown Qt
            # may no longer accept callbacks, so logging is safer than touching UI.
            print(f"Notebook could not dispatch save result: {exc}")


_background_writer = _NotebookBackgroundWriter()


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
    """Standalone window that borrows the web view from the dock.

    Two display modes:
      * windowed=False – true OS fullscreen (showFullScreen), ESC closes it.
      * windowed=True  – a normal, maximised window inside Anki with a title
        bar that can be moved/resized; ESC is NOT bound so typing stays safe.
    """

    def __init__(self, panel: "NotebookPanel", web_view: AnkiWebView,
                 parent=None, windowed: bool = False) -> None:
        super().__init__(parent)
        self.panel    = panel
        self.web_view = web_view
        self.windowed = windowed
        self.setWindowTitle(_("SynapsePro – Notebook"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(web_view)

        # ESC closes only true fullscreen (a windowed view has a close button)
        if not windowed:
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
        self.is_embedded       = False
        self.fullscreen_window: Optional[NotebookFullscreenWindow] = None
        self._current_pdf_path = ""
        self._page_ready = False
        self._flush_in_progress = False
        self._pending_tool_switch: Optional[str] = None
        self._unload_requested = False
        self._unload_callbacks: list[Callable[[bool], None]] = []
        # Store a reference to the parent dock for fullscreen toggling
        self.parent_dock: Optional[QDockWidget] = (
            parent if isinstance(parent, QDockWidget) else None
        )

    # ── Loading ───────────────────────────────

    def load_content(self):
        """Create the WebView and load current tool. Called when dock becomes visible."""
        if self.web:
            # A failed flush intentionally keeps the hidden WebView alive. Never
            # overwrite that in-memory state with an older database snapshot.
            return

        self.web = AnkiWebView(kind=AnkiWebViewKind.DEFAULT)
        self.web.set_bridge_command(self._on_bridge_cmd, self)
        self.web.loadFinished.connect(self._on_load_finished)
        self._layout.addWidget(self.web)

        self._load_tool(self.current_tool)
        self.is_initialized = True

    def unload_content(
        self, on_complete: Optional[Callable[[bool], None]] = None
    ) -> None:
        """Persist the live page, then destroy its WebView to free RAM."""
        if self.is_in_fullscreen or self.is_embedded:
            if on_complete:
                on_complete(False)
            return  # Don't unload while detached / embedded
        if on_complete:
            self._unload_callbacks.append(on_complete)
        if not self.web:
            self._finish_unload_callbacks(True)
            return
        if self._flush_in_progress:
            self._unload_requested = True
            return
        self._unload_requested = False

        web_ref = self.web

        def after_flush(saved: bool) -> None:
            if saved:
                self._destroy_web_view(web_ref)
            else:
                # Keep the hidden page alive. When the user opens the dock again,
                # load_content() returns to this exact unsaved in-memory state.
                print("Notebook: WebView kept alive because its final save failed")
            self._finish_unload_callbacks(saved)

        self._flush_current_state(after_flush)

    def _finish_unload_callbacks(self, saved: bool) -> None:
        callbacks = self._unload_callbacks
        self._unload_callbacks = []
        for callback in callbacks:
            try:
                callback(saved)
            except Exception as exc:
                print(f"Notebook unload callback failed: {exc}")

    def _on_load_finished(self, ok: bool) -> None:
        self._page_ready = bool(ok)

    def _destroy_web_view(self, web_ref: AnkiWebView) -> None:
        if self.web is not web_ref:
            return
        self._current_pdf_path = ""
        self._layout.removeWidget(web_ref)
        # AnkiWebView registers itself on gui_hooks.theme_did_change in its
        # __init__ and only deregisters in cleanup(). Without this call the
        # dead hook raises "wrapped C/C++ object of type AnkiWebView has been
        # deleted" on the next theme switch.
        try:
            web_ref.cleanup()
        except Exception as exc:
            print(f"Notebook: webview cleanup failed: {exc}")
        web_ref.deleteLater()
        self.web = None
        self.is_initialized = False
        self._page_ready = False

    @staticmethod
    def _strip_pdf_transient_flags(body: str) -> str:
        try:
            data = json.loads(body)
            if isinstance(data, dict) and isinstance(data.get("pdfs"), list):
                for entry in data["pdfs"]:
                    if isinstance(entry, dict):
                        entry.pop("_exists", None)
            return json.dumps(data)
        except Exception:
            return body

    def _queue_tool_snapshot(
        self, tool: str, body: str, callback: Callable[[bool], None]
    ) -> None:
        table = {"notebook": "notes", "todo": "todos", "pdf": "pdfs"}.get(tool)
        if table is None:
            callback(False)
            return
        if tool == "pdf":
            body = self._strip_pdf_transient_flags(body)
        try:
            # Capture the profile path now, on the main thread. A delayed write
            # therefore cannot accidentally follow mw.pm into another profile.
            database_path = db_path()
        except Exception as exc:
            print(f"Notebook could not determine save path: {exc}")
            callback(False)
            return
        _background_writer.submit(table, body, database_path, callback)

    def _notify_save_result(self, tool: str, saved: bool) -> None:
        if not self.web:
            return
        if tool == "notebook":
            callback = "onSaved" if saved else "onSaveFailed"
        elif tool == "todo":
            callback = "onTodoSaved" if saved else "onTodoSaveFailed"
        else:
            callback = "onPdfSaved" if saved else "onPdfSaveFailed"
        try:
            self.web.eval(f"if(window.{callback}) window.{callback}();")
        except Exception:
            pass

    def _flush_current_state(self, on_complete: Callable[[bool], None]) -> None:
        """Ask the page for its current snapshot and persist it before teardown.

        The snapshot is returned through runJavaScript's callback and written by
        Python before a tool switch or WebView destruction. This avoids relying on
        a last asynchronous bridge message surviving page teardown.
        """
        if not self.web:
            on_complete(True)
            return
        if self._flush_in_progress:
            return

        self._flush_in_progress = True
        web_ref = self.web
        tool = self.current_tool
        page_was_ready = self._page_ready
        completed = False
        save_attempts = 0

        def finish(saved: bool) -> None:
            nonlocal completed
            if completed:
                return
            completed = True
            self._flush_in_progress = False
            on_complete(saved)
            if self._unload_requested:
                self._unload_requested = False
                QTimer.singleShot(0, self.unload_content)

        def receive_snapshot(result) -> None:
            if self.web is not web_ref:
                finish(True)
                return
            if result is None:
                # A page still loading cannot contain user edits. Once loaded,
                # however, a missing snapshot hook is unsafe and blocks teardown.
                saved = not page_was_ready
            elif isinstance(result, str):
                persist_until_current(result)
                return
            else:
                saved = False
            finish(saved)

        def persist_until_current(snapshot: str) -> None:
            """Keep saving until no edit occurred during the background write."""
            nonlocal save_attempts
            if completed:
                return
            save_attempts += 1

            def after_background_save(saved: bool) -> None:
                if completed:
                    return
                if not saved:
                    self._notify_save_result(tool, False)
                    finish(False)
                    return
                if self.web is not web_ref:
                    finish(True)
                    return

                def verify_snapshot(latest) -> None:
                    if completed:
                        return
                    if not isinstance(latest, str):
                        finish(False)
                    elif latest == snapshot:
                        finish(True)
                    elif save_attempts >= MAX_FINAL_SAVE_ATTEMPTS:
                        # Never spin indefinitely if a page keeps changing its
                        # serialized state while we are trying to leave it. The
                        # WebView stays open, so the user can retry without loss.
                        print(
                            "Notebook final save aborted after repeated live edits"
                        )
                        finish(False)
                    else:
                        # The page remained interactive while SQLite was writing.
                        # Persist the newer state before allowing teardown/switch.
                        persist_until_current(latest)

                try:
                    web_ref.evalWithCallback(verify_js, verify_snapshot)
                except Exception as exc:
                    print(f"Notebook final save verification failed: {exc}")
                    finish(False)

            self._queue_tool_snapshot(tool, snapshot, after_background_save)

        js = (
            "(typeof window.__synapseSnapshotForUnload === 'function')"
            " ? window.__synapseSnapshotForUnload() : null"
        )
        # The unload hook is allowed to synchronize the live editor into the
        # page state. Verification must be read-only: calling the unload hook a
        # second time used to bump Notebook's updatedAt timestamp on every pass,
        # causing thousands of writes and blocking navigation until timeout.
        verify_js = (
            "(typeof window.__synapseSnapshotForVerification === 'function')"
            " ? window.__synapseSnapshotForVerification() : null"
        )
        try:
            web_ref.evalWithCallback(js, receive_snapshot)
            # A broken renderer must not leave the panel permanently locked.
            # On timeout the WebView is retained, so no data is discarded.
            QTimer.singleShot(20000, lambda: finish(False))
        except Exception as exc:
            print(f"Notebook final save request failed: {exc}")
            finish(False)

    def _apply_wide_mode(self, active: bool) -> None:
        """Toggle the widened note column on the live page (no reload)."""
        if not self.web:
            return
        action = "add" if active else "remove"
        js = f"document.body && document.body.classList.{action}('synapse-wide');"
        try:
            self.web.eval(js)
        except Exception:
            pass

    def _set_nav_toggle(self, active: bool, windowed: bool) -> None:
        """Swap the fullscreen / window button icon inside the nav bar.

        Same contract as the Mindmap tool: the page exposes
        __synapseSetFullscreen / __synapseSetWindow (see
        _build_nav_toggle_script) which swap the SVG and tooltip.
        """
        if not self.web:
            return
        titles = {
            "fullscreen_enter": _("Fullscreen"),
            "fullscreen_exit":  _("Exit Fullscreen"),
            "window_open":      _("New Window"),
            "window_exit":      _("Close Window"),
        }
        fn   = "__synapseSetWindow" if windowed else "__synapseSetFullscreen"
        flag = "true" if active else "false"
        js   = f"if(window.{fn}) {fn}({flag}, {json.dumps(titles)});"
        try:
            self.web.eval(js)
        except Exception:
            pass

    def enter_fullscreen(self) -> None:
        if not self.web or self.is_in_fullscreen or self.is_embedded:
            return
        self.is_in_fullscreen = True

        # Detach web view from dock layout
        self._layout.removeWidget(self.web)
        self.web.setParent(None)  # type: ignore[arg-type]

        # Hide the dock
        if self.parent_dock:
            self.parent_dock.hide()

        # Show in standalone OS fullscreen window
        self.fullscreen_window = NotebookFullscreenWindow(self, self.web)
        self.fullscreen_window.showFullScreen()
        # Widen the note column for the large view.
        self._apply_wide_mode(True)
        # Flip the fullscreen icon to the "exit" state (arrows pointing in).
        self._set_nav_toggle(True, windowed=False)

    def enter_window(self) -> None:
        """Embed the web view directly into Anki's main content area."""
        if not self.web or self.is_in_fullscreen or self.is_embedded:
            return

        # IMPORTANT: set the flag *before* hiding the dock. Hiding the dock
        # fires visibilityChanged, whose handler would otherwise destroy the
        # web view (RAM saving). The flag suppresses that teardown.
        self.is_embedded = True

        # Detach web view from dock layout and hide the dock.
        self._layout.removeWidget(self.web)
        self.web.setParent(None)  # type: ignore[arg-type]
        if self.parent_dock:
            self.parent_dock.hide()

        ok = embedded_window.embed(self.web, self.exit_window, _("Notebook"),
                                   show_header=False)
        if not ok:
            # Embedding failed – reattach to the dock and abort.
            self.is_embedded = False
            self._layout.addWidget(self.web)
            if self.parent_dock:
                self.parent_dock.show()
                self.parent_dock.raise_()
            return
        # Widen the note column for the large embedded view.
        self._apply_wide_mode(True)
        # Flip the window icon to the "close" state (window with a dash).
        self._set_nav_toggle(True, windowed=True)

    def exit_window(self) -> None:
        """Leave the embedded view and return the web view to the dock."""
        if not self.is_embedded:
            return
        # Revert to the narrow (sidebar) column before handing the view back.
        self._apply_wide_mode(False)
        self._set_nav_toggle(False, windowed=True)
        self.is_embedded = False
        if self.web is not None:
            self._layout.addWidget(self.web)  # reparents out of the container
        embedded_window.restore()
        if self.parent_dock:
            self.parent_dock.show()
            self.parent_dock.raise_()

    def exit_fullscreen(self, web_view_ref: AnkiWebView) -> None:
        self.is_in_fullscreen  = False
        self.fullscreen_window = None

        # Revert the widened column back to the narrow sidebar layout.
        self.web = web_view_ref
        self._apply_wide_mode(False)
        self._set_nav_toggle(False, windowed=False)

        # Reattach web view to dock panel
        self._layout.addWidget(web_view_ref)

        # Show the dock again
        if self.parent_dock:
            self.parent_dock.show()
            self.parent_dock.raise_()

    def _load_tool(self, tool_name: str) -> None:
        """Read the tool's HTML file, inject nav bar, and display it."""
        if not self.web:
            return
        self._page_ready = False
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
        html = _apply_night_mode(html)
        html = _inject_nav(html, tool_name,
                           fs_active=self.is_in_fullscreen,
                           win_active=self.is_embedded)
        if self.is_embedded or self.is_in_fullscreen:
            html = _add_wide_class(html)

        # ── Preload initial data to avoid a visual flash ──────────────
        # Instead of loading the page with default state and then calling
        # loadContent() 150 ms later (which causes a visible layout shift),
        # we embed the data directly so the page can initialise correctly
        # on first render.
        if tool_name == "notebook":
            preload_data = load_latest_note()
            preload_js   = _json_for_script(preload_data)
            preload_tag  = f'<script id="synapse-preload">window.__SYNAPSE_PRELOAD__={preload_js};</script>'
            # Use a lambda replacement so that JSON backslash-escapes (e.g. \u, \n)
            # inside preload_tag are never interpreted as regex replacement tokens.
            html = re.sub(r'</head>', lambda m: preload_tag + m.group(0), html,
                          count=1, flags=re.IGNORECASE)
        elif tool_name == "todo":
            preload_data = load_latest_todos()
            preload_js   = _json_for_script(preload_data)
            preload_tag  = (
                f'<script id="synapse-preload">'
                f'window.__SYNAPSE_TODO_PRELOAD__={preload_js};'
                f'</script>'
            )
            html = re.sub(r'</head>', lambda m: preload_tag + m.group(0), html,
                          count=1, flags=re.IGNORECASE)
        elif tool_name == "pdf":
            preload_data = load_pdf_list_enriched()
            preload_js   = _json_for_script(preload_data)
            deck_names_js = _json_for_script(_pdf_deck_names(), ensure_ascii=False)

            # Try to use locally cached PDF.js (offline support + avoids cross-origin
            # worker restriction that can occur with setHtml() pages).
            pdfjs_main_tag, worker_json = _pdfjs_local_scripts()
            _CDN_TAG = '<script id="synapse-pdfjs-placeholder"></script>'
            # Never execute a network-fetched library in this privileged local
            # WebView. Release packages must contain the pinned local files.
            html = html.replace(_CDN_TAG, pdfjs_main_tag, 1)
            if pdfjs_main_tag:
                preload_tag = (
                    f'<script id="synapse-preload">'
                    f'window.__SYNAPSE_PDF_PRELOAD__={preload_js};'
                    f'window.__SYNAPSE_DECKS__={deck_names_js};'
                    f'window.__PDFJS_WORKER_CODE__={worker_json};'
                    f'</script>'
                )
            else:
                preload_tag = (
                    f'<script id="synapse-preload">'
                    f'window.__SYNAPSE_PDF_PRELOAD__={preload_js};'
                    f'window.__SYNAPSE_DECKS__={deck_names_js};'
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
                if tool == self.current_tool:
                    return
                # Keep the latest click while a final save is running. Previously
                # a second click was silently discarded, making tabs feel broken
                # on slower computers.
                self._pending_tool_switch = tool
                if not self._flush_in_progress:
                    self._flush_current_state(self._finish_tool_switch)
            return

        # ── Fullscreen ────────────────────────
        if payload == "fullscreen":
            if self.is_in_fullscreen:
                if self.fullscreen_window:
                    self.fullscreen_window.close()  # triggers exit_fullscreen via closeEvent
            else:
                self.enter_fullscreen()
            return

        # ── Embedded view (inside the Anki main window) ──
        if payload == "window":
            if self.is_embedded:
                self.exit_window()
            elif not self.is_in_fullscreen:
                self.enter_window()
            return

        # ── Notebook commands ──────────────────
        if payload == "load":
            self.reload_from_db()
        elif payload.startswith("save:"):
            body = payload[len("save:"):]
            self._queue_tool_snapshot(
                "notebook", body,
                lambda saved: self._notify_save_result("notebook", saved),
            )
        elif payload == "export":
            self._flush_current_state(
                lambda saved: export_data() if saved else None
            )

        # ── Todo commands ──────────────────────
        elif payload == "todo:load":
            self._reload_todos()
        elif payload.startswith("todo:save:"):
            body = payload[len("todo:save:"):]
            self._queue_tool_snapshot(
                "todo", body,
                lambda saved: self._notify_save_result("todo", saved),
            )

        # ── PDF commands ───────────────────────
        elif payload == "pdf:load":
            self._reload_pdfs()
        elif payload.startswith("pdf:save:"):
            body = payload[len("pdf:save:"):]
            self._queue_tool_snapshot(
                "pdf", body,
                lambda saved: self._notify_save_result("pdf", saved),
            )
        elif payload == "pdf:add":
            self._add_pdf_dialog()
        elif payload.startswith("pdf:open:"):
            file_path = payload[len("pdf:open:"):]
            _open_file_externally(file_path)
        elif payload.startswith("pdf:render:"):
            file_path = payload[len("pdf:render:"):]
            self._render_pdf_inline(file_path)
        elif payload.startswith("pdf:copy-selection:"):
            body = payload[len("pdf:copy-selection:"):]
            self._copy_pdf_selection(body)
        elif payload.startswith("pdf:create-card:"):
            body = payload[len("pdf:create-card:"):]
            self._open_pdf_card_draft(body)
        elif payload.startswith("pdf:create-batch:"):
            body = payload[len("pdf:create-batch:"):]
            self._create_pdf_card_batch(body)
        elif payload == "pdf:back":
            self._current_pdf_path = ""
            self._load_tool("pdf")
        elif payload.startswith("pdf:relink:"):
            pdf_id = payload[len("pdf:relink:"):]
            self._relink_pdf_dialog(pdf_id)

    def _finish_tool_switch(self, saved: bool) -> None:
        """Open the latest requested tool after the current page is durable."""
        target = self._pending_tool_switch
        self._pending_tool_switch = None
        if saved and target and target != self.current_tool:
            self._load_tool(target)

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
        if file_size_mb > MAX_PDF_HARD_MB:
            showInfo(_(
                "This PDF is {size:.1f} MB and is too large for the inline viewer. "
                "Open it in the system PDF viewer instead."
            ).format(size=file_size_mb), parent=self)
            return
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

    def _notify_pdf_action(self, callback: str, success: bool, message: str) -> None:
        """Return a PDF action result to the currently visible WebView."""
        if not self.web:
            return
        callback_json = json.dumps(callback)
        message_json = json.dumps(message, ensure_ascii=False)
        try:
            self.web.eval(
                f"if(typeof window[{callback_json}]==='function') "
                f"window[{callback_json}]({json.dumps(success)}, {message_json});"
            )
        except Exception:
            pass

    @staticmethod
    def _decode_pdf_action_payload(body: str) -> dict:
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("PDF action payload must be an object")
        return data

    def _copy_pdf_selection(self, body: str) -> None:
        """Copy selected PDF text through Qt's cross-platform clipboard."""
        try:
            data = self._decode_pdf_action_payload(body)
            text = data.get("text", "")
            if not isinstance(text, str):
                raise ValueError("Selected PDF text must be a string")
            text = text.strip()
            if not text:
                raise ValueError("Selected PDF text is empty")
            if len(text) > MAX_PDF_COPY_CHARS:
                self._notify_pdf_action(
                    "onPdfSelectionCopied",
                    False,
                    _("The selected text is too long to copy at once."),
                )
                return
            QApplication.clipboard().setText(text)
        except Exception as exc:
            print(f"Notebook PDF copy failed: {exc}")
            self._notify_pdf_action(
                "onPdfSelectionCopied",
                False,
                _("Could not copy the selected text."),
            )
            return

        self._notify_pdf_action(
            "onPdfSelectionCopied", True, _("Selected text copied")
        )

    @staticmethod
    def _pdf_text_to_html(text: str) -> str:
        """Convert untrusted plain PDF text into safe Anki field HTML."""
        normalized = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
        return html.escape(normalized).replace("\n", "<br>")

    def _open_pdf_card_draft(self, body: str) -> None:
        """Open Anki's Add Cards window with a safe, unsaved PDF draft."""
        callback = "onPdfCardDraftOpened"
        try:
            data = self._decode_pdf_action_payload(body)
            front = data.get("front", "")
            back = data.get("back", "")
            if not isinstance(front, str) or not isinstance(back, str):
                raise ValueError("PDF card fields must be strings")
            front = front.strip()
            back = back.strip()
            if not front:
                self._notify_pdf_action(
                    callback, False, _("Select text for the card front first.")
                )
                return
            if len(front) + len(back) > MAX_PDF_CARD_CHARS:
                self._notify_pdf_action(
                    callback,
                    False,
                    _("The selected text is too long for a card."),
                )
                return

            pages_raw = data.get("pages", [])
            pages: list[int] = []
            if isinstance(pages_raw, list):
                for value in pages_raw:
                    try:
                        page = int(value)
                    except (TypeError, ValueError):
                        continue
                    if 1 <= page <= 1_000_000 and page not in pages:
                        pages.append(page)
            pages.sort()

            # Opening an existing Add Cards window is safe: its reopen() method
            # leaves non-empty fields untouched. Check again before set_note(),
            # because set_note() itself would replace the current draft.
            add_cards = aqt.dialogs.open("AddCards", mw)
            editor = getattr(add_cards, "editor", None)
            existing_note = getattr(editor, "note", None) if editor else None
            existing_tags = getattr(existing_note, "tags", []) if existing_note else []
            if editor is None or not editor.fieldsAreBlank() or bool(existing_tags):
                self._notify_pdf_action(
                    callback,
                    False,
                    _(
                        "The Add Cards window already contains an unfinished note. "
                        "Finish or clear it, then try again."
                    ),
                )
                return

            # Respect the notetype and deck already selected in a blank Add
            # Cards window. On a newly opened window these are Anki's defaults.
            notetype = existing_note.note_type() if existing_note else None
            deck_chooser = getattr(add_cards, "deck_chooser", None)
            deck_id = getattr(deck_chooser, "selected_deck_id", None)
            if not notetype or deck_id is None:
                reviewer = getattr(mw, "reviewer", None)
                defaults = mw.col.defaults_for_adding(
                    current_review_card=getattr(reviewer, "card", None)
                )
                if not notetype:
                    notetype = mw.col.models.get(defaults.notetype_id)
                if deck_id is None:
                    deck_id = defaults.deck_id
            if not notetype:
                raise RuntimeError("Anki did not provide a default note type")
            note = mw.col.new_note(notetype)
            if not note.fields:
                raise RuntimeError("The default note type has no fields")

            filename = os.path.basename(self._current_pdf_path) or _("PDF")
            source = "{}: {}".format(_("Source"), filename)
            if pages:
                page_label = _("Page") if len(pages) == 1 else _("Pages")
                source += f" — {page_label} {', '.join(str(page) for page in pages)}"
            source_html = (
                '<div style="margin-top:12px;color:#777;font-size:0.85em">'
                f"{html.escape(source)}</div>"
            )

            front_html = self._pdf_text_to_html(front)
            back_html = self._pdf_text_to_html(back)
            note.fields[0] = front_html
            if len(note.fields) >= 2:
                note.fields[1] = back_html + source_html
            else:
                extra = back_html + source_html
                if extra:
                    note.fields[0] += "<hr>" + extra

            add_cards.set_note(note, deck_id)
            add_cards.show()
            add_cards.raise_()
            add_cards.activateWindow()
        except Exception as exc:
            print(f"Notebook PDF card draft failed: {exc}")
            self._notify_pdf_action(
                callback,
                False,
                _("Could not open the card draft in Anki."),
            )
            return

        self._notify_pdf_action(
            callback, True, _("Card draft opened in Anki")
        )

    def _create_pdf_card_batch(self, body: str) -> None:
        """Validate and create one undoable deck/card batch from the PDF UI."""
        callback = "onPdfCardBatchCreated"
        try:
            data = self._decode_pdf_action_payload(body)
            deck_name = data.get("deckName", "")
            raw_cards = data.get("cards", [])
            if not isinstance(deck_name, str) or not isinstance(raw_cards, list):
                raise ValueError("Invalid PDF card batch payload")
            deck_name = deck_name.strip()
            if (
                not deck_name
                or len(deck_name) > 250
                or any(char in deck_name for char in ("\x00", "\n", "\r"))
            ):
                self._notify_pdf_action(
                    callback, False, _("Choose or enter a valid deck name.")
                )
                return
            if not raw_cards:
                self._notify_pdf_action(
                    callback, False, _("Add at least one card first.")
                )
                return
            if len(raw_cards) > MAX_PDF_BATCH_CARDS:
                self._notify_pdf_action(
                    callback,
                    False,
                    _("A PDF Card Creator session can contain at most {count} cards.").format(
                        count=MAX_PDF_BATCH_CARDS
                    ),
                )
                return

            cards: list[dict] = []
            total_chars = 0
            for raw_card in raw_cards:
                if not isinstance(raw_card, dict):
                    raise ValueError("PDF card entry must be an object")
                front = raw_card.get("front", "")
                back = raw_card.get("back", "")
                if not isinstance(front, str) or not isinstance(back, str):
                    raise ValueError("PDF card fields must be strings")
                front = front.strip()
                back = back.strip()
                if not front:
                    self._notify_pdf_action(
                        callback, False, _("Every card needs a front side.")
                    )
                    return
                if len(front) + len(back) > MAX_PDF_CARD_CHARS:
                    self._notify_pdf_action(
                        callback, False, _("One of the PDF cards is too long.")
                    )
                    return
                total_chars += len(front) + len(back)

                pages: list[int] = []
                pages_raw = raw_card.get("pages", [])
                if isinstance(pages_raw, list):
                    for value in pages_raw:
                        try:
                            page = int(value)
                        except (TypeError, ValueError):
                            continue
                        if 1 <= page <= 1_000_000 and page not in pages:
                            pages.append(page)
                pages.sort()
                cards.append(
                    {
                        "front": front,
                        "back": back,
                        "pages": pages,
                        "include_source": raw_card.get("includeSource") is True,
                    }
                )

            if total_chars > MAX_PDF_BATCH_CHARS:
                self._notify_pdf_action(
                    callback,
                    False,
                    _("This Card Creator session contains too much text."),
                )
                return

            reviewer = getattr(mw, "reviewer", None)
            defaults = mw.col.defaults_for_adding(
                current_review_card=getattr(reviewer, "card", None)
            )
            preferred_notetype_id = defaults.notetype_id
            source_filename = os.path.basename(self._current_pdf_path) or _("PDF")
            source_label = _("Source")
            page_label = _("Page")
            pages_label = _("Pages")
            undo_label = _("Create PDF cards")
            success_message = _("Created {count} cards in “{deck}”.").format(
                count=len(cards), deck=deck_name
            )
        except Exception as exc:
            print(f"Notebook PDF card batch validation failed: {exc}")
            self._notify_pdf_action(
                callback, False, _("Could not create the PDF cards.")
            )
            return

        def create_batch(col):
            notetype = col.models.get(preferred_notetype_id)

            def usable(candidate) -> bool:
                return bool(
                    candidate
                    and candidate.get("type", MODEL_STD) == MODEL_STD
                    and len(candidate.get("flds", [])) >= 2
                )

            if not usable(notetype):
                notetype = next(
                    (candidate for candidate in col.models.all() if usable(candidate)),
                    None,
                )
            if not notetype:
                raise RuntimeError("No standard Anki note type with two fields is available")

            notes = []
            for card in cards:
                note = col.new_note(notetype)
                if len(note.fields) < 2:
                    raise RuntimeError("The selected Anki note type has fewer than two fields")
                note.fields[0] = NotebookPanel._pdf_text_to_html(card["front"])
                back_html = NotebookPanel._pdf_text_to_html(card["back"])
                if card["include_source"]:
                    source = f"{source_label}: {source_filename}"
                    pages = card["pages"]
                    if pages:
                        label = page_label if len(pages) == 1 else pages_label
                        source += f" — {label} {', '.join(str(page) for page in pages)}"
                    back_html += (
                        '<div style="margin-top:10px;color:#888;font-size:0.72em;'
                        'line-height:1.35;border-top:1px solid rgba(128,128,128,.2);'
                        'padding-top:5px">'
                        f"{html.escape(source)}</div>"
                    )
                note.fields[1] = back_html
                notes.append(note)

            undo_entry = col.add_custom_undo_entry(undo_label)
            try:
                deck_result = col.decks.add_normal_deck_with_name(deck_name)
                deck_id = deck_result.id
                changes = col.add_notes(
                    [AddNoteRequest(note=note, deck_id=deck_id) for note in notes]
                )
            except Exception:
                # Group and revert any operations that completed before the
                # failure (for example, a newly-created empty deck).
                try:
                    col.merge_undo_entries(undo_entry)
                    col.undo()
                except Exception as rollback_exc:
                    print(f"Notebook PDF card batch rollback failed: {rollback_exc}")
                raise

            try:
                return col.merge_undo_entries(undo_entry)
            except Exception as merge_exc:
                # The cards already exist at this point. Report success instead
                # of encouraging a retry that would create duplicates; only the
                # convenience of a single undo step is lost.
                print(f"Notebook PDF card batch undo grouping failed: {merge_exc}")
                return changes

        def on_success(_changes) -> None:
            self._notify_pdf_action(callback, True, success_message)

        def on_failure(exc: Exception) -> None:
            print(f"Notebook PDF card batch failed: {exc}")
            self._notify_pdf_action(
                callback, False, _("Could not create the PDF cards.")
            )

        CollectionOp(parent=mw, op=create_batch).success(on_success).failure(
            on_failure
        ).run_in_background(initiator=self)


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
    # Verify the pinned offline dependency; never download executable JS at runtime.
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
    if not _dock:
        return

    dock_ref = _dock
    # Detach the global immediately. If a new profile opens while the old
    # profile's final background write is finishing, it must get a fresh dock
    # rather than reusing a panel bound to the previous profile.
    _dock = None
    panel = dock_ref.widget()

    def dispose(saved: bool) -> None:
        global _dock
        if not saved:
            return
        try:
            mw.removeDockWidget(dock_ref)
        except Exception:
            pass
        dock_ref.deleteLater()

    if isinstance(panel, NotebookPanel):
        if panel.fullscreen_window:
            panel.fullscreen_window.close()
        if panel.is_embedded:
            panel.exit_window()
        panel.unload_content(dispose)
    else:
        dispose(True)
