
import os
import shutil
import traceback
from typing import Optional

# --- Local Imports ---
from . import constants

# --- PyQt Imports ---
QWidget, QDockWidget, QVBoxLayout, QHBoxLayout, QLabel = object, object, object, object, object
QUrl, Qt, QPushButton, QIcon, QTimer = object, object, object, object, object
QWebEngineView, QWebEnginePage, QWebEngineProfile, QWebEngineSettings = object, object, object, object

if constants.qt_version == 6:
    try:
        from PyQt6.QtWidgets import QWidget, QDockWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from PyQt6.QtCore import QUrl, Qt, QTimer
        from PyQt6.QtGui import QIcon
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
    except ImportError: pass
elif constants.qt_version == 5:
    try:
        from PyQt5.QtWidgets import QWidget, QDockWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from PyQt5.QtCore import QUrl, Qt, QTimer
        from PyQt5.QtGui import QIcon
        from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile, QWebEngineSettings
    except ImportError: pass

# --- Anki Imports ---
if QWidget is not object:
    try:
        from aqt import mw
    except ImportError: mw = None
else: mw = None

# --- Translation ---
try:
    from .locales import _
except ImportError:
    def _(text): return text  # type: ignore

# --- Globale Referenz ---
mindmap_dock: Optional[QDockWidget] = None

# --- Vollbildfenster ---
class MindmapFullscreenWindow(QWidget):
    def __init__(self, panel_instance, web_view, parent=None):
        super().__init__(parent)
        self.panel = panel_instance
        self.web_view = web_view
        self.setWindowTitle(_("Mind Map - Fullscreen"))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web_view)

    def closeEvent(self, event):
        self.panel.exit_fullscreen(self.web_view)
        event.accept()

# --- i18n helper ───────────────────────────────────────────────────────────────
def _build_mindmap_i18n() -> dict:
    """Return the translation dict for the current addon language."""
    return {
        "new_map":          _("New"),
        "menu_title":       _("Menu"),
        "start_learning":   _("Start Learning"),
        "create_with_ai":   _("Create with AI"),
        "import_map":       _("Import"),
        "export_map":       _("Export"),
        "delete_map":       _("Delete Map"),
        "information":      _("Information"),
        "fullscreen_enter": _("Fullscreen"),
        "fullscreen_exit":  _("Exit Fullscreen"),
        "center_view":      _("Center View"),
        "reveal":           _("Reveal"),
        "didnt_know":       _("Didn't know"),
        "i_knew_it":        _("I knew it!"),
        "stop_learning":    _("Stop"),
        "learning_setup":   _("Learning Setup"),
        "scope":            _("Scope"),
        "entire_map":       _("Entire Map"),
        "select_nodes":     _("Select Nodes"),
        "order":            _("Order"),
        "top_down":         _("Top-Down"),
        "random_order":     _("Random"),
        "wrong_penalty":    _("Wrong Answer Penalty"),
        "skip":             _("Skip"),
        "retry_soon":       _("Retry Soon"),
        "revisit_later":    _("Revisit Later"),
        "cancel":           _("Cancel"),
        "start":            _("Start"),
        "tap_to_select":    _("Tap nodes to select:"),
        "footer_hint":      _("Right-click on a node for options. Drag the blue dot to create new nodes."),
    }


# --- Custom WebPage: intercepts mindmap://fullscreen navigation ---
class MindmapWebPage(QWebEnginePage):
    """Intercepts mindmap:// navigation requests and routes them to the panel."""

    def __init__(self, panel: "MindmapPanel", profile, parent=None):
        super().__init__(profile, parent)
        self._panel = panel

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if QUrl is not object and url.scheme() == "mindmap":
            cmd = url.host()
            if QTimer is not object:
                if cmd == "fullscreen":
                    QTimer.singleShot(0, self._panel.enter_fullscreen)
                elif cmd == "exitfullscreen":
                    QTimer.singleShot(0, self._panel.close_fullscreen)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


# --- Main panel class ---
class MindmapPanel(QWidget):
    def __init__(self, parent_dock: QDockWidget):
        super().__init__()
        self.parent_dock = parent_dock
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.web_container = QWidget()
        self.web_layout = QVBoxLayout(self.web_container)
        self.web_layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.web_container, 1)

        self.web_view: Optional[QWebEngineView] = None
        self.fullscreen_window = None
        self.is_in_fullscreen = False
        
        self.is_initialized = False

    def load_content(self):
        """Erstellt den Webview und lädt die Mindmap (RAM Verbrauch steigt)."""
        if self.web_view: return

        if QWebEngineView is object:
            self.web_layout.addWidget(QLabel(_("Error: QtWebEngine not available.")))
            return

        os.environ["QTWEBENGINE_REMOTE_DEBUGGING"] = "12345"

        self.web_view = QWebEngineView()
        
        if QWebEngineProfile is not object:
            old_storage = os.path.join(constants.addon_path, "web_storage")
            new_storage = old_storage
            if mw and mw.pm and mw.pm.profileFolder():
                new_storage = os.path.join(mw.pm.profileFolder(), "mindmap_web_data")

            if new_storage != old_storage and os.path.exists(old_storage) and not os.path.exists(new_storage):
                try:
                    shutil.copytree(old_storage, new_storage)
                    print("Mindmap: Data migrated to profile folder.")
                except Exception as e: print(f"Mindmap Migration Warning: {e}")

            os.makedirs(new_storage, exist_ok=True)
            
            self.profile = QWebEngineProfile("mindmap_persistent_profile_v3", self.web_view)
            self.profile.setPersistentStoragePath(new_storage)
            self.page = MindmapWebPage(self, self.profile, self.web_view)
            self.web_view.setPage(self.page)

        if QWebEngineSettings is not object:
            try:
                s = self.web_view.settings() if constants.qt_version == 6 else QWebEngineSettings.globalSettings()
                s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
                s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
                if hasattr(QWebEngineSettings.WebAttribute, 'AllowFileAccessFromFileUrls'):
                    s.setAttribute(QWebEngineSettings.WebAttribute.AllowFileAccessFromFileUrls, True)
            except Exception: pass

        self.web_view.loadFinished.connect(lambda ok: self._inject_i18n() if ok else None)

        html_path = os.path.join(constants.addon_path, constants.MINDMAP_HTML_FILENAME)
        if os.path.exists(html_path):
            self.web_view.setUrl(QUrl.fromLocalFile(html_path))
        else:
            self.web_view.setHtml(f"<h3>Error: {constants.MINDMAP_HTML_FILENAME} not found.</h3>")

        self.web_layout.addWidget(self.web_view)
        self.is_initialized = True

    def unload_content(self):
        """Zerstört den Webview (RAM wird freigegeben)."""
        if self.web_view:
            self.web_layout.removeWidget(self.web_view)
            self.web_view.deleteLater()
            self.web_view = None
            self.profile = None
            self.page = None
            self.is_initialized = False

    def _inject_i18n(self):
        """Inject the translation dict and call applyMindmapI18n() in the page."""
        if not self.web_view:
            return
        try:
            import json
            strings = _build_mindmap_i18n()
            js = (
                f"window.__SYNAPSE_MM_I18N__ = {json.dumps(strings, ensure_ascii=False)};"
                f"if(window.applyMindmapI18n) applyMindmapI18n();"
            )
            self.web_view.page().runJavaScript(js)
        except Exception:
            pass

    def enter_fullscreen(self):
        if not self.web_view: return
        self.is_in_fullscreen = True

        self.web_layout.removeWidget(self.web_view)
        self.web_view.setParent(None)
        self.parent_dock.hide()

        self.fullscreen_window = MindmapFullscreenWindow(self, self.web_view)
        self.fullscreen_window.showFullScreen()

        # Update the HTML button to show collapse icon
        try:
            import json
            strings = _build_mindmap_i18n()
            t_json = json.dumps(strings, ensure_ascii=False)
            self.web_view.page().runJavaScript(
                f"if(window.__synapseSetFullscreen) __synapseSetFullscreen(true, {t_json});"
            )
        except Exception:
            pass

    def close_fullscreen(self):
        """Called from HTML button while in fullscreen."""
        if self.fullscreen_window:
            self.fullscreen_window.close()  # triggers exit_fullscreen via closeEvent

    def exit_fullscreen(self, web_view_ref):
        self.is_in_fullscreen = False
        self.fullscreen_window = None

        self.web_layout.addWidget(web_view_ref)
        self.parent_dock.show()

        # Restore expand icon in the HTML button
        try:
            import json
            strings = _build_mindmap_i18n()
            t_json = json.dumps(strings, ensure_ascii=False)
            web_view_ref.page().runJavaScript(
                f"if(window.__synapseSetFullscreen) __synapseSetFullscreen(false, {t_json});"
            )
        except Exception:
            pass

    def on_visibility_changed(self, visible):
        """RAM-Management Logik"""
        if visible:
            self.load_content()
        else:
            if not self.is_in_fullscreen:
                self.unload_content()

# --- Setup & Toggle ---

def setup_mindmap_dock():
    global mindmap_dock
    if not mw or QDockWidget is object or mindmap_dock: return

    try:
        mindmap_dock = QDockWidget("Mind Map", mw)
        mindmap_dock.setObjectName(constants.MINDMAP_DOCK_OBJECT_NAME)
        if Qt: mindmap_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)

        title_bar = QWidget()
        title_bar.setFixedHeight(0)
        mindmap_dock.setTitleBarWidget(title_bar)

        panel = MindmapPanel(mindmap_dock)
        mindmap_dock.setWidget(panel)
        
        mindmap_dock.visibilityChanged.connect(panel.on_visibility_changed)

        if Qt: mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, mindmap_dock)
        mindmap_dock.setVisible(False)

    except Exception as e:
        print(f"MindmapSidebar Setup Error: {e}")
        traceback.print_exc()

def toggle_mindmap_dock():
    if mindmap_dock is None:
        setup_mindmap_dock()
    
    if mindmap_dock:
        if mindmap_dock.isVisible():
            mindmap_dock.hide()
        else:
            mindmap_dock.show()
            mindmap_dock.raise_()

def cleanup_mindmap_sidebar():
    global mindmap_dock
    if mindmap_dock:
        panel = mindmap_dock.widget()
        if isinstance(panel, MindmapPanel):
            panel.unload_content()
            if panel.fullscreen_window:
                panel.fullscreen_window.close()
        
        try: mw.removeDockWidget(mindmap_dock)
        except Exception: pass
        mindmap_dock.deleteLater()
        mindmap_dock = None

