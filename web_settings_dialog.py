# -*- coding: utf-8 -*-
"""
SynapsePro — Web-based Settings Dialog
======================================
A QWebEngineView-hosted settings UI (settings_web/settings.html) that mirrors
the same console.log bridge used by the onboarding dialog.

Bridge protocol (JS -> Python), every message is a console.log of the form
``SYNAPSEPRO_SETTINGS:<action>[:<payload>]``:

    ready                -> Python injects the current config via initSettings(...)
    save:<json>          -> store the new settings and accept() the dialog
    cancel               -> reject() the dialog
    editTheme            -> open the native colour editor, push the result back
    editShortcut:<key>   -> record a native Qt shortcut for one sidebar tool
    openUrl:<url>        -> open the url in the system browser

Public API (matches the native SettingsDialog so __init__.show_settings_dialog
can use either):
    dlg = WebSettingsDialog(addon_settings, mw)
    if dlg.is_available() and dlg.exec():
        new = dlg.get_new_settings()
"""

import os
import json
import base64
import threading
import time
from typing import Any, Dict, Optional

try:
    from . import constants
except Exception:
    class _C:  # pragma: no cover - safety fallback
        addon_path = "."; icons_folder = "."; ADDON_DISPLAY_NAME = "SynapsePro"; ADDON_VERSION = ""
    constants = _C()  # type: ignore

try:
    from .web_i18n import translations as _web_translations
except Exception:
    def _web_translations(_surface): return {}  # type: ignore

try:
    from . import sidebar_shortcuts
except Exception:
    sidebar_shortcuts = None  # type: ignore

try:
    from .locales import _
except Exception:
    def _(text):  # type: ignore
        return text

try:
    from aqt import mw
except Exception:
    mw = None  # type: ignore

# ── Qt 6 imports ───────────────────────────────────────────────────────────────
_QT_AVAILABLE = False
try:
    from aqt.qt import (
        QDialog, QDialogButtonBox, QKeySequence, QKeySequenceEdit, QLabel,
        QPushButton, QVBoxLayout, QDesktopServices, QUrl, Qt, pyqtSignal,
    )
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
    from PyQt6.QtGui import QColor
    _QT_AVAILABLE = True
except ImportError:
    pass


# Accent (blue) + pressed colour for each preset — kept in sync with the HTML.
_PRESET_ACCENTS = {
    "ocean":   ("#0071D3", "#004990"),
    "orchid":  ("#E95ACC", "#CB51B3"),
    "forest":  ("#619971", "#477154"),
    "deluge":  ("#7961A9", "#65508D"),
    "horizon": ("#6183A9", "#4B6683"),
    "dusty":   ("#5A9491", "#4E8280"),
}
_THEME_LOGOS = {
    "ocean":   "logo.svg",
    "orchid":  "logo_orchid.svg",
    "forest":  "logo_forest.svg",
    "deluge":  "logo_deluge.svg",
    "horizon": "logo_horizon.svg",
    "dusty":   "logo_dusty.svg",
}

# Home/news banner. The fixed config endpoint is controlled by SynapsePro and
# can update the image and click target without shipping a new add-on version.
HOME_BANNER_URL = "https://www.synapse-pro.de/addon/home_banner.png"
HOME_BANNER_LINK = "https://www.synapse-pro.de/"
HOME_BANNER_CONFIG_URL = "https://www.synapse-pro.de/addon/home_banner.json"
NEWS_BANNER_FALLBACK_FILENAME = "news-banner.png"

SUPPORTERS = [
    {
        "name": "FleggaBDog69",
        "description": (
            "Contributed feature ideas through a GitHub pull request. The concepts "
            "were reviewed and adapted to fit SynapsePro."
        ),
        "contributions": [
            "Configurable keyboard shortcuts for individual features",
            "SoundCloud support for the Music Player",
            "Claude CLI as a local API provider",
        ],
    },
    {
        "name": "o3LL",
        "description": (
            "Helped through a GitHub pull request. The changes were reviewed "
            "and adapted to fit SynapsePro."
        ),
        "contributions": [
            "llama.cpp server support as a local AI provider",
        ],
    },
]

SUPPORTERS_NOTE = (
    "Thank you as well to everyone else who shares suggestions. I always need some "
    "time to review each idea and adapt it to fit the direction of SynapsePro, so "
    "please do not take it personally if I cannot implement everything. It is a "
    "great honor that people want to contribute to my project."
)

# Config keys that are simple on/off toggles.
_TOGGLE_KEYS = [
    "minimal_dashboard_enabled",
    "gamification_widgets_enabled", "daily_widgets_enabled", "deadline_bar_enabled",
    "statistics_widget_enabled", "deck_overview_enabled", "mindmap_enabled",
    "gamification_sidebar_enabled", "music_player_enabled", "pomodoro_enabled",
    "ai_assistant_enabled", "website_viewer_enabled", "notebook_enabled",
]


def _html_path() -> str:
    base = getattr(constants, "addon_path", "") or os.path.dirname(__file__)
    return os.path.join(base, "settings_web", "settings.html")


if _QT_AVAILABLE:

    class _SettingsPage(QWebEnginePage):
        """Intercepts the console.log bridge messages from the page."""
        message = pyqtSignal(str)

        def javaScriptConsoleMessage(self, level, message, line, source):
            PREFIX = "SYNAPSEPRO_SETTINGS:"
            if isinstance(message, str) and message.startswith(PREFIX):
                try:
                    self.message.emit(message[len(PREFIX):])
                except Exception as e:
                    print(f"WebSettings: bridge emit failed: {e}")

    class WebSettingsDialog(QDialog):
        def __init__(self, current_config: Dict, parent=None):
            super().__init__(parent)
            self.current_config = dict(current_config or {})
            self._custom_theme_colors = dict(self.current_config.get("custom_theme_colors", {}))
            self._shortcut_values = (
                sidebar_shortcuts.normalise_shortcut_map(
                    self.current_config.get("sidebar_shortcuts", {})
                )
                if sidebar_shortcuts else {}
            )
            self._result: Optional[Dict] = None
            self._injected = False

            html = _html_path()
            self._available = os.path.exists(html)
            if not self._available:
                print(f"WebSettings: not available (html exists={os.path.exists(html)})")
                return

            self.setWindowTitle(f"{getattr(constants, 'ADDON_DISPLAY_NAME', 'SynapsePro')} - {_('Settings')}")
            self.resize(900, 640)
            self.setMinimumSize(640, 460)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            self._view = QWebEngineView(self)
            self._page = _SettingsPage(self._view)
            self._view.setPage(self._page)
            self._page.message.connect(self._on_message)
            self._view.loadFinished.connect(self._on_load_finished)
            layout.addWidget(self._view)

            # The local Settings page intentionally loads the SynapsePro news
            # banner. Other local add-on pages do not receive this permission.
            try:
                self._view.settings().setAttribute(
                    QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
                    True,
                )
                self._view.settings().setAttribute(
                    QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard,
                    True,
                )
            except Exception as e:
                print(f"WebSettings: could not enable optional web permissions: {e}")

            # Match the page background to the theme BEFORE anything paints —
            # otherwise the view flashes white in dark mode while loading.
            try:
                self._page.setBackgroundColor(
                    QColor("#1c1c1e") if self._is_night() else QColor("#ffffff"))
            except Exception:
                pass

            self._view.setUrl(QUrl.fromLocalFile(html))

        # -- public API ------------------------------------------------------
        def is_available(self) -> bool:
            return bool(self._available)

        def get_new_settings(self) -> Dict:
            s = dict(self._result or {})
            # custom colours are managed natively (see _edit_theme), not in JS.
            s["custom_theme_colors"] = self._custom_theme_colors
            try:
                s["stats_time_range"] = int(s.get("stats_time_range", 7))
            except Exception:
                s["stats_time_range"] = 7
            if sidebar_shortcuts:
                s["sidebar_shortcuts"] = sidebar_shortcuts.normalise_shortcut_map(
                    s.get("sidebar_shortcuts", self._shortcut_values)
                )
            else:
                s["sidebar_shortcuts"] = dict(self._shortcut_values)
            return s

        # -- bridge ----------------------------------------------------------
        def _on_load_finished(self, ok: bool):
            if ok:
                self._inject()
                self._start_banner_config_fetch()

        def _on_message(self, rest: str):
            action, _sep, payload = rest.partition(":")
            try:
                if action == "ready":
                    self._inject()
                elif action == "save":
                    self._on_save(payload)
                elif action == "cancel":
                    self.reject()
                elif action == "editTheme":
                    self._edit_theme()
                elif action == "editShortcut":
                    self._edit_shortcut(payload)
                elif action == "openUrl":
                    if payload:
                        QDesktopServices.openUrl(QUrl(payload))
            except Exception as e:
                print(f"WebSettings: error handling '{action}': {e}")

        def _inject(self):
            if self._injected:
                return
            self._injected = True
            try:
                payload = json.dumps(self._build_payload())
                self._page.runJavaScript(f"window.initSettings && initSettings({payload});")
            except Exception as e:
                print(f"WebSettings: inject failed: {e}")

        def _start_banner_config_fetch(self):
            """Fetch the optional SynapsePro news-banner configuration."""
            if getattr(self, "_banner_cfg_started", False):
                return
            self._banner_cfg_started = True

            def worker():
                try:
                    import urllib.request
                    req = urllib.request.Request(
                        f"{HOME_BANNER_CONFIG_URL}?v={int(time.time())}",
                        headers={"User-Agent": "SynapsePro"},
                    )
                    with urllib.request.urlopen(req, timeout=4) as response:
                        raw = response.read(65_537)
                    if len(raw) > 65_536:
                        raise ValueError("news banner config is larger than 64 KiB")
                    cfg = json.loads(raw.decode("utf-8"))
                    if not isinstance(cfg, dict):
                        return
                    out = {}
                    link = cfg.get("link")
                    image = cfg.get("image")
                    if isinstance(link, str) and link.startswith(("http://", "https://")):
                        out["link"] = link
                    if isinstance(image, str) and image.startswith(("http://", "https://")):
                        out["image"] = image
                    if not out:
                        return
                    data = json.dumps(out)

                    def apply():
                        try:
                            self._page.runJavaScript(
                                f"window.updateBanner && updateBanner({data});"
                            )
                        except Exception:
                            pass

                    if mw is not None:
                        mw.taskman.run_on_main(apply)
                except Exception as exc:
                    # Offline mode and a temporarily unavailable news endpoint
                    # must not prevent Settings from opening.
                    print(f"WebSettings: news banner unavailable: {exc}")

            threading.Thread(target=worker, daemon=True).start()

        def _on_save(self, payload: str):
            try:
                self._result = json.loads(payload) if payload else {}
            except Exception as e:
                print(f"WebSettings: bad save payload: {e}")
                self._result = {}
            self.accept()

        def _edit_theme(self):
            try:
                from . import theme_editor_dialog
                from .theme import COLOR_THEMES
                active = self.current_config.get("active_color_theme", "ocean")
                if self._custom_theme_colors:
                    initial = dict(self._custom_theme_colors)
                else:
                    preset = active if active in COLOR_THEMES else "ocean"
                    raw = COLOR_THEMES[preset][False]
                    initial = {k: raw[k] for k in ("blue", "blue_hover", "blue_pressed", "blue_bright")}
                dlg = theme_editor_dialog.ThemeEditorDialog(initial, self)
                if dlg.exec():
                    self._custom_theme_colors = dlg.get_colors()
                    c = self._custom_theme_colors
                    accent = c.get("blue", "#0071D3")
                    press = c.get("blue_pressed", c.get("blue_hover", "#004990"))
                    data = json.dumps({"accent": accent, "accentPress": press})
                    self._page.runJavaScript(f"window.applyCustomTheme && applyCustomTheme({data});")
            except Exception as e:
                print(f"WebSettings: theme editor error: {e}")

        def _edit_shortcut(self, feature_key: str):
            """Record one native Qt key chord and return it to the web UI."""
            if (
                not sidebar_shortcuts
                or feature_key not in constants.SIDEBAR_SHORTCUT_KEYS
            ):
                return
            try:
                feature = _(sidebar_shortcuts.FEATURE_LABELS.get(feature_key, "Sidebar"))
                dlg = QDialog(self)
                dlg.setWindowTitle(_("Keyboard Shortcut") + f" — {feature}")
                dlg.setModal(True)
                dlg.setMinimumWidth(390)

                layout = QVBoxLayout(dlg)
                prompt = QLabel(_("Press the desired key combination."))
                prompt.setWordWrap(True)
                layout.addWidget(prompt)

                edit = QKeySequenceEdit(dlg)
                try:
                    edit.setMaximumSequenceLength(1)
                    edit.setClearButtonEnabled(True)
                except (AttributeError, TypeError):
                    pass
                current = self._shortcut_values.get(feature_key, "")
                if current:
                    edit.setKeySequence(QKeySequence.fromString(
                        current, QKeySequence.SequenceFormat.PortableText
                    ))
                layout.addWidget(edit)

                hint = QLabel(_("Use Ctrl, Alt, Command or a function key."))
                hint.setWordWrap(True)
                hint.setStyleSheet("color:#8e8e93;font-size:11px;")
                layout.addWidget(hint)

                error = QLabel("")
                error.setWordWrap(True)
                error.setStyleSheet("color:#d93025;font-size:11px;")
                layout.addWidget(error)

                buttons = QDialogButtonBox(
                    QDialogButtonBox.StandardButton.Save
                    | QDialogButtonBox.StandardButton.Cancel,
                    parent=dlg,
                )
                clear_button = buttons.addButton(
                    _("Clear Shortcut"), QDialogButtonBox.ButtonRole.ResetRole
                )
                layout.addWidget(buttons)

                def clear_value():
                    edit.clear()
                    error.clear()

                def save_value():
                    raw = edit.keySequence().toString(
                        QKeySequence.SequenceFormat.PortableText
                    )
                    portable = sidebar_shortcuts.normalise_sequence(raw)
                    if raw and not sidebar_shortcuts.is_safe_sequence(raw):
                        error.setText(_("Use Ctrl, Alt, Command or a function key."))
                        return
                    for other_key, other_value in self._shortcut_values.items():
                        if other_key != feature_key and portable and other_value == portable:
                            other = _(sidebar_shortcuts.FEATURE_LABELS.get(other_key, "Sidebar"))
                            error.setText(
                                _("This shortcut is already assigned to {feature}.").format(
                                    feature=other
                                )
                            )
                            return
                    conflict = sidebar_shortcuts.find_existing_conflict(portable, mw)
                    if portable and conflict:
                        error.setText(
                            _("This shortcut is already used by Anki: {action}.").format(
                                action=conflict
                            )
                        )
                        return

                    if portable:
                        self._shortcut_values[feature_key] = portable
                    else:
                        self._shortcut_values.pop(feature_key, None)
                    data = {
                        "key": feature_key,
                        "value": portable,
                        "display": sidebar_shortcuts.display_sequence(portable),
                    }
                    self._page.runJavaScript(
                        "window.setSidebarShortcut && setSidebarShortcut(%s);"
                        % json.dumps(data)
                    )
                    dlg.accept()

                clear_button.clicked.connect(clear_value)
                buttons.accepted.connect(save_value)
                buttons.rejected.connect(dlg.reject)
                dlg.exec()
            except Exception as e:
                print(f"WebSettings: shortcut editor error: {e}")

        # -- payload helpers -------------------------------------------------
        def _is_night(self) -> bool:
            try:
                return bool(mw and hasattr(mw, "pm") and mw.pm.night_mode())
            except Exception:
                return False

        def _accent_for(self, key: str):
            if key == "custom" and self._custom_theme_colors:
                c = self._custom_theme_colors
                return c.get("blue", "#0071D3"), c.get("blue_pressed", c.get("blue_hover", "#004990"))
            return _PRESET_ACCENTS.get(key, _PRESET_ACCENTS["ocean"])

        def _logo_uri(self, filename: str) -> str:
            try:
                path = os.path.join(constants.icons_folder, filename)
                if not os.path.exists(path):
                    path = os.path.join(constants.icons_folder, "logo.svg")
                with open(path, "rb") as fh:
                    return "data:image/svg+xml;base64," + base64.b64encode(fh.read()).decode("ascii")
            except Exception:
                return ""

        def _logos(self) -> Dict[str, str]:
            out = {k: self._logo_uri(f) for k, f in _THEME_LOGOS.items()}
            out["custom"] = out.get("ocean", "")
            return out

        def _png_uri(self, filename: str) -> str:
            """Return one bundled PNG as an embeddable data URI."""
            try:
                path = os.path.join(constants.icons_folder, filename)
                if not os.path.isfile(path):
                    return ""
                with open(path, "rb") as fh:
                    return "data:image/png;base64," + base64.b64encode(fh.read()).decode("ascii")
            except Exception:
                return ""

        def _banner_fallback_uri(self) -> str:
            """Single bundled banner shown whenever remote news is unavailable."""
            return self._png_uri(NEWS_BANNER_FALLBACK_FILENAME)

        def _background_themes(self):
            items = []
            try:
                theme_path = os.path.join(getattr(constants, "addon_path", "."), "theme", "user_files")
                files = sorted(f for f in os.listdir(theme_path) if f.endswith(".css")) if os.path.exists(theme_path) else []
            except Exception:
                files = []
            if not files:
                files = ["medical_theme.css"]
            for f in files:
                if f == "custom_solid.css":
                    continue  # represented by the dedicated "Custom Color…" entry
                if f.startswith("solid_"):
                    continue  # solid presets retired — use the free colour picker
                if f == "medical_theme.css":
                    label = _("Default")
                else:
                    label = f.replace(".css", "").replace("_", " ").title()
                items.append({"value": f, "label": label, "group": "gradient"})
            items.sort(key=lambda i: i["label"])
            return items

        def _changelog(self):
            try:
                from .changelog import CHANGELOG
                return [
                    {
                        **entry,
                        "items": [dict(item) if isinstance(item, dict) else {"text": str(item)}
                                  for item in entry.get("items", [])],
                    }
                    for entry in CHANGELOG
                ]
            except Exception as e:
                print(f"WebSettings: changelog load failed: {e}")
                return []

        def _build_payload(self) -> Dict[str, Any]:
            cfg = self.current_config
            active = cfg.get("active_color_theme", "ocean")
            accent, accent_press = self._accent_for(active)
            conf = {
                "language": cfg.get("language", "auto"),
                "fact_theme": cfg.get("fact_theme", "Medical"),
                "stats_time_range": int(cfg.get("stats_time_range", 7) or 7),
                "sidebar_visibility_mode": cfg.get("sidebar_visibility_mode", "always_show"),
                "active_theme": cfg.get("active_theme", "medical_theme.css"),
                "active_color_theme": active,
                "custom_bg_light": cfg.get("custom_bg_light", "#f5f5f7"),
                "custom_bg_dark": cfg.get("custom_bg_dark", "#1f1f21"),
                "sidebar_shortcuts": dict(self._shortcut_values),
            }
            for k in _TOGGLE_KEYS:
                default = False if k == "minimal_dashboard_enabled" else True
                conf[k] = bool(cfg.get(k, default))
            banner_fallback = self._banner_fallback_uri()
            return {
                "displayName": getattr(constants, "ADDON_DISPLAY_NAME", "SynapsePro"),
                "version": getattr(constants, "ADDON_VERSION", ""),
                "isDark": self._is_night(),
                "translations": _web_translations("settings"),
                "accent": accent,
                "accentPress": accent_press,
                "logos": self._logos(),
                "banner": {
                    "url": HOME_BANNER_URL,
                    "link": HOME_BANNER_LINK,
                    "fallback": banner_fallback,
                },
                "backgroundThemes": self._background_themes(),
                "shortcutDisplays": {
                    key: sidebar_shortcuts.display_sequence(value)
                    for key, value in self._shortcut_values.items()
                } if sidebar_shortcuts else dict(self._shortcut_values),
                "changelog": self._changelog(),
                "supporters": SUPPORTERS,
                "supportersNote": SUPPORTERS_NOTE,
                "aboutLogo": self._png_uri("logo_mobesa.png"),
                "config": conf,
            }

else:  # pragma: no cover - WebEngine unavailable

    class WebSettingsDialog:  # type: ignore
        def __init__(self, current_config=None, parent=None):
            self._available = False

        def is_available(self) -> bool:
            return False

        def exec(self) -> int:
            return 0

        def get_new_settings(self) -> Dict:
            return {}
