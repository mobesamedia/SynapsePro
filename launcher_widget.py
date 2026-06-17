# -*- coding: utf-8 -*-

import os
import traceback
import webbrowser
from functools import partial
from typing import Optional, TYPE_CHECKING, Callable, Dict, Any
import weakref

# --- Local Imports ---
try:
    from . import constants
    from . import study_plan_trigger
except ImportError as e:
    print(f"Launcher Widget CRITICAL ERROR: Failed to import constants or study_plan_trigger: {e}")
    class MockConstants:
        qt_version = 0; icons_folder = "."; SIDEBAR_BG_COLOR_HEX="#FFFFFF"; BUTTON_HOVER_PRESSED_COLOR="#0071D3"; BUTTON_ACTIVE_BG_COLOR="#0071D3"; DEFAULT_TEXT_COLOR="#333333"; SEPARATOR_LINE_COLOR="#888888"; TIMER_LABEL_COLOR="#888888"; TIMER_BUTTON_HOVER_COLOR="#d0d0d0"; TIMER_BUTTON_PRESSED_COLOR="#b0b0b0"; SIDEBAR_WIDTH = 55; BUTTON_ICON_SIZE = 30; TIMER_BUTTON_ICON_SIZE = 18; BUTTON_BORDER_RADIUS = 8; LOGO_FILENAME = "logo.svg"; START_ICON_FILENAME = "start.svg"; PAUSE_ICON_FILENAME = "pause.svg"; RESET_ICON_FILENAME = "reset.svg"; SKIP_ICON_FILENAME = "skip.svg"; AI_TOOL_ICON_FILENAME = "ai_tool.svg"; WEBSITE_ICON_FILENAME = "website.svg"; NOTEBOOK_ICON_FILENAME = "notes.svg"; MINDMAP_ICON_FILENAME = "mindmap.svg"; GAME_ICON_FILENAME = "game.svg"; STUDY_PLAN_ICON_FILENAME = "study_plan.svg"; TIMER_ICON_FILENAME = "timer.svg"; MUSIC_ICON_FILENAME = "music.svg";
        AI_ASSISTANT_DOCK_OBJECT_NAME = "AIAssistantSidebarDock_Integrated_v1"; WEBSITE_DOCK_OBJECT_NAME = "IntegratedWebsiteSidebarDock_Mobesa_v1"; NOTEBOOK_DOCK_OBJECT_NAME = "IntegratedNotebookSidebarDock_Mobesa_v1"; MINDMAP_DOCK_OBJECT_NAME = "IntegratedMindmapSidebarDock_Mobesa_v1"; HOSPITAL_GAME_DOCK_OBJECT_NAME = "hospitalClickerGameDock"; DEFAULT_POMODORO_CONFIG = {"work_minutes": 25}; STATE_IDLE = 0; STATE_WORK = 1; STATE_SHORT_BREAK = 2; STATE_LONG_BREAK = 3; STATE_PAUSED = 4; addon_package_name = "Study Suite Addon"; ADDON_VERSION = "Unknown Version"; INFO_IMAGE_FILENAME = "info.png"; INFO_IMAGE_WIDTH = 200
    constants = MockConstants()
    class MockStudyPlanTrigger:
        trigger_study_plan_action = lambda: print("ERROR: Study Plan Trigger module failed to load.")
        trigger_gamification_sidebar_action = lambda: print("ERROR: Study Plan Trigger module failed to load.")
    study_plan_trigger = MockStudyPlanTrigger()

# --- PyQt Imports ---
QWidget, QVBoxLayout, QPushButton, QSizePolicy, QStyle = object, object, object, object, object
QLabel, QFrame, QDockWidget, QHBoxLayout = object, object, object, object
QIcon, QPixmap, QPalette, QColor, QFont, QMessageBox = object, object, object, object, object, object
QSize, Qt, QTimer, QEvent, QObject = object, object, object, object, object
Slot = object
MouseButton = None
QSvgWidget = object
QSvgRenderer = object
QStackedWidget = object
QByteArray = object
QDialog, QDialogButtonBox = object, object

if constants.qt_version == 6:
    try:
        from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QSizePolicy, QStyle, QLabel,
                                     QFrame, QDockWidget, QHBoxLayout, QMessageBox, QDialog, QDialogButtonBox,
                                     QStackedWidget)
        from PyQt6.QtGui import QIcon, QPixmap, QPalette, QColor, QFont, QPainter
        from PyQt6.QtCore import QSize, Qt, QTimer, QEvent, QObject, QByteArray
        try: from PyQt6.QtSvgWidgets import QSvgWidget; from PyQt6.QtSvg import QSvgRenderer
        except ImportError: QSvgWidget = object; QSvgRenderer = object
        MouseButton = Qt.MouseButton; Slot = None
    except ImportError as e: constants.qt_version = 0
elif constants.qt_version == 5:
    try:
        from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QSizePolicy, QStyle, QLabel,
                                     QFrame, QDockWidget, QHBoxLayout, QMessageBox, QDialog, QDialogButtonBox,
                                     QStackedWidget)
        from PyQt5.QtGui import QIcon, QPixmap, QPalette, QColor, QFont, QPainter
        from PyQt5.QtCore import QSize, Qt, QTimer, QEvent, QObject, QByteArray, pyqtSlot as Slot
        try: from PyQt5.QtSvgWidgets import QSvgWidget; from PyQt5.QtSvg import QSvgRenderer
        except ImportError: QSvgWidget = object; QSvgRenderer = object
        MouseButton = Qt.MouseButton
    except ImportError as e: constants.qt_version = 0
else: constants.qt_version = 0


# --- Local Component Module Imports ---
try:
    from . import pomodoro, website_sidebar, background_music, ai_assistant, mindmap_sidebar, notebook_sidebar
except ImportError as e:
    pomodoro = website_sidebar = background_music = ai_assistant = mindmap_sidebar = notebook_sidebar = object()

# --- Anki Imports ---
if QWidget is not object:
    try: from aqt import mw; from aqt.utils import qconnect, tooltip, showWarning
    except ImportError: mw = None; qconnect = lambda *a: None; tooltip = lambda *a,**k: None; showWarning = lambda *a,**k: None
else: mw = None; qconnect = lambda *a: None; tooltip = lambda *a,**k: None; showWarning = lambda *a,**k: None

try:
    from .locales import _
except ImportError:
    def _(text):  # type: ignore
        return text

# --- Type Hinting ---
if TYPE_CHECKING:
    from PyQt6.QtWidgets import QPushButton as PushButtonType, QWidget as WidgetType, QLabel as LabelType, QDockWidget as DockWidgetType
    from PyQt6.QtGui import QIcon as IconType
    from PyQt6.QtCore import QEvent as EventType, QObject as ObjectType
    from . import pomodoro, website_sidebar, background_music, ai_assistant, mindmap_sidebar, notebook_sidebar
    from .study_plan_trigger import trigger_gamification_sidebar_action, trigger_study_plan_action


# Optional callback invoked whenever a feature panel dock shows/hides.
# Set by __init__.py so the launcher can be auto-revealed mid-review when a
# panel is open. Left as None when running standalone.
feature_visibility_callback = None


class SidebarWidget(QWidget):
    def __init__(self, parent: Optional['QWidget'] = None, settings_dialog_trigger: Optional[Callable] = None, settings: Optional[Dict[str, Any]] = None):
        if QWidget is object: return
        super().__init__(parent)
        
        self.settings = settings or {}
        self.settings_dialog_trigger = settings_dialog_trigger
        
        self.setObjectName("SidebarContent")

        try:
            if constants.qt_version == 6:
                self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            else:
                self.setAttribute(Qt.WA_StyledBackground, True)
        except Exception: pass

        if QPalette is not object and QColor is not object:
            try: 
                pal = self.palette()
                bg_color_hex = getattr(constants, 'SIDEBAR_BG_COLOR_HEX', '#FFFFFF')
                
                if mw and hasattr(mw, 'pm') and mw.pm.night_mode():
                    bg_color_hex = "#2C2C2C"
                
                pal.setColor(QPalette.ColorRole.Window, QColor(bg_color_hex))
                self.setPalette(pal)
                self.setAutoFillBackground(True)
            except Exception: self.setAutoFillBackground(True)
        else: self.setAutoFillBackground(True)
        
        self.logo_widget: Optional['QWidget'] = None
        self._logo_stack: Optional['QWidget'] = None
        self._settings_svg_widget: Optional['QWidget'] = None
        self._dock_visibility_connections: dict[str, tuple[Optional[weakref.ReferenceType['DockWidgetType']], object]] = {}
        self._timer_widget_container: Optional['WidgetType'] = None; self._timer_time_label: Optional['LabelType'] = None
        self._timer_start_pause_button: Optional['PushButtonType'] = None; self._timer_reset_button: Optional['PushButtonType'] = None; self._timer_skip_button: Optional['PushButtonType'] = None
        self._start_icon: Optional['IconType'] = None; self._pause_icon: Optional['IconType'] = None; self._reset_icon: Optional['IconType'] = None; self._skip_icon: Optional['IconType'] = None
        self.init_ui()
        self.apply_stylesheet()
        
        if mw:
            try:
                from aqt import gui_hooks
                gui_hooks.theme_did_change.append(self.apply_stylesheet)
            except Exception:
                pass

    def _load_timer_icons(self):
        if QIcon is object: return
        self._start_icon = self._create_qicon_helper(constants.START_ICON_FILENAME)
        self._pause_icon = self._create_qicon_helper(constants.PAUSE_ICON_FILENAME)
        self._reset_icon = self._create_qicon_helper(constants.RESET_ICON_FILENAME)
        self._skip_icon = self._create_qicon_helper(constants.SKIP_ICON_FILENAME)

    def _create_qicon_helper(self, filename: str) -> Optional['IconType']:
        if QIcon is object or not hasattr(constants, 'icons_folder'): return None
        path = os.path.join(constants.icons_folder, filename)
        if os.path.exists(path):
            try:
                icon = QIcon(path)
                if not icon.isNull(): return icon
            except Exception: pass
        return None

    def init_ui(self):
        if any(cls is object for cls in [QWidget, QVBoxLayout, QPushButton, QLabel, QFrame, QSize, Qt]): return
        if not mw: return

        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(5, 10, 5, 10); main_layout.setSpacing(8)
        
        logo_path = self._get_logo_path()
        target_width = getattr(constants, 'SIDEBAR_WIDTH', 55) - 15

        if QSvgWidget is not object and QStackedWidget is not object and os.path.exists(logo_path):
            # Page 0 – the theme logo
            _logo_svg = QSvgWidget(logo_path)
            _logo_svg.setFixedSize(QSize(target_width, target_width))
            _logo_svg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

            # Page 1 – the settings gear icon (coloured with theme accent)
            self._settings_svg_widget = QSvgWidget()
            self._settings_svg_widget.setFixedSize(QSize(target_width, target_width))
            self._settings_svg_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self._refresh_settings_icon()

            # Stack the two pages
            self._logo_stack = QStackedWidget()
            self._logo_stack.setFixedSize(QSize(target_width, target_width))
            self._logo_stack.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self._logo_stack.addWidget(_logo_svg)                  # index 0 – logo
            self._logo_stack.addWidget(self._settings_svg_widget)  # index 1 – settings
            self._logo_stack.setCurrentIndex(0)
            self.logo_widget = self._logo_stack
        else:
            self.logo_widget = QLabel(_("Logo"))
            self.logo_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.logo_widget.setToolTip(_("Open Add-on Settings"))
        self.logo_widget.installEventFilter(self)
        try:
            if constants.qt_version == 6:
                self.logo_widget.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.logo_widget.setCursor(Qt.PointingHandCursor)
        except Exception:
            pass
        main_layout.addWidget(self.logo_widget); main_layout.addSpacing(15); main_layout.addStretch(1)

        feature_map = {
            constants.AI_TOOL_ICON_FILENAME: ("ai_assistant_enabled", getattr(ai_assistant, 'toggle_ai_assistant_dock', None), constants.AI_ASSISTANT_DOCK_OBJECT_NAME),
            constants.WEBSITE_ICON_FILENAME: ("website_viewer_enabled", getattr(website_sidebar, 'toggle_website_dock', None), constants.WEBSITE_DOCK_OBJECT_NAME),
            constants.NOTEBOOK_ICON_FILENAME: ("notebook_enabled", getattr(notebook_sidebar, 'toggle_notebook_dock', None), constants.NOTEBOOK_DOCK_OBJECT_NAME),
            constants.MINDMAP_ICON_FILENAME: ("mindmap_enabled", getattr(mindmap_sidebar, 'toggle_mindmap_dock', None), constants.MINDMAP_DOCK_OBJECT_NAME),
            constants.GAME_ICON_FILENAME: ("gamification_sidebar_enabled", getattr(study_plan_trigger, 'trigger_gamification_sidebar_action', None), None),
            constants.STUDY_PLAN_ICON_FILENAME: ("daily_widgets_enabled", getattr(study_plan_trigger, 'trigger_study_plan_action', None), None),
        }
        
        top_icon_definitions = [
            (constants.AI_TOOL_ICON_FILENAME, _("Show/Hide AI Assistant")), (constants.WEBSITE_ICON_FILENAME, _("Show/Hide Website Viewer")),
            (constants.NOTEBOOK_ICON_FILENAME, _("Show/Hide Notebook")), (constants.MINDMAP_ICON_FILENAME, _("Show/Hide Mind Map")),
            (constants.GAME_ICON_FILENAME, _("Toggle Gamification Sidebar")),
            (constants.STUDY_PLAN_ICON_FILENAME, _("Configure Study Plan")),
        ]
        buttons_to_connect: dict[weakref.ReferenceType[QPushButton], str] = {}
        for icon_const, tooltip_text in top_icon_definitions:
            if icon_const not in feature_map: continue
            setting_key, action_func, dock_name = feature_map[icon_const]
            
            if self.settings.get(setting_key, True):
                button = self.create_icon_button(icon_const, tooltip_text)
                if button and callable(action_func):
                    btn_ref = weakref.ref(button)
                    qconnect(button.clicked, partial(self._handle_feature_click, action_func, dock_name, btn_ref))
                    
                    if dock_name: buttons_to_connect[btn_ref] = dock_name
                    
                    if icon_const == constants.STUDY_PLAN_ICON_FILENAME:
                        button.setCheckable(False)

                    button.installEventFilter(self)
                    main_layout.addWidget(button)
                elif button:
                    button.setEnabled(False)
                    main_layout.addWidget(button)

        main_layout.addStretch(1)

        if self.settings.get("pomodoro_enabled", True) and hasattr(pomodoro, 'format_time'):
            self._load_timer_icons()

            self._timer_widget_container = QWidget()
            self._timer_widget_container.setObjectName("timerContainer")
            timer_layout = QVBoxLayout(self._timer_widget_container)
            timer_layout.setContentsMargins(2, 5, 2, 5); timer_layout.setSpacing(4)

            try: time_text = pomodoro.format_time(pomodoro.get_current_phase_duration())
            except Exception: time_text = pomodoro.format_time(constants.DEFAULT_POMODORO_CONFIG.get("work_minutes", 25) * 60)
            self._timer_time_label = QLabel(time_text); self._timer_time_label.setObjectName("timerTimeLabel")
            font = QFont(); font.setBold(True); self._timer_time_label.setFont(font)
            self._timer_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            timer_layout.addWidget(self._timer_time_label)

            self._timer_start_pause_button = self.create_timer_button(self._start_icon, _("Start/Pause Timer"), getattr(pomodoro, 'start_pause_action', None))
            self._timer_reset_button = self.create_timer_button(self._reset_icon, _("Reset Timer"), getattr(pomodoro, 'reset_action', None))
            self._timer_skip_button = self.create_timer_button(self._skip_icon, _("Skip current phase"), getattr(pomodoro, 'skip_action', None))
            
            timer_layout.addWidget(self._timer_start_pause_button); timer_layout.addWidget(self._timer_reset_button); timer_layout.addWidget(self._timer_skip_button)
            
            main_layout.addWidget(self._timer_widget_container)

            line_bottom = QFrame(); line_bottom.setObjectName("bottomSeparatorLine")
            line_bottom.setFrameShape(QFrame.Shape.HLine); line_bottom.setFrameShadow(QFrame.Shadow.Sunken)
            main_layout.addWidget(line_bottom)
            
            self._timer_icon_button = self.create_icon_button(constants.TIMER_ICON_FILENAME, _("Pomodoro Timer Settings"))
            if self._timer_icon_button:
                self._timer_icon_button.setCheckable(False)
                if hasattr(pomodoro, 'open_pomodoro_config'): qconnect(self._timer_icon_button.clicked, pomodoro.open_pomodoro_config)
                else: self._timer_icon_button.setEnabled(False)
                main_layout.addWidget(self._timer_icon_button)
                self._timer_icon_button.installEventFilter(self)

            if self.settings.get("music_player_enabled", True):
                self._music_button = self.create_icon_button(constants.MUSIC_ICON_FILENAME, _("Play Music"))
                if self._music_button:
                    self._music_button.setCheckable(False)
                    if hasattr(background_music, 'toggle_music_menu'):
                        btn_ref = weakref.ref(self._music_button)
                        qconnect(self._music_button.clicked, lambda _checked, b=btn_ref: background_music.toggle_music_menu(b()))
                    else: self._music_button.setEnabled(False)
                    main_layout.addWidget(self._music_button)
                    self._music_button.installEventFilter(self)
            
            self.update_timer_ui()
        
        for button_ref, dock_name in buttons_to_connect.items():
            QTimer.singleShot(500, partial(self._setup_dock_visibility_connection, button_weak_ref=button_ref, dock_object_name=dock_name))

    def _handle_feature_click(self, action_func: Callable, dock_name: Optional[str], button_weak_ref: weakref.ReferenceType['PushButtonType']):
        """
        Handles the button click. Executes the module action first (which should lazy-load 
        the widget if it's not created yet), then attempts to connect the visibility listeners.
        """
        try:
            if callable(action_func):
                action_func()
        except Exception as e:
            print(f"Error executing sidebar action: {e}")

        if dock_name and dock_name not in self._dock_visibility_connections:
            self._setup_dock_visibility_connection(button_weak_ref, dock_name)

    def _setup_dock_visibility_connection(self, button_weak_ref: weakref.ReferenceType['PushButtonType'], dock_object_name: str):
        button = button_weak_ref() if button_weak_ref else None
        if not mw or not button or not callable(qconnect): return
        try:
            target_dock: Optional['DockWidgetType'] = mw.findChild(QDockWidget, dock_object_name)
            if target_dock:
                connection_slot = partial(self._update_button_active_state_from_ref, button_weak_ref=button_weak_ref)
                self._dock_visibility_connections[dock_object_name] = (weakref.ref(target_dock), connection_slot)
                qconnect(target_dock.visibilityChanged, connection_slot)
                self._update_button_active_state(target_dock.isVisible(), button)
            else:
                self._update_button_active_state(False, button)
        except Exception as e:
            self._update_button_active_state(False, button)

    def _update_button_active_state_from_ref(self, is_visible: bool, button_weak_ref: weakref.ReferenceType['PushButtonType']):
        if button := button_weak_ref(): self._update_button_active_state(is_visible, button)
        # Notify the host (__init__) so it can re-reveal the launcher mid-review
        # when a feature panel is open.
        cb = globals().get("feature_visibility_callback")
        if callable(cb):
            try:
                cb()
            except Exception:
                pass

    def _update_button_active_state(self, is_visible: bool, button: 'PushButtonType'):
        if not button or not button.isCheckable() or not button.property("isMainIconButton"): return
        if button.isChecked() == is_visible: return
        button.setChecked(is_visible)
        normal_icon = button.property("normalIcon"); white_icon = button.property("whiteIcon")
        if isinstance(normal_icon, QIcon) and isinstance(white_icon, QIcon):
            target_icon = white_icon if is_visible else normal_icon
            button.setIcon(target_icon)
        button.update()

    def create_timer_button(self, icon: 'IconType', tooltip: str, action: Callable) -> 'PushButtonType':
        btn = QPushButton()
        btn.setObjectName("timerControlButton"); btn.setToolTip(tooltip)
        if icon: btn.setIcon(icon)
        btn.setFlat(True)
        btn.setIconSize(QSize(constants.TIMER_BUTTON_ICON_SIZE, constants.TIMER_BUTTON_ICON_SIZE))
        if callable(action): qconnect(btn.clicked, action)
        else: btn.setEnabled(False)
        return btn

    def create_icon_button(self, icon_filename: str, tooltip_text: str) -> Optional['PushButtonType']:
        if any(c is object for c in [QPushButton, QIcon, QSize]): return None
        button = QPushButton(); button.setToolTip(tooltip_text)
        sidebar_width = getattr(constants, 'SIDEBAR_WIDTH', 55)
        button_icon_size = getattr(constants, 'BUTTON_ICON_SIZE', 30)
        button.setFixedSize(QSize(sidebar_width - 10, button_icon_size + 10))
        button.setIconSize(QSize(button_icon_size, button_icon_size))
        button.setFlat(True); button.setProperty("isMainIconButton", True)
        button.setCheckable(True)
        normal_icon = self._create_qicon_helper(icon_filename)
        base, ext = os.path.splitext(icon_filename); white_icon = self._create_qicon_helper(f"{base}_white{ext}")
        empty_icon = QIcon()
        valid_normal_icon = normal_icon if (normal_icon and not normal_icon.isNull()) else empty_icon
        valid_white_icon = white_icon if (white_icon and not white_icon.isNull()) else valid_normal_icon
        button.setProperty("normalIcon", valid_normal_icon)
        button.setProperty("whiteIcon", valid_white_icon)
        if valid_normal_icon is not empty_icon: button.setIcon(valid_normal_icon)
        else: button.setText("?")
        return button

    def _show_settings_dialog(self):
        if self.settings_dialog_trigger:
            self.settings_dialog_trigger()
        else:
            showWarning(_("Settings dialog could not be opened."))

    def eventFilter(self, watched: 'ObjectType', event: 'EventType') -> bool:
        if any(c is object for c in [QObject, QEvent, MouseButton, QIcon, QPushButton]): return super().eventFilter(watched, event)
        if isinstance(watched, QPushButton) and watched.property("isMainIconButton"):
            if watched.isEnabled():
                normal_icon = watched.property("normalIcon"); white_icon = watched.property("whiteIcon"); is_checked = watched.isChecked()
                if isinstance(normal_icon, QIcon) and isinstance(white_icon, QIcon):
                    if event.type() == QEvent.Type.Enter: watched.setIcon(white_icon)
                    elif event.type() == QEvent.Type.Leave: watched.setIcon(white_icon if is_checked and watched.isCheckable() else normal_icon)
        elif watched == self.logo_widget:
            if event.type() == QEvent.Type.Enter and self._logo_stack is not None:
                self._logo_stack.setCurrentIndex(1)
            elif event.type() == QEvent.Type.Leave and self._logo_stack is not None:
                self._logo_stack.setCurrentIndex(0)
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self._show_settings_dialog()
                return True
        return super().eventFilter(watched, event)

    # ── Logo helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _get_logo_path() -> str:
        """Return the SVG path for the currently active colour theme."""
        icons = getattr(constants, 'icons_folder', '.')
        _LOGO_MAP = {
            "ocean":   "logo.svg",
            "orchid":  "logo_orchid.svg",
            "forest":  "logo_forest.svg",
            "deluge":  "logo_deluge.svg",
            "horizon": "logo_horizon.svg",
            "dusty":   "logo_dusty.svg",
        }
        try:
            from .theme import get_active_theme
            theme_name = get_active_theme()
        except Exception:
            theme_name = "ocean"
        filename = _LOGO_MAP.get(theme_name, "logo.svg")
        path = os.path.join(icons, filename)
        # Graceful fallback: if the theme-specific file is missing, use default
        if not os.path.exists(path):
            path = os.path.join(icons, "logo.svg")
        return path

    def update_logo(self) -> None:
        """Reload the logo SVG to reflect the current colour theme."""
        if self.logo_widget is None or QSvgWidget is object:
            return
        try:
            logo_path = self._get_logo_path()
            if self._logo_stack is not None and self._logo_stack.count() > 0:
                first = self._logo_stack.widget(0)
                if isinstance(first, QSvgWidget):
                    first.load(logo_path)
            elif isinstance(self.logo_widget, QSvgWidget):
                self.logo_widget.load(logo_path)
            self._refresh_settings_icon()
        except Exception:
            pass

    @staticmethod
    def _get_settings_svg_bytes(color: str) -> bytes:
        """Load settings.svg and inject *color* as the fill colour."""
        icons = getattr(constants, 'icons_folder', '.')
        path = os.path.join(icons, "settings.svg")
        if not os.path.exists(path):
            return b""
        try:
            import re
            with open(path, "r", encoding="utf-8") as f:
                svg = f.read()
            # Replace currentColor occurrences
            svg = svg.replace("currentColor", color)
            # If SVG has no explicit fill/stroke at all, inject fill on root <svg>
            if "fill=" not in svg and "stroke=" not in svg:
                svg = re.sub(r"(<svg\b)", rf'\1 fill="{color}"', svg, count=1)
            return svg.encode("utf-8")
        except Exception:
            return b""

    def _refresh_settings_icon(self) -> None:
        """Re-colour the settings SVG with the current theme's primary accent."""
        if self._settings_svg_widget is None or QSvgWidget is object or QByteArray is object:
            return
        try:
            from .theme import palette
            night = mw.pm.night_mode() if mw and hasattr(mw, 'pm') else False
            color = palette(night).get("blue_accent", "#0071D3")
            data = self._get_settings_svg_bytes(color)
            if data:
                self._settings_svg_widget.load(QByteArray(data))
        except Exception:
            pass

    def apply_stylesheet(self):
        if not hasattr(self, 'setStyleSheet'): return

        self.update_logo()

        night = bool(mw and hasattr(mw, 'pm') and mw.pm.night_mode())
        try:
            from .theme import palette as _tp
            c = _tp(night)
            bg          = c['surface']
            hover       = c['blue']
            active      = c['blue']
            timer_text  = c['sep_accent']
            timer_hover = c['grey_mid']
            timer_press = c['grey_dark']
            sep         = c['sep_accent']
        except Exception:
            bg          = "#2C2C2C" if night else getattr(constants, 'SIDEBAR_BG_COLOR_HEX', '#FFFFFF')
            hover       = getattr(constants, 'BUTTON_HOVER_PRESSED_COLOR', '#0071D3')
            active      = getattr(constants, 'BUTTON_ACTIVE_BG_COLOR', '#0071D3')
            timer_text  = getattr(constants, 'TIMER_LABEL_COLOR', '#577B9A')
            timer_hover = getattr(constants, 'TIMER_BUTTON_HOVER_COLOR', '#D0D0D0')
            timer_press = getattr(constants, 'TIMER_BUTTON_PRESSED_COLOR', '#B0B0B0')
            sep         = getattr(constants, 'SEPARATOR_LINE_COLOR', '#577A9A')

        radius = constants.BUTTON_BORDER_RADIUS
        stylesheet = f"""
           QWidget#SidebarContent {{ background-color: {bg}; border: none; }}
           QPushButton[isMainIconButton="true"] {{ background-color: transparent; border: none; border-radius: {radius}px; }}
           QPushButton[isMainIconButton="true"]:!disabled:hover,
           QPushButton[isMainIconButton="true"]:!disabled:pressed {{ background-color: {hover}; }}
           QPushButton[isMainIconButton="true"]:checked {{ background-color: {active}; }}
           QPushButton[isMainIconButton="true"][checkable="false"]:checked {{ background-color: transparent; }}
           QPushButton#timerControlButton {{ background-color: transparent; border: none; border-radius: 4px; }}
           QPushButton#timerControlButton:!disabled:hover {{ background-color: {timer_hover}; }}
           QPushButton#timerControlButton:!disabled:pressed {{ background-color: {timer_press}; }}
           QLabel#timerTimeLabel {{ color: {timer_text}; font-weight: bold; }}
           QFrame#bottomSeparatorLine {{ border: none; border-top: 1px solid {sep}; margin: 5px 3px; min-height: 1px; max-height: 1px; }}
           """
        self.setStyleSheet(stylesheet)

    def update_timer_ui(self):
        if not all([self._timer_time_label, self._timer_start_pause_button]) or not hasattr(pomodoro, 'current_state'): return
        try:
            state = pomodoro.current_state
            is_active = state in [constants.STATE_WORK, constants.STATE_SHORT_BREAK, constants.STATE_LONG_BREAK]
            self._timer_start_pause_button.setIcon(self._pause_icon if is_active else self._start_icon)
            self.update_timer_label_only()
        except Exception as e: print(f"Error updating timer UI: {e}")

    def update_timer_label_only(self):
        if not self._timer_time_label or not hasattr(pomodoro, 'format_time') or not hasattr(pomodoro, 'time_remaining'): return
        try:
            self._timer_time_label.setText(pomodoro.format_time(pomodoro.time_remaining))
        except Exception as e: print(f"Error updating timer label: {e}")