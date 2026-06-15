# -*- coding: utf-8 -*-

import json
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
    if constants.qt_version == 6:
        from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                     QInputDialog, QDockWidget, QSizePolicy,
                                     QMessageBox, QMenu)
        from PyQt6.QtGui import QAction
        from PyQt6.QtCore import QUrl, QTimer, QSize, Qt
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings
        WebAction = QWebEnginePage.WebAction
        print("Website Sidebar: Using PyQt6 components")
        _qt_available = True
    elif constants.qt_version == 5:
        from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                     QInputDialog, QDockWidget, QSizePolicy,
                                     QMessageBox, QAction, QMenu)
        from PyQt5.QtCore import QUrl, QTimer, QSize, Qt
        from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
        QWebEngineProfile = QWebEngineProfile
        QWebEngineSettings = QWebEngineSettings
        WebAction = QWebEnginePage.WebAction
        print("Website Sidebar: Using PyQt5 components")
        _qt_available = True
    else:
        raise ImportError("No supported Qt version found by Launcher.")
except ImportError as e:
    print(f"Website Sidebar Error: Could not import necessary PyQt components. {e}")
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton = object, object, object, object
    QInputDialog, QDockWidget, QSizePolicy, QMessageBox = object, object, object, object
    QUrl, QTimer, QSize, Qt = object, object, object, None
    QWebEngineView, QWebEngineProfile, QWebEnginePage, QWebEngineSettings = object, object, object, object
    QAction = object; WebAction = object; QMenu = object


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

def _get_blue_button_style() -> str:
    """Return a primary-colour button stylesheet using the active theme palette."""
    try:
        from .theme import palette as _tp
        night = bool(mw and hasattr(mw, 'pm') and mw.pm.night_mode())
        c = _tp(night)
        bg      = c["blue"]
        hover   = c["blue_hover"]
        pressed = c["blue_pressed"]
        shadow  = c["blue_pressed"]
    except Exception:
        bg = "#0071D3"; hover = "#0062C4"; pressed = "#004990"; shadow = "#004990"
    return f"""
QPushButton {{
    background-color: {bg};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 5px 10px;
}}
QPushButton:hover {{
    background-color: {hover};
}}
QPushButton:pressed {{
    background-color: {pressed};
}}
"""

WHITE_BUTTON_STYLE = """
QPushButton {
    background-color: #F0F0F0;
    color: #333333;
    border: none;
    border-radius: 8px;
    padding: 5px 8px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #E8E8E8;
    color: #D32F2F;
}
QPushButton:pressed {
    background-color: #DCDCDC;
}
"""

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
custom_button_containers: List[QWidget] = []

# --- Configuration Management ---
def get_default_sites_if_empty() -> List[Dict[str, str]]:
    """Returns Notion as a default suggestion if no sites are configured."""
    return [
        {"name": "YouTube", "url": "https://www.youtube.com/"}
    ]

def load_custom_sites() -> List[Dict[str, str]]:
    if not mw or not mw.col: return get_default_sites_if_empty() 

    config_json = mw.col.get_config(constants.CONFIG_KEY_CUSTOM_SITES)
    
    if config_json is not None:
        try:
            sites = json.loads(config_json)
            if isinstance(sites, list) and all(isinstance(s, dict) and 'name' in s and 'url' in s for s in sites):
                if len(sites) > constants.MAX_CUSTOM_SITES:
                    sites = sites[:constants.MAX_CUSTOM_SITES]
                return sites
            else:
                print("WS Warn: Invalid format for custom sites in config. Resetting to defaults.")
                default_sites = get_default_sites_if_empty()
                save_custom_sites(default_sites)
                return default_sites
        except json.JSONDecodeError:
            print("WS Warn: JSONDecodeError for custom sites in config. Resetting to defaults.")
            default_sites = get_default_sites_if_empty()
            save_custom_sites(default_sites)
            return default_sites
    else:
        print("WS Info: No custom sites found in config. Initializing with defaults.")
        default_sites = get_default_sites_if_empty()
        save_custom_sites(default_sites)
        return default_sites


def save_custom_sites(sites: List[Dict[str, str]]):
    if not mw or not mw.col: return
    if len(sites) > constants.MAX_CUSTOM_SITES: sites = sites[:constants.MAX_CUSTOM_SITES]
    config_json = json.dumps(sites)
    mw.col.set_config(constants.CONFIG_KEY_CUSTOM_SITES, config_json)

def save_last_opened_url(url: str):
    if not mw or not mw.col: return
    if not hasattr(constants, 'CONFIG_KEY_LAST_OPENED_URL'):
        print("WS Warn: CONFIG_KEY_LAST_OPENED_URL not in constants. Cannot save last URL.")
        return
    mw.col.set_config(constants.CONFIG_KEY_LAST_OPENED_URL, url)
    print(f"WS Info: Saved last opened URL: {url}")

def load_last_opened_url() -> Optional[str]:
    if not mw or not mw.col: return None
    if not hasattr(constants, 'CONFIG_KEY_LAST_OPENED_URL'):
        print("WS Warn: CONFIG_KEY_LAST_OPENED_URL not in constants. Cannot load last URL.")
        return None
    return mw.col.get_config(constants.CONFIG_KEY_LAST_OPENED_URL)


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
        error_html = _("""
        <body style='font-family: sans-serif; padding: 20px; color: #333; background-color: #f9f9f9;'>
            <h2 style='color: #d32f2f;'>Invalid URL</h2>
            <p>The URL you tried to open seems to be invalid or is not a standard web URL (http/https).</p>
            <p>Attempted URL: <code>{url_str}</code></p>
        </body>""").format(url_str=url_str)
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
    site_button.setStyleSheet(_get_blue_button_style()) # Hier Blaues Design anwenden
    site_button.setToolTip(_("Open: {}").format(url))
    site_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    delete_button = QPushButton("-")
    delete_button.setObjectName("DeleteButton")
    delete_button.setStyleSheet(WHITE_BUTTON_STYLE)
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

        profile_dir = os.path.join(constants.addon_path, constants.WEBSITE_PROFILE_SUBDIR)
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

        sidebar_dock = QDockWidget(_("Web Sidebar"), mw)
        sidebar_dock.setObjectName(constants.WEBSITE_DOCK_OBJECT_NAME)
        allowed_areas_enum = Qt.DockWidgetArea if hasattr(Qt, 'DockWidgetArea') else Qt
        sidebar_dock.setAllowedAreas(allowed_areas_enum.LeftDockWidgetArea | allowed_areas_enum.RightDockWidgetArea)
        sidebar_dock.setMinimumWidth(350)
        
        title_bar_widget = QWidget(); title_bar_widget.setFixedHeight(0)
        sidebar_dock.setTitleBarWidget(title_bar_widget)
        
        features_enum = QDockWidget.DockWidgetFeature if hasattr(QDockWidget, 'DockWidgetFeature') else QDockWidget
        sidebar_dock.setFeatures(features_enum.DockWidgetClosable | features_enum.DockWidgetMovable | features_enum.DockWidgetFloatable)

        container_widget = QWidget()
        main_layout = QVBoxLayout(container_widget)
        main_layout.setContentsMargins(2, 8, 2, 2); main_layout.setSpacing(5)

        button_container_layout = QHBoxLayout(); button_container_layout.setSpacing(3)
        main_layout.addLayout(button_container_layout)

        add_button_widget = QPushButton("+")
        add_button_widget.setObjectName("AddButton")
        add_button_widget.setStyleSheet(_get_blue_button_style()) # Hier Blaues Design anwenden
        add_button_widget.setToolTip(_("Add new website"))
        add_button_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        if qconnect: qconnect(add_button_widget.clicked, open_add_site_dialog)
        else: add_button_widget.setEnabled(False)

        home_button_widget = QPushButton(_("Home"))
        home_button_widget.setObjectName("HomeButton")
        home_button_widget.setStyleSheet(_get_blue_button_style()) # Hier Blaues Design anwenden
        home_button_widget.setToolTip(_("Home (Synapse Browser)"))
        home_button_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        nav_button_layout = QHBoxLayout(); nav_button_layout.setSpacing(5)
        back_button = QPushButton("←"); back_button.setToolTip(_("Go Back")); back_button.setEnabled(False)
        forward_button = QPushButton("→"); forward_button.setToolTip(_("Go Forward")); forward_button.setEnabled(False)
        refresh_button = QPushButton("↻"); refresh_button.setToolTip(_("Reload Page"))
        nav_button_layout.addWidget(back_button); nav_button_layout.addWidget(forward_button)
        nav_button_layout.addWidget(refresh_button); nav_button_layout.addStretch(1)
        main_layout.addLayout(nav_button_layout)

        sidebar_webview = QWebEngineView()
        sidebar_webview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        page = QWebEnginePage(website_profile, sidebar_webview)
        sidebar_webview.setPage(page)
        settings = sidebar_webview.settings()
        if hasattr(QWebEngineSettings, 'WebAttribute'):
            attrs_to_set = [
                (QWebEngineSettings.WebAttribute.JavascriptEnabled, True),
                (QWebEngineSettings.WebAttribute.LocalStorageEnabled, True),
                (QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True),
                (QWebEngineSettings.WebAttribute.PluginsEnabled, False),
                (QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True), ]
        else:
            attrs_to_set = [
                (QWebEngineSettings.JavascriptEnabled, True),
                (QWebEngineSettings.LocalStorageEnabled, True),
                (QWebEngineSettings.ScrollAnimatorEnabled, True),
                (QWebEngineSettings.PluginsEnabled, False),
                (QWebEngineSettings.FullScreenSupportEnabled, True), ]
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
        add_dock_area_enum = Qt.DockWidgetArea if hasattr(Qt, 'DockWidgetArea') else Qt
        mw.addDockWidget(add_dock_area_enum.RightDockWidgetArea, sidebar_dock)
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
    style = _get_blue_button_style()
    if add_button_widget is not None:
        try: add_button_widget.setStyleSheet(style)
        except Exception: pass
    if home_button_widget is not None:
        try: home_button_widget.setStyleSheet(style)
        except Exception: pass

# --- Cleanup Function ---
def cleanup_website_sidebar():
    global sidebar_dock, sidebar_webview, website_profile, button_container_layout, nav_button_layout, add_button_widget
    global home_button_widget 
    global back_button, forward_button, refresh_button
    global custom_button_containers
    
    if sidebar_webview and hasattr(sidebar_webview, 'urlChanged') and hasattr(sidebar_webview, '_urlChangedConnected_ws'):
        try:
            if hasattr(sidebar_webview.urlChanged, 'disconnect'):
                 sidebar_webview.urlChanged.disconnect(on_webview_url_changed) # type: ignore
            del sidebar_webview._urlChangedConnected_ws
        except (TypeError, RuntimeError, Exception) as e_disc:
            print(f"WS Info: Could not disconnect urlChanged on cleanup: {e_disc}")
        except AttributeError: pass

    sidebar_dock = None; sidebar_webview = None; website_profile = None; button_container_layout = None; nav_button_layout = None
    add_button_widget = None; home_button_widget = None; back_button = None; forward_button = None; refresh_button = None
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

            if sidebar_webview:
                print(f"WS Search: Searching for '{text}'")
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