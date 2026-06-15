# -*- coding: utf-8 -*-

import os
import traceback
from typing import Optional, TYPE_CHECKING, List, Dict, Any

from aqt import mw
from aqt.qt import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QSizePolicy, Qt, QDockWidget, QScrollArea, QSpacerItem, QGridLayout,
    QPixmap, QFrame, QMovie, QTimer, QSize, QPainter, QColor,
    QByteArray, QBuffer, QIODevice
)
from aqt.utils import tooltip

try:
    from .gamification import ADDON_NAME
except ImportError:
    ADDON_NAME = "GamificationSidebar"

try:
    from .locales import _
except ImportError:
    def _(text):  # type: ignore
        return text

if TYPE_CHECKING:
    from .gamification import GamificationManager

MAIN_BADGE_SIZE = 140
SMALL_BADGE_SIZE = 55
GRID_COLUMNS = 4

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

def _build_sidebar_style(night: bool) -> str:
    c = _palette(night)
    return f"""
    QWidget#MainWidget {{
        background-color: {c['bg']};
        font-family: {_FONT_FAMILY};
    }}
    QFrame#CardFrame {{
        background-color: {c['surface']};
        border-radius: 12px;
        border: 1px solid {c['grey_light']};
    }}
    QLabel {{
        color: {c['text']};
        background-color: transparent;
        border: none;
    }}
    QLabel#SectionTitle {{
        font-size: 13px; font-weight: 600; color: {c['text_muted']};
        margin-top: 5px; margin-bottom: 2px; background-color: transparent;
    }}
    QLabel#RankTitle {{ font-size: 18px; font-weight: 700; color: {c['blue']}; background-color: transparent; }}
    QLabel#LevelLabel {{ font-size: 15px; font-weight: 600; color: {c['text']}; background-color: transparent; }}
    QPushButton {{
        background-color: {c['blue']}; color: white; border-radius: 15px;
        padding: 8px 16px; font-weight: 600; font-size: 13px; border: {c['blue_border']};
    }}
    QPushButton:hover {{ background-color: {c['blue_hover']}; }}
    QPushButton:pressed {{ background-color: {c['blue_pressed']}; }}
    QPushButton:disabled {{ background-color: {c['grey_light']}; color: {c['text_faint']}; border: {'1px solid ' + c['grey_light'] if night else 'none'}; }}
    QProgressBar {{
        border: none; border-radius: 4px; background-color: {c['grey_light']}; height: 8px; text-align: center;
    }}
    QProgressBar::chunk {{ background-color: {c['blue']}; border-radius: 4px; }}
"""

# NOTE: Styles are intentionally NOT cached at module level here.
# _build_sidebar_style() is called at widget-creation time so that a
# colour-theme change (via theme.set_active_theme()) is always reflected
# in the widget's appearance when it is first opened or refreshed.

class BadgeLabel(QLabel):
    def __init__(self, locked=False, parent=None):
        super().__init__(parent)
        self._locked = locked
        self.setStyleSheet("background-color: transparent;")

    def setLocked(self, locked: bool):
        if self._locked != locked:
            self._locked = locked
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._locked:
            painter = QPainter(self)
            if is_night_mode:
                overlay_color = QColor(0, 0, 0, 180)
            else:
                overlay_color = QColor(255, 255, 255, 180)
                
            painter.setBrush(overlay_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.drawRoundedRect(self.rect(), 5.0, 5.0)


class GamificationSidebar(QDockWidget):
    def __init__(self, manager: 'GamificationManager', parent: Optional[QWidget] = None):
        super().__init__("", parent)
        self.manager = manager
        self.setObjectName("GamificationSidebar")
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setMinimumWidth(300) 
        self.setTitleBarWidget(QWidget()) 

        self.main_rank_movie: Optional[QMovie] = None
        self._movie_buffer: Optional[QBuffer] = None
        self._movie_byte_array: Optional[QByteArray] = None
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        scroll_bg = _palette(is_night_mode)["bg"]
        self.scroll_area.setStyleSheet(f"background-color: {scroll_bg}; border: none;")

        self.main_widget = QWidget()
        self.main_widget.setObjectName("MainWidget")
        
        self.main_widget.setStyleSheet(_build_sidebar_style(is_night_mode))
        
        self.layout = QVBoxLayout(self.main_widget)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(15)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._setup_ui()
        
        self.scroll_area.setWidget(self.main_widget)
        self.setWidget(self.scroll_area)
        
        self.update_display()

    def _setup_ui(self):
        profile_card = QFrame()
        profile_card.setObjectName("CardFrame")
        profile_layout = QVBoxLayout(profile_card)
        profile_layout.setContentsMargins(15, 20, 15, 20)
        profile_layout.setSpacing(10)

        self.rank_badge_label = QLabel()
        self.rank_badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rank_badge_label.setMinimumSize(MAIN_BADGE_SIZE, MAIN_BADGE_SIZE)
        self.rank_badge_label.setMaximumSize(MAIN_BADGE_SIZE, MAIN_BADGE_SIZE)
        self.rank_badge_label.setStyleSheet("background-color: transparent; border: none;")
        profile_layout.addWidget(self.rank_badge_label, 0, Qt.AlignmentFlag.AlignCenter)

        self.level_label = QLabel(_("Level: ?"))
        self.level_label.setObjectName("LevelLabel")
        self.level_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.rank_name_label = QLabel(_("Rank: ???"))
        self.rank_name_label.setObjectName("RankTitle")
        self.rank_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rank_name_label.setTextFormat(Qt.TextFormat.RichText)
        self.rank_name_label.setWordWrap(True)
        
        profile_layout.addWidget(self.level_label)
        profile_layout.addWidget(self.rank_name_label)
        
        xp_layout = QVBoxLayout()
        xp_layout.setSpacing(6)
        
        self.xp_progress_bar = QProgressBar()
        self.xp_progress_bar.setTextVisible(False)
        self.xp_progress_bar.setFixedHeight(8)
        
        self.xp_label = QLabel(_("XP: ? / ?"))
        self.xp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        xp_label_color = _palette(is_night_mode)["text_muted"]
        self.xp_label.setStyleSheet(f"font-size: 11px; color: {xp_label_color}; background-color: transparent;")
        
        xp_layout.addWidget(self.xp_progress_bar)
        xp_layout.addWidget(self.xp_label)
        profile_layout.addSpacing(5)
        profile_layout.addLayout(xp_layout)
        
        self.layout.addWidget(profile_card)

        self.next_goal_group = QFrame()
        self.next_goal_group.setObjectName("CardFrame")
        goal_layout = QVBoxLayout(self.next_goal_group)
        goal_layout.setContentsMargins(15, 15, 15, 15)
        
        goal_title = QLabel(_("Next Goal"))
        goal_title.setObjectName("SectionTitle")
        goal_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        goal_layout.addWidget(goal_title)

        self.next_goal_text_label = QLabel(_("Loading next goal..."))
        self.next_goal_text_label.setTextFormat(Qt.TextFormat.RichText)
        self.next_goal_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_goal_text_label.setWordWrap(True)
        self.next_goal_text_label.setStyleSheet("background-color: transparent; border: none;")
        goal_layout.addWidget(self.next_goal_text_label)
        
        self.layout.addWidget(self.next_goal_group)

        streak_group = QFrame()
        streak_group.setObjectName("CardFrame")
        streak_layout = QVBoxLayout(streak_group)
        streak_layout.setContentsMargins(15, 15, 15, 15)
        streak_layout.setSpacing(2)
        
        streak_title = QLabel(_("Current Streak"))
        streak_title.setObjectName("SectionTitle")
        streak_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        streak_layout.addWidget(streak_title)

        self.streak_days_label = QLabel(_("? Day Streak"))
        self.streak_days_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        streak_color = _palette(is_night_mode)["blue_accent"]
        self.streak_days_label.setStyleSheet(f"font-size: 16px; color: {streak_color}; font-weight: 700; background-color: transparent;")
        
        self.streak_xp_label = QLabel("(+? XP)")
        self.streak_xp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.streak_xp_label.setStyleSheet(f"font-size: 13px; color: {_palette(is_night_mode)['green']}; font-weight: 500; background-color: transparent;")
        
        streak_layout.addWidget(self.streak_days_label)
        streak_layout.addWidget(self.streak_xp_label)
        self.layout.addWidget(streak_group)

        self.challenge_group = QFrame()
        self.challenge_group.setObjectName("CardFrame")
        challenge_layout = QVBoxLayout(self.challenge_group)
        challenge_layout.setContentsMargins(15, 15, 15, 15)
        challenge_layout.setSpacing(10)
        
        challenge_title = QLabel(_("Daily Challenge"))
        challenge_title.setObjectName("SectionTitle")
        challenge_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        challenge_layout.addWidget(challenge_title)

        self.challenge_text_label = QLabel(_("Loading challenge..."))
        self.challenge_text_label.setWordWrap(True)
        self.challenge_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        chal_text_color = _palette(is_night_mode)["text"]
        self.challenge_text_label.setStyleSheet(f"font-size: 13px; color: {chal_text_color}; padding: 5px 0; background-color: transparent;")
        
        challenge_layout.addWidget(self.challenge_text_label)
        
        self.challenge_complete_button = QPushButton(_("Complete Challenge"))
        self.challenge_complete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.challenge_complete_button.clicked.connect(self._on_complete_challenge_clicked)
        self.challenge_complete_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        challenge_layout.addWidget(self.challenge_complete_button)
        self.layout.addWidget(self.challenge_group)

        ranks_card = QFrame()
        ranks_card.setObjectName("CardFrame")
        ranks_layout = QVBoxLayout(ranks_card)
        ranks_layout.setContentsMargins(15, 15, 15, 15)
        
        ranks_title = QLabel(_("All Ranks"))
        ranks_title.setObjectName("SectionTitle")
        ranks_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ranks_layout.addWidget(ranks_title)
        ranks_layout.addSpacing(5)

        self.all_ranks_widget = QWidget()
        self.all_ranks_layout = QGridLayout(self.all_ranks_widget)
        self.all_ranks_layout.setSpacing(10)
        self.all_ranks_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.all_ranks_layout.setContentsMargins(0, 0, 0, 0)
        self.all_ranks_widget.setStyleSheet("background-color: transparent;")
        
        ranks_layout.addWidget(self.all_ranks_widget)
        self.layout.addWidget(ranks_card)

        guide_card = QFrame()
        guide_card.setObjectName("CardFrame")
        guide_layout = QVBoxLayout(guide_card)
        guide_layout.setContentsMargins(15, 15, 15, 15)
        
        guide_title_label = QLabel(_("How it works"))
        guide_title_label.setObjectName("SectionTitle")
        guide_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        guide_layout.addWidget(guide_title_label)
        
        self.guide_label = QLabel()
        self.guide_label.setTextFormat(Qt.TextFormat.RichText)
        self.guide_label.setWordWrap(True)
        self.guide_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        guide_text_color = _palette(is_night_mode)["text"]
        self.guide_label.setStyleSheet(f"font-size: 11px; color: {guide_text_color}; background-color: transparent;")
        self.guide_label.setText(self._get_guide_html())
        
        guide_layout.addWidget(self.guide_label)
        self.layout.addWidget(guide_card)

        self.layout.addStretch(1)

    def _get_guide_html(self) -> str:
        sec_color = _palette(is_night_mode)["text_muted"]
        tpl = _(
            "<p style=\"margin-bottom: 8px;\">Earn XP, level up, and climb the ranks while studying!</p>"
            "<p style=\"margin-bottom: 2px;\"><b>How to Earn XP</b></p>"
            "<ul style=\"margin-top: 0px; margin-bottom: 8px; padding-left: 20px;\">"
            "<li><b>Study Time:</b> 10 XP per minute.</li>"
            "<li><b>Daily Challenge:</b> Bonus XP based on level.</li>"
            "<li><b>Streak:</b> 20 XP \u00d7 current streak day.</li>"
            "</ul>"
            "<p style=\"margin-bottom: 2px;\"><b>Leveling & Ranks</b></p>"
            "<ul style=\"margin-top: 0px; margin-bottom: 8px; padding-left: 20px;\">"
            "<li>Max Level: 100.</li>"
            "<li>New Rank every 5 levels.</li>"
            "</ul>"
            "<p style=\"margin-top: 5px; color: {sec_color};\"><i>Tip: Consistency is key!</i></p>"
        )
        return tpl.format(sec_color=sec_color)

    def _clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None: widget.deleteLater()
                else:
                    sub_layout = item.layout()
                    if sub_layout is not None: self._clear_layout(sub_layout)
    
    def _setup_gif_animation(self, movie: QMovie, label: QLabel):
        def restart_animation(): movie.start()
        def on_movie_finished(): QTimer.singleShot(5000, restart_animation)
        def on_frame_changed(frame_number: int):
            if movie.frameCount() > 0 and frame_number == movie.frameCount() - 1: movie.stop()
        try: movie.finished.disconnect()
        except TypeError: pass
        try: movie.frameChanged.disconnect()
        except TypeError: pass
        movie.finished.connect(on_movie_finished)
        movie.frameChanged.connect(on_frame_changed)
        movie.start()

    def refresh_style(self) -> None:
        """Re-apply the current colour theme after a settings change.

        Called from ``__init__.py`` immediately after the user saves settings
        so that the sidebar reflects the new theme without an Anki restart.
        Updates the main Qt stylesheet and refreshes all inline-styled labels
        via :meth:`update_display`.
        """
        self.main_widget.setStyleSheet(_build_sidebar_style(is_night_mode))
        scroll_bg = _palette(is_night_mode)["bg"]
        self.scroll_area.setStyleSheet(f"background-color: {scroll_bg}; border: none;")
        # Re-apply inline styles that carry colour tokens (streak, xp label …)
        streak_color = _palette(is_night_mode)["blue_accent"]
        self.streak_days_label.setStyleSheet(
            f"font-size: 16px; color: {streak_color}; font-weight: 700; background-color: transparent;"
        )
        xp_label_color = _palette(is_night_mode)["text_muted"]
        self.xp_label.setStyleSheet(
            f"font-size: 11px; color: {xp_label_color}; background-color: transparent;"
        )
        self.update_display()

    def update_display(self):
        if not self.manager:
            self.rank_badge_label.setText("?")
            self.level_label.setText(_("Level: ?")); self.rank_name_label.setText(_("Rank: ???"))
            self.next_goal_text_label.setText(_("Loading next goal..."))
            self.streak_days_label.setText(_("? Day Streak"))
            self.streak_xp_label.setText("(+? XP)")
            self.xp_label.setText(_("XP: ? / ?"))
            self.xp_progress_bar.setValue(0); self.challenge_text_label.setText(_("Loading..."))
            self.challenge_complete_button.setEnabled(False); self.challenge_complete_button.setText(_("Complete Challenge"))
            self._clear_layout(self.all_ranks_layout)
            self.guide_label.setText(self._get_guide_html())
            return

        try:
            current_level = self.manager.get_level()
            current_rank_info = self.manager.get_current_rank_info()
            current_rank_name = _(current_rank_info.get("name", _("Unknown Rank")))
            current_rank_image_file = current_rank_info.get("image")
            current_rank_image_path = self.manager.get_rank_image_path(current_rank_image_file)
            streak = self.manager.get_streak(); xp_current = self.manager.data.get('xp', 0); needed = self.manager.get_xp_for_level(current_level)
            remaining_xp = self.manager.get_remaining_xp(); progress_percent = self.manager.get_progress_percentage()
            challenge_text, _unused = self.manager.get_current_challenge(); is_completed = self.manager.is_challenge_completed_today()
            
            xp_reward = self.manager.get_daily_challenge_xp()
            
            all_ranks: List[Dict[str, Any]] = self.manager.get_all_ranks()

            # Release old movie resources to prevent C++ memory crashes.
            self.rank_badge_label.setMovie(None)

            if self.main_rank_movie:
                self.main_rank_movie.stop()
                self.main_rank_movie.deleteLater()
                self.main_rank_movie = None

            if self._movie_buffer:
                try: self._movie_buffer.close()
                except Exception: pass
                self._movie_buffer.deleteLater()
                self._movie_buffer = None

            # Load GIF from disk into memory to avoid file-lock issues.
            main_badge_exists = current_rank_image_path and os.path.exists(current_rank_image_path)
            if main_badge_exists:
                with open(current_rank_image_path, 'rb') as f:
                    img_data = f.read()

                self._movie_byte_array = QByteArray(img_data)
                self._movie_buffer = QBuffer(self._movie_byte_array)

                # PyQt5 / PyQt6 compatibility
                try:
                    self._movie_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
                except AttributeError:
                    self._movie_buffer.open(QIODevice.ReadOnly)

                self.main_rank_movie = QMovie(self._movie_buffer, b"gif")
                
                self.main_rank_movie.setScaledSize(QSize(MAIN_BADGE_SIZE, MAIN_BADGE_SIZE))
                self.rank_badge_label.setMovie(self.main_rank_movie)
                self.rank_badge_label.setToolTip(current_rank_name.replace("<br>", " "))
                self._setup_gif_animation(self.main_rank_movie, self.rank_badge_label)
            else:
                self.rank_badge_label.setText(current_rank_name[0] if current_rank_name else "?")
                self.rank_badge_label.setToolTip(_("Image not found: {}").format(current_rank_image_file or "N/A"))

            self.level_label.setText(_("Level {}").format(current_level))
            self.rank_name_label.setText(current_rank_name)
            needed_str = "MAX" if needed == float('inf') else f"{int(needed):,}"; rem_str = "N/A" if remaining_xp == float('inf') or not isinstance(remaining_xp, int) else f"{int(remaining_xp):,}"

            xp_text = f"{xp_current:,} / {needed_str} XP"
            self.xp_label.setText(xp_text)
            self.xp_label.setToolTip(_("Needed for next level: {}").format(rem_str))

            self.xp_progress_bar.setValue(progress_percent); self.xp_progress_bar.setToolTip(f"{progress_percent}%")

            streak_xp_bonus = streak * 20
            streak_text_tpl = _("{} Day Streak") if streak == 1 else _("{} Days Streak")
            self.streak_days_label.setText(streak_text_tpl.format(streak))
            self.streak_xp_label.setText(f"(+{streak_xp_bonus:,} XP)")
            streak_tooltip = _("Current streak bonus: +{} XP per day.\n(Formula: 20 XP \u00d7 {} days)").format(f"{streak_xp_bonus:,}", streak)
            self.streak_days_label.setToolTip(streak_tooltip)
            self.streak_xp_label.setToolTip(streak_tooltip)

            self.challenge_text_label.setText(challenge_text)

            _c = _palette(is_night_mode)
            if is_completed:
                self.challenge_group.setStyleSheet(
                    f"QFrame#CardFrame {{ background-color: {_c['green_bg']}; border: 1px solid {_c['green_border']}; border-radius: 12px; }}"
                )
                self.challenge_complete_button.setText(_("Completed"))
                self.challenge_complete_button.setEnabled(False)
                self.challenge_complete_button.setToolTip("")
            else:
                self.challenge_group.setStyleSheet(
                    f"QFrame#CardFrame {{ background-color: {_c['info_bg']}; border: 1px solid {_c['info_border']}; border-radius: 12px; }}"
                )
                self.challenge_complete_button.setText(_("Complete (+{} XP)").format(xp_reward))
                self.challenge_complete_button.setEnabled(True)
                self.challenge_complete_button.setToolTip(_("Click to gain {} XP.").format(xp_reward))

            next_rank_info = None
            for rank in all_ranks:
                if rank['level'] > current_level:
                    next_rank_info = rank
                    break
            
            sub_text_col = _palette(is_night_mode)["text_muted"]
            accent_col = _palette(is_night_mode)["blue_accent"]
            
            if next_rank_info:
                xp_needed_for_current_level = self.manager.get_xp_for_level(current_level) - xp_current
                total_xp_for_intermediate_levels = 0
                for i in range(current_level + 1, next_rank_info['level']):
                    total_xp_for_intermediate_levels += self.manager.get_xp_for_level(i)
                total_remaining_xp = xp_needed_for_current_level + total_xp_for_intermediate_levels

                next_rank_display = _(next_rank_info['name']).replace('<br>', ' ')
                only_xp_until = _("Only {} XP until:").format(f"{int(total_remaining_xp):,}")
                next_goal_html = (f"<div style='font-size: 11px; color: {sub_text_col};'>{only_xp_until}</div>"
                                  f"<div style='font-weight: bold; font-size: 16px; color: {accent_col}; margin-top:2px;'>{next_rank_display}</div>")
                self.next_goal_text_label.setText(next_goal_html)
            else:
                max_rank_html = (f"<div style='font-weight: bold; color: {accent_col};'>{_('Maximum Rank Achieved!')}</div>"
                                 f"<div style='font-size: 14px; margin-top:2px;'>{_('Congratulations!')}</div>")
                self.next_goal_text_label.setText(max_rank_html)


            self._clear_layout(self.all_ranks_layout)
            row, col = 0, 0
            for rank_info in all_ranks:
                rank_level = rank_info.get('level', 999)
                is_unlocked = current_level >= rank_level
                rank_name = _(rank_info.get("name", "?")).replace("<br>", " ")
                rank_image_file = rank_info.get("image")
                rank_image_path = self.manager.get_rank_image_path(rank_image_file)

                icon_label = BadgeLabel(locked=not is_unlocked)
                icon_label.setMinimumSize(SMALL_BADGE_SIZE, SMALL_BADGE_SIZE)
                icon_label.setMaximumSize(SMALL_BADGE_SIZE, SMALL_BADGE_SIZE)
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                tooltip_text = _("Lvl {}+: {}").format(rank_info.get('level', '?'), rank_name)
                if not is_unlocked:
                    tooltip_text += " " + _("(Locked)")
                icon_label.setToolTip(tooltip_text)

                small_badge_exists = rank_image_path and os.path.exists(rank_image_path)
                
                if small_badge_exists:
                    static_image_path = rank_image_path.replace(".gif", ".png")
                    
                    if not os.path.exists(static_image_path):
                        static_image_path = rank_image_path
                    
                    # Load small badge images into memory to avoid file-lock issues.
                    with open(static_image_path, 'rb') as f:
                        static_img_data = f.read()
                        
                    pixmap = QPixmap()
                    pixmap.loadFromData(static_img_data)
                    
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(
                            QSize(SMALL_BADGE_SIZE, SMALL_BADGE_SIZE), 
                            Qt.AspectRatioMode.KeepAspectRatio, 
                            Qt.TransformationMode.SmoothTransformation
                        )
                        icon_label.setPixmap(scaled_pixmap)
                    else:
                        icon_label.setText("?")
                else:
                    icon_label.setText("?")

                self.all_ranks_layout.addWidget(icon_label, row, col); col += 1
                if col >= GRID_COLUMNS: col = 0; row += 1

            self.guide_label.setText(self._get_guide_html())

        except Exception as e:
            print(f"{ADDON_NAME}: Error updating sidebar display: {e}"); traceback.print_exc()
            self.rank_name_label.setText(_("Error")); self.challenge_text_label.setText(_("Error"))
            self.challenge_complete_button.setEnabled(False)
            self._clear_layout(self.all_ranks_layout)
            self.guide_label.setText("<i>" + _("Error loading guide.") + "</i>")

    def _on_complete_challenge_clicked(self):
        if not self.manager: tooltip(_("Error: Gamification Manager not available.")); return
        if self.manager.is_challenge_completed_today(): tooltip(_("Challenge already completed today!")); return
        try: self.manager.on_complete_challenge(); self.update_display()
        except Exception as e: print(f"{ADDON_NAME}: Error calling on_complete_challenge: {e}"); tooltip(_("An error occurred."))