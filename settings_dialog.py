# -*- coding: utf-8 -*-

import os
from typing import Any, Optional, Dict

# --- Local Imports ---
try:
    from . import constants
except ImportError:
    print("SettingsDialog CRITICAL: Failed to import constants.")
    class MockConstants:
        addon_package_name = "SynapsePro1"; icons_folder = "."; INFO_IMAGE_FILENAME = "news-banner.png"; INFO_IMAGE_WIDTH = 200; ADDON_VERSION = "Unknown"
    constants = MockConstants()

try:
    from . import sidebar_shortcuts
except Exception:
    sidebar_shortcuts = None  # type: ignore

# --- Translation Function ---
try:
    from .locales import _
except ImportError:
    def _(text): return text  # safety fallback

# --- Anki and PyQt Imports ---
QKeySequenceEdit = QKeySequence = QMessageBox = object
try:
    from aqt import mw
    from aqt.qt import (QDialog, QVBoxLayout, QLabel, QDialogButtonBox,
                        QCheckBox, QWidget, QGridLayout, QFrame, QComboBox,
                        QGroupBox, QScrollArea, QPushButton, QHBoxLayout,
                        QSizePolicy, QApplication, QListWidget, QListWidgetItem,
                        QStackedWidget, QPixmap, QDesktopServices, Qt, QUrl, QTimer,
                        QKeySequenceEdit, QKeySequence, QMessageBox)
except ImportError as e:
    print(f"SettingsDialog Error: Failed to import required modules: {e}")
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QCheckBox, QWidget, QGridLayout, QFrame, Qt, QPixmap, QComboBox, QGroupBox, QScrollArea, QPushButton, QHBoxLayout, QDesktopServices, QUrl, QSizePolicy, QApplication, QTimer, QListWidget, QListWidgetItem, QStackedWidget = (object,) * 23

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
    QLabel#SectionTitle {{ font-size: 17px; font-weight: 700; }}
    QLabel#SectionDesc {{ font-size: 12px; }}
    QLabel#SettingDesc {{ font-size: 11px; }}
    QLabel#FieldLabel {{ font-size: 13px; font-weight: 600; }}
    QLabel#HintText {{ font-size: 11px; }}
    QCheckBox {{ spacing: 10px; padding: 5px 0px; font-size: 13px; }}
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
    QLabel#SectionDesc {{ color: {c['text_muted']}; }}
    QLabel#SettingDesc {{ color: {c['text_muted']}; }}
    QComboBox {{ background-color: {c['surface']}; color: {c['text']}; border: 1px solid {c['grey_mid']}; }}
    QKeySequenceEdit {{ background-color: {c['surface']}; color: {c['text']}; border: 1px solid {c['grey_mid']}; border-radius: 8px; padding: 4px 8px; min-width: 125px; }}
    QKeySequenceEdit:focus {{ border: 1px solid {c['blue']}; }}
    QComboBox QAbstractItemView {{ background-color: {c['surface']}; color: {c['text']}; }}
    QCheckBox {{ color: {c['text']}; }}
    QCheckBox::indicator {{ border: 1px solid {c['grey_mid']}; background-color: {c['surface']}; }}
    QCheckBox::indicator:checked {{ background-color: {c['blue']}; border: 1px solid {c['blue']}; }}
    QPushButton {{ background-color: {c['blue']}; color: white; border: {c['blue_border']}; }}
    QPushButton:hover {{ background-color: {c['blue_hover']}; }}
    QPushButton#CancelButton {{ background-color: {c['grey_light']}; color: {c['text']}; border: {'1px solid ' + c['grey_light'] if night else 'none'}; }}
    QPushButton#CancelButton:hover {{ background-color: {c['grey_mid']}; }}

    /* Apple-style left category navigation */
    QListWidget#SettingsNav {{
        background-color: {c['surface']};
        border: none;
        border-right: 1px solid {c['grey_light']};
        outline: 0;
        padding: 10px 6px;
        font-size: 13px;
    }}
    QListWidget#SettingsNav::item {{
        color: {c['text']};
        padding: 9px 12px;
        margin: 2px 4px;
        border-radius: 8px;
    }}
    QListWidget#SettingsNav::item:hover {{ background-color: {c['grey_light']}; }}
    QListWidget#SettingsNav::item:selected {{ background-color: {c['blue']}; color: white; }}

    QFrame#FooterSep {{ background-color: {c['grey_light']}; border: none; }}
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
        self.shortcut_edits = {}
        self._info_image_label = None
        self._info_pixmap_original = None

        self.setWindowTitle(f"{getattr(constants, 'ADDON_DISPLAY_NAME', constants.addon_package_name)} - {_('Settings')}")
        self.setStyleSheet(_build_settings_style(is_night_mode))

        self.setMinimumSize(540, 380)
        self.setSizeGripEnabled(True)

        # --- Master-detail layout: category nav (left) | pages (right) ---
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(0)

        # Left: category list
        self._nav = QListWidget()
        self._nav.setObjectName("SettingsNav")
        self._nav.setFixedWidth(190)
        self._nav.setFrameShape(QFrame.Shape.NoFrame)
        self._nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._nav.setCursor(Qt.CursorShape.PointingHandCursor)

        # Right: stacked pages (one per category)
        self._stack = QStackedWidget()

        content_row.addWidget(self._nav)
        content_row.addWidget(self._stack, 1)
        self.main_layout.addLayout(content_row, 1)

        # Build the cards and wire them into nav + stack.
        self.setup_ui()

        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._nav.setCurrentRow(0)

        # Button row pinned at the bottom — always visible.
        self.add_button_row()

        self._apply_initial_size()
        QTimer.singleShot(0, self._rescale_info_image)

    # ------------------------------------------------------------------ #
    # Layout construction
    # ------------------------------------------------------------------ #
    def setup_ui(self):
        """Build each settings card and place it on its own category page."""
        info_card      = self.create_info_card()
        support_card   = self.create_support_card()
        general_card   = self.create_general_settings_card()
        themes_card    = self.create_themes_card()
        dashboard_card = self.create_dashboard_card()
        deck_card      = self.create_deck_overview_card()
        sidebar_card   = self.create_sidebar_card()

        # Home: the landing page — logo/version, Reddit & Changelog buttons,
        # plus the "Rate on AnkiWeb" call-to-action.
        home = QWidget()
        home_layout = QVBoxLayout(home)
        home_layout.setContentsMargins(0, 0, 0, 0)
        home_layout.setSpacing(12)
        home_layout.addWidget(info_card)
        home_layout.addWidget(support_card)

        # (nav label, page content) — one entry per left-hand category.
        self._pages = [
            (_("Home"),          home),
            (_("General"),       general_card),
            (_("Appearance"),    themes_card),
            (_("Dashboard"),     dashboard_card),
            (_("Deck Overview"), deck_card),
            (_("Sidebar"),       sidebar_card),
        ]
        for title, widget in self._pages:
            self._add_page(title, widget)

    def _add_page(self, title: str, widget) -> None:
        """Add a category to the nav and its (scrollable) content to the stack."""
        self._nav.addItem(QListWidgetItem(title))

        page = QScrollArea()
        page.setObjectName("ContentScrollArea")
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.Shape.NoFrame)
        page.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        page.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(18, 18, 18, 18)
        inner_layout.setSpacing(12)
        inner_layout.addWidget(widget)
        inner_layout.addStretch(1)

        page.setWidget(inner)
        self._stack.addWidget(page)

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
            image_path = os.path.join(
                constants.icons_folder,
                getattr(constants, "INFO_IMAGE_FILENAME", "news-banner.png"),
            )
            if os.path.exists(image_path):
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    self._info_pixmap_original = pixmap
                    # initial scaling; refined by _rescale_info_image() on show/resize
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
        layout.setContentsMargins(20, 18, 20, 18)

        self._add_section_header(
            layout, _("General"),
            _("Language, daily facts, the statistics range and when the sidebar is shown."),
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 0)
        self._gen_grid_row = 0

        def _combo():
            c = QComboBox()
            c.setMinimumWidth(180)
            c.setMinimumHeight(30)
            c.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            return c

        def _row(title, desc, combo):
            cell = QWidget()
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(2)
            tl = QLabel(title); tl.setObjectName("FieldLabel"); tl.setWordWrap(True)
            dl = QLabel(desc); dl.setObjectName("SettingDesc"); dl.setWordWrap(True)
            cl.addWidget(tl); cl.addWidget(dl)
            r = self._gen_grid_row
            grid.addWidget(cell, r, 0)
            grid.addWidget(combo, r, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._gen_grid_row += 1

        # --- Language --------------------------------------------------
        # The config value stored is always one of "auto"/"en"/"de"/"es";
        # the visible labels are translated (for "Auto") or shown as
        # endonyms (English / Deutsch / Español).
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
        _row(_("Language"),
             _("Interface language. \"Auto\" follows your Anki language."),
             self.language_combo)

        # --- Daily fact topic -----------------------------------------
        # IMPORTANT: the underlying config value must stay in English
        # ("Medical", "Law", ...) – only the display label is translated.
        self.fact_theme_combo = _combo()
        self.fact_theme_combo.addItem(_("Medical"), "Medical")
        self.fact_theme_combo.addItem(_("Law"), "Law")
        self.fact_theme_combo.addItem(_("General"), "General")
        self.fact_theme_combo.addItem(_("Countries"), "Countries")
        idx = self.fact_theme_combo.findData(self.current_config.get("fact_theme", "Medical"))
        if idx != -1:
            self.fact_theme_combo.setCurrentIndex(idx)
        _row(_("Daily Fact Topic"),
             _("Subject the daily fact on the home screen is drawn from."),
             self.fact_theme_combo)

        # --- Statistics time range ------------------------------------
        self.stats_range_combo = _combo()
        self.stats_range_combo.addItem(_("Last 24 Hours"), 1)
        self.stats_range_combo.addItem(_("Last 7 Days (Week)"), 7)
        self.stats_range_combo.addItem(_("Last 30 Days (Month)"), 30)
        raw_val = self.current_config.get("stats_time_range", 7)
        idx = self.stats_range_combo.findData(int(raw_val))
        self.stats_range_combo.setCurrentIndex(idx if idx != -1 else 1)
        _row(_("Statistics Time Range"),
             _("Period covered by the statistics widget."),
             self.stats_range_combo)

        # --- Sidebar visibility ---------------------------------------
        self.sidebar_vis_combo = _combo()
        self.sidebar_vis_combo.addItem(_("Always Show"), "always_show")
        self.sidebar_vis_combo.addItem(_("Hide while Reviewing"), "hide_review")
        vis_val = self.current_config.get("sidebar_visibility_mode", "always_show")
        idx = self.sidebar_vis_combo.findData(vis_val)
        self.sidebar_vis_combo.setCurrentIndex(idx if idx != -1 else 0)
        _row(_("Sidebar Visibility"),
             _("Show the launcher always, or hide it while you review."),
             self.sidebar_vis_combo)

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

    def _theme_btn_style(self, bg: str, pressed: str, checked: bool) -> str:
        border = "rgba(255,255,255,0.9)" if checked else "transparent"
        return f"""
            QPushButton {{
                background-color: {bg};
                color: white;
                border-radius: 8px;
                border: 2px solid {border};
                font-weight: 600;
                font-size: 13px;
                padding: 7px 10px;
            }}
            QPushButton:hover {{ background-color: {pressed}; }}
            QPushButton:checked {{ background-color: {pressed}; border: 2px solid rgba(255,255,255,0.9); }}
        """

    def create_themes_card(self) -> QFrame:
        """Appearance card — accent-colour presets, theme editor, background style."""
        card = QFrame()
        card.setObjectName("CardFrame")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(6)

        self._add_section_header(
            layout, _("Appearance"),
            _("Choose the accent colour used across SynapsePro and the background style."),
        )

        self._color_theme_value   = self.current_config.get("active_color_theme", "ocean")
        self._custom_theme_colors = dict(self.current_config.get("custom_theme_colors", {}))
        self._color_theme_buttons: dict = {}

        # ── Accent colour ────────────────────────────────────────────────────
        color_lbl = QLabel(_("Color Theme"))
        color_lbl.setObjectName("FieldLabel")
        layout.addWidget(color_lbl)
        color_desc = QLabel(_("Accent colour for buttons, highlights and widgets."))
        color_desc.setObjectName("SettingDesc"); color_desc.setWordWrap(True)
        layout.addWidget(color_desc)
        layout.addSpacing(6)

        _preset_defs = [
            ("ocean",   _("Ocean"),   "#0071D3", "#004990"),
            ("orchid",  _("Orchid"),  "#E95ACC", "#CB51B3"),
            ("forest",  _("Forest"),  "#619971", "#477154"),
            ("deluge",  _("Deluge"),  "#7961A9", "#65508D"),
            ("horizon", _("Horizon"), "#6183A9", "#4B6683"),
            ("dusty",   _("Dusty"),   "#5A9491", "#4E8280"),
        ]
        self._theme_presets = {k: (bg, pr) for k, _name, bg, pr in _preset_defs}

        preset_grid = QGridLayout()
        preset_grid.setSpacing(8)
        for col in range(3):
            preset_grid.setColumnStretch(col, 1)
        for idx, (key, label, bg, pressed) in enumerate(_preset_defs):
            checked = (key == self._color_theme_value)
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(checked)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(36)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setStyleSheet(self._theme_btn_style(bg, pressed, checked))
            btn.clicked.connect(lambda _, k=key: self._select_color_theme(k))
            self._color_theme_buttons[key] = btn
            preset_grid.addWidget(btn, idx // 3, idx % 3)
        layout.addLayout(preset_grid)

        # "Edit Theme" — opens the custom colour editor
        c = _palette(is_night_mode)
        edit_row = QHBoxLayout()
        edit_row.addStretch(1)
        edit_btn = QPushButton(_("Edit Theme") + " ✎")
        edit_btn.setObjectName("EditThemeBtn")
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setFixedHeight(30)
        edit_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        edit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.get("grey_light","#E5E5EA")};
                color: {c.get("text","#1D1D1F")};
                border-radius: 8px; border: none; font-size: 12px; padding: 4px 14px;
            }}
            QPushButton:hover {{ background-color: {c.get("grey_mid","#D1D1D6")}; }}
        """)
        edit_btn.clicked.connect(self._open_theme_editor)
        edit_row.addWidget(edit_btn)
        layout.addSpacing(4)
        layout.addLayout(edit_row)

        # ── Separator ────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setObjectName("FooterSep")
        sep.setFixedHeight(1)
        layout.addSpacing(8)
        layout.addWidget(sep)
        layout.addSpacing(8)

        # ── Background style ─────────────────────────────────────────────────
        bg_lbl = QLabel(_("Background Style"))
        bg_lbl.setObjectName("FieldLabel")
        layout.addWidget(bg_lbl)
        bg_desc = QLabel(_("Overall background of the add-on screens."))
        bg_desc.setObjectName("SettingDesc"); bg_desc.setWordWrap(True)
        layout.addWidget(bg_desc)
        layout.addSpacing(6)
        self.visual_theme_combo = QComboBox()
        self.visual_theme_combo.setMinimumHeight(30)
        self.visual_theme_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.populate_themes()
        layout.addWidget(self.visual_theme_combo)

        return card

    def _select_color_theme(self, key: str) -> None:
        """Update the active preset and refresh all button checked-states."""
        self._color_theme_value = key
        for k, btn in self._color_theme_buttons.items():
            checked = (k == key)
            btn.setChecked(checked)
            bg, pr = self._theme_presets.get(k, ("#0071D3", "#004990"))
            btn.setStyleSheet(self._theme_btn_style(bg, pr, checked))

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
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(2)

        self._add_section_header(
            layout, _("Dashboard"),
            _("Widgets shown on the Anki home screen (the deck list)."),
        )

        self.add_checkbox(
            "minimal_dashboard_enabled", _("Minimalist Dashboard"), layout,
            _("Shows level, streak, challenge, study plan, deadline and key statistics in one compact panel."),
        )
        layout.addSpacing(8)

        features = [
            ("gamification_widgets_enabled", _("Gamification Widgets"),
             _("Your level, XP and daily streak.")),
            ("daily_widgets_enabled", _("Daily Widgets"),
             _("Your study plan and the daily fact.")),
            ("deadline_bar_enabled", _("Deadline Bar"),
             _("A countdown bar towards your exam or deadline.")),
            ("statistics_widget_enabled", _("Advanced Statistics"),
             _("An extra panel with detailed review statistics.")),
        ]
        for key, text, desc in features:
            self.add_checkbox(key, text, layout, desc)

        minimal_cb = self.checkboxes["minimal_dashboard_enabled"]
        widget_keys = [key for key, _text, _desc in features]

        def sync_minimal_widgets(enabled):
            for key in widget_keys:
                self.checkboxes[key].setEnabled(not bool(enabled))

        minimal_cb.toggled.connect(sync_minimal_widgets)
        sync_minimal_widgets(minimal_cb.isChecked())

        return card

    def create_deck_overview_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("CardFrame")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(2)

        self._add_section_header(
            layout, _("Deck Overview"),
            _("The screen shown after you click a deck, before studying."),
        )

        self.add_checkbox(
            "deck_overview_enabled", _("Enable Custom Deck Dashboard"), layout,
            _("Replaces the standard overview with a modern dashboard showing "
              "retention, hard cards and more."),
        )

        return card

    def create_sidebar_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("CardFrame")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(2)

        self._add_section_header(
            layout, _("Sidebar"),
            _("Tools available in the launcher bar on the side of Anki."),
        )

        features = [
            ("mindmap_enabled", _("Mind Map"),
             _("A visual mind-mapping panel.")),
            ("gamification_sidebar_enabled", _("Gamification Sidebar"),
             _("Progress, rewards and motivation panel.")),
            ("music_player_enabled", _("Music Player"),
             _("Background music while you study.")),
            ("pomodoro_enabled", _("Pomodoro Timer"),
             _("A focus timer with work and break intervals.")),
            ("ai_assistant_enabled", _("AI Assistant"),
             _("Chat assistant that can explain your cards.")),
            ("website_viewer_enabled", _("Website Viewer"),
             _("Open websites in a panel without leaving Anki.")),
            ("notebook_enabled", _("Notebook"),
             _("Notes, to-dos and PDFs alongside your cards.")),
        ]
        for key, text, desc in features:
            self.add_sidebar_setting(key, text, layout, desc)

        layout.addSpacing(8)
        hint = QLabel(_("Shortcuts apply immediately after saving. Restart Anki after enabling or disabling sidebar tools."))
        hint.setObjectName("HintText")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()
        return card

    def add_sidebar_setting(self, key, text, layout, desc=""):
        """Add one sidebar toggle and its native Qt shortcut recorder."""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 3, 0, 5)
        row_layout.setSpacing(12)

        labels = QWidget()
        labels_layout = QVBoxLayout(labels)
        labels_layout.setContentsMargins(0, 0, 0, 0)
        labels_layout.setSpacing(2)
        title = QLabel(text)
        title.setObjectName("FieldLabel")
        title.setWordWrap(True)
        labels_layout.addWidget(title)
        if desc:
            description = QLabel(desc)
            description.setObjectName("SettingDesc")
            description.setWordWrap(True)
            labels_layout.addWidget(description)
        row_layout.addWidget(labels, 1)

        cb = QCheckBox()
        cb.setCursor(Qt.CursorShape.PointingHandCursor)
        cb.setChecked(bool(self.current_config.get(key, True)))
        cb.setToolTip(_("Enable or disable this sidebar tool."))
        self.checkboxes[key] = cb
        row_layout.addWidget(cb, 0, Qt.AlignmentFlag.AlignVCenter)

        edit = QKeySequenceEdit()
        edit.setToolTip(_("Click and press a keyboard shortcut."))
        edit.setFixedWidth(145)
        try:
            edit.setMaximumSequenceLength(1)
            edit.setClearButtonEnabled(True)
        except (AttributeError, TypeError):
            pass
        current = {}
        if sidebar_shortcuts:
            current = sidebar_shortcuts.normalise_shortcut_map(
                self.current_config.get("sidebar_shortcuts", {})
            )
        portable = current.get(key, "")
        if portable:
            edit.setKeySequence(QKeySequence.fromString(
                portable, QKeySequence.SequenceFormat.PortableText
            ))
        self.shortcut_edits[key] = edit
        row_layout.addWidget(edit, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(row)

    def _add_section_header(self, layout, title, subtitle=""):
        """Left-aligned section title + optional muted description line."""
        t = QLabel(title)
        t.setObjectName("SectionTitle")
        t.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(t)
        if subtitle:
            d = QLabel(subtitle)
            d.setObjectName("SectionDesc")
            d.setWordWrap(True)
            layout.addWidget(d)
        layout.addSpacing(8)

    def add_checkbox(self, key, text, layout, desc=""):
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
        if desc:
            d = QLabel(desc)
            d.setObjectName("SettingDesc")
            d.setWordWrap(True)
            d.setContentsMargins(28, 0, 0, 6)  # indent under the checkbox label
            layout.addWidget(d)

    def add_button_row(self):
        """Save / Cancel row. Lives OUTSIDE the scroll area so it is always
        visible and clickable – no matter how small the screen is."""
        sep = QFrame()
        sep.setObjectName("FooterSep")
        sep.setFixedHeight(1)
        self.main_layout.addWidget(sep)

        hbox = QHBoxLayout()
        hbox.setContentsMargins(16, 10, 16, 12)
        hbox.setSpacing(8)

        cancel_btn = QPushButton(_("Cancel"))
        # ObjectName-based styling so the CSS selector keeps working even
        # when the button label is translated (see stylesheet).
        cancel_btn.setObjectName("CancelButton")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        save_btn = QPushButton(_("Save Settings"))
        save_btn.clicked.connect(self._accept_if_valid)
        save_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        save_btn.setDefault(True)

        hbox.addStretch()
        hbox.addWidget(cancel_btn)
        hbox.addWidget(save_btn)
        self.main_layout.addLayout(hbox)

    def _accept_if_valid(self):
        """Keep unsafe, duplicate or known-conflicting shortcuts out of config."""
        if sidebar_shortcuts:
            used = {}
            for key, edit in self.shortcut_edits.items():
                raw = edit.keySequence().toString(
                    QKeySequence.SequenceFormat.PortableText
                )
                if not raw:
                    continue
                feature = _(sidebar_shortcuts.FEATURE_LABELS.get(key, "Sidebar"))
                portable = sidebar_shortcuts.normalise_sequence(raw)
                if not sidebar_shortcuts.is_safe_sequence(raw):
                    QMessageBox.warning(
                        self, _("Keyboard Shortcut"),
                        _("Use Ctrl, Alt, Command or a function key.")
                    )
                    return
                if portable in used:
                    other = _(sidebar_shortcuts.FEATURE_LABELS.get(used[portable], "Sidebar"))
                    QMessageBox.warning(
                        self, _("Keyboard Shortcut"),
                        _("This shortcut is already assigned to {feature}.").format(
                            feature=other
                        )
                    )
                    return
                conflict = sidebar_shortcuts.find_existing_conflict(portable, mw)
                if conflict:
                    QMessageBox.warning(
                        self, _("Keyboard Shortcut"),
                        _("This shortcut is already used by Anki: {action}.").format(
                            action=conflict
                        )
                    )
                    return
                used[portable] = key
        self.accept()

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

    def _rescale_info_image(self):
        """Keep the header image sized to the current page width."""
        if self._info_image_label is None or self._info_pixmap_original is None:
            return
        try:
            avail = self._stack.width() if getattr(self, "_stack", None) else self.width()
            target_w = max(160, min(440, avail - 80))
            scaled = self._info_pixmap_original.scaledToWidth(
                target_w, Qt.TransformationMode.SmoothTransformation
            )
            self._info_image_label.setPixmap(scaled)
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale_info_image()

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
        QDesktopServices.openUrl(QUrl("https://ankiweb.net/shared/review/236979321"))

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
        if sidebar_shortcuts:
            settings["sidebar_shortcuts"] = sidebar_shortcuts.normalise_shortcut_map({
                key: edit.keySequence().toString(
                    QKeySequence.SequenceFormat.PortableText
                )
                for key, edit in self.shortcut_edits.items()
            })
        else:
            settings["sidebar_shortcuts"] = {}
        return settings
