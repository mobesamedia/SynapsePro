# -*- coding: utf-8 -*-

import os
from typing import Any, Optional, Dict

# --- Local Imports ---
try:
    from . import constants
except ImportError:
    print("SettingsDialog CRITICAL: Failed to import constants.")
    class MockConstants:
        addon_package_name = "SynapsePro1"; qt_version = 0; icons_folder = "."; INFO_IMAGE_FILENAME = "info.png"; INFO_IMAGE_WIDTH = 200; ADDON_VERSION = "Unknown"
    constants = MockConstants()

# --- Translation Function ---
try:
    from .locales import _
except ImportError:
    def _(text): return text  # safety fallback

# --- Anki and PyQt Imports ---
try:
    from aqt import mw
    if constants.qt_version == 6:
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QDialogButtonBox,
                                     QCheckBox, QWidget, QGridLayout, QFrame, QComboBox,
                                     QGroupBox, QScrollArea, QPushButton, QHBoxLayout,
                                     QSizePolicy, QApplication)
        from PyQt6.QtGui import QPixmap, QDesktopServices
        from PyQt6.QtCore import Qt, QUrl, QTimer
    elif constants.qt_version == 5:
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QDialogButtonBox,
                                     QCheckBox, QWidget, QGridLayout, QFrame, QComboBox,
                                     QGroupBox, QScrollArea, QPushButton, QHBoxLayout,
                                     QSizePolicy, QApplication)
        from PyQt5.QtGui import QPixmap, QDesktopServices
        from PyQt5.QtCore import Qt, QUrl, QTimer
    else:
        raise ImportError("No valid Qt version found for SettingsDialog")
except ImportError as e:
    print(f"SettingsDialog Error: Failed to import required modules: {e}")
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QCheckBox, QWidget, QGridLayout, QFrame, Qt, QPixmap, QComboBox, QGroupBox, QScrollArea, QPushButton, QHBoxLayout, QDesktopServices, QUrl, QSizePolicy, QApplication, QTimer = (object,) * 20

# --- Night Mode Detection ---
is_night_mode = False
try:
    if mw.pm.night_mode():
        is_night_mode = True
except Exception:
    pass

# --- Theme ---
try:
    from .theme import palette as _palette, FONT_FAMILY as _FONT_FAMILY
except ImportError:
    def _palette(night): return {}  # type: ignore
    _FONT_FAMILY = "sans-serif"

# --- Stylesheets ---
# The Cancel button is targeted via its objectName ("CancelButton") instead of
# QPushButton[text="Cancel"] so the style keeps working when translated.
# QScrollArea#ContentScrollArea is explicitly transparent so the dialog bg shows through.

_COMMON_STYLE = f"""
    QDialog {{
        font-family: {_FONT_FAMILY};
        font-size: 13px;
    }}
    QFrame#CardFrame {{ border-radius: 12px; }}
    QLabel#SubHeaderLabel {{ font-size: 14px; font-weight: 700; margin-bottom: 5px; }}
    QLabel#HintText {{ font-size: 11px; }}
    QCheckBox {{ spacing: 10px; padding: 6px 0px; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; }}
    QPushButton {{ border-radius: 8px; padding: 6px 16px; font-weight: 600; min-width: 80px; }}
    QComboBox {{ border-radius: 8px; padding: 4px 8px; min-width: 120px; }}
    QComboBox::drop-down {{ border: none; width: 25px; }}
    QScrollArea#ContentScrollArea {{ background: transparent; border: none; }}
    QScrollArea#ContentScrollArea > QWidget > QWidget {{ background: transparent; }}
"""

def _build_settings_style(night: bool) -> str:
    c = _palette(night)
    return _COMMON_STYLE + f"""
    QDialog {{ background-color: {c['bg']}; color: {c['text']}; }}
    QFrame#CardFrame {{ background-color: {c['surface']}; border: 1px solid {c['grey_light']}; }}
    QLabel {{ color: {c['text']}; }}
    QLabel#HintText {{ color: {c['text_muted']}; }}
    QComboBox {{ background-color: {c['surface']}; color: {c['text']}; border: 1px solid {c['grey_mid']}; }}
    QComboBox QAbstractItemView {{ background-color: {c['surface']}; color: {c['text']}; }}
    QCheckBox {{ color: {c['text']}; }}
    QCheckBox::indicator {{ border: 1px solid {c['grey_mid']}; background-color: {c['surface']}; }}
    QCheckBox::indicator:checked {{ background-color: {c['blue']}; border: 1px solid {c['blue']}; }}
    QPushButton {{ background-color: {c['blue']}; color: white; border: {c['blue_border']}; }}
    QPushButton:hover {{ background-color: {c['blue_hover']}; }}
    QPushButton#CancelButton {{ background-color: {c['grey_light']}; color: {c['text']}; border: {'1px solid ' + c['grey_light'] if night else 'none'}; }}
    QPushButton#CancelButton:hover {{ background-color: {c['grey_mid']}; }}
"""

# Styles computed per-instance at dialog creation time (not cached here).


# --- Responsive breakpoints (available width of the dialog's content area) ---
# Below COMPACT_BREAKPOINT: single-column layout, smaller margins, smaller image
# Below TINY_BREAKPOINT:    additionally hide/shrink non-essential text
COMPACT_BREAKPOINT = 720
TINY_BREAKPOINT = 480


class SettingsDialog(QDialog):
    def __init__(self, current_config: Dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_config = current_config
        self.checkboxes = {}
        self._info_image_label = None
        self._info_pixmap_original = None
        self._compact_mode = False
        self._cards = []  # list of (card_widget, role) tuples for re-layout
        self._grid = None

        self.setWindowTitle(f"{getattr(constants, 'ADDON_DISPLAY_NAME', constants.addon_package_name)} - {_('Settings')}")
        self.setStyleSheet(_build_settings_style(is_night_mode))

        # Allow the dialog itself to be shrunk freely by the user / OS.
        # The minimum is small enough to fit on very low-resolution screens
        # (e.g. 800x600 or netbooks). The scroll area makes up for the
        # limited vertical space.
        self.setMinimumSize(380, 300)
        self.setSizeGripEnabled(True)

        # --- Main layout: scroll area on top, button row pinned at bottom ---
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(10)

        # Scrollable content container (everything except the action buttons).
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setObjectName("ContentScrollArea")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._content_widget = QWidget()
        self._content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)

        self.setup_ui()

        self._scroll_area.setWidget(self._content_widget)
        self.main_layout.addWidget(self._scroll_area, 1)

        # Button row OUTSIDE the scroll area - always visible, always clickable
        self.add_button_row()

        # Pick a sensible initial size that never exceeds the available screen.
        self._apply_initial_size()

        # Do a first responsive pass after the dialog is shown so widgets
        # have proper geometry.
        QTimer.singleShot(0, self._apply_responsive_layout)

    # ------------------------------------------------------------------ #
    # Layout construction
    # ------------------------------------------------------------------ #
    def setup_ui(self):
        """Build the cards once; place them via _apply_responsive_layout()."""
        info_card = self.create_info_card()
        general_card = self.create_general_settings_card()
        support_card = self.create_support_card()
        themes_card = self.create_themes_card()
        dashboard_card = self.create_dashboard_card()
        deck_card = self.create_deck_overview_card()
        sidebar_card = self.create_sidebar_card()

        # Store with a "role" hint so we can rearrange depending on width.
        self._cards = [
            ("info", info_card),
            ("general", general_card),
            ("support", support_card),
            ("themes", themes_card),
            ("dashboard", dashboard_card),
            ("deck", deck_card),
            ("sidebar", sidebar_card),
        ]

        # Container that gets swapped between grid (wide) and vbox (narrow).
        self._cards_container = QWidget()
        self._cards_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._content_layout.addWidget(self._cards_container)
        self._content_layout.addStretch(1)

    def _install_grid_layout(self):
        """Two-column grid layout for wide dialogs."""
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)

        cards = dict(self._cards)
        grid.addWidget(cards["info"], 0, 0)
        grid.addWidget(cards["general"], 0, 1)
        grid.addWidget(cards["support"], 1, 0, 1, 2)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        left_layout.addWidget(cards["dashboard"])
        left_layout.addWidget(cards["deck"])
        left_layout.addStretch()
        grid.addWidget(left_container, 2, 0)
        grid.addWidget(cards["sidebar"], 2, 1)

        # Themes card spans full width at the very bottom
        grid.addWidget(cards["themes"], 3, 0, 1, 2)

        # Column stretch: both columns share space equally
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self._cards_container.setLayout(grid)

    def _install_stack_layout(self):
        """Single-column stack for narrow dialogs - everything remains reachable."""
        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(12)
        # NOTE: using ``_role`` (not ``_``) because ``_`` is the translation
        # function imported from ``locales`` and would be shadowed otherwise.
        for _role, card in self._cards:
            vbox.addWidget(card)
        vbox.addStretch(1)
        self._cards_container.setLayout(vbox)

    def _replace_container_layout(self, installer):
        """Swap the container's layout safely (needed to switch between grid/stack)."""
        old_layout = self._cards_container.layout()
        if old_layout is not None:
            # Remove every stored card from the old layout *before* deleting it,
            # otherwise the cards would be destroyed along with their parent layout.
            # NOTE: using ``_role`` to avoid shadowing the translation ``_`` function.
            for _role, card in self._cards:
                old_layout.removeWidget(card)
                card.setParent(self._cards_container)  # re-parent so it survives
            # Drop any remaining items (stretches, sub-layouts, helper widgets).
            while old_layout.count():
                item = old_layout.takeAt(0)
                sub = item.layout()
                if sub is not None:
                    while sub.count():
                        inner = sub.takeAt(0)
                        w = inner.widget()
                        if w is not None:
                            w.setParent(self._cards_container)
            # Detach the old layout from the container so the new one can be set.
            # We create a throw-away QWidget to steal ownership of the old layout.
            trash = QWidget()
            trash.setLayout(old_layout)
            trash.deleteLater()

        installer()

    # ------------------------------------------------------------------ #
    # Cards
    # ------------------------------------------------------------------ #
    def create_info_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("CardFrame")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        try:
            from .theme import get_active_theme as _get_theme
            _INFO_MAP = {
                "ocean":   "info.png",
                "orchid":  "info_pink.png",
                "forest":  "info_forest.png",
                "horizon": "info_horizon.png",
                "deluge":  "info_deluge.png",
                "dusty":   "info_dusty.png",
            }
            _info_file = _INFO_MAP.get(_get_theme(), "info.png")
            image_path = os.path.join(constants.icons_folder, _info_file)
            if not os.path.exists(image_path):
                image_path = os.path.join(constants.icons_folder, "info.png")
            if os.path.exists(image_path):
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    self._info_pixmap_original = pixmap
                    # initial scaling; will be adjusted in _apply_responsive_layout
                    scaled = pixmap.scaledToWidth(380, Qt.TransformationMode.SmoothTransformation)
                    image_label.setPixmap(scaled)
                    layout.addWidget(image_label)
                    self._info_image_label = image_label
        except Exception:
            pass

        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 4, 0, 0)
        bottom_layout.setSpacing(8)

        text_label = QLabel()
        credits_color = _palette(is_night_mode)["text_muted"]
        info_text = (
            f"<div style='text-align: left; line-height: 120%;'>"
            f"<span style='font-size: 15px; font-weight: bold;'>{getattr(constants, 'ADDON_DISPLAY_NAME', constants.addon_package_name)}</span><br>"
            f"<span style='font-size: 11px;'>{_('Version')} {constants.ADDON_VERSION}</span><br>"
            f"<span style='color:{credits_color}; font-size: 10px;'>by MobesaMedia</span>"
            f"</div>"
        )
        text_label.setText(info_text)
        text_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        text_label.setWordWrap(True)
        text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bottom_layout.addWidget(text_label, 1)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(5)

        reddit_btn = QPushButton(_("Reddit"))
        reddit_btn.setObjectName("PrimaryButton")
        reddit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reddit_btn.clicked.connect(self.open_news)
        reddit_btn.setMinimumWidth(90)
        reddit_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        changelog_btn = QPushButton(_("Changelog"))
        changelog_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        changelog_btn.clicked.connect(self.open_changelog)
        changelog_btn.setMinimumWidth(90)
        changelog_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        _c = _palette(is_night_mode)
        changelog_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_c.get("grey_light", "#E5E5EA")};
                color: {_c.get("text", "#1D1D1F")};
                border-radius: 6px;
                border: none;
                font-size: 12px;
                padding: 1px 10px;
            }}
            QPushButton:hover {{ background-color: {_c.get("grey_mid", "#D1D1D6")}; }}
        """)

        btn_layout.addWidget(reddit_btn)
        btn_layout.addWidget(changelog_btn)

        bottom_layout.addLayout(btn_layout, 0)
        layout.addLayout(bottom_layout)
        return card

    def create_general_settings_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("CardFrame")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel(_("General Settings"))
        header.setObjectName("SubHeaderLabel")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)

        def _lbl(text):
            l = QLabel(text)
            l.setWordWrap(True)
            l.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            return l

        def _combo():
            c = QComboBox()
            c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            return c

        # --- Language --------------------------------------------------
        # The config value stored is always one of "auto"/"en"/"de"/"es";
        # the visible labels are translated (for "Auto") or shown as
        # endonyms (English / Deutsch / Español).
        grid.addWidget(_lbl(_("Language:")), 0, 0)
        self.language_combo = _combo()
        self.language_combo.addItem(_("Auto"), "auto")
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("Deutsch", "de")
        self.language_combo.addItem("Español", "es")
        self.language_combo.addItem("Français", "fr")
        self.language_combo.addItem("Português", "pt")
        self.language_combo.addItem("Tiếng Việt", "vi")
        self.language_combo.addItem("한국어", "ko")
        self.language_combo.addItem("中文", "zh")
        self.language_combo.addItem("हिन्दी", "hi")
        lang_val = self.current_config.get("language", "auto")
        idx = self.language_combo.findData(lang_val)
        self.language_combo.setCurrentIndex(idx if idx != -1 else 0)
        grid.addWidget(self.language_combo, 0, 1)

        # --- Daily fact topic -----------------------------------------
        # IMPORTANT: the underlying config value must stay in English
        # ("Medical", "Law", ...) – only the display label is translated.
        grid.addWidget(_lbl(_("Daily Fact Topic:")), 1, 0)
        self.fact_theme_combo = _combo()
        self.fact_theme_combo.addItem(_("Medical"), "Medical")
        self.fact_theme_combo.addItem(_("Law"), "Law")
        self.fact_theme_combo.addItem(_("General"), "General")
        self.fact_theme_combo.addItem(_("Countries"), "Countries")
        idx = self.fact_theme_combo.findData(self.current_config.get("fact_theme", "Medical"))
        if idx != -1:
            self.fact_theme_combo.setCurrentIndex(idx)
        grid.addWidget(self.fact_theme_combo, 1, 1)

        # --- Statistics time range ------------------------------------
        grid.addWidget(_lbl(_("Statistics Time Range:")), 2, 0)
        self.stats_range_combo = _combo()
        self.stats_range_combo.addItem(_("Last 24 Hours"), 1)
        self.stats_range_combo.addItem(_("Last 7 Days (Week)"), 7)
        self.stats_range_combo.addItem(_("Last 30 Days (Month)"), 30)
        raw_val = self.current_config.get("stats_time_range", 7)
        idx = self.stats_range_combo.findData(int(raw_val))
        self.stats_range_combo.setCurrentIndex(idx if idx != -1 else 1)
        grid.addWidget(self.stats_range_combo, 2, 1)

        # --- Sidebar visibility ---------------------------------------
        grid.addWidget(_lbl(_("Sidebar Visibility:")), 3, 0)
        self.sidebar_vis_combo = _combo()
        self.sidebar_vis_combo.addItem(_("Always Show"), "always_show")
        self.sidebar_vis_combo.addItem(_("Hide while Reviewing"), "hide_review")
        vis_val = self.current_config.get("sidebar_visibility_mode", "always_show")
        idx = self.sidebar_vis_combo.findData(vis_val)
        self.sidebar_vis_combo.setCurrentIndex(idx if idx != -1 else 0)
        grid.addWidget(self.sidebar_vis_combo, 3, 1)

        layout.addLayout(grid)
        layout.addStretch()
        return card

    def create_support_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("CardFrame")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(10)

        info_text = QLabel(
            _("Enjoying the add-on? Please leave a <b>Thumbs Up</b> on AnkiWeb – it supports me the most!")
        )
        info_text.setWordWrap(True)
        info_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        rate_btn = QPushButton(_("Rate on AnkiWeb"))
        rate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rate_btn.setMinimumWidth(130)
        rate_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        rate_btn.clicked.connect(self.open_ankiweb_link)

        layout.addWidget(info_text, 1)
        layout.addWidget(rate_btn, 0)
        return card

    def create_themes_card(self) -> QFrame:
        """Compact Themes card — colour presets, editor button, background combo."""
        card = QFrame()
        card.setObjectName("CardFrame")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        header = QLabel(_("Themes"))
        header.setObjectName("SubHeaderLabel")
        header.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(header)

        # ── Colour-theme row ─────────────────────────────────────────────────
        self._color_theme_value   = self.current_config.get("active_color_theme", "ocean")
        self._custom_theme_colors = dict(self.current_config.get("custom_theme_colors", {}))
        self._color_theme_buttons: dict = {}

        color_row = QHBoxLayout()
        color_row.setSpacing(6)

        color_lbl = QLabel(_("Color Theme:"))
        color_lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        color_row.addWidget(color_lbl)

        _preset_defs = [
            ("ocean",   "Ocean",   "#0071D3", "#004990"),
            ("orchid",  "Orchid",  "#E95ACC", "#CB51B3"),
            ("forest",  "Forest",  "#619971", "#477154"),
            ("deluge",  "Deluge",  "#7961A9", "#65508D"),
            ("horizon", "Horizon", "#6183A9", "#4B6683"),
            ("dusty",   "Dusty",   "#5A9491", "#4E8280"),
        ]
        preset_row = QHBoxLayout()
        preset_row.setSpacing(5)
        for idx, (key, label, bg, pressed) in enumerate(_preset_defs):
            is_checked = (key == self._color_theme_value)
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(is_checked)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(24)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: white;
                    border-radius: 6px;
                    border: 2px solid {("rgba(255,255,255,0.85)" if is_checked else "transparent")};
                    font-weight: 600;
                    font-size: 11px;
                    padding: 1px 8px;
                    min-width: 52px;
                }}
                QPushButton:hover {{ background-color: {pressed}; }}
                QPushButton:checked {{
                    background-color: {pressed};
                    border: 2px solid rgba(255,255,255,0.85);
                }}
            """)
            btn.clicked.connect(lambda _, k=key: self._select_color_theme(k))
            self._color_theme_buttons[key] = btn
            preset_row.addWidget(btn)
        color_row.addLayout(preset_row)
        color_row.addStretch()

        # "Edit Theme" button — opens the custom editor popup
        c = _palette(is_night_mode)
        edit_btn = QPushButton(_("Edit Theme") + " ✎")
        edit_btn.setObjectName("EditThemeBtn")
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setFixedHeight(26)
        edit_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        edit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.get("grey_light","#E5E5EA")};
                color: {c.get("text","#1D1D1F")};
                border-radius: 6px;
                border: none;
                font-size: 12px;
                padding: 1px 10px;
            }}
            QPushButton:hover {{ background-color: {c.get("grey_mid","#D1D1D6")}; }}
        """)
        edit_btn.clicked.connect(self._open_theme_editor)
        color_row.addWidget(edit_btn)

        layout.addLayout(color_row)

        # ── Separator ─────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # ── Background Color ─────────────────────────────────────────────────
        bg_row = QHBoxLayout()
        bg_row.setSpacing(8)
        bg_lbl = QLabel(_("Background Color:"))
        bg_lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        bg_row.addWidget(bg_lbl)
        self.visual_theme_combo = QComboBox()
        self.visual_theme_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.populate_themes()
        bg_row.addWidget(self.visual_theme_combo, 1)
        layout.addLayout(bg_row)

        return card

    def _select_color_theme(self, key: str) -> None:
        """Update the active preset and refresh all button checked-states."""
        self._color_theme_value = key
        _colors  = {
            "ocean": "#0071D3", "orchid": "#E95ACC", "forest": "#619971",
            "deluge": "#7961A9", "horizon": "#6183A9", "dusty": "#5A9491",
        }
        _pressed = {
            "ocean": "#004990", "orchid": "#CB51B3", "forest": "#477154",
            "deluge": "#65508D", "horizon": "#4B6683", "dusty": "#4E8280",
        }
        for k, btn in self._color_theme_buttons.items():
            checked = (k == key)
            btn.setChecked(checked)
            bg = _colors.get(k, "#0071D3")
            pr = _pressed.get(k, "#004990")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: white;
                    border-radius: 6px;
                    border: 2px solid {("rgba(255,255,255,0.85)" if checked else "transparent")};
                    font-weight: 600;
                    font-size: 11px;
                    padding: 1px 8px;
                    min-width: 52px;
                }}
                QPushButton:hover {{ background-color: {pr}; }}
                QPushButton:checked {{
                    background-color: {pr};
                    border: 2px solid rgba(255,255,255,0.85);
                }}
            """)

    def _open_theme_editor(self) -> None:
        """Open the custom ThemeEditorDialog; apply result as the 'custom' theme."""
        try:
            from . import theme_editor_dialog
            from .theme import COLOR_THEMES
            # Seed the editor with current custom colours or the active preset
            if self._color_theme_value == "custom" and self._custom_theme_colors:
                initial = dict(self._custom_theme_colors)
            else:
                preset = self._color_theme_value if self._color_theme_value in COLOR_THEMES else "ocean"
                raw = COLOR_THEMES[preset][False]
                initial = {k: raw[k] for k in ("blue", "blue_hover", "blue_pressed", "blue_bright")}

            dlg = theme_editor_dialog.ThemeEditorDialog(initial, self)
            if dlg.exec():
                self._custom_theme_colors = dlg.get_colors()
                self._color_theme_value = "custom"
                # Deselect all preset buttons to signal "custom" is active
                for btn in self._color_theme_buttons.values():
                    btn.setChecked(False)
        except Exception as e:
            print(f"SettingsDialog: theme editor error: {e}")

    def create_dashboard_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("CardFrame")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(2)

        header = QLabel(_("Home Screen Dashboard"))
        header.setObjectName("SubHeaderLabel")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        features = [
            ("gamification_widgets_enabled", _("Gamification Widgets (Level, XP, Streak)")),
            ("daily_widgets_enabled", _("Daily Widgets (Study Plan & Facts)")),
            ("deadline_bar_enabled", _("Deadline Bar")),
            ("statistics_widget_enabled", _("Advanced Statistics")),
        ]
        for key, text in features:
            self.add_checkbox(key, text, layout)

        return card

    def create_deck_overview_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("CardFrame")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(2)

        header = QLabel(_("Deck Overview"))
        header.setObjectName("SubHeaderLabel")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        self.add_checkbox("deck_overview_enabled", _("Enable Custom Deck Dashboard"), layout)

        hint = QLabel(
            _("Replaces the standard Deck Overview screen with a modern dashboard displaying Retention, Hard Cards, and more.")
        )
        hint.setObjectName("HintText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        return card

    def create_sidebar_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("CardFrame")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(2)

        header = QLabel(_("Sidebar"))
        header.setObjectName("SubHeaderLabel")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        features = [
            ("mindmap_enabled", _("Mind Map")),
            ("gamification_sidebar_enabled", _("Gamification Sidebar")),
            ("music_player_enabled", _("Music Player")),
            ("pomodoro_enabled", _("Pomodoro Timer")),
            ("ai_assistant_enabled", _("AI Assistant")),
            ("website_viewer_enabled", _("Website Viewer")),
            ("notebook_enabled", _("Notebook")),
        ]
        for key, text in features:
            self.add_checkbox(key, text, layout)

        layout.addSpacing(8)
        hint = QLabel(_("You need to restart Anki to see the changes of the Sidebar Settings."))
        hint.setObjectName("HintText")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()
        return card

    def add_checkbox(self, key, text, layout):
        cb = QCheckBox(text)
        cb.setCursor(Qt.CursorShape.PointingHandCursor)
        cb.setChecked(bool(self.current_config.get(key, True)))
        # Allow long labels to wrap instead of forcing the card wider.
        try:
            cb.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        except Exception:
            pass
        self.checkboxes[key] = cb
        layout.addWidget(cb)

    def add_button_row(self):
        """Save / Cancel row. Lives OUTSIDE the scroll area so it is always
        visible and clickable – no matter how small the screen is."""
        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 6, 0, 0)
        hbox.setSpacing(8)

        cancel_btn = QPushButton(_("Cancel"))
        # ObjectName-based styling so the CSS selector keeps working even
        # when the button label is translated (see stylesheet).
        cancel_btn.setObjectName("CancelButton")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        save_btn = QPushButton(_("Save Settings"))
        save_btn.clicked.connect(self.accept)
        save_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        save_btn.setDefault(True)

        hbox.addStretch()
        hbox.addWidget(cancel_btn)
        hbox.addWidget(save_btn)
        self.main_layout.addLayout(hbox)

    # ------------------------------------------------------------------ #
    # Responsive behaviour
    # ------------------------------------------------------------------ #
    def _available_screen_size(self):
        """Return (w, h) we are allowed to occupy (minus some chrome)."""
        try:
            screen = None
            if self.parent() is not None and hasattr(self.parent(), "screen"):
                screen = self.parent().screen()
            if screen is None:
                screen = QApplication.primaryScreen()
            if screen is not None:
                geom = screen.availableGeometry()
                return max(320, geom.width() - 40), max(300, geom.height() - 80)
        except Exception:
            pass
        return 800, 600

    def _apply_initial_size(self):
        avail_w, avail_h = self._available_screen_size()
        # Preferred default for big screens is the old 880×… layout, but we
        # never exceed the current screen. The scroll area handles the rest.
        target_w = min(900, avail_w)
        target_h = min(780, avail_h)
        self.resize(target_w, target_h)
        # Also clamp maximum size so the dialog can't overshoot the screen.
        self.setMaximumSize(avail_w, avail_h)

    def _apply_responsive_layout(self):
        """Choose 1- or 2-column layout depending on the dialog's current width
        and rescale the info image accordingly."""
        try:
            inner_w = self._scroll_area.viewport().width() if self._scroll_area else self.width()
        except Exception:
            inner_w = self.width()

        compact = inner_w < COMPACT_BREAKPOINT
        tiny = inner_w < TINY_BREAKPOINT

        # Re-build the card container if the mode changed.
        if compact != self._compact_mode or self._cards_container.layout() is None:
            self._compact_mode = compact
            if compact:
                self._replace_container_layout(self._install_stack_layout)
            else:
                self._replace_container_layout(self._install_grid_layout)

        # Dynamically rescale the info image to available width.
        if self._info_image_label is not None and self._info_pixmap_original is not None:
            # In compact mode the image spans the full card width; in wide mode
            # it lives in one grid cell that is ~half the content width.
            if compact:
                target_img_w = max(180, min(520, inner_w - 60))
            else:
                target_img_w = max(180, min(420, int(inner_w / 2) - 60))
            if tiny:
                target_img_w = max(140, min(260, inner_w - 40))
            try:
                scaled = self._info_pixmap_original.scaledToWidth(
                    target_img_w, Qt.TransformationMode.SmoothTransformation
                )
                self._info_image_label.setPixmap(scaled)
            except Exception:
                pass

        # Shrink outer margins a bit on very small screens.
        if tiny:
            self.main_layout.setContentsMargins(6, 6, 6, 6)
            self._content_layout.setSpacing(8)
        elif compact:
            self.main_layout.setContentsMargins(10, 10, 10, 10)
            self._content_layout.setSpacing(10)
        else:
            self.main_layout.setContentsMargins(14, 14, 14, 14)
            self._content_layout.setSpacing(12)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Re-run responsive pass on every resize so the layout, image, and
        # margins stay in sync with the current dialog size.
        self._apply_responsive_layout()

    # ------------------------------------------------------------------ #
    # Helpers (unchanged behaviour)
    # ------------------------------------------------------------------ #
    def populate_themes(self):
        found_themes = []
        try:
            path = getattr(constants, 'addon_path', '.')
            theme_path = os.path.join(path, "theme", "user_files")
            if os.path.exists(theme_path):
                found_themes = [f for f in os.listdir(theme_path) if f.endswith(".css")]
                found_themes.sort()
        except Exception:
            pass

        if not found_themes:
            self.visual_theme_combo.addItem(_("Default"), "medical_theme.css")
        else:
            for filename in found_themes:
                display_name = (
                    _("Default") if filename == "medical_theme.css"
                    else filename.replace(".css", "").replace("_", " ").title()
                )
                self.visual_theme_combo.addItem(display_name, filename)

        current_css = self.current_config.get("active_theme", "medical_theme.css")
        idx = self.visual_theme_combo.findData(current_css)
        self.visual_theme_combo.setCurrentIndex(idx if idx != -1 else 0)

    def open_ankiweb_link(self):
        QDesktopServices.openUrl(QUrl("https://ankiweb.net/shared/info/236979321"))

    def open_changelog(self):
        QDesktopServices.openUrl(QUrl("https://www.synapse-pro.de/changelog"))

    def open_news(self):
        QDesktopServices.openUrl(QUrl("https://www.reddit.com/r/SynapseProAnki/"))

    def get_new_settings(self) -> Dict:
        settings = {
            # fact_theme is stored as an English key ("Medical", "Law", ...)
            # regardless of the displayed translation.
            "fact_theme": self.fact_theme_combo.currentData() or "Medical",
            "active_theme": self.visual_theme_combo.currentData() or "medical_theme.css",
            "active_color_theme":  getattr(self, "_color_theme_value", "blue"),
            "custom_theme_colors": getattr(self, "_custom_theme_colors", {}),
            "stats_time_range": int(self.stats_range_combo.currentData() or 7),
            "sidebar_visibility_mode": self.sidebar_vis_combo.currentData() or "always_show",
            "language": self.language_combo.currentData() or "auto",
        }
        for key, cb in self.checkboxes.items():
            settings[key] = cb.isChecked()
        return settings
