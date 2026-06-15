# -*- coding: utf-8 -*-

import json
import random
import os
from datetime import date, datetime, timedelta
import traceback
from typing import Union, List, Dict, Optional, Any

from aqt import mw
from aqt.utils import showInfo, tooltip, askUser, QMessageBox

try:
    from . import constants
    ADDON_FOLDER_NAME = constants.addon_package_name
except (ImportError, AttributeError):
    ADDON_FOLDER_NAME = "SynapsePro1"

try:
    from .locales import _
except ImportError:
    def _(text):  # type: ignore
        return text

# --- Night Mode Detection ---
is_night_mode = False
try:
    if mw and mw.pm.night_mode():
        is_night_mode = True
except Exception:
    pass

try:
    from .theme import palette as _palette, FONT_FAMILY as _FONT_FAMILY
except ImportError:
    def _palette(night): return {"blue": "#0071D3", "blue_bright": "#098BFF" if night else "#007AFF", "text": "#1D1D1F", "text_muted": "#86868B", "grey_light": "#e9ecef"}  # type: ignore
    _FONT_FAMILY = "sans-serif"

ADDON_NAME = "GamificationPlusDailyWidgets_" + ADDON_FOLDER_NAME
CONFIG_KEY = f"addon_{ADDON_NAME}_data"
CMD_RESET_DATA = f"gamification_reset_data_{ADDON_FOLDER_NAME}"
CMD_LP_START_PREFIX = f"lp_start"
CMD_LP_PAUSE_PREFIX = f"lp_pause"
IMAGES_SUBFOLDER = "images"

# --- Gamification Balancing ---
XP_PER_MINUTE_STUDIED = 10
XP_FOR_DAILY_CHALLENGE_BASE = 120
XP_FOR_DAILY_CHALLENGE_PER_LEVEL = 5
XP_PER_STREAK_DAY = 20
XP_LEVEL_BASE = 100
XP_LEVEL_FACTOR = 1.065

# --- Rank Struktur mit .gif ---
RANKS: List[Dict[str, Any]] = [
    {"level": 0,   "name": "Anki<br>Starter",          "image": "rang1.gif"},
    {"level": 5,   "name": "Card<br>Crawler",       "image": "rang2.gif"},
    {"level": 10,  "name": "Note<br>Nerd",        "image": "rang3.gif"},
    {"level": 15,  "name": "Deck<br>Diver",         "image": "rang4.gif"},
    {"level": 20,  "name": "Review<br>Rookie",      "image": "rang5.gif"},
    {"level": 25,  "name": "Recall<br>Rabbit",     "image": "rang6.gif"},
    {"level": 30,  "name": "Memory<br>Mover",       "image": "rang7.gif"},
    {"level": 35,  "name": "Recall<br>Ranger",      "image": "rang8.gif"},
    {"level": 40,  "name": "Synapse<br>Scout",      "image": "rang9.gif"},
    {"level": 45,  "name": "Fact<br>Ferret",        "image": "rang10.gif"},
    {"level": 50,  "name": "Focus<br>Falcon",       "image": "rang11.gif"},
    {"level": 55,  "name": "Recall<br>Raider",      "image": "rang12.gif"},
    {"level": 60,  "name": "Cognition<br>Crafter", "image": "rang13.gif"},
    {"level": 65,  "name": "Focus<br>Forager",     "image": "rang14.gif"},
    {"level": 70,  "name": "Knowledge<br>Knight",  "image": "rang15.gif"},
    {"level": 75,  "name": "Memory<br>Mage",       "image": "rang16.gif"},
    {"level": 80,  "name": "Review<br>Rocket",       "image": "rang17.gif"},
    {"level": 85,  "name": "Study<br>Samurai",     "image": "rang18.gif"},
    {"level": 90,  "name": "Flashcard<br>Fanatic", "image": "rang19.gif"},
    {"level": 95,  "name": "Neuro<br>Ninja",       "image": "rang20.gif"},
    {"level": 100, "name": "Anki<br>Admiral",      "image": "rang21.gif"}
]
DEFAULT_RANK_INFO = RANKS[0]

# --- Daily Challenges ---
DAILY_CHALLENGES = [
    {"text": "Review cards for 15 minutes straight.", "points": 0},
    {"text": "Learn 10 new cards today.", "points": 0},
    {"text": "Review for at least 1 hour today", "points": 0},
    {"text": "Review cards from 3 different decks.", "points": 0},
    {"text": "Review 200 cards today", "points": 0},
    {"text": "Finish all due reviews before noon.", "points": 0},
    {"text": "Review 50 cards.", "points": 0},
    {"text": "Do your reviews with no distractions", "points": 0},
    {"text": "Review 150 cards", "points": 0},
    {"text": "Do Anki for 30 minutes straight.", "points": 0},
    {"text": "Add 3 new notes with images.", "points": 0},
    {"text": "Review 50 cards", "points": 0},
    {"text": "Study one filtered deck completely.", "points": 0},
    {"text": "Review 100 cards total", "points": 0},
    {"text": "Review 250 Cards.", "points": 0},
    {"text": "Learn 30 new cards", "points": 0},
    {"text": "Review 100 cards.", "points": 0},
    {"text": "Learn 15 new cards.", "points": 0},
    {"text": "Sync your collection to AnkiWeb.", "points": 0},
    {"text": "Review all due cards for today.", "points": 0},
]

def calculate_streak_from_revlog() -> int:
    """
    Berechnet den aktuellen Streak dynamisch aus der revlog-Tabelle.

    Optimierung: Gruppierung nach Anki-Tag direkt in SQL (DISTINCT),
    sodass nur O(Lerntage) statt O(alle Reviews) übertragen werden.

    Regeln:
    - Nur echte Reviews (ease > 0), kein manuelles Rescheduling
    - Ankis Rollover-Stunde + lokale Zeitzone werden berücksichtigt
    - Streak = aufeinanderfolgende Lerntage endend bei heute/gestern
    - Wenn letzter Lerntag vorgestern oder früher → Streak = 0
    """
    if not mw or not mw.col:
        return 0
    try:
        import time as _time
        from datetime import date as _date

        rollover = int(mw.col.conf.get("rollover", 4))
        offset_seconds = rollover * 3600

        # Local timezone offset including DST
        if _time.daylight and _time.localtime().tm_isdst:
            tz_offset = -_time.altzone
        else:
            tz_offset = -_time.timezone

        # Combined offset: timezone + rollover shift
        total_offset = tz_offset - offset_seconds

        # SQL computes Anki day number directly, returning only DISTINCT days.
        rows = mw.col.db.all(
            "SELECT DISTINCT CAST((id / 1000 + ?) / 86400 AS INTEGER) AS day_num "
            "FROM revlog WHERE ease > 0",
            total_offset
        )
        if not rows:
            return 0

        EPOCH = _date(1970, 1, 1)
        study_days = {EPOCH + timedelta(days=int(day_num)) for (day_num,) in rows}

        today_day_num = int((datetime.now().timestamp() + total_offset) / 86400)
        today_anki_date = EPOCH + timedelta(days=today_day_num)

        last_study_day = max(study_days)
        days_since_last = (today_anki_date - last_study_day).days

        if days_since_last > 1:
            return 0

        streak = 0
        check_day = last_study_day
        while check_day in study_days:
            streak += 1
            check_day -= timedelta(days=1)

        return streak

    except Exception as e:
        print(f"SynapsePro: Fehler bei Streak-Berechnung aus revlog: {e}")
        traceback.print_exc()
        return 0


class GamificationManager:
    """Handles all gamification logic: XP, levels, ranks, streaks, challenges."""

    def __init__(self, addon_path: Optional[str]):
        self.data: Dict = {}
        self._addon_dir_path: Optional[str] = addon_path
        self.load_data()
        self._todays_challenge: Optional[Dict] = None
        challenge_id = self.data.get("current_challenge_id")
        if challenge_id is not None:
             try: self._todays_challenge = DAILY_CHALLENGES[challenge_id]
             except IndexError: self._todays_challenge = None; self.data["current_challenge_id"] = None

    def _default_data(self) -> Dict:
        yest = int((date.today() - timedelta(days=1)).strftime("%Y%m%d"))
        return {"level": 1, "xp": 0, "streak": 0, "last_login_day": 0,
                "last_time_xp_check_day": yest, "current_challenge_id": None,
                "challenge_completed_day": 0, "version": 4}

    # ------------------------------------------------------------------
    # JSON backup helpers (resilient against Anki schema upgrades that
    # can wipe mw.col.conf entries)
    # ------------------------------------------------------------------

    def _get_profile_data_path(self) -> Optional[str]:
        """Returns the path to the profile-specific JSON backup file."""
        try:
            profile_folder = mw.pm.profileFolder()
            data_folder = os.path.join(profile_folder, "SynapsePro_Data")
            os.makedirs(data_folder, exist_ok=True)
            return os.path.join(data_folder, "gamification_data.json")
        except Exception:
            return None

    def _load_from_json_backup(self) -> Optional[Dict]:
        """Try to load gamification data from the JSON backup file."""
        try:
            path = self._get_profile_data_path()
            if path and os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    print(f"{ADDON_NAME}: Loaded gamification data from JSON backup.")
                    return data
        except Exception as e:
            print(f"{ADDON_NAME}: Could not read JSON backup: {e}")
        return None

    def _save_to_json_backup(self):
        """Save gamification data to the JSON backup file (profile folder)."""
        try:
            path = self._get_profile_data_path()
            if path:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"{ADDON_NAME}: Could not write JSON backup: {e}")

    def load_data(self):
        conf = mw.col.conf.get(CONFIG_KEY)
        defaults = self._default_data()
        loaded_from_col = False

        if conf and isinstance(conf, dict):
            self.data = conf
            loaded_from_col = True
        else:
            # mw.col.conf had no data — this happens after an Anki update that
            # performs a schema migration or resets collection config.
            # Fall back to the JSON backup stored in the profile folder.
            backup = self._load_from_json_backup()
            if backup and isinstance(backup, dict):
                self.data = backup
                # Restore into col.conf so future saves are consistent.
                try:
                    mw.col.conf[CONFIG_KEY] = self.data
                except Exception:
                    pass
                print(f"{ADDON_NAME}: Restored gamification data from JSON backup after col.conf loss.")
            else:
                self.data = defaults

        # Fill in any missing keys from a newer version of the addon.
        updated = False
        for k, v in defaults.items():
            if k not in self.data:
                self.data[k] = v
                updated = True
        if self.data.get("version", 0) < defaults["version"]:
            self.data["version"] = defaults["version"]
            updated = True

        if updated or not loaded_from_col:
            self.save_data()

    def save_data(self):
        if mw.col:
            try:
                mw.col.conf[CONFIG_KEY] = self.data
            except Exception as e:
                print(f"{ADDON_NAME} ERROR saving gamification data to col.conf: {e}")
                traceback.print_exc()
        # Always write the JSON backup so data survives future collection migrations.
        self._save_to_json_backup()

    def get_xp_for_level(self, level: int) -> Union[int, float]:
        if level < 1: return 0
        try:
            needed = round(XP_LEVEL_BASE * (XP_LEVEL_FACTOR ** (level - 1)))
            return max(1, needed)
        except OverflowError:
            return float('inf')

    def get_rank_info_for_level(self, level_to_check: int) -> Dict[str, Any]:
        selected_rank = DEFAULT_RANK_INFO
        for rank_info in reversed(RANKS):
            if level_to_check >= rank_info["level"]:
                selected_rank = rank_info
                break
        return selected_rank

    def get_current_rank_info(self) -> Dict[str, Any]:
        return self.get_rank_info_for_level(self.data.get("level", 1))

    def get_rank_name(self) -> str:
        return self.get_current_rank_info().get("name", DEFAULT_RANK_INFO["name"])

    def get_all_ranks(self) -> List[Dict[str, Any]]:
        return RANKS

    def get_rank_image_path(self, image_filename: Optional[str]) -> Optional[str]:
        if not image_filename or not hasattr(constants, 'icons_folder'):
            return None
        try:
            return os.path.join(constants.icons_folder, image_filename)
        except Exception:
            return None

    def add_xp(self, amount: int, reason: str = "") -> bool:
        if amount <= 0: return False
        current_xp = self.data.get("xp", 0)
        current_level = self.data.get("level", 1)
        level_before = current_level
        new_total_xp_at_level = current_xp + amount
        needed_for_current_level = self.get_xp_for_level(current_level)
        levels_gained = 0
        old_rank_info = self.get_rank_info_for_level(level_before)
        while needed_for_current_level != float('inf') and new_total_xp_at_level >= needed_for_current_level:
            new_total_xp_at_level -= needed_for_current_level
            current_level += 1
            levels_gained += 1
            needed_for_current_level = self.get_xp_for_level(current_level)
        if levels_gained > 0:
            self.data["level"] = current_level
            new_rank_info = self.get_current_rank_info()
            rank_display_name = _(new_rank_info.get("name", _("Unknown Rank"))).replace("<br>", " ")
            tooltip(_("Level Up! Lvl {}!").format(current_level), period=3000)
            if old_rank_info["name"] != new_rank_info["name"]:
                tooltip(_("New Rank: {}!").format(rank_display_name), period=3500)
        self.data["xp"] = int(round(new_total_xp_at_level))
        self.save_data()
        return True

    def _get_study_time_for_day(self, day_int: int) -> float:
        if not mw.col: return 0
        try:
            target_date = datetime.strptime(str(day_int), "%Y%m%d").date()
        except ValueError:
            return 0
        start_dt = datetime.combine(target_date, datetime.min.time())
        end_dt = datetime.combine(target_date + timedelta(days=1), datetime.min.time())
        start_ts_ms = int(start_dt.timestamp() * 1000)
        end_ts_ms = int(end_dt.timestamp() * 1000)
        try:
            total_ms = mw.col.db.scalar("SELECT sum(time) FROM revlog WHERE id >= ? AND id < ?", start_ts_ms, end_ts_ms) or 0
            return total_ms / 1000.0
        except Exception:
            return 0
            
    def _get_rollover_hour(self) -> int:
        """
        Returns Anki's configured day-rollover hour (default 4).
        Reviews before this hour count as the *previous* calendar day in Anki's
        scheduler. We need to account for this when checking streak boundaries.
        """
        try:
            return int(mw.col.conf.get("rollover", 4))
        except Exception:
            return 4

    def _did_user_study_on_day(self, day_int: int) -> bool:
        """
        Prüft, ob an einem bestimmten Tag Lernaktivität stattfand (mind. 1 Review).

        Uses Anki's rollover hour so that late-night sessions (e.g. studying
        until 2 AM when rollover is 4 AM) are correctly attributed to the
        calendar day the user *experienced* as their study day, rather than
        the next calendar day that the wall clock shows.

        The window checked is:
            [day_int 00:00] → [day_int+1 00:00 + rollover_hours]
        This covers both the normal midnight boundary AND the early-morning
        rollover period of the *next* calendar day.
        """
        if not mw.col or day_int == 0: return False
        try:
            target_date = datetime.strptime(str(day_int), "%Y%m%d").date()
            rollover = self._get_rollover_hour()

            # Start: midnight of the target calendar day
            day_start_ts_ms = int(
                datetime.combine(target_date, datetime.min.time()).timestamp() * 1000
            )
            # End: midnight of the next calendar day PLUS the rollover buffer,
            # so reviews done before rollover on day+1 still count for day_int.
            day_end_ts_ms = int(
                (datetime.combine(target_date + timedelta(days=1), datetime.min.time())
                 + timedelta(hours=rollover)).timestamp() * 1000
            )

            count = mw.col.db.scalar(
                "SELECT COUNT(*) FROM revlog WHERE id >= ? AND id < ?",
                day_start_ts_ms,
                day_end_ts_ms,
            )
            return count > 0
        except (ValueError, Exception):
            return False

    def check_and_update_streak_and_time_xp(self) -> bool:
        today_int = int(date.today().strftime("%Y%m%d"))
        last_login_day = self.data.get("last_login_day", 0)
        xp_gain_streak = 0
        streak_reason = ""
        data_changed = False

        if today_int > last_login_day:
            data_changed = True

            # Recalculate streak from revlog (not from stored config counter).
            current_streak = calculate_streak_from_revlog()

            # Keep data["streak"] in sync for compatibility.
            self.data["streak"] = current_streak

            if current_streak > 1:
                xp_gain_streak = current_streak * XP_PER_STREAK_DAY
                streak_reason = f"Daily Streak: Day {current_streak} (+{xp_gain_streak} XP)"
                tooltip(_("Streak: {} days!\n+{} XP Bonus").format(current_streak, xp_gain_streak), period=4000)
            else:
                # No active streak: award base daily login XP.
                xp_gain_streak = XP_PER_STREAK_DAY
                streak_reason = f"Daily Login (+{xp_gain_streak} XP)"
                if current_streak == 0:
                    if hasattr(mw, 'learning_plan_manager') and mw.learning_plan_manager:
                        mw.learning_plan_manager.reset_plan_status()

            self.assign_new_daily_challenge()
            self.data["last_login_day"] = today_int
        
        last_time_check_day = self.data.get("last_time_xp_check_day", 0)
        time_xp_gain = 0
        time_reason = ""
        if today_int > last_time_check_day:
            day_to_calculate = date.today() - timedelta(days=1)
            day_to_calculate_int = int(day_to_calculate.strftime("%Y%m%d"))
            if day_to_calculate_int >= last_time_check_day:
                study_seconds = self._get_study_time_for_day(day_to_calculate_int)
                if study_seconds > 0:
                    time_xp_gain = int((study_seconds / 60.0) * XP_PER_MINUTE_STUDIED)
            self.data["last_time_xp_check_day"] = today_int
            data_changed = True
            
        total_xp_to_add = xp_gain_streak + time_xp_gain
        if total_xp_to_add > 0:
            full_reason = ", ".join(filter(None, [streak_reason, time_reason])) or "Daily Activity"
            if self.add_xp(total_xp_to_add, full_reason):
                data_changed = True
        elif data_changed:
            self.save_data()
        return data_changed

    def assign_new_daily_challenge(self):
        if not DAILY_CHALLENGES: return
        self.data["challenge_completed_day"] = 0
        challenge_index = random.randrange(len(DAILY_CHALLENGES))
        self.data["current_challenge_id"] = challenge_index
        try:
            self._todays_challenge = DAILY_CHALLENGES[challenge_index]
        except IndexError:
            self._todays_challenge = None
            self.data["current_challenge_id"] = None

    def get_current_challenge(self) -> tuple[str, int]:
        challenge_id = self.data.get("current_challenge_id")
        challenge_text = _("No challenge available.")
        if challenge_id is not None:
            try:
                raw = DAILY_CHALLENGES[challenge_id].get('text', "Error")
                challenge_text = _(raw) if raw else _("Error")
            except IndexError:
                challenge_id = None
        if challenge_id is None:
            self.assign_new_daily_challenge()
            self.save_data()
            if self._todays_challenge:
                raw = self._todays_challenge.get('text', "Error")
                challenge_text = _(raw) if raw else _("Error")
        return challenge_text, 0

    def get_daily_challenge_xp(self) -> int:
        return int(XP_FOR_DAILY_CHALLENGE_BASE + (self.get_level() * XP_FOR_DAILY_CHALLENGE_PER_LEVEL))

    def is_challenge_completed_today(self) -> bool:
        return self.data.get("challenge_completed_day", 0) == int(date.today().strftime("%Y%m%d"))

    def on_complete_challenge(self):
        if self.is_challenge_completed_today():
            tooltip(_("Challenge already completed today!"))
            return
        xp_reward = self.get_daily_challenge_xp()
        today_int = int(date.today().strftime("%Y%m%d"))
        self.data["challenge_completed_day"] = today_int
        self.add_xp(xp_reward, "Daily Challenge")
        tooltip(_("Challenge complete! +{} XP").format(xp_reward), period=3500)
        self._force_refresh("on_complete_challenge")

    def get_level(self) -> int: return self.data.get("level", 1)
    def get_streak(self) -> int: return calculate_streak_from_revlog()

    def get_progress_percentage(self) -> int:
        needed = self.get_xp_for_level(self.get_level())
        if needed == float('inf') or needed <= 0:
            return 100 if needed == float('inf') else 0
        return min(100, int((self.data.get("xp", 0) / needed) * 100))

    def get_remaining_xp(self) -> Union[int, float]:
        needed = self.get_xp_for_level(self.get_level())
        if needed == float('inf'): return 0
        return max(0, int(needed - self.data.get("xp", 0)))

    def _force_refresh(self, reason: str = ""):
        try:
            if mw.state == "deckBrowser":
                mw.deckBrowser.refresh()
            else:
                mw.moveToState("deckBrowser")
        except Exception:
            pass

    # --- Debug Methoden ---
    def debug_add_xp(self, amount: int):
        if self.add_xp(amount, "Debug"): self._force_refresh("debug_add_xp")

    def debug_set_level(self, new_level: int):
        if new_level < 1: return
        self.data["level"] = new_level; self.data["xp"] = 0
        self.save_data(); self._force_refresh("debug_set_level")

    def debug_new_challenge(self):
        self.assign_new_daily_challenge(); self.save_data(); self._force_refresh("debug_new_challenge")
        
    def debug_next_daily_fact(self):
        if hasattr(mw, 'daily_widgets') and hasattr(mw.daily_widgets, '_debug_day_offset'):
            mw.daily_widgets._debug_day_offset += 1
            self._force_refresh("debug_next_daily_fact")
            
    def reset_all_data(self) -> bool:
        if not askUser(_("Reset all {} Gamification data?").format(ADDON_NAME)):
            return False
        self.data = self._default_data()
        self._todays_challenge = None
        lpm = getattr(mw, 'learning_plan_manager', None)
        lpm_json_path = getattr(lpm, '_config_json_path', None) if lpm else None
        delete_json = False
        if lpm_json_path and os.path.exists(lpm_json_path):
             if QMessageBox.question(mw, _("Delete Study Plan?"), _("Also delete Study Plan config?"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                 delete_json = True
        if hasattr(mw, 'daily_widgets') and hasattr(mw.daily_widgets, '_debug_day_offset'):
            mw.daily_widgets._debug_day_offset = 0
        if lpm:
            lpm.reset_plan_status()
        if delete_json and lpm_json_path:
             try: os.remove(lpm_json_path)
             except OSError: pass
        self.save_data()
        self._force_refresh("reset_all_data")
        showInfo(_("{} data reset.").format(ADDON_NAME))
        return True

    def render_widgets_html(self) -> str:
        """
        Generiert das vollständige HTML und CSS für die Gamification-Widgets.
        """
        lvl = self.get_level()
        rank = _(self.get_rank_name())
        streak = self.get_streak()
        chall_txt, _unused = self.get_current_challenge()
        prog = self.get_progress_percentage()
        rem_xp = self.get_remaining_xp()
        needed = self.get_xp_for_level(lvl)
        xp_current = self.data.get('xp', 0)

        # Pre-computed translated labels for the HTML template
        label_streak = _("Streak")
        label_days = _("Days")
        label_daily_challenge = _("Daily Challenge")
        label_next_level = _("Next Level")
        label_remaining_tpl = _("remaining: {} XP")
        label_max_reached_tpl = _("Max Level Reached ({} XP Total)")

        WIDGET_CONTAINER_MAX_WIDTH = "880px"; gap = "15px"; margin_b = "15px"

        _c_light = _palette(False)
        _c_dark  = _palette(True)
        css = f"""
        <style>
            :root {{
                --stat-bg: {_c_light["surface"]}; --stat-border: {_c_light["grey_light"]};
                --text-color: {_c_light["text"]}; --text-color-light: {_c_light["text_muted"]};
                --progress-bg: {_c_light["grey_light"]}; --primary-blue: {_c_light["blue"]};
                --level-accent: {_c_light["blue"]};
                --rank-color: var(--level-accent); --level-icon-text: #ffffff;
            }}
            body.night_mode {{
                --stat-bg: {_c_dark["surface"]}; --stat-border: {_c_dark["grey_mid"]};
                --text-color: {_c_dark["text"]}; --text-color-light: {_c_dark["text_muted"]};
                --progress-bg: {_c_dark["grey_mid"]}; --primary-blue: {_c_dark["blue_bright"]};
                --level-accent: {_c_dark["blue"]};
            }}
            .gamewidget {{
                background-color: var(--stat-bg); border-radius: 12px; padding: 15px;
                border: 1px solid var(--stat-border); text-align: left;
                flex: 1 1 auto; min-width: 150px; box-sizing: border-box;
                display: flex; flex-direction: column; justify-content: center; position: relative;
            }}
            body.night_mode .gamewidget {{ border: 1px solid {_c_dark["grey_mid"]}; }}
        </style>
        """
        
        title_style_gam = f"font-size:0.95em; font-weight:bold; color: var(--text-color); margin:0 0 5px 0;"
        cont_style_gam = f"font-size:0.9em; color: var(--text-color); margin:0;"
        sec_style_gam = f"font-size:0.8em; color: var(--text-color-light); margin-left:10px; white-space:nowrap;"
        bar_h="8px"
        
        lvl_icon = f'<div class="level-icon" style="background-color: var(--level-accent); color: var(--level-icon-text); border-radius:50%; width:45px; height:45px; display:flex; justify-content:center; align-items:center; font-weight:bold; font-size:1.3em; flex-shrink:0;">{lvl}</div>'
        rank_name_html = f'<span style="font-weight:bold; color: var(--rank-color); font-size:1.05em; line-height:1.2;">{rank}</span>'
        
        lvl_wid = f'''<div class="gamewidget level-widget" style="flex-direction:row; align-items:center; flex-grow:0; flex-basis:160px; padding:10px 15px; gap: 10px;">
                        {lvl_icon}
                        <div style="flex-grow: 1; min-width: 0;">{rank_name_html}</div>
                    </div>'''
        
        strk_wid=f'<div class="gamewidget streak-widget" style="text-align:center; flex-grow:0; flex-shrink:1; flex-basis:95px; min-width:90px;"><h5 style="{title_style_gam}">{label_streak}</h5><p style="{cont_style_gam}">{streak} {label_days}</p></div>'

        challenge_text_style = f"font-size: 0.9em; color: var(--text-color); margin: 5px 0 0 0; line-height: 1.3;"
        chall_wid = f'''<div class="gamewidget challenge-widget">
                          <h5 style="{title_style_gam.replace("margin:0 0 5px 0;", "margin:0;")}">{label_daily_challenge}</h5>
                          <p style="{challenge_text_style}">{chall_txt}</p>
                        </div>'''

        xp_current_str = f"{xp_current:,}"; needed_str = "MAX" if needed == float('inf') else f"{needed:,}"; rem_xp_disp = "N/A" if needed == float('inf') else f"{rem_xp:,}";
        prog_bar_title = label_max_reached_tpl.format(xp_current_str) if needed == float('inf') else f"{xp_current_str} / {needed_str} XP"
        prog_bar=f'<div class="progress-bar-outer" style="width:100%; height:{bar_h}; background-color: var(--progress-bg); border-radius:{bar_h}; overflow:hidden; margin-top:8px;" title="{prog_bar_title}"><div class="progress-bar-inner" style="height:100%; width:{prog}%; background-color: var(--primary-blue); border-radius:{bar_h}; transition:width 0.3s ease-out;"></div></div>'

        next_lvl_wid=f'<div class="gamewidget next-level-widget"><div style="display:flex; justify-content:space-between; align-items:baseline; width:100%;"><h5 style="{title_style_gam}">{label_next_level}</h5><span style="{sec_style_gam}">{label_remaining_tpl.format(rem_xp_disp)}</span></div>{prog_bar}</div>'
        
        gamification_container_style = f""" display: flex; justify-content: center; align-items: stretch; flex-wrap: wrap; gap: {gap}; max-width: {WIDGET_CONTAINER_MAX_WIDTH}; margin: 0 auto {margin_b} auto; padding: 0 10px; box-sizing: border-box; """
        
        html = f'<div id="gamification-widgets-container" style="{gamification_container_style}">{lvl_wid}{strk_wid}{chall_wid}{next_lvl_wid}</div>'

        return css + html