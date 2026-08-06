# -*- coding: utf-8 -*-

import json
import os
import traceback
import copy
import uuid
from typing import Dict, Optional, List, TYPE_CHECKING
from datetime import date, datetime

from aqt import mw
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QPushButton, QLineEdit, QTimeEdit, QTime,
    QLabel, QDialogButtonBox, QMessageBox, QWidget, Qt, QTimer, QShortcut, QKeySequence,
    QCalendarWidget, QDate, QCheckBox, QDateEdit, QFrame,
    QFormLayout,
    QSizePolicy,
    QFont, QColor, QPainter, QPen, QBrush, QRectF, QIcon, QToolButton,
    QTextEdit,
    QApplication,
    QDesktopServices, QUrl
)
from aqt.utils import showInfo, tooltip

# --- Addon Imports ---
try:
    from .learning_plan import PlanItemConfig, LearningPlanManager
except ImportError:
    PlanItemConfig = Dict; LearningPlanManager = None

try:
    from .gamification import ADDON_NAME, GamificationManager
except ImportError:
    ADDON_NAME = "GamificationPlusDailyWidgets_ConfigImportFailed"; GamificationManager = None

try:
    from .deadline_bar import DeadlineManager, DEADLINE_CONFIG_KEY
except ImportError:
    DeadlineManager = None; DEADLINE_CONFIG_KEY = "deadline_import_fail"

is_night_mode = False
try:
    if mw.pm.night_mode():
        is_night_mode = True
except Exception:
    pass

# --- Translation ---
try:
    from .locales import _
except ImportError:
    def _(text): return text  # type: ignore

# --- Theme ---
try:
    from .theme import palette as _palette, FONT_FAMILY as _FONT_FAMILY
except ImportError:
    def _palette(night): return {}  # type: ignore
    _FONT_FAMILY = "sans-serif"

# --- Stylesheets ---

def _build_style(night: bool) -> str:
    c = _palette(night)
    return f"""
    QDialog {{
        background-color: {c['bg']};
        font-family: {_FONT_FAMILY};
        font-size: 13px;
        color: {c['text']};
    }}

    QFrame#CardFrame {{
        background-color: {c['surface']};
        border-radius: 12px;
        border: 1px solid {c['grey_light']};
    }}

    QLabel {{ color: {c['text']}; }}
    QLabel#HeaderLabel {{ font-size: 16px; font-weight: 700; color: {c['text']}; margin-bottom: 4px; }}
    QLabel#SubLabel {{ color: {c['text_muted']}; font-size: 12px; }}

    QLineEdit, QTimeEdit, QDateEdit, QTextEdit {{
        background-color: {c['surface']}; border: 1px solid {c['grey_mid']}; border-radius: 8px; padding: 6px 8px; color: {c['text']};
    }}
    QLineEdit:focus, QTimeEdit:focus, QDateEdit:focus, QTextEdit:focus {{ border: 2px solid {c['blue_bright']}; }}

    QPushButton {{
        background-color: {c['blue']}; color: white; border-radius: 8px; padding: 6px 16px; font-weight: 600; border: {c['blue_border']};
    }}
    QPushButton:hover {{ background-color: {c['blue_hover']}; }}
    QPushButton:pressed {{ background-color: {c['blue_pressed']}; }}
    QPushButton:disabled {{ background-color: {c['grey_light']}; color: {c['text_faint']}; border: none; }}

    QPushButton#SecondaryButton {{ background-color: {c['grey_light']}; color: {c['text']}; border: {c['red_border'].replace('A00000','404040') if night else 'none'}; }}
    QPushButton#SecondaryButton:hover {{ background-color: {c['grey_mid']}; }}

    QPushButton#DangerButton {{ background-color: {c['red']}; color: white; border: {c['red_border']}; }}
    QPushButton#DangerButton:hover {{ background-color: {c['red_hover']}; }}

    QTableWidget {{
        background-color: {c['surface']}; border: 1px solid {c['grey_light']}; border-radius: 8px; color: {c['text']};
        selection-background-color: {c['selection_bg']}; selection-color: {c['blue_bright']}; gridline-color: {c['grey_light']};
    }}
    QHeaderView::section {{
        background-color: {c['surface']}; border: none; border-bottom: 1px solid {c['grey_light']};
        padding: 6px; font-weight: bold; color: {c['text_muted']};
    }}

    QCalendarWidget {{ background-color: {c['surface']}; border: none; }}
    QCalendarWidget QWidget {{ alternate-background-color: {c['surface']}; background-color: {c['surface']}; color: {c['text']}; }}
    QCalendarWidget QWidget#qt_calendar_navigationbar {{
        background-color: {c['surface']}; border-bottom: 1px solid {c['hover_subtle']};
    }}
    QCalendarWidget QToolButton {{
        color: {c['text']}; background-color: transparent; border: none;
        border-radius: 7px; padding: 3px 7px;
    }}
    QCalendarWidget QToolButton:hover {{ background-color: {c['hover_subtle']}; }}
    QCalendarWidget QToolButton:pressed {{ background-color: {c['grey_light']}; }}
    QCalendarWidget QToolButton#qt_calendar_prevmonth,
    QCalendarWidget QToolButton#qt_calendar_nextmonth {{
        color: {c['text_muted']}; border-radius: 14px; padding: 0;
        font-size: 24px; font-weight: 400;
    }}
    QCalendarWidget QToolButton#qt_calendar_prevmonth:hover,
    QCalendarWidget QToolButton#qt_calendar_nextmonth:hover {{
        color: {c['blue_accent']}; background-color: {c['hover_subtle']};
    }}
    QCalendarWidget QToolButton#qt_calendar_monthbutton,
    QCalendarWidget QToolButton#qt_calendar_yearbutton {{
        color: {c['text']}; font-size: 14px; font-weight: 600;
    }}
    QCalendarWidget QToolButton::menu-indicator {{ image: none; }}
    QCalendarWidget QSpinBox {{
        color: {c['text']}; background: {c['surface']}; border: 1px solid {c['grey_mid']};
        border-radius: 6px; padding: 2px 5px;
        selection-background-color: {c['selection_bg']}; selection-color: {c['text']};
    }}
    QCalendarWidget QAbstractItemView:enabled {{
        color: {c['text']}; background-color: {c['surface']};
        selection-background-color: transparent; selection-color: {c['text']};
        border: none; outline: none;
    }}
    QCalendarWidget QAbstractItemView:disabled {{ color: {c['text_faint']}; }}

    QCheckBox {{ color: {c['text']}; }}
"""

# Styles computed per-instance at widget creation time (not cached here).


class StudyPlanCalendarWidget(QCalendarWidget):
    """Clean, theme-aware calendar without platform-specific Qt chrome.

    QCalendarWidget intentionally exposes ``paintCell()`` for custom day
    rendering.  Keeping the customization there preserves Qt's native date
    model, keyboard navigation and accessibility while avoiding fragile
    delegates or per-cell child widgets.
    """

    _SELECTION_DIAMETER = 32.0
    _PLAN_DOT_DIAMETER = 5.0

    def __init__(self, night: bool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        colors = _palette(night)
        self._surface_color = QColor(colors["surface"])
        self._accent_color = QColor(colors["blue_accent"])
        self._selected_text_color = QColor("#FFFFFF")
        self._plan_dates: set[int] = set()
        self._configure_navigation_buttons()

    def _configure_navigation_buttons(self) -> None:
        """Replace style-dependent native arrows with quiet text chevrons.

        The internal object names have been stable throughout Qt 6.  Missing
        buttons are simply ignored, so a future Qt change falls back to its
        native icons instead of breaking the calendar.
        """
        buttons = (
            ("qt_calendar_prevmonth", "\u2039"),
            ("qt_calendar_nextmonth", "\u203a"),
        )
        for object_name, chevron in buttons:
            button = self.findChild(QToolButton, object_name)
            if button is None:
                continue
            button.setIcon(QIcon())
            button.setText(chevron)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            button.setFixedSize(28, 28)
            button.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_plan_dates(self, dates: List[QDate]) -> None:
        """Replace all plan markers atomically and discard invalid dates."""
        updated = {
            value.toJulianDay()
            for value in dates
            if isinstance(value, QDate) and value.isValid()
        }
        if updated == self._plan_dates:
            return
        self._plan_dates = updated
        self.updateCells()

    def _day_circle(self, rect) -> QRectF:
        available = max(18.0, min(float(rect.width()), float(rect.height())) - 8.0)
        diameter = min(self._SELECTION_DIAMETER, available)
        center = rect.center()
        return QRectF(
            center.x() - diameter / 2.0,
            center.y() - diameter / 2.0,
            diameter,
            diameter,
        )

    def paintCell(self, painter: QPainter, rect, cell_date: QDate) -> None:  # noqa: N802 - Qt API
        selected = cell_date == self.selectedDate()
        today = cell_date == QDate.currentDate()
        has_plan = cell_date.toJulianDay() in self._plan_dates

        if not selected:
            super().paintCell(painter, rect, cell_date)

        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            circle = self._day_circle(rect)

            if selected:
                # Fully repaint the selected cell so Qt's platform-specific
                # rectangular selection cannot remain visible underneath.
                painter.fillRect(rect, self._surface_color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(self._accent_color))
                painter.drawEllipse(circle)

                font = painter.font()
                font.setWeight(QFont.Weight.DemiBold)
                painter.setFont(font)
                painter.setPen(self._selected_text_color)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(cell_date.day()))
            elif today:
                pen = QPen(self._accent_color)
                pen.setWidthF(1.5)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(circle.adjusted(1.0, 1.0, -1.0, -1.0))

            if has_plan:
                # A compact dot communicates that work is planned without
                # competing with the selected-date circle.
                dot_diameter = self._PLAN_DOT_DIAMETER
                dot_y = min(
                    float(rect.bottom()) - dot_diameter - 2.0,
                    circle.bottom() + 4.0,
                )
                dot = QRectF(
                    float(rect.center().x()) - dot_diameter / 2.0,
                    dot_y,
                    dot_diameter,
                    dot_diameter,
                )
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(self._accent_color))
                painter.drawEllipse(dot)
        finally:
            painter.restore()

class AIPlanHelperDialog(QDialog):
    """A dialog to help users generate a study plan JSON using an AI like ChatGPT."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle(_("AI Study Plan Generator Helper"))
        
        self.resize(700, 750)
        self.setMinimumSize(500, 500) 
        
        self.setStyleSheet(_build_style(is_night_mode))
        self.imported_plan: Optional[Dict] = None

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        instruction_frame = QFrame()
        instruction_frame.setObjectName("CardFrame")
        instr_layout = QVBoxLayout(instruction_frame)
        title = QLabel(_("Generate with AI"))
        title.setObjectName("HeaderLabel")
        instr_layout.addWidget(title)
        intro_label = QLabel(_("Follow these steps to generate a study plan with an AI (like ChatGPT, Claude) and import it."))
        intro_label.setWordWrap(True)
        instr_layout.addWidget(intro_label)

        self.yt_button = QPushButton(_("Watch Tutorial on YouTube"))
        self.yt_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.yt_button.clicked.connect(self.open_youtube_tutorial)
        instr_layout.addWidget(self.yt_button)

        layout.addWidget(instruction_frame)

        step1_frame = QFrame()
        step1_frame.setObjectName("CardFrame")
        step1_layout = QVBoxLayout(step1_frame)
        step1_label = QLabel("Step 1: Get the Prompt")
        step1_label.setObjectName("HeaderLabel")
        step1_layout.addWidget(step1_label)
        instructions1 = QLabel(_("Fill in your details, then copy this to your AI."))
        instructions1.setWordWrap(True); instructions1.setObjectName("SubLabel")
        step1_layout.addWidget(instructions1)
        self.prompt_text_edit = QTextEdit()
        self.prompt_text_edit.setPlainText(self._get_prompt_template())
        self.prompt_text_edit.setFixedHeight(150)
        step1_layout.addWidget(self.prompt_text_edit)
        copy_button = QPushButton("Copy Prompt to Clipboard")
        copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_button.clicked.connect(self.copy_prompt_to_clipboard)
        step1_layout.addWidget(copy_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(step1_frame)

        step2_frame = QFrame()
        step2_frame.setObjectName("CardFrame")
        step2_layout = QVBoxLayout(step2_frame)
        step2_label = QLabel(_("Step 2: Paste JSON Result"))
        step2_label.setObjectName("HeaderLabel")
        step2_layout.addWidget(step2_label)
        instructions2 = QLabel(_("Paste the JSON code block here."))
        instructions2.setObjectName("SubLabel")
        step2_layout.addWidget(instructions2)
        self.json_input_area = QTextEdit()
        self.json_input_area.setPlaceholderText(_("Paste the { ... } JSON code here..."))
        self.json_input_area.setFont(QFont("Courier New", 12))
        step2_layout.addWidget(self.json_input_area)
        layout.addWidget(step2_frame)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText(_("Import Plan"))
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setCursor(Qt.CursorShape.PointingHandCursor)
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("SecondaryButton")
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setCursor(Qt.CursorShape.PointingHandCursor)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        
    def open_youtube_tutorial(self):
        url = QUrl("https://www.youtube.com/watch?v=7cpZ4dHNiDs&t")
        QDesktopServices.openUrl(url)

    def _get_prompt_template(self) -> str:
        return """You are an expert assistant tasked with creating a structured study plan for a student using the Anki flashcard application.

The final output MUST be a JSON object, and nothing else.

The JSON structure must be as follows:
- The root is an object.
- Each key is a string representing a date in "YYYYMMDD" format.
- The value for each date is another object containing the subjects to study on that day.
- Each subject key is the name of the subject (e.g., "Anatomy").
- The value for each subject is an object with a single key: "target_seconds".
- The value of "target_seconds" is an integer representing the total study time for that subject on that day in seconds.

Example:
{
    "20260125": { "Anatomy": { "target_seconds": 3600 } }
}

Create a plan based on these requirements:
--- REQUIREMENTS ---
- Start Date: [Enter start date]
- End Date: [Enter exam date]
- Subjects: [List subjects and frequency]
- Days off: [e.g. Sundays]
- Strategy: [e.g. Even distribution]
"""

    def copy_prompt_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.prompt_text_edit.toPlainText())
        tooltip("Prompt copied to clipboard!", parent=self)

    @staticmethod
    def _sanitize_plan(parsed_data: dict):
        """Validates and normalizes an imported plan.

        Expected: { "YYYYMMDD": { "Subject": { "target_seconds": int } } }.
        Heals common AI output quirks (dates with dashes, numeric strings,
        bare numbers as subject values) and drops unusable entries.
        Returns (plan_dict, list_of_dropped_entry_descriptions).
        """
        plan: Dict[str, Dict[str, Dict]] = {}
        dropped: List[str] = []
        for raw_date, day_value in parsed_data.items():
            date_key = str(raw_date).strip().replace("-", "")
            if not (len(date_key) == 8 and date_key.isdigit()):
                dropped.append(f'"{raw_date}" (not a YYYYMMDD date)')
                continue
            try:
                datetime.strptime(date_key, "%Y%m%d")
            except ValueError:
                dropped.append(f'"{raw_date}" (not a real calendar date)')
                continue
            if not isinstance(day_value, dict):
                dropped.append(f'"{raw_date}" (value must be an object with subjects)')
                continue
            day_plan: Dict[str, Dict] = {}
            for subject, cfg in day_value.items():
                subject_name = str(subject).strip()[:120]
                if not subject_name:
                    dropped.append(f'"{raw_date}" (empty subject name)')
                    continue
                # Heal: bare number instead of { "target_seconds": n }
                if isinstance(cfg, (int, float)) and not isinstance(cfg, bool):
                    cfg = {"target_seconds": cfg}
                if not isinstance(cfg, dict):
                    dropped.append(f'"{raw_date}" → "{subject_name}" (value must be an object)')
                    continue
                target = cfg.get("target_seconds", 0)
                if isinstance(target, str):
                    try: target = float(target)
                    except ValueError: target = None
                if (isinstance(target, bool) or not isinstance(target, (int, float))
                        or target <= 0 or target > 86400):
                    dropped.append(f'"{raw_date}" → "{subject_name}" ("target_seconds" must be between 1 and 86400)')
                    continue
                clean_cfg = dict(cfg)
                clean_cfg["target_seconds"] = int(target)
                day_plan[subject_name] = clean_cfg
            if day_plan:
                plan[date_key] = day_plan
        return plan, dropped

    def accept(self):
        json_text = self.json_input_area.toPlainText().strip()
        if not json_text: return
        try:
            if json_text.startswith("```json"): json_text = json_text[7:]
            if json_text.startswith("```"): json_text = json_text[3:]
            if json_text.endswith("```"): json_text = json_text[:-3]
            parsed_data = json.loads(json_text)
        except Exception as e:
            QMessageBox.critical(self, _("Import Error"), _("Invalid JSON.") + f"\n{e}")
            return
        try:
            if not isinstance(parsed_data, dict):
                QMessageBox.critical(self, _("Import Error"),
                    _("Invalid JSON.") + "\n" +
                    'The root must be an object like {"20260125": {"Anatomy": {"target_seconds": 3600}}}, '
                    f'but got: {type(parsed_data).__name__}.')
                return
            plan, dropped = self._sanitize_plan(parsed_data)
            if not plan:
                QMessageBox.critical(self, _("Import Error"),
                    _("Invalid JSON.") + "\n" +
                    'No valid plan entries found. Expected structure:\n'
                    '{"20260125": {"Anatomy": {"target_seconds": 3600}}}\n\n'
                    + ("Problems:\n" + "\n".join(dropped[:8]) if dropped else ""))
                return
            if dropped:
                QMessageBox.warning(self, _("Import Error"),
                    f"{len(dropped)} invalid entr{'y was' if len(dropped) == 1 else 'ies were'} skipped:\n"
                    + "\n".join(dropped[:8])
                    + ("\n…" if len(dropped) > 8 else ""))
            self.imported_plan = plan
            super().accept()
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, _("Import Error"), _("Invalid JSON.") + f"\n{e}")


class LearningPlanConfigDialog(QDialog):
    """Dialog to configure subjects/times (JSON) and Deadline Bar settings."""

    DATE_FORMAT = "yyyyMMdd"
    DEADLINE_DATE_FORMAT = "%Y-%m-%d"

    def __init__(self, config_json_path: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        if is_night_mode:
            self.setStyleSheet(_build_style(is_night_mode))
        else:
            self.setStyleSheet(_build_style(is_night_mode))
        
        if not config_json_path:
            QTimer.singleShot(0, self.reject)
            return

        self.config_json_path = config_json_path
        self.config_changed = False 
        self.deadline_config_changed = False 
        self.current_full_plan: Dict[str, Dict[str, PlanItemConfig]] = {}
        self.selected_date: QDate = QDate.currentDate()

        self.deadline_manager: Optional['DeadlineManager'] = getattr(mw, 'deadline_manager', None)
        if not self.deadline_manager and DeadlineManager is not None:
             try: self.deadline_manager = DeadlineManager()
             except Exception: self.deadline_manager = None

        self.setWindowTitle(f"Configure Study Plan & Deadline")
        
        self.resize(1000, 700)
        self.setMinimumSize(750, 500)

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        left_panel = QFrame()
        left_panel.setObjectName("CardFrame")
        left_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 15, 10, 10)

        cal_label = QLabel(_("Select Date"))
        cal_label.setObjectName("HeaderLabel")
        cal_label.setContentsMargins(5, 0, 0, 5)
        left_layout.addWidget(cal_label)

        self.calendar = StudyPlanCalendarWidget(is_night_mode)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar.setGridVisible(False)
        self.calendar.setSelectedDate(self.selected_date)
        self.calendar.selectionChanged.connect(self.on_date_selected)
        
        self.calendar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout.addWidget(self.calendar)
        
        main_layout.addWidget(left_panel, 1)

        right_panel_layout = QVBoxLayout()
        right_panel_layout.setSpacing(15)

        plan_card = QFrame()
        plan_card.setObjectName("CardFrame")
        
        plan_layout = QVBoxLayout(plan_card)
        plan_layout.setContentsMargins(20, 20, 20, 20)

        self.selected_date_label = QLabel(f"Plan for: {self.selected_date.toString(Qt.DateFormat.ISODate)}")
        self.selected_date_label.setObjectName("HeaderLabel")
        plan_layout.addWidget(self.selected_date_label)

        input_layout = QHBoxLayout()
        self.subject_input = QLineEdit()
        self.subject_input.setPlaceholderText(_("Subject (e.g., Anatomy)"))
        self.time_input = QTimeEdit(QTime(1, 0, 0))
        self.time_input.setDisplayFormat("hh:mm")
        self.time_input.setFixedWidth(80)
        
        self.add_button = QPushButton(_("Add"))
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_button.clicked.connect(self.add_or_update_item_for_selected_date)

        input_layout.addWidget(self.subject_input)
        input_layout.addWidget(QLabel(_("Time:")))
        input_layout.addWidget(self.time_input)
        input_layout.addWidget(self.add_button)
        plan_layout.addLayout(input_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Subject", "Target"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 100)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.itemSelectionChanged.connect(self.on_table_item_selection_changed)
        self.table.itemDoubleClicked.connect(self.load_selected_item_for_edit)
        plan_layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.timeline_button = QPushButton(_("View Timeline"))
        self.timeline_button.setObjectName("SecondaryButton")
        self.timeline_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.timeline_button.clicked.connect(self.open_timeline_dialog)
        btn_layout.addWidget(self.timeline_button)
        btn_layout.addStretch()
        self.clear_plan_button = QPushButton(_("Clear All"))
        self.clear_plan_button.setObjectName("SecondaryButton")
        self.clear_plan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_plan_button.clicked.connect(self.clear_all_plan)
        btn_layout.addWidget(self.clear_plan_button)
        self.remove_button = QPushButton(_("Remove Selected"))
        self.remove_button.setObjectName("SecondaryButton")
        self.remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_button.clicked.connect(self.remove_item_from_selected_date)
        self.remove_button.setEnabled(False)
        btn_layout.addWidget(self.remove_button)
        plan_layout.addLayout(btn_layout)
        
        right_panel_layout.addWidget(plan_card, 2)

        deadline_card = QFrame()
        deadline_card.setObjectName("CardFrame")
        deadline_layout = QVBoxLayout(deadline_card)
        deadline_layout.setContentsMargins(15, 15, 15, 15)
        deadline_layout.setSpacing(8)

        dl_header_row = QHBoxLayout()
        dl_label = QLabel(_("Deadlines"))
        dl_label.setObjectName("HeaderLabel")
        dl_header_row.addWidget(dl_label)
        dl_header_row.addStretch()
        deadline_layout.addLayout(dl_header_row)

        dl_btn_row = QHBoxLayout()
        self.dl_view_btn = QPushButton(_("View Deadlines"))
        self.dl_view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dl_view_btn.setObjectName("SecondaryButton")
        self.dl_view_btn.clicked.connect(self._open_deadline_viewer)
        self.dl_config_btn = QPushButton(_("Configure Deadlines"))
        self.dl_config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dl_config_btn.clicked.connect(self._open_deadline_config)
        dl_btn_row.addWidget(self.dl_view_btn)
        dl_btn_row.addStretch()
        dl_btn_row.addWidget(self.dl_config_btn)
        deadline_layout.addLayout(dl_btn_row)

        right_panel_layout.addWidget(deadline_card)

        ai_card = QFrame()
        ai_card.setObjectName("CardFrame")
        ai_layout = QHBoxLayout(ai_card)
        ai_layout.setContentsMargins(15, 15, 15, 15)

        ai_info_layout = QVBoxLayout()
        ai_title = QLabel(_("AI Plan Generator"))
        ai_title.setObjectName("HeaderLabel")
        ai_desc = QLabel(_("Create a full schedule using ChatGPT."))
        ai_desc.setObjectName("SubLabel")
        ai_info_layout.addWidget(ai_title)
        ai_info_layout.addWidget(ai_desc)
        
        self.ai_helper_button = QPushButton(_("Open AI Assistant"))
        self.ai_helper_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ai_helper_button.clicked.connect(self.open_ai_helper_dialog)
        
        ai_layout.addLayout(ai_info_layout)
        ai_layout.addStretch()
        ai_layout.addWidget(self.ai_helper_button)
        
        right_panel_layout.addWidget(ai_card)

        action_layout = QHBoxLayout()
        action_layout.addStretch()
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setCursor(Qt.CursorShape.PointingHandCursor)
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setCursor(Qt.CursorShape.PointingHandCursor)
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("SecondaryButton")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        action_layout.addWidget(self.button_box)
        
        right_panel_layout.addLayout(action_layout)
        main_layout.addLayout(right_panel_layout, 2)

        self.load_full_plan_from_file()
        self.load_deadline_data_into_ui()
        self.on_date_selected()

        self.subject_input.returnPressed.connect(self.add_or_update_item_for_selected_date)

    def open_ai_helper_dialog(self):
        dialog = AIPlanHelperDialog(self)
        if dialog.exec() and dialog.imported_plan is not None:
             if QMessageBox.question(self, _("Confirm Import"), _("Replace plan with AI generated one?"), QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                self.current_full_plan = dialog.imported_plan; self.config_changed = True
                self.update_calendar_highlights(); self.load_plan_for_selected_date_into_table()

    def _qtime_to_seconds(self, qtime: QTime) -> int: return qtime.hour() * 3600 + qtime.minute() * 60
    def _seconds_to_qtime(self, seconds: int) -> QTime: return QTime((seconds//3600)%24, (seconds%3600)//60, 0)
    def _seconds_to_formatted_string(self, seconds: int) -> str:
        t = self._seconds_to_qtime(seconds)
        return f"{t.hour()}h {t.minute()}m" if t.hour() > 0 else f"{t.minute()}m"

    def _load_plan_from_file(self) -> Dict:
        if not os.path.exists(self.config_json_path): return {}
        try:
            with open(self.config_json_path, 'r', encoding='utf-8') as f:
                value = json.load(f)
            return value if isinstance(value, dict) else {}
        except Exception as exc:
            print(f"SynapsePro: could not read study plan: {exc}")
            return {}

    def _save_plan_to_file(self):
        tmp_path = self.config_json_path + ".tmp"
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self.current_full_plan, f, indent=4, ensure_ascii=False)
            os.replace(tmp_path, self.config_json_path)
        except Exception as e:
            try:
                if os.path.exists(tmp_path): os.remove(tmp_path)
            except OSError: pass
            QMessageBox.critical(self, _("Save Error"), f"{e}")

    def load_full_plan_from_file(self): self.current_full_plan = self._load_plan_from_file(); self.update_calendar_highlights()

    def update_calendar_highlights(self):
        plan_dates: List[QDate] = []
        for raw_date in self.current_full_plan:
            try:
                parsed = QDate.fromString(str(raw_date), self.DATE_FORMAT)
                if parsed.isValid():
                    plan_dates.append(parsed)
            except Exception:
                pass
        self.calendar.set_plan_dates(plan_dates)

    def on_date_selected(self):
        self.selected_date = self.calendar.selectedDate()
        self.selected_date_label.setText(f"Plan for: {self.selected_date.toString('dddd, MMM d, yyyy')}")
        self.load_plan_for_selected_date_into_table()
        self.subject_input.clear(); self.time_input.setTime(QTime(1, 0))
        self.subject_input.setFocus(); self.table.clearSelection(); self.remove_button.setEnabled(False)

    def load_plan_for_selected_date_into_table(self):
        plan = self.current_full_plan.get(self.selected_date.toString("yyyyMMdd"), {})
        if not isinstance(plan, dict): plan = {}
        self.table.setRowCount(0); self.table.setSortingEnabled(False)
        for s, c in plan.items():
            if not isinstance(c, dict): continue
            r = self.table.rowCount(); self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(s))
            i = QTableWidgetItem(self._seconds_to_formatted_string(c.get("target_seconds", 0)))
            i.setData(Qt.ItemDataRole.UserRole, c.get("target_seconds", 0)); i.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 1, i)
        self.table.setSortingEnabled(True)

    def on_table_item_selection_changed(self): self.remove_button.setEnabled(bool(self.table.selectedItems()))

    def load_selected_item_for_edit(self):
        if not (rows := self.table.selectionModel().selectedRows()): return
        self.subject_input.setText(self.table.item(rows[0].row(), 0).text())
        self.time_input.setTime(self._seconds_to_qtime(self.table.item(rows[0].row(), 1).data(Qt.ItemDataRole.UserRole)))

    def add_or_update_item_for_selected_date(self):
        sub = self.subject_input.text().strip(); sec = self._qtime_to_seconds(self.time_input.time())
        if not sub or sec <= 0: return
        dk = self.selected_date.toString("yyyyMMdd")
        if dk not in self.current_full_plan or not isinstance(self.current_full_plan[dk], dict): self.current_full_plan[dk] = {}
        target = next((k for k in self.current_full_plan[dk] if k.lower() == sub.lower()), sub)
        self.current_full_plan[dk][target] = {"target_seconds": sec}
        self.config_changed = True; self.load_plan_for_selected_date_into_table(); self.update_calendar_highlights()
        self.subject_input.clear(); self.time_input.setTime(QTime(1, 0))

    def remove_item_from_selected_date(self):
        if not (rows := self.table.selectionModel().selectedRows()): return
        sub = self.table.item(rows[0].row(), 0).text(); dk = self.selected_date.toString("yyyyMMdd")
        if dk in self.current_full_plan and sub in self.current_full_plan[dk]:
            del self.current_full_plan[dk][sub];
            if not self.current_full_plan[dk]: del self.current_full_plan[dk]
            self.config_changed = True; self.load_plan_for_selected_date_into_table(); self.update_calendar_highlights()

    def open_timeline_dialog(self):
        """Open the interactive study plan timeline visualization."""
        dlg = StudyPlanTimelineDialog(self.current_full_plan, parent=self)
        dlg.exec()

    def clear_all_plan(self):
        """Prompt the user and then wipe the entire study plan."""
        if not self.current_full_plan:
            return
        reply = QMessageBox.question(
            self, "Clear Entire Plan",
            "This will permanently delete all scheduled days from your study plan.\n"
            "Are you sure you want to start fresh?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.current_full_plan.clear()
            self.config_changed = True
            self.load_plan_for_selected_date_into_table()
            self.update_calendar_highlights()

    def load_deadline_data_into_ui(self):
        pass  # Deadline data is managed by the separate DeadlineConfigDialog

    def _open_deadline_viewer(self):
        dm = self.deadline_manager or getattr(mw, 'deadline_manager', None)
        DeadlineViewerDialog(dm, parent=self).exec()

    def _open_deadline_config(self):
        dm = self.deadline_manager or getattr(mw, 'deadline_manager', None)
        changed = DeadlineConfigDialog(dm, parent=self).exec()
        # Refresh only after the user explicitly committed changes.
        if changed and mw and mw.state == "deckBrowser":
            mw.deckBrowser.refresh()

    def accept(self):
        if self.config_changed:
            self._save_plan_to_file()
            tooltip("Configuration saved.", parent=mw)
        super().accept()

def show_study_plan_dialog(config_json_path: Optional[str]): pass


# ─────────────────────────────────────────────────────────────────────────────
# StudyPlanTimelineDialog — pure-Qt timeline (no WebEngine, no close bug)
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# _TimelineWidget — custom QPainter day-strip (no WebEngine required)
# ─────────────────────────────────────────────────────────────────────────────

def _import_painter_tools():
    """Lazy-import QPainter helpers to avoid touching the global import list."""
    from aqt.qt import QPainter, QPen, QBrush, QPoint, QFontMetrics, QScrollArea
    return QPainter, QPen, QBrush, QPoint, QFontMetrics, QScrollArea


from aqt.qt import pyqtSignal as _pyqtSignal


class _TimelineWidget(QWidget):
    """Draws a horizontally-scrollable row of day-circles using QPainter."""

    day_selected = _pyqtSignal(str)   # emits "YYYYMMDD"

    DAY_W    = 64    # column width per day (px)
    CY       = 68    # y of circle centres (from widget top)
    R        = 20    # circle radius
    WIDGET_H = 145   # fixed widget height

    MONTHS_S = ['Jan','Feb','Mar','Apr','May','Jun',
                'Jul','Aug','Sep','Oct','Nov','Dec']
    WDAYS_S  = ['Mo','Tu','We','Th','Fr','Sa','Su']  # weekday() 0=Mon

    def __init__(self, plan_data: dict, today_str: str, parent=None):
        super().__init__(parent)
        self._plan  = plan_data
        self._today = today_str
        self._sel   = None
        self._days  = []
        self._build_days()
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ── build day list ────────────────────────────────────────────────────────

    def _build_days(self):
        from datetime import timedelta
        keys = sorted(self._plan.keys())
        if not keys:
            self._days = []
            self.setFixedSize(300, self.WIDGET_H)
            return
        today_d = date.today()
        first   = date(int(keys[0][:4]),  int(keys[0][4:6]),  int(keys[0][6:8]))
        last    = date(int(keys[-1][:4]), int(keys[-1][4:6]), int(keys[-1][6:8]))
        start   = min(first, today_d - timedelta(days=7))
        end     = max(last,  today_d + timedelta(days=7))
        d = start
        while d <= end:
            self._days.append(d)
            d += timedelta(days=1)
        self.setFixedSize(len(self._days) * self.DAY_W + 64, self.WIDGET_H)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _cx(self, i: int) -> int:
        return 32 + i * self.DAY_W + self.DAY_W // 2

    def _max_sec(self) -> int:
        vals = [sum(v.get('target_seconds', 0) for v in dp.values())
                for dp in self._plan.values() if dp]
        return max(vals, default=1)

    @staticmethod
    def _circ_color(norm: float):
        from aqt.qt import QColor
        if norm < 0.33: return QColor('#28CD41')
        if norm < 0.66: return QColor('#FF9F0A')
        return QColor('#FF3B30')

    # ── painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, _ev):
        QPainter, QPen, QBrush, QPoint, QFontMetrics, _ = _import_painter_tools()
        from aqt.qt import QColor

        if not self._days:
            return

        p   = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c   = _palette(is_night_mode)
        today  = self._today
        max_s  = self._max_sec()
        cy     = self.CY
        r      = self.R

        # connector line
        p.setOpacity(1.0)
        p.setPen(QPen(QColor(c['grey_light']), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(self._cx(0), cy, self._cx(len(self._days) - 1), cy)

        last_month = -1

        for i, d in enumerate(self._days):
            dk       = d.strftime('%Y%m%d')
            dp       = self._plan.get(dk, {})
            has_plan = bool(dp)
            sec      = sum(v.get('target_seconds', 0) for v in dp.values()) if dp else 0
            norm     = sec / max_s
            is_past  = dk < today
            is_today = dk == today
            is_sel   = dk == self._sel
            cx       = self._cx(i)

            p.setOpacity(0.38 if (is_past and not is_today) else 1.0)

            # month label on first day of each month
            if d.month != last_month:
                last_month = d.month
                f = QFont(_FONT_FAMILY.split(',')[0].strip().strip('"'), 9)
                f.setBold(True)
                p.setFont(f)
                p.setPen(QColor(c['text_muted']))
                p.drawText(cx - r, 2, self.DAY_W * 4, 18,
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                           '{} {}'.format(self.MONTHS_S[d.month - 1], d.year))

            # circle
            if has_plan:
                col = self._circ_color(norm)
                p.setBrush(QBrush(col))
                p.setPen(Qt.PenStyle.NoPen)
                draw_r = r + 2 if is_sel else r
                p.drawEllipse(QPoint(cx, cy), draw_r, draw_r)
                if is_sel:
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.setPen(QPen(QColor('#007AFF'), 2.5))
                    p.drawEllipse(QPoint(cx, cy), draw_r + 4, draw_r + 4)
            else:
                pen = QPen(QColor(c['text_faint']), 1.5)
                pen.setStyle(Qt.PenStyle.DashLine)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPoint(cx, cy), r, r)

            # date labels
            f2 = QFont(_FONT_FAMILY.split(',')[0].strip().strip('"'), 9)
            f2.setBold(False)
            p.setFont(f2)
            p.setPen(QColor(c['text_muted']))
            lbl_y = cy + r + 6
            p.drawText(cx - 16, lbl_y,      32, 15,
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                       str(d.day))
            p.drawText(cx - 16, lbl_y + 15, 32, 15,
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                       self.WDAYS_S[d.weekday()])

        # today marker — always full opacity, drawn on top
        today_idx = next(
            (i for i, d in enumerate(self._days) if d.strftime('%Y%m%d') == today),
            None)
        if today_idx is not None:
            p.setOpacity(1.0)
            tx = self._cx(today_idx)

            # vertical line
            p.setPen(QPen(QColor('#007AFF'), 2))
            p.drawLine(tx, 20, tx, cy + r + 2)

            # "TODAY" pill above circles
            fb = QFont(_FONT_FAMILY.split(',')[0].strip().strip('"'), 9)
            fb.setBold(True)
            p.setFont(fb)
            fm   = QFontMetrics(fb)
            lbl  = 'TODAY'
            lw   = fm.horizontalAdvance(lbl)
            pw   = lw + 14; ph = 20
            px   = tx - pw // 2; py = 2
            p.setBrush(QBrush(QColor('#007AFF')))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(px, py, pw, ph, 7, 7)
            p.setPen(QColor('white'))
            p.drawText(px, py, pw, ph, Qt.AlignmentFlag.AlignCenter, lbl)

        p.end()

    # ── interaction ───────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if not self._days:
            return
        try:
            pos = event.position(); x, y = int(pos.x()), int(pos.y())
        except AttributeError:
            x, y = event.x(), event.y()
        click_r = self.R + 8
        for i, d in enumerate(self._days):
            cx = self._cx(i)
            if (x - cx) ** 2 + (y - self.CY) ** 2 <= click_r ** 2:
                dk = d.strftime('%Y%m%d')
                self._sel = dk
                self.update()
                self.day_selected.emit(dk)
                return

    def select_day(self, dk: str):
        self._sel = dk
        self.update()

    def scroll_to_today(self, scroll_area):
        idx = next(
            (i for i, d in enumerate(self._days) if d.strftime('%Y%m%d') == self._today),
            None)
        if idx is not None:
            from aqt.qt import QTimer as _QTimer
            def _do():
                bar = scroll_area.horizontalScrollBar()
                bar.setValue(max(0, self._cx(idx) - scroll_area.width() // 2))
            _QTimer.singleShot(80, _do)


# ─────────────────────────────────────────────────────────────────────────────
# StudyPlanTimelineDialog — pure-Qt dialog (no web engine, no close bug)
# ─────────────────────────────────────────────────────────────────────────────

class StudyPlanTimelineDialog(QDialog):
    """Interactive study-plan timeline built entirely with Qt widgets.

    Works exactly like AIPlanHelperDialog: exec() + parent=self, no WebEngine.
    """

    def __init__(self, plan_data: dict, parent=None):
        super().__init__(parent)
        self._plan  = plan_data
        self._today = date.today().strftime('%Y%m%d')
        self.setWindowTitle(_('Study Plan Timeline'))
        self.resize(1040, 500)
        self.setMinimumSize(700, 380)
        self.setStyleSheet(_build_style(is_night_mode))
        self._build_ui()

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt(sec: int) -> str:
        h = sec // 3600; m = (sec % 3600) // 60
        if h > 0: return '{h}h {m}m'.format(h=h, m=m) if m else '{h}h'.format(h=h)
        return '{m}m'.format(m=m)

    # ── build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        _, _, _, _, _, QScrollArea = _import_painter_tools()

        keys      = sorted(self._plan.keys())
        today     = self._today
        total     = len(keys)
        elapsed   = sum(1 for k in keys if k < today)
        upcoming  = sum(1 for k in keys if k >= today)
        total_sec = sum(
            sum(v.get('target_seconds', 0) for v in dp.values())
            for dp in self._plan.values())
        pct = round(elapsed / total * 100) if total else 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        # ── stat header ───────────────────────────────────────────────────────
        hdr = QFrame(); hdr.setObjectName('CardFrame')
        hl  = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 10, 16, 10); hl.setSpacing(12)
        ttl = QLabel('Study Plan Timeline'); ttl.setObjectName('HeaderLabel')
        hl.addWidget(ttl); hl.addStretch()
        chip_bg = _palette(is_night_mode)['grey_light']
        chip_fg = _palette(is_night_mode)['text_muted']
        chip_tx = _palette(is_night_mode)['text']
        for label, val in [('Total', '{} days'.format(total)),
                           ('Elapsed',  '{} days'.format(elapsed)),
                           ('Upcoming', '{} days'.format(upcoming)),
                           ('Time',  self._fmt(total_sec))]:
            chip = QLabel()
            chip.setText('<span style="color:{fg}">{lbl}:</span>'
                         ' <b style="color:{tx}">{val}</b>'.format(
                             fg=chip_fg, lbl=label, tx=chip_tx, val=val))
            chip.setTextFormat(Qt.TextFormat.RichText)
            chip_border = _palette(is_night_mode)['grey_mid']
            chip.setStyleSheet(
                'background:{bg};padding:5px 13px;'
                'border-radius:16px;font-size:11px;'
                'border:1px solid {bd};'.format(bg=chip_bg, bd=chip_border))
            hl.addWidget(chip)
        outer.addWidget(hdr)

        # ── progress bar ──────────────────────────────────────────────────────
        prog_frame = QFrame(); prog_frame.setObjectName('CardFrame')
        pl = QHBoxLayout(prog_frame)
        pl.setContentsMargins(16, 8, 16, 8); pl.setSpacing(10)
        lbl_l = QLabel('{}% schedule elapsed'.format(pct)); lbl_l.setObjectName('SubLabel')
        try:
            from aqt.qt import QProgressBar
            bar = QProgressBar()
            bar.setRange(0, 100); bar.setValue(pct)
            bar.setTextVisible(False); bar.setFixedHeight(5)
            bar.setStyleSheet(
                'QProgressBar{{border:none;border-radius:2px;background:{bg};}}'
                'QProgressBar::chunk{{border-radius:2px;'
                'background:qlineargradient(x1:0,y1:0,x2:1,y2:0,'
                'stop:0 #28CD41,stop:1 #007AFF);}}'.format(
                    bg=_palette(is_night_mode)['grey_light']))
        except Exception:
            bar = QWidget()
        lbl_r = QLabel('{} of {} scheduled dates are in the past'.format(elapsed, total))
        lbl_r.setObjectName('SubLabel')
        pl.addWidget(lbl_l); pl.addWidget(bar, 1); pl.addWidget(lbl_r)
        outer.addWidget(prog_frame)

        # ── timeline card ─────────────────────────────────────────────────────
        tl_card = QFrame(); tl_card.setObjectName('CardFrame')
        tl_layout = QVBoxLayout(tl_card)
        tl_layout.setContentsMargins(0, 8, 0, 8); tl_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(False)

        self._tl = _TimelineWidget(self._plan, self._today)
        self._tl.day_selected.connect(self._on_day_selected)
        scroll.setWidget(self._tl)
        scroll.setFixedHeight(self._tl.WIDGET_H + 18)
        tl_layout.addWidget(scroll)
        outer.addWidget(tl_card)

        # ── detail card ───────────────────────────────────────────────────────
        self._detail = QFrame(); self._detail.setObjectName('CardFrame')
        self._dl = QVBoxLayout(self._detail)
        self._dl.setContentsMargins(16, 12, 16, 12); self._dl.setSpacing(8)
        hint = QLabel('Click on any day to see its schedule.')
        hint.setObjectName('SubLabel')
        self._dl.addWidget(hint)
        outer.addWidget(self._detail, 1)

        # ── legend ────────────────────────────────────────────────────────────
        leg = QFrame(); leg.setObjectName('CardFrame')
        ll  = QHBoxLayout(leg)
        ll.setContentsMargins(14, 8, 14, 8); ll.setSpacing(14)
        ll.addWidget(QLabel('Intensity') if True else None)
        leg.layout().itemAt(0).widget().setObjectName('SubLabel')
        for dot_style, name in [
                ('border:1.5px dashed #AEAEB2;background:transparent;', 'Rest'),
                ('background:#28CD41;',  'Light'),
                ('background:#FF9F0A;',  'Moderate'),
                ('background:#FF3B30;',  'Intensive')]:
            dot = QLabel(); dot.setFixedSize(10, 10)
            dot.setStyleSheet('border-radius:5px;' + dot_style)
            txt = QLabel(name); txt.setObjectName('SubLabel')
            ll.addWidget(dot); ll.addWidget(txt)
        ll.addStretch()
        outer.addWidget(leg)

        # ── close button ──────────────────────────────────────────────────────
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.button(QDialogButtonBox.StandardButton.Close).setObjectName('SecondaryButton')
        bb.button(QDialogButtonBox.StandardButton.Close).setCursor(
            Qt.CursorShape.PointingHandCursor)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

        # scroll to today, auto-select
        self._tl.scroll_to_today(scroll)
        if keys:
            auto = today if (self._plan.get(today) and self._plan[today]) else keys[0]
            self._tl.select_day(auto)
            self._on_day_selected(auto)

    # ── day selection handler ─────────────────────────────────────────────────

    def _on_day_selected(self, dk: str):
        # clear existing widgets
        while self._dl.count():
            item = self._dl.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None); w.deleteLater()

        d        = date(int(dk[:4]), int(dk[4:6]), int(dk[6:8]))
        dp       = self._plan.get(dk, {})
        has_pl   = bool(dp)
        is_today = dk == self._today
        is_past  = dk < self._today

        MONTHS_L = ['January','February','March','April','May','June',
                    'July','August','September','October','November','December']
        WDAYS_L  = ['Monday','Tuesday','Wednesday','Thursday',
                    'Friday','Saturday','Sunday']
        day_str  = '{wd}, {mn} {day}, {yr}'.format(
            wd=WDAYS_L[d.weekday()], mn=MONTHS_L[d.month - 1],
            day=d.day, yr=d.year)

        # header row
        hdr_row = QHBoxLayout(); hdr_row.setSpacing(8)
        day_lbl_w = QLabel(day_str); day_lbl_w.setObjectName('HeaderLabel')
        hdr_row.addWidget(day_lbl_w)

        if is_today:
            b = QLabel('TODAY')
            b.setStyleSheet('background:#007AFF;color:white;padding:2px 9px;'
                            'border-radius:9px;font-size:10px;font-weight:700;')
            hdr_row.addWidget(b)
        elif is_past and has_pl:
            b = QLabel('past'); b.setObjectName('SubLabel')
            hdr_row.addWidget(b)

        if has_pl:
            tot = sum(v.get('target_seconds', 0) for v in dp.values())
            tl  = QLabel('Total: ' + self._fmt(tot)); tl.setObjectName('SubLabel')
            hdr_row.addStretch(); hdr_row.addWidget(tl)
        else:
            hdr_row.addStretch()

        hc = QWidget(); hc.setLayout(hdr_row)
        self._dl.addWidget(hc)

        if not has_pl:
            rl = QLabel('Rest day \u2014 no subjects scheduled')
            rl.setObjectName('SubLabel')
            self._dl.addWidget(rl)
        else:
            chips_row = QHBoxLayout()
            chips_row.setSpacing(8)
            chips_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
            for sub in sorted(dp.keys()):
                sec  = dp[sub].get('target_seconds', 0)
                chip = QFrame(); chip.setObjectName('CardFrame')
                cl   = QHBoxLayout(chip)
                cl.setContentsMargins(10, 5, 10, 5); cl.setSpacing(8)
                nl = QLabel(sub); nl.setStyleSheet('font-weight:600;font-size:12px;')
                tl = QLabel(self._fmt(sec)); tl.setObjectName('SubLabel')
                cl.addWidget(nl); cl.addWidget(tl)
                chips_row.addWidget(chip)
            chips_row.addStretch()
            cw = QWidget(); cw.setLayout(chips_row)
            self._dl.addWidget(cw)

        self._dl.addStretch()

# ─────────────────────────────────────────────────────────────────────────────
# DeadlineConfigDialog — manage (add / remove / pin) multiple deadlines
# ─────────────────────────────────────────────────────────────────────────────

class DeadlineConfigDialog(QDialog):
    """Popup for adding, removing, and pinning deadlines."""

    def __init__(self, deadline_manager, parent=None):
        super().__init__(parent)
        self.deadline_manager = deadline_manager
        # Edit a detached copy. Add/remove/pin actions therefore remain
        # reversible until the user presses Done, and Cancel/window-close
        # cannot leak partial changes into collection configuration.
        self._working_data = copy.deepcopy(deadline_manager.data) if deadline_manager else {
            "deadlines": [], "pinned_id": None, "enabled": True,
        }
        self.setWindowTitle(_("Configure Deadlines"))
        self.resize(660, 460)
        self.setMinimumSize(520, 360)
        self.setStyleSheet(_build_style(is_night_mode))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # ── Enable checkbox ──────────────────────────────────────────────
        top_row = QHBoxLayout()
        lbl = QLabel(_("Deadlines"))
        lbl.setObjectName("HeaderLabel")
        self.enabled_cb = QCheckBox("Enable deadline bar")
        self.enabled_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.enabled_cb.setChecked(self._working_data.get("enabled", True))
        top_row.addWidget(lbl)
        top_row.addStretch()
        top_row.addWidget(self.enabled_cb)
        layout.addLayout(top_row)

        # ── Table ────────────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Start", "End", "Default"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 60)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        layout.addWidget(self.table)

        hint_lbl = QLabel(_("If no deadline is set as default, the nearest upcoming one is shown automatically."))
        hint_lbl.setObjectName("SubLabel")
        hint_lbl.setWordWrap(True)
        layout.addWidget(hint_lbl)

        # ── Add row ──────────────────────────────────────────────────────
        add_frame = QFrame()
        add_frame.setObjectName("CardFrame")
        add_layout = QHBoxLayout(add_frame)
        add_layout.setContentsMargins(10, 8, 10, 8)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(_("Name"))
        self.start_edit = QDateEdit(QDate.currentDate())
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_edit.setFixedWidth(105)
        self.end_edit = QDateEdit(QDate.currentDate().addMonths(3))
        self.end_edit.setCalendarPopup(True)
        self.end_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_edit.setFixedWidth(105)
        add_btn = QPushButton(_("+ Add"))
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFixedWidth(64)
        add_btn.clicked.connect(self._add_deadline)
        self.name_input.returnPressed.connect(self._add_deadline)
        add_layout.addWidget(self.name_input)
        add_layout.addWidget(QLabel(_("Start:")))
        add_layout.addWidget(self.start_edit)
        add_layout.addWidget(QLabel(_("End:")))
        add_layout.addWidget(self.end_edit)
        add_layout.addWidget(add_btn)
        layout.addWidget(add_frame)

        # ── Bottom buttons ───────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self.remove_btn = QPushButton(_("Remove Selected"))
        self.remove_btn.setObjectName("SecondaryButton")
        self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_btn.setEnabled(False)
        self.remove_btn.clicked.connect(self._remove_deadline)
        btn_row.addWidget(self.remove_btn)
        btn_row.addStretch()
        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.setObjectName("SecondaryButton")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        close_btn = QPushButton(_("Done"))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._save_and_close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.table.itemSelectionChanged.connect(
            lambda: self.remove_btn.setEnabled(bool(self.table.selectionModel().selectedRows()))
        )

        self._refresh_table()

    def _refresh_table(self):
        deadlines = sorted(
            self._working_data.get("deadlines", []),
            key=lambda deadline: deadline.get("end_date", "9999-12-31"),
        )
        pinned_id = self._working_data.get("pinned_id")
        self.table.setRowCount(0)
        for dl in deadlines:
            row = self.table.rowCount()
            self.table.insertRow(row)
            item0 = QTableWidgetItem(dl.get("name", ""))
            item0.setData(Qt.ItemDataRole.UserRole, dl.get("id"))
            self.table.setItem(row, 0, item0)
            self.table.setItem(row, 1, QTableWidgetItem(dl.get("start_date", "")))
            self.table.setItem(row, 2, QTableWidgetItem(dl.get("end_date", "")))
            dl_id = dl.get("id")
            is_pinned = (dl_id == pinned_id)
            pin_cb = QCheckBox()
            pin_cb.setChecked(is_pinned)
            pin_cb.setToolTip(_("Always show this deadline (uncheck = auto-select nearest upcoming)"))
            pin_cb.setCursor(Qt.CursorShape.PointingHandCursor)
            pin_cb.stateChanged.connect(lambda state, did=dl_id: self._toggle_pin(did, state == 0))
            # Center the checkbox in the cell
            cell_widget = QWidget()
            cell_layout = QHBoxLayout(cell_widget)
            cell_layout.addWidget(pin_cb)
            cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 3, cell_widget)
        self.table.resizeRowsToContents()

    def _toggle_pin(self, deadline_id: str, currently_pinned: bool):
        self._working_data["pinned_id"] = None if currently_pinned else deadline_id
        self._refresh_table()

    def _add_deadline(self):
        name = self.name_input.text().strip()
        if not name:
            return
        if self.start_edit.date() > self.end_edit.date():
            showInfo(_("The start date must not be after the end date."), parent=self)
            return
        self._working_data.setdefault("deadlines", []).append({
            "id": str(uuid.uuid4())[:8],
            "name": name[:120],
            "start_date": self.start_edit.date().toString(Qt.DateFormat.ISODate),
            "end_date": self.end_edit.date().toString(Qt.DateFormat.ISODate),
        })
        self.name_input.clear()
        self._refresh_table()

    def _remove_deadline(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        item = self.table.item(rows[0].row(), 0)
        if item:
            dl_id = item.data(Qt.ItemDataRole.UserRole)
            if dl_id:
                self._working_data["deadlines"] = [
                    deadline for deadline in self._working_data.get("deadlines", [])
                    if deadline.get("id") != dl_id
                ]
                if self._working_data.get("pinned_id") == dl_id:
                    self._working_data["pinned_id"] = None
                self._refresh_table()

    def _save_and_close(self):
        if self.deadline_manager:
            self._working_data["enabled"] = self.enabled_cb.isChecked()
            self.deadline_manager.data = copy.deepcopy(self._working_data)
            self.deadline_manager.save_data()
        self.accept()


# ─────────────────────────────────────────────────────────────────────────────
# StudyPlanViewerDialog — today's subjects with directly editable completion
# ─────────────────────────────────────────────────────────────────────────────

class StudyPlanViewerDialog(QDialog):
    """Compact viewer for today's study-plan subjects and completion state."""

    def __init__(self, learning_plan_manager, config_json_path: str, parent=None):
        super().__init__(parent)
        self.learning_plan_manager = learning_plan_manager
        self.config_json_path = config_json_path
        self.setWindowTitle(_("Study Plan"))
        self.resize(460, 410)
        self.setMinimumSize(360, 280)
        self.setStyleSheet(_build_style(is_night_mode))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        plan = []
        if learning_plan_manager:
            try:
                plan = learning_plan_manager.get_plan_for_display() or []
            except Exception:
                plan = []
        done_count = sum(1 for item in plan if item.get("state") == "Done")

        header_row = QHBoxLayout()
        header = QLabel(_("Study Plan"))
        header.setObjectName("HeaderLabel")
        header_row.addWidget(header)
        header_row.addStretch()
        self.summary_label = QLabel(f"{done_count}/{len(plan)}")
        self.summary_label.setObjectName("SubLabel")
        header_row.addWidget(self.summary_label)
        layout.addLayout(header_row)

        from aqt.qt import QScrollArea, QProgressBar
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 8, 0)
        inner_layout.setSpacing(8)
        colours = _palette(is_night_mode)

        if not plan:
            empty = QLabel(_("No learning plan configured yet."))
            empty.setObjectName("SubLabel")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inner_layout.addWidget(empty)
        else:
            for item in plan:
                subject = str(item.get("subject") or _("Unknown Subject"))
                target = max(0, int(item.get("target_seconds") or 0))
                elapsed = max(0, min(target, int(item.get("elapsed_seconds") or 0)))
                progress = int((elapsed / target) * 100) if target else 0

                card = QFrame()
                card.setObjectName("CardFrame")
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(13, 10, 13, 10)
                card_layout.setSpacing(7)

                row = QHBoxLayout()
                checkbox = QCheckBox(subject)
                checkbox.setChecked(item.get("state") == "Done")
                row.addWidget(checkbox, 1)
                minutes = max(1, round(target / 60)) if target else 0
                duration = QLabel(_("{} min").format(minutes) if minutes else "—")
                duration.setObjectName("SubLabel")
                row.addWidget(duration)
                state = item.get("state") or "Not Started"
                if state != "Done":
                    if state == "Running":
                        action_text = _("Pause")
                    elif state == "Paused":
                        action_text = _("Resume")
                    else:
                        action_text = _("Start")
                    action = QPushButton(action_text)
                    if state == "Running":
                        action.setObjectName("SecondaryButton")
                    action.setCursor(Qt.CursorShape.PointingHandCursor)
                    action.clicked.connect(
                        lambda _checked=False, name=subject, running=(state == "Running"):
                            self._toggle_timer(name, running)
                    )
                    row.addWidget(action)
                card_layout.addLayout(row)

                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setValue(progress)
                bar.setTextVisible(False)
                bar.setFixedHeight(7)
                bar.setStyleSheet(
                    f"QProgressBar {{ background: {colours['grey_light']}; border-radius: 3px; border: none; }}"
                    f"QProgressBar::chunk {{ background: {colours['blue']}; border-radius: 3px; }}"
                )
                card_layout.addWidget(bar)

                checkbox.toggled.connect(
                    lambda checked, name=subject, progress_bar=bar: self._set_done(
                        name, checked, progress_bar
                    )
                )
                inner_layout.addWidget(card)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        buttons = QHBoxLayout()
        configure = QPushButton(_("Configure Study Plan"))
        configure.setObjectName("SecondaryButton")
        configure.clicked.connect(self._open_config)
        buttons.addWidget(configure)
        buttons.addStretch()
        close = QPushButton(_("Close"))
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _set_done(self, subject: str, checked: bool, progress_bar=None):
        if self.learning_plan_manager:
            self.learning_plan_manager.set_subject_done(subject, checked)
            if progress_bar is not None:
                progress_bar.setValue(100 if checked else 0)
            try:
                plan = self.learning_plan_manager.get_plan_for_display() or []
                done = sum(1 for item in plan if item.get("state") == "Done")
                self.summary_label.setText(f"{done}/{len(plan)}")
            except Exception:
                pass

    def _toggle_timer(self, subject: str, currently_running: bool):
        if not self.learning_plan_manager:
            return
        if currently_running:
            self.learning_plan_manager.pause_timer(subject)
        else:
            # The compact dashboard intentionally has one prominent countdown.
            # Pause any other running subject before starting the selected one.
            for item in self.learning_plan_manager.get_plan_for_display() or []:
                if item.get("state") == "Running" and item.get("subject") != subject:
                    self.learning_plan_manager.pause_timer(str(item.get("subject")))
            self.learning_plan_manager.start_timer(subject)
        self.accept()

    def _open_config(self):
        if LearningPlanConfigDialog(self.config_json_path, self).exec():
            if self.learning_plan_manager:
                self.learning_plan_manager._initialize_status_for_today()
            self.accept()


# ─────────────────────────────────────────────────────────────────────────────
# DeadlineViewerDialog — read-only overview of all deadlines with progress bars
# ─────────────────────────────────────────────────────────────────────────────

class DeadlineViewerDialog(QDialog):
    """Shows all deadlines as progress cards — read-only overview."""

    def __init__(self, deadline_manager, parent=None):
        super().__init__(parent)
        self.deadline_manager = deadline_manager
        self.setWindowTitle(_("Deadlines"))
        self.resize(480, 400)
        self.setMinimumSize(360, 260)
        self.setStyleSheet(_build_style(is_night_mode))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        header = QLabel(_("Your Deadlines"))
        header.setObjectName("HeaderLabel")
        layout.addWidget(header)

        from aqt.qt import QScrollArea, QProgressBar
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(10)
        inner_layout.setContentsMargins(0, 0, 8, 0)

        c = _palette(is_night_mode)

        if deadline_manager:
            from datetime import date as _date, datetime as _dt, timedelta as _td
            DATE_FMT = "%Y-%m-%d"
            deadlines = deadline_manager.get_all_deadlines()
            pinned_id = deadline_manager.data.get("pinned_id")

            if not deadlines:
                lbl = QLabel(_("No deadlines configured yet.\nUse 'Configure Deadlines' to add one."))
                lbl.setObjectName("SubLabel")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                inner_layout.addWidget(lbl)
            else:
                for dl in deadlines:
                    card = QFrame()
                    card.setObjectName("CardFrame")
                    card_layout = QVBoxLayout(card)
                    card_layout.setContentsMargins(14, 12, 14, 12)
                    card_layout.setSpacing(6)

                    # Title row
                    title_row = QHBoxLayout()
                    name_lbl = QLabel(dl.get("name", "Deadline"))
                    name_lbl.setObjectName("HeaderLabel")
                    name_font = name_lbl.font()
                    name_font.setPointSize(13)
                    name_lbl.setFont(name_font)
                    title_row.addWidget(name_lbl)
                    title_row.addStretch()
                    if dl.get("id") == pinned_id:
                        pin_lbl = QLabel("default")
                        pin_lbl.setStyleSheet(
                            f"color: {c.get('blue_bright','#007AFF')}; font-size: 11px; "
                            f"background: {c.get('hover_subtle','#e8f0fe')}; "
                            f"border-radius: 4px; padding: 2px 6px;"
                        )
                        title_row.addWidget(pin_lbl)
                    card_layout.addLayout(title_row)

                    # Progress calculation
                    try:
                        today = _date.today()
                        start = _dt.strptime(dl["start_date"], DATE_FMT).date()
                        end   = _dt.strptime(dl["end_date"],   DATE_FMT).date()
                        total = (end - start).days
                        elapsed = (today - start).days
                        if today < start:
                            progress = 0
                            days_lbl_txt = f"Starts in {(start - today).days} day(s)"
                        elif today > end:
                            progress = 100
                            days_lbl_txt = f"Ended {(today - end).days} day(s) ago"
                        else:
                            progress = max(0, min(100, int(max(0, elapsed) / max(1, total) * 100)))
                            days_lbl_txt = f"{(end - today).days} day(s) remaining"
                    except Exception:
                        progress = 0
                        days_lbl_txt = "Invalid date"

                    bar = QProgressBar()
                    bar.setRange(0, 100)
                    bar.setValue(progress)
                    bar.setTextVisible(False)
                    bar.setFixedHeight(10)
                    bar.setStyleSheet(
                        f"QProgressBar {{ background: {c.get('grey_light','#e0e0e0')}; border-radius: 5px; border: none; }}"
                        f"QProgressBar::chunk {{ background: {c.get('blue','#007AFF')}; border-radius: 5px; }}"
                    )
                    card_layout.addWidget(bar)

                    # Dates + days label
                    info_row = QHBoxLayout()
                    date_lbl = QLabel(f"{dl.get('start_date','')}  →  {dl.get('end_date','')}")
                    date_lbl.setObjectName("SubLabel")
                    days_lbl = QLabel(days_lbl_txt)
                    days_lbl.setObjectName("SubLabel")
                    info_row.addWidget(date_lbl)
                    info_row.addStretch()
                    info_row.addWidget(days_lbl)
                    card_layout.addLayout(info_row)

                    inner_layout.addWidget(card)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        # Bottom row
        btn_row = QHBoxLayout()
        config_btn = QPushButton(_("Configure Deadlines"))
        config_btn.setObjectName("SecondaryButton")
        config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        config_btn.clicked.connect(self._open_config)
        btn_row.addWidget(config_btn)
        btn_row.addStretch()
        close_btn = QPushButton(_("Close"))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _open_config(self):
        if DeadlineConfigDialog(self.deadline_manager, parent=self).exec():
            self.accept()  # Close viewer; user can reopen to see updated list
