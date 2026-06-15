
# -*- coding: utf-8 -*-

import os
import time
import traceback
import datetime
from typing import Optional, Callable

# --- PyQt Imports ---
try:
    from PyQt6.QtWidgets import (QDialog, QGridLayout, QLabel, QSpinBox, QLineEdit,
                                 QCheckBox, QDialogButtonBox, QVBoxLayout, QFrame,
                                 QHBoxLayout, QPushButton, QWidget, QTabWidget)
    from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont
    from PyQt6.QtCore import QTimer, pyqtSignal, Qt
    _qt_version = 6
except ImportError:
    try:
        from PyQt5.QtWidgets import (QDialog, QGridLayout, QLabel, QSpinBox, QLineEdit,
                                     QCheckBox, QDialogButtonBox, QVBoxLayout, QFrame,
                                     QHBoxLayout, QPushButton, QWidget, QTabWidget)
        from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont
        from PyQt5.QtCore import QTimer, pyqtSignal, Qt, pyqtSlot as Slot
        _qt_version = 5
    except ImportError:
        _qt_version = 0
        QDialog = object
        QTimer = object
        pyqtSignal = object
        Qt = object

# --- Anki Imports ---
from aqt import mw
from aqt.utils import showWarning, showInfo, tooltip, qconnect, askUser

# --- Local Imports ---
from . import constants

try:
    from .locales import _
except ImportError:
    def _(text):  # type: ignore
        return text

try:
    from .theme import palette as _palette, FONT_FAMILY as _FONT_FAMILY
except ImportError:
    def _palette(night): return {}  # type: ignore
    _FONT_FAMILY = "sans-serif"

pomodoro_timer: Optional[QTimer] = None
current_state = constants.STATE_IDLE
pomodoros_completed_cycle = 0
time_remaining = 0
previous_state = constants.STATE_IDLE
intended_next_state = constants.STATE_WORK

work_duration = 0
short_break_duration = 0
long_break_duration = 0
pomodoros_target = 0
sound_work_end = ""
sound_break_end = ""
auto_start_next = False

_update_ui_callback: Optional[Callable] = None
_update_label_only_callback: Optional[Callable] = None

# --- Night Mode Detection ---
is_night_mode = False
try:
    if mw.pm.night_mode():
        is_night_mode = True
except Exception:
    pass

# --- Stylesheets ---

def _build_pomodoro_style(night: bool) -> str:
    c = _palette(night)
    tab_inactive_bg  = c['surface'] if night else c['grey_light']
    tab_inactive_txt = c['text_muted'] if night else c['text']
    tab_hover_bg     = c['grey_mid'] if night else c['grey_mid']
    return f"""
    QDialog {{
        background-color: {c['bg']};
        font-family: {_FONT_FAMILY};
        font-size: 13px;
        color: {c['text']};
    }}
    QTabWidget::pane {{ border: none; background: transparent; }}
    QTabWidget > QWidget {{ background: transparent; }}
    QTabBar {{ background: transparent; }}
    QTabBar::tab {{
        background-color: {tab_inactive_bg};
        color: {tab_inactive_txt};
        border-radius: 7px;
        padding: 6px 22px;
        margin-right: 5px;
        font-weight: 500;
        min-width: 90px;
        border: none;
    }}
    QTabBar::tab:selected {{ background-color: {c['blue']}; color: white; }}
    QTabBar::tab:hover:!selected {{ background-color: {tab_hover_bg}; }}
    QFrame#CardFrame {{
        background-color: {c['surface']};
        border-radius: 12px;
        border: 1px solid {c['grey_light']};
    }}
    QLabel {{ color: {c['text']}; }}
    QLabel#HeaderLabel {{ font-size: 15px; font-weight: 700; }}
    QLabel#SettingLabel {{ font-size: 13px; font-weight: 500; }}
    QSpinBox {{
        background-color: {c['surface']}; border: 1px solid {c['grey_mid']}; border-radius: 8px;
        padding: 6px 8px; font-size: 13px; min-width: 60px; color: {c['text']};
    }}
    QSpinBox:focus {{ border: 2px solid {c['blue_bright']}; }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; height: 0px; border: none; }}
    QCheckBox {{ spacing: 8px; color: {c['text']}; }}
    QCheckBox::indicator {{
        width: 18px; height: 18px; border-radius: 4px;
        border: 1px solid {c['grey_mid']}; background-color: {c['surface']};
    }}
    QCheckBox::indicator:checked {{ background-color: {c['blue_bright']}; border: 1px solid {c['blue_bright']}; }}
    QPushButton {{
        background-color: {c['blue']}; color: white; border-radius: 8px;
        padding: 6px 16px; font-weight: 600; border: {c['blue_border']}; min-width: 80px;
    }}
    QPushButton:hover {{ background-color: {c['blue_hover']}; }}
    QPushButton:pressed {{ background-color: {c['blue_pressed']}; }}
    QPushButton#CancelButton {{
        background-color: {c['grey_light']}; color: {c['text']};
        border: {'1px solid ' + c['grey_light'] if night else 'none'};
    }}
    QPushButton#CancelButton:hover {{ background-color: {c['grey_mid']}; }}
"""

# Styles computed per-instance at widget creation time (not cached here).


# ─────────────────────────────────────────────────────────────────────────────
# Statistics helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_pomodoro_stats() -> dict:
    """Load Pomodoro statistics from Anki collection config."""
    if not mw or not mw.col:
        return constants.DEFAULT_POMODORO_STATS.copy()
    stats = mw.col.get_config(constants.CONFIG_KEY_POMODORO_STATS, constants.DEFAULT_POMODORO_STATS)
    for key, default_value in constants.DEFAULT_POMODORO_STATS.items():
        stats.setdefault(key, default_value)
    return stats


def save_pomodoro_stats(stats: dict):
    """Persist Pomodoro statistics to Anki collection config."""
    if not mw or not mw.col:
        return
    mw.col.set_config(constants.CONFIG_KEY_POMODORO_STATS, stats)


def calculate_current_streak(stats: dict) -> int:
    """Return the number of consecutive days (ending today) with ≥1 pomodoro."""
    daily_data = stats.get("daily_data", {})
    today = datetime.date.today()
    streak = 0
    day = today
    while True:
        date_str = day.isoformat()
        if daily_data.get(date_str, {}).get("pomodoros", 0) > 0:
            streak += 1
            day = day - datetime.timedelta(days=1)
        else:
            break
    return streak


def record_pomodoro_completed():
    """Record one finished Pomodoro work session into statistics."""
    work_mins = work_duration // 60 if work_duration > 0 else constants.DEFAULT_POMODORO_CONFIG["work_minutes"]
    stats = load_pomodoro_stats()
    today = datetime.date.today().isoformat()

    stats["total_pomodoros"] = stats.get("total_pomodoros", 0) + 1
    stats["total_focus_minutes"] = stats.get("total_focus_minutes", 0) + work_mins

    daily_data = stats.get("daily_data", {})
    if today not in daily_data:
        daily_data[today] = {"pomodoros": 0, "focus_minutes": 0}
    daily_data[today]["pomodoros"] += 1
    daily_data[today]["focus_minutes"] += work_mins
    stats["daily_data"] = daily_data

    current_streak = calculate_current_streak(stats)
    if current_streak > stats.get("best_streak", 0):
        stats["best_streak"] = current_streak

    save_pomodoro_stats(stats)
    print(f"{constants.ADDON_NAME_POMODORO}: Pomodoro recorded. Total: {stats['total_pomodoros']}")


# ─────────────────────────────────────────────────────────────────────────────
# Bar Chart Widget
# ─────────────────────────────────────────────────────────────────────────────

class PomodoroBarChart(QWidget):
    """Custom widget that paints a 7-day Pomodoro bar chart using QPainter."""

    def __init__(self, daily_data: dict, is_dark: bool = False, parent=None):
        super().__init__(parent)
        self.daily_data = daily_data
        self.is_dark = is_dark
        self.setMinimumHeight(150)

    def paintEvent(self, event):
        painter = QPainter(self)
        if _qt_version == 6:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        else:
            painter.setRenderHint(QPainter.Antialiasing)

        # ── Colours (from central theme) ─────────────────────────────────────
        c = _palette(self.is_dark)
        bar_color       = QColor(c["blue"])
        today_bar_color = QColor(c["blue_bright"])
        text_color      = QColor(c["text_muted"])
        today_txt_color = QColor(c["blue_bright"])
        count_color     = QColor(c["text_faint"])
        empty_color     = QColor(c["grey_light"] if not self.is_dark else c["hover_subtle"])

        # ── Data ─────────────────────────────────────────────────────────────
        SHORT_DAY_KEYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        today_date = datetime.date.today()
        days   = [today_date - datetime.timedelta(days=(6 - i)) for i in range(7)]
        labels = [_(SHORT_DAY_KEYS[d.weekday()]) for d in days]
        counts = [self.daily_data.get(d.isoformat(), {}).get("pomodoros", 0) for d in days]
        max_count = max((c for c in counts if c > 0), default=1)

        # ── Layout ───────────────────────────────────────────────────────────
        w           = self.width()
        h           = self.height()
        pad_left    = 6
        pad_right   = 6
        pad_top     = 20   # room for count labels above bars
        pad_bottom  = 22   # room for day labels below bars
        chart_w     = w - pad_left - pad_right
        chart_h     = h - pad_top - pad_bottom
        slot_w      = chart_w / 7
        bar_w       = max(slot_w * 0.52, 8.0)

        small_font = QFont()
        small_font.setPointSize(8)

        for i, (label, count, day) in enumerate(zip(labels, counts, days)):
            is_today   = (day == today_date)
            slot_x     = pad_left + i * slot_w
            bar_x      = slot_x + (slot_w - bar_w) / 2

            b_color  = today_bar_color if is_today else bar_color
            lbl_color = today_txt_color if is_today else text_color

            if _qt_version == 6:
                no_pen = Qt.PenStyle.NoPen
                align_hc = Qt.AlignmentFlag.AlignHCenter
                align_bot = Qt.AlignmentFlag.AlignBottom
                align_top = Qt.AlignmentFlag.AlignTop
            else:
                no_pen = Qt.NoPen
                align_hc  = Qt.AlignHCenter
                align_bot = Qt.AlignBottom
                align_top = Qt.AlignTop

            if count > 0:
                bar_h_px = max((count / max_count) * chart_h, 6.0)
                bar_y    = pad_top + chart_h - bar_h_px
                painter.setBrush(b_color)
                painter.setPen(no_pen)
                painter.drawRoundedRect(int(bar_x), int(bar_y), int(bar_w), int(bar_h_px), 4, 4)

                # Count label above bar
                cnt_font = QFont()
                cnt_font.setPointSize(8)
                if is_today:
                    cnt_font.setBold(True)
                painter.setFont(cnt_font)
                painter.setPen(b_color if is_today else count_color)
                painter.drawText(
                    int(bar_x), int(bar_y) - 16, int(bar_w), 16,
                    align_hc | align_bot, str(count)
                )
            else:
                # Ghost bar
                painter.setBrush(empty_color)
                painter.setPen(no_pen)
                painter.drawRoundedRect(
                    int(bar_x), int(pad_top + chart_h - 4), int(bar_w), 4, 2, 2
                )

            # Day label below
            lbl_font = QFont()
            lbl_font.setPointSize(8)
            if is_today:
                lbl_font.setBold(True)
            painter.setFont(lbl_font)
            painter.setPen(lbl_color)
            painter.drawText(
                int(slot_x), int(h - pad_bottom + 3), int(slot_w), 18,
                align_hc | align_top, label
            )

        painter.end()


# ─────────────────────────────────────────────────────────────────────────────
# Statistics Tab Widget
# ─────────────────────────────────────────────────────────────────────────────

class StatisticsTab(QWidget):
    """Tab widget that shows Pomodoro statistics with a 7-day bar chart."""

    def __init__(self, is_dark: bool = False, parent=None):
        super().__init__(parent)
        self.is_dark = is_dark
        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setSpacing(0)
        self._content = None
        self._refresh()

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _refresh(self):
        if self._content is not None:
            self._content.deleteLater()
        self._content = QWidget()
        self._outer_layout.addWidget(self._content)
        self._build_ui(self._content)

    def _make_stat_card(self, value_text: str, label_text: str) -> QFrame:
        card = QFrame()
        card.setObjectName("CardFrame")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 14, 8, 14)
        layout.setSpacing(4)

        if _qt_version == 6:
            center = Qt.AlignmentFlag.AlignCenter
        else:
            center = Qt.AlignCenter

        val_lbl = QLabel(value_text)
        val_lbl.setAlignment(center)
        val_lbl.setStyleSheet("font-size: 18px; font-weight: 700; border: none; background: transparent;")
        layout.addWidget(val_lbl)

        sub_color = _palette(self.is_dark)["text_muted"]
        lbl = QLabel(label_text)
        lbl.setWordWrap(True)
        lbl.setAlignment(center)
        lbl.setStyleSheet(
            f"font-size: 10px; color: {sub_color}; border: none; background: transparent;"
        )
        layout.addWidget(lbl)

        return card

    def _build_ui(self, container: QWidget):
        stats = load_pomodoro_stats()

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 14, 0, 4)
        layout.setSpacing(12)

        # ── Computed values ───────────────────────────────────────────────────
        total_pomodoros  = stats.get("total_pomodoros", 0)
        total_minutes    = stats.get("total_focus_minutes", 0)
        best_streak      = stats.get("best_streak", 0)
        current_streak   = calculate_current_streak(stats)

        def fmt_time(minutes: int) -> str:
            if minutes >= 60:
                return f"{minutes // 60}h {minutes % 60}m"
            return f"{minutes}m"

        today_str  = datetime.date.today().isoformat()
        today_data = stats.get("daily_data", {}).get(today_str, {})
        today_pom  = today_data.get("pomodoros", 0)
        today_min  = today_data.get("focus_minutes", 0)

        # ── Top stat cards ────────────────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)
        for val, lbl in [
            (str(total_pomodoros),    _("Total Pomodoros")),
            (fmt_time(total_minutes), _("Focus Time")),
            (str(current_streak),     _("Current Streak")),
            (str(best_streak),        _("Best Streak")),
        ]:
            cards_row.addWidget(self._make_stat_card(val, lbl))
        layout.addLayout(cards_row)

        # ── 7-day bar chart card ──────────────────────────────────────────────
        chart_card = QFrame()
        chart_card.setObjectName("CardFrame")
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(16, 14, 16, 14)
        chart_layout.setSpacing(8)

        chart_title = QLabel(_("Last 7 Days"))
        chart_title.setObjectName("HeaderLabel")
        chart_layout.addWidget(chart_title)

        chart = PomodoroBarChart(stats.get("daily_data", {}), is_dark=self.is_dark)
        chart.setFixedHeight(155)
        chart_layout.addWidget(chart)

        layout.addWidget(chart_card)

        # ── Today summary card ────────────────────────────────────────────────
        today_card = QFrame()
        today_card.setObjectName("CardFrame")
        today_layout = QHBoxLayout(today_card)
        today_layout.setContentsMargins(16, 11, 16, 11)

        today_lbl = QLabel(_("Today"))
        today_lbl.setObjectName("SettingLabel")
        today_layout.addWidget(today_lbl)
        today_layout.addStretch()

        today_val = QLabel(f"{today_pom} {_('sessions')}  ·  {fmt_time(today_min)}")
        today_layout.addWidget(today_val)

        layout.addWidget(today_card)

        # ── Reset button ──────────────────────────────────────────────────────
        reset_btn = QPushButton(_("Reset Statistics"))
        reset_btn.setObjectName("CancelButton")
        if _qt_version == 6:
            reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.clicked.connect(self._on_reset)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(reset_btn)
        layout.addLayout(btn_row)

        layout.addStretch()

    def _on_reset(self):
        if askUser(_("Are you sure you want to reset all Pomodoro statistics?")):
            if mw and mw.col:
                mw.col.set_config(
                    constants.CONFIG_KEY_POMODORO_STATS,
                    constants.DEFAULT_POMODORO_STATS.copy()
                )
            tooltip(_("Statistics reset."))
            self._refresh()


# ─────────────────────────────────────────────────────────────────────────────
# Config Dialog (with Tabs)
# ─────────────────────────────────────────────────────────────────────────────

def load_pomodoro_config(update_ui: bool = True):
    global work_duration, short_break_duration, long_break_duration, pomodoros_target
    global sound_work_end, sound_break_end, auto_start_next
    if not mw or not mw.col:
        print(f"{constants.ADDON_NAME_POMODORO}: Cannot load config, mw.col not available.")
        config = constants.DEFAULT_POMODORO_CONFIG.copy()
    else:
        config = mw.col.get_config(constants.CONFIG_KEY_POMODORO, constants.DEFAULT_POMODORO_CONFIG)
        for key, default_value in constants.DEFAULT_POMODORO_CONFIG.items():
            config.setdefault(key, default_value)

    work_duration = config["work_minutes"] * 60
    short_break_duration = config["short_break_minutes"] * 60
    long_break_duration = config["long_break_minutes"] * 60
    pomodoros_target = config["pomodoros_before_long_break"]
    auto_start_next = config["auto_start_next"]

    sound_work_end = "bells.wav"
    sound_break_end = "chime.wav"

    if current_state == constants.STATE_IDLE:
        reset_action(update_ui=False)

    if update_ui and _update_ui_callback:
        _update_ui_callback()

    print(f"{constants.ADDON_NAME_POMODORO}: Config loaded.")

def save_pomodoro_config(config):
     if not mw or not mw.col:
        print(f"{constants.ADDON_NAME_POMODORO}: Cannot save config, mw.col not available.")
        return
     config.pop("sound_work_end", None)
     config.pop("sound_break_end", None)
     mw.col.set_config(constants.CONFIG_KEY_POMODORO, config)
     load_pomodoro_config()
     tooltip(_("Pomodoro settings saved."))


class PomodoroConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle(_("Pomodoro"))
        self.setMinimumWidth(500)
        self.setMinimumHeight(380)
        self.setMaximumHeight(520)

        self.setStyleSheet(_build_pomodoro_style(is_night_mode))

        self.config = (
            mw.col.get_config(constants.CONFIG_KEY_POMODORO, constants.DEFAULT_POMODORO_CONFIG)
            if mw and mw.col else constants.DEFAULT_POMODORO_CONFIG.copy()
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # ── Tab widget ────────────────────────────────────────────────────────
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("PomodoroTabWidget")

        # Tab 1 – Settings
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)
        settings_layout.setContentsMargins(0, 14, 0, 0)
        settings_layout.setSpacing(14)
        self._build_settings_content(settings_layout)
        self.tab_widget.addTab(settings_tab, _("Settings"))

        # Tab 2 – Statistics
        self._stats_tab = StatisticsTab(is_dark=is_night_mode)
        self.tab_widget.addTab(self._stats_tab, _("Statistics"))

        main_layout.addWidget(self.tab_widget)

        # ── Bottom buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        self.cancel_btn = QPushButton(_("Cancel"))
        self.cancel_btn.setObjectName("CancelButton")
        if _qt_version == 6:
            self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton(_("Save Settings"))
        if _qt_version == 6:
            self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self.on_accept)

        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.save_btn)
        main_layout.addLayout(btn_row)

        # Show/hide Save button depending on active tab
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int):
        self.save_btn.setVisible(index == 0)

    def _build_settings_content(self, layout: QVBoxLayout):
        """Build the Settings card into *layout*."""
        card = QFrame()
        card.setObjectName("CardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 28, 20, 28)
        card_layout.setSpacing(15)


        grid = QGridLayout()
        grid.setVerticalSpacing(14)
        grid.setHorizontalSpacing(15)

        def _spin(label_key: str, attr: str, min_val: int, max_val: int, cfg_key: str, row: int):
            lbl = QLabel(_(label_key))
            lbl.setObjectName("SettingLabel")
            spin = QSpinBox()
            spin.setRange(min_val, max_val)
            spin.setValue(self.config[cfg_key])
            spin.setSuffix(_(" min"))
            if _qt_version == 6:
                spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                spin.setAlignment(Qt.AlignCenter)
            setattr(self, attr, spin)
            grid.addWidget(lbl,  row, 0)
            grid.addWidget(spin, row, 1)

        _spin("Work Duration:",    "work_spin",   1, 120, "work_minutes",               0)
        _spin("Short Break:",      "short_spin",  1,  60, "short_break_minutes",        1)
        _spin("Long Break:",       "long_spin",   1, 120, "long_break_minutes",         2)

        lbl_target = QLabel(_("Intervals per Cycle:"))
        lbl_target.setObjectName("SettingLabel")
        self.target_spin = QSpinBox()
        self.target_spin.setRange(1, 10)
        self.target_spin.setValue(self.config["pomodoros_before_long_break"])
        if _qt_version == 6:
            self.target_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            self.target_spin.setAlignment(Qt.AlignCenter)
        grid.addWidget(lbl_target,       3, 0)
        grid.addWidget(self.target_spin, 3, 1)

        card_layout.addLayout(grid)
        card_layout.addSpacing(8)

        self.auto_start_check = QCheckBox(_("Auto-start next timer"))
        self.auto_start_check.setChecked(self.config["auto_start_next"])
        if _qt_version == 6:
            self.auto_start_check.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.auto_start_check.setCursor(Qt.PointingHandCursor)

        chk_row = QHBoxLayout()
        chk_row.addStretch()
        chk_row.addWidget(self.auto_start_check)
        chk_row.addStretch()
        card_layout.addLayout(chk_row)

        layout.addWidget(card)
        layout.addStretch()

    def on_accept(self):
        self.config["work_minutes"]               = self.work_spin.value()
        self.config["short_break_minutes"]        = self.short_spin.value()
        self.config["long_break_minutes"]         = self.long_spin.value()
        self.config["pomodoros_before_long_break"] = self.target_spin.value()
        self.config["auto_start_next"]            = self.auto_start_check.isChecked()
        save_pomodoro_config(self.config)
        self.accept()


def open_pomodoro_config():
    if not mw:
        return
    load_pomodoro_config(update_ui=False)
    dialog = PomodoroConfigDialog()
    dialog.exec()
    if _update_ui_callback:
        _update_ui_callback()


# ─────────────────────────────────────────────────────────────────────────────
# Timer helpers
# ─────────────────────────────────────────────────────────────────────────────

def format_time(seconds):
    mins, secs = divmod(int(seconds), 60)
    return f"{mins:02d}:{secs:02d}"

def get_current_phase_duration() -> int:
    state = current_state if current_state != constants.STATE_PAUSED else previous_state
    if state == constants.STATE_WORK:        return work_duration
    if state == constants.STATE_SHORT_BREAK: return short_break_duration
    if state == constants.STATE_LONG_BREAK:  return long_break_duration
    if state == constants.STATE_IDLE:
        next_intended = intended_next_state if intended_next_state is not None else constants.STATE_WORK
        if next_intended == constants.STATE_LONG_BREAK:  return long_break_duration
        if next_intended == constants.STATE_SHORT_BREAK: return short_break_duration
        return work_duration
    return 1

def start_pause_action():
    global current_state, previous_state, time_remaining, intended_next_state
    if not pomodoro_timer: return
    if pomodoro_timer.isActive():
        if current_state != constants.STATE_PAUSED: previous_state = current_state
        current_state = constants.STATE_PAUSED
        pomodoro_timer.stop()
        print(f"{constants.ADDON_NAME_POMODORO}: Paused (was {previous_state})")
    else:
        if current_state == constants.STATE_IDLE:
            if intended_next_state is None: intended_next_state = constants.STATE_WORK
            current_state = intended_next_state
            time_remaining = get_current_phase_duration()
            previous_state = constants.STATE_IDLE
            intended_next_state = None
            print(f"{constants.ADDON_NAME_POMODORO}: Starting state {current_state} from IDLE with duration {time_remaining}")
        elif current_state == constants.STATE_PAUSED:
            current_state = previous_state
            print(f"{constants.ADDON_NAME_POMODORO}: Resuming state {current_state}")
        else:
            print(f"{constants.ADDON_NAME_POMODORO}: Unexpected state {current_state} on start/resume. Resetting.")
            reset_action(True); return

        if time_remaining > 0:
            pomodoro_timer.start(1000)
        else:
            print(f"{constants.ADDON_NAME_POMODORO}: Warning - Start/resume attempt with 0 time remaining. Resetting.")
            reset_action(True); return

    if _update_ui_callback:
        _update_ui_callback()

def reset_action(update_ui=True):
    global current_state, time_remaining, pomodoros_completed_cycle, previous_state, intended_next_state
    if pomodoro_timer: pomodoro_timer.stop()
    current_state = constants.STATE_IDLE
    pomodoros_completed_cycle = 0
    previous_state = constants.STATE_IDLE
    intended_next_state = constants.STATE_WORK
    current_work_duration = work_duration if work_duration > 0 else constants.DEFAULT_POMODORO_CONFIG["work_minutes"] * 60
    time_remaining = current_work_duration

    print(f"{constants.ADDON_NAME_POMODORO}: Reset. Next is WORK with duration {time_remaining}")
    if update_ui and _update_ui_callback:
        _update_ui_callback()

def skip_action():
    global previous_state
    if not pomodoro_timer: return
    pomodoro_timer.stop()

    state_to_skip = current_state if current_state != constants.STATE_PAUSED else previous_state

    if state_to_skip == constants.STATE_IDLE:
        print(f"{constants.ADDON_NAME_POMODORO}: Skipping from IDLE state. Transitioning to next intended: {intended_next_state}")
        handle_state_transition(finished_state=intended_next_state)
    else:
        print(f"{constants.ADDON_NAME_POMODORO}: Skipping active/paused state {state_to_skip}")
        handle_state_transition(skipped_state=state_to_skip)


def update_timer():
    global time_remaining
    if not pomodoro_timer or not pomodoro_timer.isActive(): return

    if time_remaining > 0:
        time_remaining -= 1
        if _update_label_only_callback:
            _update_label_only_callback()
    else:
        pomodoro_timer.stop()
        finished_state = current_state
        print(f"{constants.ADDON_NAME_POMODORO}: State {finished_state} finished.")
        handle_state_transition(finished_state=finished_state)
        if auto_start_next and current_state == constants.STATE_IDLE and intended_next_state is not None:
            print(f"{constants.ADDON_NAME_POMODORO}: Auto-starting next phase ({intended_next_state})...")
            QTimer.singleShot(500, start_pause_action)


def handle_state_transition(finished_state=None, skipped_state=None):
    global current_state, time_remaining, pomodoros_completed_cycle, previous_state, intended_next_state

    state_ended = finished_state if finished_state is not None else skipped_state

    next_state = constants.STATE_WORK
    next_duration = work_duration
    sound_to_play = None
    notification = None

    if state_ended == constants.STATE_WORK:
        pomodoros_completed_cycle += 1
        sound_to_play = sound_work_end
        notification = _("Work session finished! ({}/{})").format(pomodoros_completed_cycle, pomodoros_target)

        # Only record stats for natural completion (not user skips)
        if finished_state is not None:
            try:
                record_pomodoro_completed()
            except Exception as e:
                print(f"{constants.ADDON_NAME_POMODORO}: Error recording stats: {e}")

        if pomodoros_completed_cycle >= pomodoros_target:
            next_state = constants.STATE_LONG_BREAK
            next_duration = long_break_duration
            pomodoros_completed_cycle = 0
            notification += _("\nNext: Long Break!")
        else:
            next_state = constants.STATE_SHORT_BREAK
            next_duration = short_break_duration
            notification += _("\nNext: Short Break!")

    elif state_ended in [constants.STATE_SHORT_BREAK, constants.STATE_LONG_BREAK]:
        next_state = constants.STATE_WORK
        next_duration = work_duration
        sound_to_play = sound_break_end
        notification = _("Break finished!\nNext: Work")

    elif state_ended == constants.STATE_IDLE or state_ended is None:
        next_state = constants.STATE_WORK
        next_duration = work_duration
        pomodoros_completed_cycle = 0
        print(f"{constants.ADDON_NAME_POMODORO}: Transition from IDLE/Reset/Skip-Idle, next is WORK")

    else:
        print(f"{constants.ADDON_NAME_POMODORO}: Fallback state transition from unknown state {state_ended}, next is WORK")
        next_state = constants.STATE_WORK
        next_duration = work_duration
        pomodoros_completed_cycle = 0

    if sound_to_play and finished_state is not None:
        if constants.sound_available:
            full_sound_path = os.path.join(constants.icons_folder, sound_to_play)
            if os.path.exists(full_sound_path):
                try:
                    print(f"{constants.ADDON_NAME_POMODORO}: Attempting to play sound: {full_sound_path}")
                    constants.play_sound_function(full_sound_path)
                except Exception as e:
                    err_msg = _("Pomodoro: Error playing '{}': {}").format(sound_to_play, e)
                    print(f"{constants.ADDON_NAME_POMODORO}: Sound Error playing '{full_sound_path}': {e}")
                    tooltip(err_msg)
            else:
                err_msg = _("Pomodoro: Sound file '{}' not found in folder '{}'.").format(
                    sound_to_play, os.path.basename(constants.icons_folder)
                )
                print(f"{constants.ADDON_NAME_POMODORO}: Sound file not found at: {full_sound_path}")
                tooltip(err_msg)
        else:
            print(f"{constants.ADDON_NAME_POMODORO}: Sound playback skipped (anki.sound not available or disabled).")

    if notification and finished_state is not None:
        try:
            if mw:
                showInfo(notification, title=_("Pomodoro"))
            else:
                print(f"{constants.ADDON_NAME_POMODORO}: Notification skipped (mw not available): {notification}")
        except Exception as e:
            print(f"{constants.ADDON_NAME_POMODORO}: Error showing notification: {e}")

    current_state = constants.STATE_IDLE
    intended_next_state = next_state
    time_remaining = next_duration

    print(f"{constants.ADDON_NAME_POMODORO}: Transition complete. Now IDLE, next intended: {intended_next_state}, duration: {time_remaining}")

    if _update_ui_callback:
        _update_ui_callback()


def init_pomodoro(parent, update_ui_func: Callable, update_label_func: Callable):
    global pomodoro_timer, _update_ui_callback, _update_label_only_callback
    if not pomodoro_timer:
        try:
            pomodoro_timer = QTimer(parent)
            qconnect(pomodoro_timer.timeout, update_timer)
            _update_ui_callback = update_ui_func
            _update_label_only_callback = update_label_func
            print(f"{constants.ADDON_NAME_POMODORO}: QTimer created and callbacks set.")
            load_pomodoro_config(update_ui=True)
        except Exception as e:
            print(f"{constants.ADDON_NAME_POMODORO}: Error initializing timer: {e}")
            traceback.print_exc()
            pomodoro_timer = None
    else:
        _update_ui_callback = update_ui_func
        _update_label_only_callback = update_label_func
        print(f"{constants.ADDON_NAME_POMODORO}: Timer already exists, callbacks updated.")
        load_pomodoro_config(update_ui=True)

def cleanup_pomodoro():
    global pomodoro_timer, _update_ui_callback, _update_label_only_callback
    if pomodoro_timer:
        if pomodoro_timer.isActive():
            pomodoro_timer.stop()
        try:
            pomodoro_timer.timeout.disconnect(update_timer)
        except (TypeError, RuntimeError):
            pass
        pomodoro_timer = None
        _update_ui_callback = None
        _update_label_only_callback = None
        print(f"{constants.ADDON_NAME_POMODORO}: Timer stopped and cleaned up.")
