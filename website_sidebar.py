# -*- coding: utf-8 -*-

import json
import html
import traceback
from functools import partial
from typing import Optional, List, Dict, Tuple
import os
import urllib.parse

# --- Local Imports ---
from . import constants

try:
    from .locales import _
except ImportError:
    def _(text):  # type: ignore
        return text

# --- PyQt Imports ---
_qt_available = False
try:
    from aqt.qt import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                        QInputDialog, QDockWidget, QSizePolicy, QMessageBox,
                        QMenu, QAction, QIcon, QPixmap, QPainter, QUrl, QTimer,
                        QSize, Qt, QByteArray)
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings
    WebAction = QWebEnginePage.WebAction
    print("Website Sidebar: Using Qt6 components")
    _qt_available = True
except ImportError as e:
    print(f"Website Sidebar Error: Could not import necessary PyQt components. {e}")
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton = object, object, object, object
    QInputDialog, QDockWidget, QSizePolicy, QMessageBox = object, object, object, object
    QUrl, QTimer, QSize, Qt = object, object, object, None
    QByteArray = object; QIcon = object; QPixmap = object; QPainter = object
    QWebEngineView, QWebEngineProfile, QWebEnginePage, QWebEngineSettings = object, object, object, object
    QAction = object; WebAction = object; QMenu = object

# QtSvg is optional – used only to render crisp toolbar icons. A failure here
# must never break the rest of the module, so it gets its own guarded import.
_svg_available = False
try:
    from PyQt6.QtSvg import QSvgRenderer
    _svg_available = True
except Exception as _e_svg:
    QSvgRenderer = object  # type: ignore
    print(f"Website Sidebar: QtSvg unavailable, using glyph fallback. {_e_svg}")


# --- Anki Imports ---
try:
    from aqt import mw, gui_hooks
    from aqt.utils import showInfo, tooltip, qconnect, showWarning
except ImportError:
    print("Website Sidebar Error: Could not import aqt modules.")
    mw = None; showInfo = lambda *a, **k: print("Info:", a); tooltip = lambda *a, **k: print("Tooltip:", a)
    qconnect = lambda *a: None; showWarning = lambda *a, **k: print("Warning:", a)
    gui_hooks = None


# --- Button Stylesheets ---
# Moderner Look: Kein Rahmen, leichter Schlagschatten (via border-bottom) und Klick-Animation

def _toolbar_palette() -> dict:
    """Clean grey toolbar palette matching the Notebook nav bar (theme-aware)."""
    night = False
    try:
        night = bool(mw and hasattr(mw, 'pm') and mw.pm.night_mode())
    except Exception:
        night = False
    if night:
        return {
            "bar": "#2c2c2e", "line": "rgba(255,255,255,0.12)",
            "text": "#e6e6e6", "hover": "#3a3a3c", "pressed": "#48484a",
            "muted": "#6a6a6a", "select_bg": "#3a3a3c",
        }
    return {
        "bar": "#f2f2f2", "line": "rgba(0,0,0,0.10)",
        "text": "#37352f", "hover": "#e6e6e6", "pressed": "#dcdcdc",
        "muted": "#b3b3b3", "select_bg": "#ffffff",
    }


def _get_blue_button_style() -> str:
    """Minimal text button (transparent on the grey bar, subtle hover)."""
    c = _toolbar_palette()
    return f"""
QPushButton {{
    background-color: transparent;
    color: {c['text']};
    border: none;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 13px;
}}
QPushButton:hover {{ background-color: {c['hover']}; }}
QPushButton:pressed {{ background-color: {c['pressed']}; }}
"""


def _get_icon_button_style() -> str:
    """Minimal square-ish icon button for nav glyphs (← → ↻ ⧉ +)."""
    c = _toolbar_palette()
    return f"""
QPushButton {{
    background-color: transparent;
    color: {c['text']};
    border: none;
    border-radius: 6px;
    padding: 4px 9px;
    font-size: 15px;
}}
QPushButton:hover {{ background-color: {c['hover']}; }}
QPushButton:pressed {{ background-color: {c['pressed']}; }}
QPushButton:disabled {{ color: {c['muted']}; }}
"""


def _get_raised_text_button_style() -> str:
    """Clean 'card' text button: white/elevated surface with a soft border.

    Mirrors the Mindmap 'New' button so saved sites / Home clearly read as
    clickable buttons while staying minimal."""
    c = _toolbar_palette()
    return f"""
QPushButton {{
    background-color: {c['select_bg']};
    color: {c['text']};
    border: 1px solid {c['line']};
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton:hover {{ background-color: {c['hover']}; }}
QPushButton:pressed {{ background-color: {c['pressed']}; }}
QPushButton:disabled {{ color: {c['muted']}; }}
"""


def _get_raised_icon_button_style() -> str:
    """Clean 'card' icon button (white/elevated) for the add (+) button."""
    c = _toolbar_palette()
    return f"""
QPushButton {{
    background-color: {c['select_bg']};
    color: {c['text']};
    border: 1px solid {c['line']};
    border-radius: 6px;
    padding: 4px 11px;
    font-size: 15px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: {c['hover']}; }}
QPushButton:pressed {{ background-color: {c['pressed']}; }}
QPushButton:disabled {{ color: {c['muted']}; }}
"""


def _get_delete_button_style() -> str:
    """Clean 'card' icon button with a red hover, for the site delete (-) button."""
    c = _toolbar_palette()
    return f"""
QPushButton {{
    background-color: {c['select_bg']};
    color: {c['text']};
    border: 1px solid {c['line']};
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 15px;
}}
QPushButton:hover {{ background-color: {c['hover']}; color: #e5484d; border-color: #e5484d; }}
QPushButton:pressed {{ background-color: {c['pressed']}; }}
"""


# Backwards-compatible alias (still referenced in a few places).
WHITE_BUTTON_STYLE = _get_delete_button_style()


# Same "open in main window" glyph used by the Mindmap / Notebook nav bars:
# a window frame (rectangle with a title-bar line).
_WINDOW_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 24 24" '
    'fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="3" y="3" width="18" height="18" rx="2"></rect>'
    '<line x1="3" y1="9" x2="21" y2="9"></line>'
    '</svg>'
)

# Variant shown while the embedded main-window view is active: the same
# window frame with a small dash inside ("close window" state, identical to
# the Mindmap / Notebook nav bars).
_WINDOW_CLOSE_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 24 24" '
    'fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="3" y="3" width="18" height="18" rx="2"></rect>'
    '<line x1="3" y1="9" x2="21" y2="9"></line>'
    '<line x1="9" y1="15" x2="15" y2="15"></line>'
    '</svg>'
)


def _make_window_icon(size: int = 16, active: bool = False):
    """Render the window-frame SVG into a crisp QIcon (theme-aware). None on failure.

    ``active`` selects the "close window" variant (frame with a dash) shown
    while the embedded main-window view is open.
    """
    if not _svg_available or QIcon is object or QPixmap is object or QPainter is object:
        return None
    try:
        color = _toolbar_palette()["text"]
        scale = 2  # render at 2x for retina crispness
        template = _WINDOW_CLOSE_ICON_SVG if active else _WINDOW_ICON_SVG
        svg = template.format(s=size, c=color)
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        pm = QPixmap(QSize(size * scale, size * scale))
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        renderer.render(painter)
        painter.end()
        try:
            pm.setDevicePixelRatio(float(scale))
        except Exception:
            pass
        return QIcon(pm)
    except Exception as e:
        print(f"WS Warn: could not build window icon: {e}")
        return None


def _apply_window_icon(btn, active: bool = False) -> None:
    """Put the window-frame icon on ``btn`` (falls back to the ⧉ glyph).

    ``active`` shows the "close window" variant while the embedded view is on.
    """
    if btn is None:
        return
    icon = _make_window_icon(16, active=active)
    if icon is not None:
        try:
            btn.setText("")
            btn.setIcon(icon)
            btn.setIconSize(QSize(16, 16))
            return
        except Exception:
            pass
    try:
        btn.setText("⧉")  # ⧉ fallback glyph
    except Exception:
        pass

def _install_dark_scrollbar_script(profile) -> None:
    """Give pages on synapse-pro.de dark scrollbars.

    The hosted browser home page is dark-designed, but its scrollbar renders
    light because the page never sets ``color-scheme: dark``. A tiny injected
    script fixes that — scoped strictly to the synapse-pro.de domain so no
    other website is touched.
    """
    try:
        from PyQt6.QtWebEngineCore import QWebEngineScript
        js = (
            "(function(){try{"
            "if(!/(^|\\.)synapse-pro\\.de$/.test(location.hostname)) return;"
            # Only in dark mode — Anki propagates its theme to the webview via
            # prefers-color-scheme, so light mode keeps the light scrollbar.
            "if(!(window.matchMedia"
            " && matchMedia('(prefers-color-scheme: dark)').matches)) return;"
            "if(document.getElementById('sp-dark-scroll')) return;"
            "var s=document.createElement('style');"
            "s.id='sp-dark-scroll';"
            "s.textContent=':root{color-scheme:dark;}';"
            "(document.head||document.documentElement).appendChild(s);"
            "}catch(e){}})();"
        )
        script = QWebEngineScript()
        script.setName("sp_dark_scrollbars")
        script.setSourceCode(js)
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        script.setWorldId(QWebEngineScript.ScriptWorldId.ApplicationWorld)
        script.setRunsOnSubFrames(False)
        # Avoid duplicates when the dock is torn down and recreated.
        try:
            for old in profile.scripts().find("sp_dark_scrollbars"):
                profile.scripts().remove(old)
        except Exception:
            pass
        profile.scripts().insert(script)
    except Exception as e:
        print(f"WS Warn: could not install scrollbar script: {e}")


# --- Module Globals ---
sidebar_dock: Optional[QDockWidget] = None
sidebar_webview: Optional[QWebEngineView] = None
website_profile: Optional[QWebEngineProfile] = None
button_container_layout: Optional[QHBoxLayout] = None
nav_button_layout: Optional[QHBoxLayout] = None
add_button_widget: Optional[QPushButton] = None
home_button_widget: Optional[QPushButton] = None
back_button: Optional[QPushButton] = None
forward_button: Optional[QPushButton] = None
refresh_button: Optional[QPushButton] = None
window_button: Optional[QPushButton] = None
custom_button_containers: List[QWidget] = []

# Embedded view (inside the Anki main window) that borrows the dock content.
website_main_layout: Optional[QVBoxLayout] = None
website_window = None  # truthy marker while an embedded view is active
website_embedded_content: Optional[QWidget] = None  # the dock body while embedded

# --- Configuration Management ---
def get_default_sites_if_empty() -> List[Dict[str, str]]:
    """Returns Notion as a default suggestion if no sites are configured."""
    return [
        {"name": "YouTube", "url": "https://www.youtube.com/"}
    ]


def _website_state_path() -> Optional[str]:
    try:
        root = mw.pm.profileFolder() if mw and mw.pm else None
        if not root:
            return None
        folder = os.path.join(root, "SynapsePro_Data")
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, "website_state.json")
    except Exception:
        return None


def _load_website_state() -> Dict:
    path = _website_state_path()
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                value = json.load(handle)
            return value if isinstance(value, dict) else {}
        except Exception as exc:
            print(f"WS Warn: Could not read local website state: {exc}")

    # Migrate older collection-synced browser metadata into profile-local data.
    state: Dict = {}
    if mw and mw.col:
        try:
            raw_sites = mw.col.get_config(constants.CONFIG_KEY_CUSTOM_SITES)
            if isinstance(raw_sites, str):
                parsed = json.loads(raw_sites)
                if isinstance(parsed, list):
                    state["custom_sites"] = parsed
            raw_url = mw.col.get_config(constants.CONFIG_KEY_LAST_OPENED_URL)
            if isinstance(raw_url, str):
                state["last_url"] = raw_url
            for key in (constants.CONFIG_KEY_CUSTOM_SITES,
                        constants.CONFIG_KEY_LAST_OPENED_URL):
                remover = getattr(mw.col, "remove_config", None)
                if callable(remover): remover(key)
                else: mw.col.set_config(key, None)
        except Exception as exc:
            print(f"WS Warn: Could not migrate website state: {exc}")
    _save_website_state(state)
    return state


def _save_website_state(state: Dict) -> None:
    path = _website_state_path()
    if not path:
        return
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception as exc:
        print(f"WS Warn: Could not save local website state: {exc}")
        try:
            if os.path.exists(tmp): os.remove(tmp)
        except OSError: pass

def load_custom_sites() -> List[Dict[str, str]]:
    sites = _load_website_state().get("custom_sites")
    if isinstance(sites, list):
        clean = [
            {"name": str(site.get("name", ""))[:80], "url": str(site.get("url", ""))[:8192]}
            for site in sites if isinstance(site, dict) and site.get("name") and site.get("url")
        ]
        if clean:
            return clean[:constants.MAX_CUSTOM_SITES]
    return get_default_sites_if_empty()


def save_custom_sites(sites: List[Dict[str, str]]):
    if len(sites) > constants.MAX_CUSTOM_SITES: sites = sites[:constants.MAX_CUSTOM_SITES]
    state = _load_website_state()
    state["custom_sites"] = sites
    _save_website_state(state)

def save_last_opened_url(url: str):
    if not isinstance(url, str) or len(url) > 8192:
        return
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return
    state = _load_website_state()
    state["last_url"] = url
    _save_website_state(state)

def load_last_opened_url() -> Optional[str]:
    value = _load_website_state().get("last_url")
    return value if isinstance(value, str) and len(value) <= 8192 else None


# --- UI Actions ---
def open_add_site_dialog():
    if not mw or QInputDialog is object or not _qt_available: return
    current_sites = load_custom_sites()
    if len(current_sites) >= constants.MAX_CUSTOM_SITES:
        showWarning(_("Limit of {} custom sites reached.").format(constants.MAX_CUSTOM_SITES)); return

    new_name, ok_name = QInputDialog.getText(mw, _("Add Website"), _("Name for the new button:"), text="")
    if not ok_name or not new_name.strip(): return
    new_name = new_name.strip()

    new_url, ok_url = QInputDialog.getText(mw, _("Add Website"), _("URL for '{}':").format(new_name), text="https://")
    if not ok_url or not new_url.strip(): return
    new_url = new_url.strip()

    if not new_url.startswith("http://") and not new_url.startswith("https://"):
        new_url = "https://" + new_url
        tooltip(_("URL automatically prefixed with https://"))

    if "." not in new_url or "://" not in new_url:
        showWarning(_("URL '{}' seems invalid.").format(new_url)); return

    current_sites.append({"name": new_name, "url": new_url})
    save_custom_sites(current_sites)
    tooltip(_("Site '{}' added.").format(new_name))
    rebuild_custom_buttons_ui()

def delete_custom_site(index_to_delete: int):
    current_sites = load_custom_sites()
    if 0 <= index_to_delete < len(current_sites):
        deleted_site = current_sites.pop(index_to_delete)
        save_custom_sites(current_sites)
        tooltip(_("Site '{}' removed.").format(deleted_site.get('name')))
        rebuild_custom_buttons_ui()
    else:
        showWarning(_("Could not delete site: Invalid index."))

def load_url_in_webview(webview: Optional[QWebEngineView], url_str: str):
    if not webview or QWebEngineView is object or QUrl is object or not _qt_available: return
    url = QUrl.fromUserInput(url_str)
    if url.isValid() and url.scheme() in ["http", "https"]:
        webview.setUrl(url)
    else:
        safe_url = html.escape(str(url_str), quote=True)
        error_html = _("""
        <body style='font-family: sans-serif; padding: 20px; color: #333; background-color: #f9f9f9;'>
            <h2 style='color: #d32f2f;'>Invalid URL</h2>
            <p>The URL you tried to open seems to be invalid or is not a standard web URL (http/https).</p>
            <p>Attempted URL: <code>{url_str}</code></p>
        </body>""").format(url_str=safe_url)
        webview.setHtml(error_html)

# --- UI Construction Helpers ---
def create_button_pair(name: str, url: str, index: int) -> Optional[QWidget]:
    if QWidget is object or QHBoxLayout is object or QPushButton is object or QSizePolicy is object or not sidebar_webview or not _qt_available:
        return None
    button_pair_widget = QWidget()
    pair_layout = QHBoxLayout(button_pair_widget)
    pair_layout.setContentsMargins(0, 0, 0, 0)
    pair_layout.setSpacing(2)

    site_button = QPushButton(name)
    site_button.setStyleSheet(_get_raised_text_button_style())
    site_button.setToolTip(_("Open: {}").format(url))
    site_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    delete_button = QPushButton("-")
    delete_button.setObjectName("DeleteButton")
    delete_button.setStyleSheet(_get_delete_button_style())
    delete_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    delete_button.setToolTip(_("Remove '{}'").format(name))

    if qconnect:
        action = partial(load_url_in_webview, webview=sidebar_webview, url_str=url)
        qconnect(site_button.clicked, action)
        delete_action = partial(delete_custom_site, index_to_delete=index)
        qconnect(delete_button.clicked, delete_action)
    else:
        site_button.setEnabled(False)
        delete_button.setEnabled(False)

    pair_layout.addWidget(site_button)
    pair_layout.addWidget(delete_button)
    return button_pair_widget

def rebuild_custom_buttons_ui():
    global button_container_layout, custom_button_containers, add_button_widget
    if not button_container_layout or QHBoxLayout is object or QWidget is object or QPushButton is object or not _qt_available:
        return

    for container in custom_button_containers:
        button_container_layout.removeWidget(container)
        container.deleteLater()
    custom_button_containers.clear()

    custom_sites = load_custom_sites()

    for i, site_info in enumerate(custom_sites):
        pair_widget = create_button_pair(site_info['name'], site_info['url'], index=i)
        if pair_widget:
            button_container_layout.addWidget(pair_widget)
            custom_button_containers.append(pair_widget)

    if add_button_widget:
        can_add_more = len(custom_sites) < constants.MAX_CUSTOM_SITES
        add_button_widget.setVisible(can_add_more)
        add_button_widget.setEnabled(can_add_more)
        add_button_widget.setToolTip(_("Add new website") if can_add_more else _("Maximum {} custom sites reached").format(constants.MAX_CUSTOM_SITES))


# --- Main Dock Creation ---
def create_website_dock() -> Optional[QDockWidget]:
    global sidebar_dock, sidebar_webview, website_profile, button_container_layout, add_button_widget
    global home_button_widget
    global back_button, forward_button, refresh_button, nav_button_layout
    global custom_button_containers
    global website_main_layout, window_button

    if not _qt_available or QDockWidget is object or QWidget is object or QVBoxLayout is object or QHBoxLayout is object or QWebEngineView is object or QWebEngineProfile is object or QPushButton is object or mw is None:
        print("WS Error: Essential Qt/Anki components missing for dock creation.")
        return None

    existing_dock = mw.findChild(QDockWidget, constants.WEBSITE_DOCK_OBJECT_NAME)
    if existing_dock:
        sidebar_dock = existing_dock
        found_webview = sidebar_dock.findChild(QWebEngineView)
        if found_webview and isinstance(found_webview, QWebEngineView):
             sidebar_webview = found_webview
             if sidebar_webview.page() and sidebar_webview.page().profile():
                 current_profile = sidebar_webview.page().profile()
                 if not website_profile or website_profile != current_profile:
                     website_profile = current_profile
             if qconnect and not hasattr(sidebar_webview, '_urlChangedConnected_ws'):
                 qconnect(sidebar_webview.urlChanged, on_webview_url_changed)
                 sidebar_webview._urlChangedConnected_ws = True
        
        rebuild_custom_buttons_ui()
        print(f"WS Info: Re-using existing dock '{constants.WEBSITE_DOCK_OBJECT_NAME}'.")
        return sidebar_dock

    print(f"WS Info: Creating new dock '{constants.WEBSITE_DOCK_OBJECT_NAME}'.")
    try:
        if not constants.addon_path:
            print("WS Error: Addon path not set in constants. Cannot create profile directory.")
            return None

        profile_root = mw.pm.profileFolder() if mw and mw.pm else None
        if not profile_root:
            raise RuntimeError("Anki profile folder is unavailable")
        profile_dir = os.path.join(
            profile_root, "SynapsePro_Data", "web_profiles", "website")
        profile_name = f"profile_{constants.ADDON_NAME_LAUNCHER}_Website_v2"
        try:
            os.makedirs(profile_dir, exist_ok=True)
            website_profile = QWebEngineProfile(profile_name, mw)
            website_profile.setPersistentStoragePath(profile_dir)
            website_profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
            website_profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
            print(f"WS Info: Created/Using persistent profile: {profile_name} at {profile_dir}")
        except Exception as e_profile:
            print(f"WS Warn: Could not create persistent profile (Error: {e_profile}). Falling back to an off-the-record profile.")
            if mw: website_profile = QWebEngineProfile(mw)
            else: website_profile = QWebEngineProfile()
            if not website_profile.isOffTheRecord():
                 print("WS Warn: Fallback profile was not off-the-record. Using global default profile.")
                 website_profile = QWebEngineProfile.defaultProfile()
            else: print("WS Info: Using off-the-record (in-memory) profile.")

        if not website_profile:
            print("WS FATAL: Could not obtain any QWebEngineProfile.")
            return None

        _install_dark_scrollbar_script(website_profile)

        sidebar_dock = QDockWidget(_("Web Sidebar"), mw)
        sidebar_dock.setObjectName(constants.WEBSITE_DOCK_OBJECT_NAME)
        sidebar_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        sidebar_dock.setMinimumWidth(350)
        
        title_bar_widget = QWidget(); title_bar_widget.setFixedHeight(0)
        sidebar_dock.setTitleBarWidget(title_bar_widget)
        
        sidebar_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable)

        container_widget = QWidget()
        main_layout = QVBoxLayout(container_widget)
        main_layout.setContentsMargins(0, 0, 0, 0); main_layout.setSpacing(0)
        website_main_layout = main_layout

        # Clean grey toolbar bar (matches the Notebook nav bar look).
        _pal = _toolbar_palette()
        toolbar_widget = QWidget()
        toolbar_widget.setObjectName("synapseWebToolbar")
        toolbar_widget.setStyleSheet(
            f"#synapseWebToolbar {{ background-color: {_pal['bar']};"
            f" border-bottom: 1px solid {_pal['line']}; }}"
        )
        toolbar_layout = QVBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(8, 6, 8, 6); toolbar_layout.setSpacing(5)

        button_container_layout = QHBoxLayout(); button_container_layout.setSpacing(3)
        toolbar_layout.addLayout(button_container_layout)

        add_button_widget = QPushButton("+")
        add_button_widget.setObjectName("AddButton")
        add_button_widget.setStyleSheet(_get_raised_icon_button_style())
        add_button_widget.setToolTip(_("Add new website"))
        add_button_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        if qconnect: qconnect(add_button_widget.clicked, open_add_site_dialog)
        else: add_button_widget.setEnabled(False)

        home_button_widget = QPushButton(_("Home"))
        home_button_widget.setObjectName("HomeButton")
        home_button_widget.setStyleSheet(_get_raised_text_button_style())
        home_button_widget.setToolTip(_("Home (Synapse Browser)"))
        home_button_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        nav_button_layout = QHBoxLayout(); nav_button_layout.setSpacing(5)
        _icon_style = _get_icon_button_style()
        back_button = QPushButton("←"); back_button.setToolTip(_("Go Back")); back_button.setEnabled(False)
        forward_button = QPushButton("→"); forward_button.setToolTip(_("Go Forward")); forward_button.setEnabled(False)
        refresh_button = QPushButton("↻"); refresh_button.setToolTip(_("Reload Page"))
        window_button = QPushButton("⧉"); window_button.setToolTip(_("Open in main window"))
        for _btn in (back_button, forward_button, refresh_button, window_button):
            _btn.setStyleSheet(_icon_style)
        _apply_window_icon(window_button)
        nav_button_layout.addWidget(back_button); nav_button_layout.addWidget(forward_button)
        nav_button_layout.addWidget(refresh_button); nav_button_layout.addStretch(1)
        nav_button_layout.addWidget(window_button)
        toolbar_layout.addLayout(nav_button_layout)
        main_layout.addWidget(toolbar_widget)
        if qconnect and window_button:
            qconnect(window_button.clicked, toggle_website_window)

        sidebar_webview = QWebEngineView()
        sidebar_webview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        page = QWebEnginePage(website_profile, sidebar_webview)
        sidebar_webview.setPage(page)
        settings = sidebar_webview.settings()
        attrs_to_set = [
            (QWebEngineSettings.WebAttribute.JavascriptEnabled, True),
            (QWebEngineSettings.WebAttribute.LocalStorageEnabled, True),
            (QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True),
            (QWebEngineSettings.WebAttribute.PluginsEnabled, False),
            (QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True), ]
        for attr, value in attrs_to_set:
            try: settings.setAttribute(attr, value)
            except AttributeError: pass
        sidebar_webview.setUrl(QUrl("about:blank"))
        main_layout.addWidget(sidebar_webview)

        if qconnect and sidebar_webview:
             qconnect(home_button_widget.clicked, partial(load_url_in_webview, webview=sidebar_webview, url_str="https://www.synapse-pro.de/browser"))
        else:
             home_button_widget.setEnabled(False)

        rebuild_custom_buttons_ui()
        button_container_layout.addWidget(add_button_widget)
        button_container_layout.addWidget(home_button_widget) 
        button_container_layout.addStretch(1)

        page = sidebar_webview.page()
        if page and QAction is not object and WebAction is not object:
            action_enum = WebAction if hasattr(WebAction, 'Back') else QWebEnginePage.WebAction
            back_action = page.action(action_enum.Back)
            forward_action = page.action(action_enum.Forward)
            reload_action = page.action(action_enum.Reload)
            if qconnect and back_button and forward_button and refresh_button:
                qconnect(back_button.clicked, back_action.trigger)
                qconnect(forward_button.clicked, forward_action.trigger)
                qconnect(refresh_button.clicked, reload_action.trigger)
                qconnect(back_action.changed, lambda: back_button.setEnabled(back_action.isEnabled()) if back_button is not None else None)
                qconnect(forward_action.changed, lambda: forward_button.setEnabled(forward_action.isEnabled()) if forward_button is not None else None)
        
        if qconnect and not hasattr(sidebar_webview, '_urlChangedConnected_ws'):
            qconnect(sidebar_webview.urlChanged, on_webview_url_changed)
            sidebar_webview._urlChangedConnected_ws = True

        sidebar_dock.setWidget(container_widget)
        sidebar_dock.setVisible(False)
        mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, sidebar_dock)
        print(f"WS Info: New dock created and added successfully.")

    except Exception as e:
        print(f"WS FATAL: Error during new dock creation: {e}")
        traceback.print_exc()
        if sidebar_dock: sidebar_dock.deleteLater(); sidebar_dock = None
        sidebar_webview = None; website_profile = None; button_container_layout = None; nav_button_layout = None
        add_button_widget = None; home_button_widget = None
        back_button = None; forward_button = None; refresh_button = None
        custom_button_containers.clear()
    return sidebar_dock

def on_webview_url_changed(url: QUrl):
    if not sidebar_webview or QUrl is object or not _qt_available: return
    current_url_str = url.toString()
    if current_url_str and current_url_str != "about:blank" and not current_url_str.startswith("data:text/html"):
        save_last_opened_url(current_url_str)

# --- Embedded View (inside the Anki main window) ---
from . import embedded_window


def toggle_website_window():
    """Toggle the embedded main-window view on/off (the ⧉ button)."""
    if website_window is not None and embedded_window.is_active():
        close_website_window()
    else:
        open_website_window()


def open_website_window():
    """Embed the whole dock body into Anki's main content area.

    We borrow the dock's *content widget* (its own toolbar + the webview),
    not just the webview, so the navigation bar – including the ⧉ button –
    stays visible and provides the way back to the sidebar. No extra header
    bar is drawn (show_header=False).
    """
    global website_window, sidebar_dock, sidebar_webview, website_embedded_content
    if not _qt_available or QWidget is object:
        return

    if sidebar_dock is None:
        sidebar_dock = create_website_dock()
    if not sidebar_webview or not sidebar_dock:
        if callable(showWarning):
            showWarning(_("Sidebar Browser not initialized."))
        return

    # Already embedded → nothing to do.
    if website_window is not None or embedded_window.is_active():
        return

    # Make sure a real page is loaded (not about:blank).
    try:
        cur = sidebar_webview.url().toString() if QUrl is not object else ""
    except Exception:
        cur = ""
    if not cur or cur == "about:blank" or cur.startswith("data:text/html"):
        last_url = load_last_opened_url()
        target = last_url if (last_url and last_url != "about:blank"
                              and not last_url.startswith("data:text/html")) \
            else "https://www.synapse-pro.de/browser"
        load_url_in_webview(sidebar_webview, target)

    # Detach the dock's content widget and hide the (now empty) dock.
    content = sidebar_dock.widget()
    if content is None:
        return
    content.setParent(None)
    sidebar_dock.hide()

    ok = embedded_window.embed(content, close_website_window, _("Web"),
                               show_header=False)
    if not ok:
        # Embedding failed – put the content back and abort.
        sidebar_dock.setWidget(content)
        sidebar_dock.show()
        sidebar_dock.raise_()
        return
    website_embedded_content = content
    website_window = True  # marker: an embedded view is active
    if window_button is not None:
        try:
            window_button.setToolTip(_("Back to sidebar"))
        except Exception:
            pass
        # Flip the icon to the "close window" state (frame with a dash).
        _apply_window_icon(window_button, active=True)


def close_website_window():
    """Leave the embedded view and return the content to the dock."""
    global website_window, sidebar_dock, website_embedded_content
    content = website_embedded_content
    if content is not None and sidebar_dock is not None:
        try:
            sidebar_dock.setWidget(content)  # reparents out of the embed container
        except Exception:
            pass
    embedded_window.restore()
    website_embedded_content = None
    website_window = None
    if window_button is not None:
        try:
            window_button.setToolTip(_("Open in main window"))
        except Exception:
            pass
        # Restore the normal "open in main window" icon.
        _apply_window_icon(window_button, active=False)
    if sidebar_dock is not None:
        try:
            sidebar_dock.show()
            sidebar_dock.raise_()
        except Exception:
            pass


# --- Toggle Function ---
def toggle_website_dock():
    global sidebar_dock, sidebar_webview
    if not _qt_available:
        if callable(showWarning): showWarning(_("Website Sidebar: Qt components not available.")); return

    if sidebar_dock is None:
        sidebar_dock = create_website_dock()

    if sidebar_dock is None or QDockWidget is object:
        if callable(showWarning): showWarning(_("{}:\nCould not create or find the website sidebar.").format(constants.ADDON_NAME_WEBSITE)); return
    
    if sidebar_webview is None:
        temp_webview = sidebar_dock.findChild(QWebEngineView)
        if temp_webview and isinstance(temp_webview, QWebEngineView):
            sidebar_webview = temp_webview
            if qconnect and not hasattr(sidebar_webview, '_urlChangedConnected_ws'):
                 qconnect(sidebar_webview.urlChanged, on_webview_url_changed)
                 sidebar_webview._urlChangedConnected_ws = True
    try:
        if sidebar_dock.isVisible():
            sidebar_dock.hide()
        else:
            rebuild_custom_buttons_ui() 

            sidebar_dock.show()
            sidebar_dock.raise_()

            if sidebar_webview:
                last_url = load_last_opened_url()
                if last_url and last_url != "about:blank" and not last_url.startswith("data:text/html"):
                    print(f"WS Info: Loading last opened URL: {last_url}")
                    load_url_in_webview(sidebar_webview, last_url)
                else:
                    print("WS Info: No last URL found. Loading default start page: Synapse Browser.")
                    load_url_in_webview(sidebar_webview, "https://www.synapse-pro.de/browser")
            else:
                print("WS Warn: Sidebar webview not available on toggle show.")
    except Exception as e:
        print(f"WS Error toggling dock visibility: {e}")
        traceback.print_exc()

# --- Theme Refresh Function ---
def refresh_website_theme() -> None:
    """Re-apply theme-aware button styles after a colour-theme change."""
    icon_style = _get_icon_button_style()
    if home_button_widget is not None:
        try: home_button_widget.setStyleSheet(_get_raised_text_button_style())
        except Exception: pass
    if add_button_widget is not None:
        try: add_button_widget.setStyleSheet(_get_raised_icon_button_style())
        except Exception: pass
    for _btn in (back_button, forward_button, refresh_button, window_button):
        if _btn is not None:
            try: _btn.setStyleSheet(icon_style)
            except Exception: pass
    if window_button is not None:
        # Keep the "close window" variant while the embedded view is active.
        try: _apply_window_icon(window_button, active=(website_window is not None))
        except Exception: pass
    # Re-paint the grey bar itself.
    try:
        if mw is not None:
            bar = mw.findChild(QWidget, "synapseWebToolbar")
            if bar is not None:
                pal = _toolbar_palette()
                bar.setStyleSheet(
                    f"#synapseWebToolbar {{ background-color: {pal['bar']};"
                    f" border-bottom: 1px solid {pal['line']}; }}"
                )
    except Exception: pass
    # Rebuild custom site buttons so their styles refresh too.
    try: rebuild_custom_buttons_ui()
    except Exception: pass

# --- Cleanup Function ---
def cleanup_website_sidebar():
    global sidebar_dock, sidebar_webview, website_profile, button_container_layout, nav_button_layout, add_button_widget
    global home_button_widget
    global back_button, forward_button, refresh_button
    global custom_button_containers
    global website_main_layout, website_window, window_button

    # Only close the embedded Browser owned by this module.  A Notebook or
    # Mind Map may be the active embedded tool; restoring its container here
    # would leave that tool's own state flag out of sync with the main layout.
    if website_window is not None:
        try: close_website_window()
        except Exception:
            try: embedded_window.restore()
            except Exception: pass
        website_window = None

    if sidebar_webview and hasattr(sidebar_webview, 'urlChanged') and hasattr(sidebar_webview, '_urlChangedConnected_ws'):
        try:
            if hasattr(sidebar_webview.urlChanged, 'disconnect'):
                 sidebar_webview.urlChanged.disconnect(on_webview_url_changed) # type: ignore
            del sidebar_webview._urlChangedConnected_ws
        except (TypeError, RuntimeError, Exception) as e_disc:
            print(f"WS Info: Could not disconnect urlChanged on cleanup: {e_disc}")
        except AttributeError: pass

    # Anki's main window survives profile switches. Destroy the Qt objects so
    # a page, cookie store, or signal from the old profile cannot remain live.
    if sidebar_webview is not None:
        try: sidebar_webview.setUrl(QUrl("about:blank"))
        except Exception: pass
        try: sidebar_webview.deleteLater()
        except Exception: pass
    if sidebar_dock is not None:
        try: mw.removeDockWidget(sidebar_dock)
        except Exception: pass
        try: sidebar_dock.deleteLater()
        except Exception: pass
    if website_profile is not None:
        try: website_profile.deleteLater()
        except Exception: pass

    sidebar_dock = None; sidebar_webview = None; website_profile = None; button_container_layout = None; nav_button_layout = None
    add_button_widget = None; home_button_widget = None; back_button = None; forward_button = None; refresh_button = None
    window_button = None; website_main_layout = None
    custom_button_containers.clear()
    print(f"{constants.ADDON_NAME_WEBSITE}: Cleaned up references.")

def search_in_sidebar(text: str):
    """
    1. Öffnet die Sidebar (falls geschlossen).
    2. Googelt den Text.

    IMPORTANT: This function must NOT be called synchronously from within a
    context-menu callback while the WebView is still processing the event.
    Doing so can create a QWebEngineView / addDockWidget call on top of an
    active WebEngine event, which causes a silent C++ crash with no Python
    traceback. Always defer via QTimer.singleShot(0, …) instead.
    """
    if not text: return
    # Defer the actual work to the next event-loop tick so that Qt has fully
    # closed the context menu and the WebView is no longer in an active event
    # handler. This prevents the silent C++ crash.
    if QTimer is not object:
        QTimer.singleShot(0, lambda: _execute_search_in_sidebar(text))
    else:
        _execute_search_in_sidebar(text)


def _notify_launcher_dock_opened():
    """Ask the launcher sidebar to highlight the Website icon.

    The search path opens the dock without going through the launcher button,
    so the launcher never wires up its visibility listener on its own. Poke it
    here so the icon reflects the now-open dock (no-op if the launcher or its
    hook isn't available)."""
    try:
        import importlib
        pkg = importlib.import_module(__package__)
        inst = getattr(pkg, "sidebar_widget_instance", None)
        if inst is not None and hasattr(inst, "sync_dock_button"):
            inst.sync_dock_button(constants.WEBSITE_DOCK_OBJECT_NAME)
    except Exception as e:
        print(f"WS Info: could not notify launcher about dock open: {e}")


def _execute_search_in_sidebar(text: str):
    """Internal helper – runs the actual search after the event loop has ticked."""
    if not text: return

    query = urllib.parse.quote(text)
    search_url = f"https://www.google.com/search?q={query}"

    global sidebar_dock, sidebar_webview
    try:
        if not sidebar_dock:
            sidebar_dock = create_website_dock()

        if sidebar_dock:
            if not sidebar_dock.isVisible():
                sidebar_dock.show()
            sidebar_dock.raise_()
            _notify_launcher_dock_opened()

            if sidebar_webview:
                load_url_in_webview(sidebar_webview, search_url)
            else:
                if callable(showWarning): showWarning(_("Sidebar Browser not initialized."))
    except Exception as e:
        print(f"WS Search Error: {e}")
        import traceback; traceback.print_exc()

def on_context_menu(webview, menu):
    """
    Wird aufgerufen, wenn man Rechtsklick im Editor oder Reviewer macht.
    Fügt die "Search in Sidebar" Option hinzu, wenn Text markiert ist.

    NOTE: search_in_sidebar() uses QTimer.singleShot(0, …) internally so
    that dock creation / WebEngine operations happen after this callback
    returns – avoiding the silent C++ crash that occurs when a new
    QWebEngineView is added while the current WebView is still processing
    the context-menu event.
    """
    try:
        # The context-menu hooks remain registered for Anki's lifetime.
        import importlib
        package = importlib.import_module(__package__)
        if not getattr(package, "addon_settings", {}).get("website_viewer_enabled", True):
            return
        selected_text = webview.selectedText()
    except (AttributeError, RuntimeError):
        return

    if selected_text and len(selected_text.strip()) > 0:
        display_text = (selected_text[:20] + '...') if len(selected_text) > 20 else selected_text

        action = menu.addAction(_("Search '{}' in Sidebar").format(display_text))

        # Capture selected_text in the closure explicitly to avoid late-binding issues.
        qconnect(action.triggered, lambda checked=False, t=selected_text: search_in_sidebar(t))

# --- Hooks registrieren ---
if gui_hooks:
    gui_hooks.editor_will_show_context_menu.append(on_context_menu)
    gui_hooks.webview_will_show_context_menu.append(on_context_menu)

print(f"{constants.ADDON_NAME_WEBSITE}: Module Loaded (Updated with Search)")
