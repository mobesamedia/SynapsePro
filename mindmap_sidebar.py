
import json
import os
import shutil
import time
import traceback
from typing import Callable, Optional

# --- Local Imports ---
from . import constants

# --- PyQt Imports ---
QWidget, QDockWidget, QVBoxLayout, QHBoxLayout, QLabel = object, object, object, object, object
QUrl, Qt, QPushButton, QIcon, QTimer = object, object, object, object, object
QWebEngineView, QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineScript = object, object, object, object, object

try:
    from aqt.qt import (QWidget, QDockWidget, QVBoxLayout, QHBoxLayout, QLabel,
                        QPushButton, QUrl, Qt, QTimer, QIcon, QColor)
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineScript
except ImportError:
    pass

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

from . import embedded_window

# --- Globale Referenz ---
mindmap_dock: Optional[QDockWidget] = None
MINDMAP_RECOVERY_FILENAME = "mindmap_recovery.json"


def _mindmap_recovery_path() -> str:
    if mw and mw.pm and mw.pm.profileFolder():
        return os.path.join(mw.pm.profileFolder(), MINDMAP_RECOVERY_FILENAME)
    return os.path.join(constants.addon_path, MINDMAP_RECOVERY_FILENAME)


def _write_mindmap_recovery(snapshot: str, saved_at: int) -> bool:
    """Atomically mirror the latest map collection outside QtWebEngine storage."""
    path = _mindmap_recovery_path()
    tmp_path = f"{path}.tmp"
    try:
        mindmaps = json.loads(snapshot)
        if not isinstance(mindmaps, dict):
            raise ValueError("mind map recovery snapshot is not an object")
        payload = {
            "version": 1,
            "saved_at": int(saved_at),
            "mindmaps": mindmaps,
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        return True
    except Exception as exc:
        print(f"Mindmap recovery save failed: {exc}")
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        return False


def _load_mindmap_recovery() -> Optional[dict]:
    try:
        with open(_mindmap_recovery_path(), "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if (
            isinstance(payload, dict)
            and isinstance(payload.get("saved_at"), int)
            and isinstance(payload.get("mindmaps"), dict)
        ):
            return payload
    except FileNotFoundError:
        pass
    except Exception as exc:
        print(f"Mindmap recovery load failed: {exc}")
    return None

# --- Vollbildfenster ---
class MindmapFullscreenWindow(QWidget):
    def __init__(self, panel_instance, web_view, parent=None, windowed=False):
        super().__init__(parent)
        self.panel = panel_instance
        self.web_view = web_view
        self.windowed = windowed
        self.setWindowTitle(
            _("Mind Map") if windowed else _("Mind Map - Fullscreen")
        )
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
        "app_title":        _("Mind Map"),
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
        "window_open":      _("New Window"),
        "window_exit":      _("Close Window"),
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
        "edit_hints":       _("Edit Hints"),
        "save":             _("Save"),
        "selected_count":   _("{count} selected"),
        "enter_here":       _("Enter here..."),
        "confirm":          _("Confirm"),
        "undo":             _("Undo (Ctrl+Z)"),
        "redo":             _("Redo (Ctrl+Y)"),
        "error_title":      _("Mind Map error"),
        "error_show":       _("Show details"),
        "error_hide":       _("Hide details"),
        "error_copy":       _("Copy error"),
        "error_copied":     _("Copied!"),
        "error_dismiss":    _("Dismiss"),
        "error_unexpected": _("Unexpected error"),
        "error_unexpected_async": _("Unexpected error (async)"),
        "error_safe":       _("Your data is safe. Please screenshot the details and send them to help.synapse.pro@gmail.com."),
        "error_no_stack":   _("(no stack trace available)"),
        "info_basic":       _("Basic Controls"),
        "info_pan":         _("Pan View: Click and drag on the empty background."),
        "info_zoom":        _("Zoom View: Use the mouse wheel or the +/- buttons."),
        "info_move":        _("Move Node: Click and drag any node."),
        "info_child":       _("Create Child Node: Click and drag the blue dot on a node."),
        "info_undo":        _("Undo/Redo: Use the arrows at the top right or Ctrl+Z / Ctrl+Y."),
        "info_edit":        _("Edit Text: Double-click the text inside a node."),
        "info_features":    _("Features"),
        "info_manage":      _("New Map / Delete Map: Manage your mind maps."),
        "info_ai":          _("Create with AI: Generate a mind map from a topic using AI."),
        "info_learn":       _("Start Learning: Review mode with active recall."),
        "info_title":       _("Mind Map Information"),
        "ai_step1":        _("Step 1: Customize and Copy the Prompt"),
        "copy_prompt":      _("Copy Prompt"),
        "ai_step2":        _("Step 2: Paste the AI-Generated JSON"),
        "paste_json":      _("Paste JSON here..."),
        "import_mindmap":  _("Import Mind Map"),
        "import_save_failed": _("The current mind map could not be saved. Import was cancelled to protect your changes."),
        "import_paste_first": _("Please paste your mind map JSON first."),
        "invalid_json":    _("Invalid JSON: {error}. Make sure you copied the complete JSON object."),
        "invalid_map":     _("This JSON is not a valid mind map: {error}"),
        "import_store_failed": _("The mind map is valid but could not be saved (storage full?)."),
        "import_load_failed": _("Import failed while loading the map: {error}"),
        "import_repaired": _("Mind map imported. Some data was repaired automatically: {details}"),
        "unnamed_map":     _("Unnamed Map"),
        "create_title":    _("Create New Mind Map"),
        "enter_name":      _("Please enter a name."),
        "create":          _("Create"),
        "central_topic":   _("Central Topic"),
        "import_json":     _("Import from JSON"),
        "paste_map_json":  _("Paste your mind map JSON data below."),
        "export_json":     _("Export to JSON"),
        "copy_json":       _("Copy the JSON data below."),
        "copy_clipboard":  _("Copy to Clipboard"),
        "nothing_export":  _("Nothing to export: the current mind map was not found in storage."),
        "color":           _("Color"),
        "size":            _("Size"),
        "small":           _("Small"),
        "medium":          _("Medium"),
        "large":           _("Large"),
        "delete_map_confirm": _("Delete this map?"),
        "resize":          _("Resize"),
        "hint_placeholder": _("Hint…"),
        "new_node":        _("New Node"),
        "delete_node_confirm": _("Delete node?"),
        "review_missed":   _("Reviewing missed cards…"),
        "learning_done":   _("Done! Great work!"),
        "recall_prompt":   _("Recall the highlighted node · {remaining} remaining"),
        "recall_correct":  _("Did you recall it correctly?"),
        "storage_read_failed": _("Storage read failed"),
        "storage_corrupt": _("Stored mind map data was corrupted and has been backed up. Starting fresh."),
        "storage_full": _("Could not save: browser storage is full. Export your maps as backup and delete unused maps."),
        "save_failed": _("Could not save mind maps: {error}"),
        "recovery_invalid": _("Recovery data is invalid"),
        "recovery_restored": _("A newer mind map recovery copy was restored."),
        "recovery_memory": _("Your recovery copy is open in memory. Free browser storage or export it before closing."),
        "corrupt_removed_count": _("{count} corrupted mind map(s) were removed so the tool works again. A backup was kept in storage."),
        "repaired_count": _("{count} mind map(s) had invalid data and were repaired automatically."),
        "startup_check": _("Startup check"),
        "loading_map": _("Loading mind map"),
        "corrupt_map_removed": _("This mind map was corrupted and has been removed. A backup was kept in storage."),
        "initialization": _("Initialization"),
        "ai_prompt_intro": _("You are an expert assistant that creates mind maps in a specific JSON format."),
        "ai_prompt_json_only": _("The output must be one valid JSON object and nothing else. Do not add explanations."),
        "ai_prompt_structure": _("Use this JSON structure:"),
        "ai_sample_name": _("Name of the Mind Map"),
        "ai_sample_central": _("Central Topic"),
        "ai_sample_branch": _("Main Branch"),
        "ai_sample_subpoint": _("Sub-point"),
        "ai_prompt_generate": _("Generate the mind map JSON now."),
        "tutorial_name": _("Mind Map Tutorial"),
        "tutorial_welcome": _("Welcome to the Mind Map Tool!"),
        "tutorial_center": _("Center View: Use the Center View button to focus on the root node."),
        "tutorial_manage_nodes": _("Managing Nodes"),
        "tutorial_delete_node": _("Delete Node: Hover over a node and use the minus button."),
        "tutorial_customize": _("Customize Nodes (right-click)"),
        "tutorial_color": _("Change Color: Right-click a node and choose a color."),
        "tutorial_size": _("Change Size: Right-click and choose Small, Medium, or Large."),
        "tutorial_special": _("Special Features"),
        "tutorial_ai_1": _("1. Select Create with AI in the menu."),
        "tutorial_ai_2": _("2. Copy the prompt and paste it into an AI service."),
        "tutorial_ai_3": _("3. Copy the AI's JSON response and paste it back into the tool."),
        "tutorial_recall": _("Turns your map into an active-recall session."),
        "tutorial_hidden": _("Child nodes are hidden so you can recall them."),
        "tutorial_rate": _("Rate your answer to reinforce your memory."),
        "tutorial_data": _("Data & Maps"),
        "tutorial_switch": _("Use the list at the top left to switch between maps."),
        "tutorial_collection": _("New Map and Delete Map manage your collection."),
        "tutorial_backup": _("Import / Export (backup)"),
        "tutorial_export": _("Export saves your map as JSON for backup."),
        "tutorial_import": _("Import loads a map from a JSON file."),
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
                elif cmd == "window":
                    QTimer.singleShot(0, self._panel.enter_window)
                elif cmd == "exitwindow":
                    QTimer.singleShot(0, self._panel.exit_window)
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
        self.is_embedded = False  # True when embedded in the Anki main window
        self._windowed = False

        self.is_initialized = False
        self._page_ready = False
        self._unload_in_progress = False
        self._unload_callbacks: list[Callable[[bool], None]] = []

    def load_content(self):
        """Erstellt den Webview und lädt die Mindmap (RAM Verbrauch steigt)."""
        if self.web_view: return

        if QWebEngineView is object:
            self.web_layout.addWidget(QLabel(_("Error: QtWebEngine not available.")))
            return

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
            
            # The profile must NOT be a child of the web_view: Qt destroys
            # children in creation order, so the profile would be torn down
            # while the page (created after it) still exists — QtWebEngine's
            # "Release of profile requested but WebEnginePage still not
            # deleted" hard-crash scenario. Keep it parentless and delete it
            # explicitly in _destroy_web_view() AFTER view+page are gone.
            self.profile = QWebEngineProfile("mindmap_persistent_profile_v3")
            self.profile.setPersistentStoragePath(new_storage)
            self.page = MindmapWebPage(self, self.profile, self.web_view)
            self.web_view.setPage(self.page)

            # The default tutorial and startup diagnostics are created before
            # loadFinished. Inject translations at DocumentCreation so even
            # those first-run contents use the selected add-on language.
            try:
                boot_i18n = json.dumps(_build_mindmap_i18n(), ensure_ascii=False).replace("</", "<\\/")
                boot_dark = bool(mw and mw.pm.night_mode())
                boot_accent = None
                boot_pressed = None
                try:
                    from .theme import palette
                    boot_palette = palette(boot_dark)
                    boot_accent = boot_palette.get("blue_accent") or boot_palette.get("blue")
                    boot_pressed = boot_palette.get("blue_pressed") or boot_accent
                except Exception:
                    # The post-load theme injection below remains as a fallback.
                    pass
                script = QWebEngineScript()
                script.setName("synapse-mindmap-i18n")
                script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
                script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
                script.setRunsOnSubFrames(False)
                script.setSourceCode(
                    f"window.__SYNAPSE_MM_I18N__={boot_i18n};"
                    f"window.__SYNAPSE_MM_DARK__={json.dumps(boot_dark)};"
                    f"window.__SYNAPSE_MM_ACCENT__={json.dumps(boot_accent)};"
                    f"window.__SYNAPSE_MM_ACCENT_PRESSED__={json.dumps(boot_pressed)};"
                )
                self.page.scripts().insert(script)
            except Exception as exc:
                print(f"Mindmap: early translation injection failed: {exc}")

        if QWebEngineSettings is not object:
            try:
                s = self.web_view.settings()
                s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
                s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
                if hasattr(QWebEngineSettings.WebAttribute, 'AllowFileAccessFromFileUrls'):
                    s.setAttribute(QWebEngineSettings.WebAttribute.AllowFileAccessFromFileUrls, True)
            except Exception: pass

        # Match the page background to the theme BEFORE anything paints —
        # otherwise the view flashes white in dark mode while loading.
        try:
            dark = bool(mw and mw.pm.night_mode())
            self.web_view.page().setBackgroundColor(
                QColor("#191919") if dark else QColor("#f8f9fa"))
        except Exception:
            pass

        self.web_view.loadFinished.connect(self._on_load_finished)

        html_path = os.path.join(constants.addon_path, constants.MINDMAP_HTML_FILENAME)
        if os.path.exists(html_path):
            self.web_view.setUrl(QUrl.fromLocalFile(html_path))
        else:
            self.web_view.setHtml(f"<h3>Error: {constants.MINDMAP_HTML_FILENAME} not found.</h3>")

        self.web_layout.addWidget(self.web_view)
        self.is_initialized = True

    def _on_load_finished(self, ok: bool) -> None:
        self._page_ready = bool(ok)
        if not ok:
            return
        self._inject_i18n()
        self._inject_theme_accent()
        self._inject_recovery_snapshot()

    def _inject_recovery_snapshot(self) -> None:
        """Restore a newer disk mirror after a failed/rolled-back LocalStorage save."""
        if not self.web_view:
            return
        recovery = _load_mindmap_recovery()
        if not recovery:
            return
        snapshot_json = json.dumps(
            recovery["mindmaps"], ensure_ascii=False, separators=(",", ":")
        )
        js = (
            "if(window.__synapseRestoreMindmapRecovery) "
            f"window.__synapseRestoreMindmapRecovery({json.dumps(snapshot_json)}, "
            f"{int(recovery['saved_at'])});"
        )
        try:
            self.web_view.page().runJavaScript(js)
        except Exception as exc:
            print(f"Mindmap recovery injection failed: {exc}")

    def _destroy_web_view(self, web_ref) -> None:
        if self.web_view is not web_ref:
            return
        self.web_layout.removeWidget(web_ref)
        profile_ref = self.profile
        web_ref.deleteLater()
        self.web_view = None
        self.profile = None
        self.page = None
        self.is_initialized = False
        self._page_ready = False
        # Delete the (parentless) profile only after the queued deleteLater of
        # view+page has been processed — the profile must outlive the page.
        if profile_ref is not None and QTimer is not object:
            QTimer.singleShot(0, profile_ref.deleteLater)

    def unload_content(
        self, on_complete: Optional[Callable[[bool], None]] = None
    ) -> None:
        """Persist LocalStorage plus a disk recovery copy before freeing RAM."""
        if on_complete:
            self._unload_callbacks.append(on_complete)
        if not self.web_view:
            self._finish_unload_callbacks(True)
            return
        if self._unload_in_progress:
            return

        self._unload_in_progress = True
        web_ref = self.web_view
        page_was_ready = self._page_ready
        completed = False

        def finish(durable: bool) -> None:
            nonlocal completed
            if completed:
                return
            completed = True
            self._unload_in_progress = False
            if durable:
                self._destroy_web_view(web_ref)
            else:
                # Keep the hidden WebView alive so reopening the dock returns to
                # the unsaved in-memory state instead of loading older data.
                print("Mindmap: WebView kept alive because final persistence failed")
            self._finish_unload_callbacks(durable)

        def receive_snapshot(result) -> None:
            if self.web_view is not web_ref:
                finish(True)
                return
            if result is None:
                finish(not page_was_ready)
                return
            if not isinstance(result, dict):
                finish(False)
                return

            snapshot = result.get("snapshot")
            local_saved = result.get("saved") is True
            try:
                saved_at = int(result.get("savedAt") or int(time.time() * 1000))
            except (TypeError, ValueError):
                saved_at = int(time.time() * 1000)
            recovery_saved = (
                isinstance(snapshot, str)
                and _write_mindmap_recovery(snapshot, saved_at)
            )
            finish(local_saved or recovery_saved)

        js = (
            "(typeof window.__synapseFlushMindmap === 'function')"
            " ? window.__synapseFlushMindmap() : null"
        )
        try:
            web_ref.page().runJavaScript(js, receive_snapshot)
            # A renderer failure must not discard the live page. Timeout only
            # unlocks the panel and deliberately keeps the WebView in memory.
            QTimer.singleShot(5000, lambda: finish(False))
        except Exception as exc:
            print(f"Mindmap final save request failed: {exc}")
            finish(False)

    def _finish_unload_callbacks(self, saved: bool) -> None:
        callbacks = self._unload_callbacks
        self._unload_callbacks = []
        for callback in callbacks:
            try:
                callback(saved)
            except Exception as exc:
                print(f"Mindmap unload callback failed: {exc}")

    def _inject_i18n(self):
        """Inject the translation dict and call applyMindmapI18n() in the page."""
        if not self.web_view:
            return
        try:
            import json
            strings = _build_mindmap_i18n()
            dark = bool(mw and mw.pm.night_mode())
            js = (
                f"window.__SYNAPSE_MM_I18N__ = {json.dumps(strings, ensure_ascii=False)};"
                f"document.documentElement.classList.toggle('dark', {json.dumps(dark)});"
                f"if(window.applyMindmapI18n) applyMindmapI18n();"
            )
            self.web_view.page().runJavaScript(js)
        except Exception:
            pass

    def _inject_theme_accent(self):
        """Apply the add-on's colour theme to the page.

        Overrides the hardcoded ``--primary-color`` CSS variable so the root
        node (and selection rings, drag handles …) use the accent colour of
        whichever theme the user picked instead of the default blue.
        """
        if not self.web_view:
            return
        try:
            from .theme import palette
            c = palette(bool(mw and mw.pm.night_mode()))
            accent = c.get("blue_accent") or c.get("blue")
            pressed = c.get("blue_pressed") or accent
            js = ""
            if accent:
                js += (
                    "document.documentElement.style.setProperty('--primary-color', %s);"
                    "document.documentElement.style.setProperty('--primary-color-dark', %s);"
                ) % (json.dumps(accent), json.dumps(pressed))
            js += (
                "if(window.__synapseMarkMindmapThemeReady) "
                "window.__synapseMarkMindmapThemeReady();"
            )
            self.web_view.page().runJavaScript(js)
        except Exception:
            # Never leave the loading cover stuck just because a custom palette
            # could not be read. The HTML still has safe light/dark defaults.
            try:
                self.web_view.page().runJavaScript(
                    "if(window.__synapseMarkMindmapThemeReady) "
                    "window.__synapseMarkMindmapThemeReady();"
                )
            except Exception:
                pass

    def enter_fullscreen(self):
        if not self.web_view: return
        if self.is_in_fullscreen or self.is_embedded: return
        self.is_in_fullscreen = True

        self.web_layout.removeWidget(self.web_view)
        self.web_view.setParent(None)
        self.parent_dock.hide()

        self.fullscreen_window = MindmapFullscreenWindow(self, self.web_view)
        self.fullscreen_window.showFullScreen()

        self._set_html_toggle(self.web_view, True, windowed=False)

    def close_fullscreen(self):
        """Called from the HTML fullscreen button while in fullscreen."""
        if self.fullscreen_window:
            self.fullscreen_window.close()  # triggers exit_fullscreen via closeEvent

    def exit_fullscreen(self, web_view_ref):
        self.is_in_fullscreen = False
        self.fullscreen_window = None

        self.web_layout.addWidget(web_view_ref)
        self.parent_dock.show()

        self._set_html_toggle(web_view_ref, False, windowed=False)

    # ── Embedded view (inside the Anki main window) ──
    def enter_window(self):
        if not self.web_view: return
        if self.is_in_fullscreen or self.is_embedded: return

        # IMPORTANT: set the flag *before* hiding the dock. Hiding the dock
        # fires visibilityChanged, whose handler would otherwise destroy the
        # web view (RAM saving) via unload_content(). The flag suppresses that
        # teardown so the borrowed web view survives to be embedded.
        self.is_embedded = True
        self.web_layout.removeWidget(self.web_view)
        self.web_view.setParent(None)
        self.parent_dock.hide()

        ok = embedded_window.embed(self.web_view, self.exit_window, _("Mind Map"),
                                   show_header=False)
        if not ok:
            self.is_embedded = False
            self.web_layout.addWidget(self.web_view)
            self.parent_dock.show()
            return
        self._set_html_toggle(self.web_view, True, windowed=True)

    def exit_window(self):
        if not self.is_embedded:
            return
        self.is_embedded = False
        wv = self.web_view
        if wv is not None:
            self.web_layout.addWidget(wv)  # reparents out of the container
        embedded_window.restore()
        self.parent_dock.show()
        self.parent_dock.raise_()
        if wv is not None:
            self._set_html_toggle(wv, False, windowed=True)

    def _set_html_toggle(self, web_view_ref, active, windowed=False):
        """Update the fullscreen or window button state inside the page."""
        try:
            import json
            strings = _build_mindmap_i18n()
            t_json = json.dumps(strings, ensure_ascii=False)
            flag = "true" if active else "false"
            fn = "__synapseSetWindow" if windowed else "__synapseSetFullscreen"
            web_view_ref.page().runJavaScript(
                f"if(window.{fn}) {fn}({flag}, {t_json});"
            )
        except Exception:
            pass

    def on_visibility_changed(self, visible):
        """RAM-Management Logik"""
        if visible:
            self.load_content()
        else:
            if not self.is_in_fullscreen and not self.is_embedded:
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
    if not mindmap_dock:
        return

    dock_ref = mindmap_dock
    panel = dock_ref.widget()

    def dispose(saved: bool) -> None:
        global mindmap_dock
        if not saved:
            # Do not deliberately destroy the only live copy when both
            # LocalStorage and the recovery-file write failed.
            return
        try:
            mw.removeDockWidget(dock_ref)
        except Exception:
            pass
        dock_ref.deleteLater()
        if mindmap_dock is dock_ref:
            mindmap_dock = None

    if isinstance(panel, MindmapPanel):
        if panel.fullscreen_window:
            panel.fullscreen_window.close()
        if panel.is_embedded:
            panel.exit_window()
        panel.unload_content(dispose)
    else:
        dispose(True)
