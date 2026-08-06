# -*- coding: utf-8 -*-

import json
import random
import os
import time
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
CMD_CLAIM_CHALLENGE = f"gamification_claim_challenge_{ADDON_FOLDER_NAME}"
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
# Every challenge is MEASURABLE from Anki's review log, so completion can be
# verified automatically. "type" selects the metric, "target" the goal.
# Text templates are translated via locales.py; "{}" receives the target.
CHALLENGE_TEXT_TEMPLATES: Dict[str, str] = {
    "reviews":    "Review {} cards today.",
    "new_cards":  "Learn {} new cards today.",
    "study_time": "Study for {} minutes today.",
    "decks":      "Review cards from {} different decks today.",
}

DAILY_CHALLENGES: List[Dict[str, Any]] = [
    {"type": "reviews",    "target": 30},
    {"type": "reviews",    "target": 50},
    {"type": "reviews",    "target": 75},
    {"type": "reviews",    "target": 100},
    {"type": "reviews",    "target": 150},
    {"type": "reviews",    "target": 200},
    {"type": "new_cards",  "target": 5},
    {"type": "new_cards",  "target": 10},
    {"type": "new_cards",  "target": 15},
    {"type": "new_cards",  "target": 20},
    {"type": "study_time", "target": 10},
    {"type": "study_time", "target": 15},
    {"type": "study_time", "target": 30},
    {"type": "study_time", "target": 45},
    {"type": "study_time", "target": 60},
    {"type": "decks",      "target": 2},
    {"type": "decks",      "target": 3},
]


def _anki_today() -> date:
    """Current scheduler day, respecting the collection rollover hour."""
    try:
        rollover = max(0, min(23, int(mw.col.conf.get("rollover", 4))))
    except Exception:
        rollover = 4
    return (datetime.now() - timedelta(hours=rollover)).date()


def _anki_today_int() -> int:
    return int(_anki_today().strftime("%Y%m%d"))

def _tint_hex(color: str, factor: float = 0.45) -> str:
    """Lighten a #rrggbb colour by mixing it towards white (0=no change, 1=white)."""
    try:
        color = color.strip()
        if not color.startswith("#") or len(color) != 7:
            return color
        r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
        mix = lambda ch: int(round(ch + (255 - ch) * factor))
        return f"#{mix(r):02x}{mix(g):02x}{mix(b):02x}"
    except Exception:
        return color


def calculate_streak_from_revlog() -> int:
    """
    Berechnet den aktuellen Streak dynamisch aus der revlog-Tabelle.

    Performance: The revlog is read in bounded one-year windows, newest first.
    As soon as the first missing day ends the streak, older history is never
    touched. Long streaks transparently load another window and remain exact.

    WICHTIG (Bugfix): Die Tageszuordnung nutzt SQLites 'localtime'-Modifier,
    der für jeden Zeitstempel die *damals* gültige Zeitzonenregel (Sommer-/
    Winterzeit) anwendet. Die frühere Variante hat den AKTUELLEN DST-Offset
    auf die gesamte Historie angewendet — dadurch verschob sich die Tages-
    grenze für alle Winterdaten um eine Stunde (effektiv Rollover 3 Uhr statt
    4 Uhr), und Reviews zwischen 3 und 4 Uhr nachts rutschten auf den
    Folgetag. Ergebnis: fälschlich gerissene Streaks, z. B. exakt am
    Jahreswechsel bei einer Lernsession in der Silvesternacht.

    Regeln:
    - Nur echte Reviews (ease > 0), kein manuelles Rescheduling
    - Ankis Rollover-Stunde + historisch korrekte lokale Zeitzone
    - Streak = aufeinanderfolgende Lerntage endend bei heute/gestern
    - Wenn letzter Lerntag vorgestern oder früher → Streak = 0
    """
    if not mw or not mw.col:
        return 0
    try:
        from datetime import date as _date

        rollover = int(mw.col.conf.get("rollover", 4))

        # "Today" as an Anki day (datetime.now() is already correct local time).
        today_anki_date = (datetime.now() - timedelta(hours=rollover)).date()
        chunk_days = 370
        chunk_end = today_anki_date + timedelta(days=1)
        chunk_start = chunk_end - timedelta(days=chunk_days)

        def load_days(start_day, end_day):
            # Bounds use local rollover datetimes, while SQL retains the same
            # historical localtime/DST bucketing as the previous implementation.
            start_dt = datetime.combine(start_day, datetime.min.time()) + timedelta(hours=rollover)
            end_dt = datetime.combine(end_day, datetime.min.time()) + timedelta(hours=rollover)
            rows = mw.col.db.all(
                "SELECT DISTINCT strftime('%Y-%m-%d', id / 1000 - ?, "
                "'unixepoch', 'localtime') AS d "
                "FROM revlog WHERE ease > 0 AND id >= ? AND id < ?",
                rollover * 3600,
                int(start_dt.timestamp() * 1000),
                int(end_dt.timestamp() * 1000),
            )
            return {_date.fromisoformat(r[0]) for r in rows if r and r[0]}

        study_days = load_days(chunk_start, chunk_end)
        if today_anki_date in study_days:
            check_day = today_anki_date
        elif today_anki_date - timedelta(days=1) in study_days:
            check_day = today_anki_date - timedelta(days=1)
        else:
            return 0

        streak = 0
        while True:
            if check_day < chunk_start:
                chunk_end = chunk_start
                chunk_start = chunk_end - timedelta(days=chunk_days)
                study_days = load_days(chunk_start, chunk_end)
            if check_day not in study_days:
                break
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
        today_int = _anki_today_int()
        # A streak cannot change between two launches on the same Anki day
        # unless reviews were performed. The review-leave hook refreshes and
        # persists it, so same-day restarts can use the stored value instead of
        # grouping the complete revlog again.
        self._streak_cache: Optional[int] = (
            int(self.data.get("streak", 0))
            if self.data.get("last_login_day", 0) == today_int
            else None
        )
        self._challenge_progress_cache = None
        self._todays_challenge: Optional[Dict] = None
        challenge_id = self.data.get("current_challenge_id")
        if challenge_id is not None:
             try: self._todays_challenge = DAILY_CHALLENGES[int(challenge_id)]
             except (IndexError, ValueError, TypeError): self._todays_challenge = None; self.data["current_challenge_id"] = None

    def _default_data(self) -> Dict:
        yest = int((_anki_today() - timedelta(days=1)).strftime("%Y%m%d"))
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
        tmp_path = None
        try:
            path = self._get_profile_data_path()
            if path:
                # Write beside the destination and replace atomically. If Anki
                # or the computer stops mid-write, the previous valid backup
                # remains intact instead of becoming a truncated JSON file.
                tmp_path = path + ".tmp"
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, indent=2)
                os.replace(tmp_path, path)
        except Exception as e:
            print(f"{ADDON_NAME}: Could not write JSON backup: {e}")
            if tmp_path:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def load_data(self):
        # Defensive: if no collection is loaded yet, fall back to the JSON
        # backup (or defaults) instead of crashing on mw.col being None.
        if not mw or not mw.col:
            base = self._default_data()
            backup = self._load_from_json_backup()
            if isinstance(backup, dict):
                base.update(backup)
            self.data = base
            return
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
        rollover = self._get_rollover_hour()
        start_dt = (datetime.combine(target_date, datetime.min.time())
                    + timedelta(hours=rollover))
        end_dt = start_dt + timedelta(days=1)
        start_ts_ms = int(start_dt.timestamp() * 1000)
        end_ts_ms = int(end_dt.timestamp() * 1000)
        try:
            total_ms = mw.col.db.scalar(
                "SELECT sum(CASE WHEN time > 45000 THEN 45000 "
                "WHEN time < 0 THEN 0 ELSE time END) FROM revlog "
                "WHERE ease > 0 AND id >= ? AND id < ?",
                start_ts_ms, end_ts_ms) or 0
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

            # Use the same non-overlapping rollover window as Anki.
            day_start_ts_ms = int(
                (datetime.combine(target_date, datetime.min.time())
                 + timedelta(hours=rollover)).timestamp() * 1000
            )
            day_end_ts_ms = int(
                (datetime.combine(target_date + timedelta(days=1), datetime.min.time())
                 + timedelta(hours=rollover)).timestamp() * 1000
            )

            count = mw.col.db.scalar(
                "SELECT COUNT(*) FROM revlog WHERE ease > 0 AND id >= ? AND id < ?",
                day_start_ts_ms,
                day_end_ts_ms,
            )
            return count > 0
        except (ValueError, Exception):
            return False

    def check_and_update_streak_and_time_xp(self) -> bool:
        today_int = _anki_today_int()
        last_login_day = self.data.get("last_login_day", 0)
        xp_gain_streak = 0
        streak_reason = ""
        data_changed = False

        if today_int > last_login_day:
            data_changed = True

            # Recalculate streak from revlog (not from stored config counter).
            current_streak = calculate_streak_from_revlog()
            self._streak_cache = current_streak

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
                        # Startup already performs one final refresh after the
                        # daily maintenance; avoid a nested duplicate refresh.
                        mw.learning_plan_manager.reset_plan_status(refresh=False)

            self.assign_new_daily_challenge()
            self.data["last_login_day"] = today_int
        
        last_time_check_day = self.data.get("last_time_xp_check_day", 0)
        time_xp_gain = 0
        time_reason = ""
        if today_int > last_time_check_day:
            day_to_calculate = _anki_today() - timedelta(days=1)
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
        self._challenge_progress_cache = None
        self.data["challenge_completed_day"] = 0
        challenge_index = random.randrange(len(DAILY_CHALLENGES))
        self.data["current_challenge_id"] = challenge_index
        try:
            self._todays_challenge = DAILY_CHALLENGES[challenge_index]
        except IndexError:
            self._todays_challenge = None
            self.data["current_challenge_id"] = None

    def _get_valid_challenge(self) -> Optional[Dict[str, Any]]:
        """Return today's challenge dict, assigning a fresh one if needed."""
        challenge_id = self.data.get("current_challenge_id")
        if isinstance(challenge_id, int) and 0 <= challenge_id < len(DAILY_CHALLENGES):
            return DAILY_CHALLENGES[challenge_id]
        # Missing / legacy / out-of-range id → assign a new measurable one.
        self.assign_new_daily_challenge()
        self.save_data()
        return self._todays_challenge

    @staticmethod
    def _challenge_text(challenge: Optional[Dict[str, Any]]) -> str:
        if not challenge:
            return _("No challenge available.")
        tpl = CHALLENGE_TEXT_TEMPLATES.get(challenge.get("type", ""), "")
        if not tpl:
            return _("No challenge available.")
        return _(tpl).format(challenge.get("target", 0))

    def get_current_challenge(self) -> tuple[str, int]:
        return self._challenge_text(self._get_valid_challenge()), 0

    def _day_start_ms(self) -> int:
        """Epoch ms of the start of the current Anki day (respects rollover)."""
        try:
            cutoff = None
            sched = getattr(mw.col, "sched", None)
            if sched is not None:
                cutoff = getattr(sched, "day_cutoff", None)   # modern Anki
                if cutoff is None:
                    cutoff = getattr(sched, "dayCutoff", None)  # legacy Anki
            if cutoff:
                return (int(cutoff) - 86400) * 1000
        except Exception:
            pass
        # Fallback: derive the configured rollover boundary locally.
        start = (datetime.combine(_anki_today(), datetime.min.time())
                 + timedelta(hours=self._get_rollover_hour()))
        return int(start.timestamp() * 1000)

    def get_challenge_progress(self) -> tuple[int, int]:
        """Return (current, target) for today's challenge, measured from revlog."""
        challenge = self._get_valid_challenge()
        if not challenge or not mw or not mw.col:
            return 0, 1
        ctype  = challenge.get("type", "")
        target = max(1, int(challenge.get("target", 1)))
        start_ms = self._day_start_ms()
        cache_key = (
            self.data.get("current_challenge_id"), ctype, target, start_ms)
        cached = self._challenge_progress_cache
        now = time.monotonic()
        # render_widgets_html() and get_celebration_events() ask for the same
        # value back-to-back during one dashboard render. Coalesce only that
        # tiny burst; review boundaries explicitly invalidate the cache.
        if cached and cached[0] == cache_key and now - cached[1] <= 0.5:
            return cached[2]
        try:
            if ctype == "reviews":
                current = mw.col.db.scalar(
                    "SELECT COUNT(*) FROM revlog WHERE id >= ? AND ease > 0", start_ms) or 0
            elif ctype == "new_cards":
                # Cards that had a learning-step review today (revlog type 0).
                current = mw.col.db.scalar(
                    "SELECT COUNT(DISTINCT cid) FROM revlog WHERE id >= ? AND type = 0",
                    start_ms) or 0
            elif ctype == "study_time":
                total_ms = mw.col.db.scalar(
                    "SELECT SUM(time) FROM revlog WHERE id >= ?", start_ms) or 0
                current = int(total_ms / 60000)
            elif ctype == "decks":
                current = mw.col.db.scalar(
                    "SELECT COUNT(DISTINCT c.did) FROM revlog r "
                    "JOIN cards c ON r.cid = c.id WHERE r.id >= ?", start_ms) or 0
            else:
                current = 0
        except Exception as e:
            print(f"{ADDON_NAME}: challenge progress query error: {e}")
            current = 0
        result = (min(int(current), target), target)
        self._challenge_progress_cache = (cache_key, now, result)
        return result

    def invalidate_dashboard_cache(self) -> None:
        """Invalidate values that may have changed during a review session."""
        self._streak_cache = None
        self._challenge_progress_cache = None

    def refresh_streak_cache(self, persist: bool = False) -> int:
        """Recalculate the streak once and optionally persist it for restarts."""
        streak = calculate_streak_from_revlog()
        self._streak_cache = streak
        if self.data.get("streak") != streak:
            self.data["streak"] = streak
            if persist:
                self.save_data()
        return streak

    def is_challenge_achieved(self) -> bool:
        """True if today's challenge goal has actually been reached."""
        current, target = self.get_challenge_progress()
        return current >= target

    def get_daily_challenge_xp(self) -> int:
        return int(XP_FOR_DAILY_CHALLENGE_BASE + (self.get_level() * XP_FOR_DAILY_CHALLENGE_PER_LEVEL))

    def is_challenge_completed_today(self) -> bool:
        return self.data.get("challenge_completed_day", 0) == _anki_today_int()

    def on_complete_challenge(self):
        if self.is_challenge_completed_today():
            tooltip(_("Challenge already completed today!"))
            return
        # Server-side validation: XP can only be claimed once the goal is met.
        self._challenge_progress_cache = None
        current, target = self.get_challenge_progress()
        if current < target:
            tooltip(_("Challenge not completed yet ({}/{}).").format(current, target))
            return
        xp_reward = self.get_daily_challenge_xp()
        today_int = _anki_today_int()
        self.data["challenge_completed_day"] = today_int
        self.add_xp(xp_reward, "Daily Challenge")
        tooltip(_("Challenge complete! +{} XP").format(xp_reward), period=3500)
        self._force_refresh("on_complete_challenge")

    # ------------------------------------------------------------------
    # Celebration events (deck-browser popup)
    # ------------------------------------------------------------------
    def get_celebration_events(self) -> Dict[str, Any]:
        """New level-up / rank-up / challenge events since the last check.

        Compares the current state against 'celebrated_*' markers stored in
        the gamification data and advances the markers immediately, so every
        event is reported exactly once. Called by the deck-browser render
        hook; returns {} when nothing new happened.
        """
        events: Dict[str, Any] = {}
        try:
            level = self.get_level()
            rank_now = self.get_rank_info_for_level(level)
            changed = False

            cel_level = self.data.get("celebrated_level")
            cel_rank_img = self.data.get("celebrated_rank_image")
            if cel_level is None or cel_rank_img is None:
                # First run after install/update: initialise silently so the
                # user's existing level/rank doesn't trigger a popup.
                self.data["celebrated_level"] = level
                self.data["celebrated_rank_image"] = rank_now.get("image")
                self.save_data()
                return {}

            # Level-up (a lowered level, e.g. after a reset, just re-syncs).
            if level > int(cel_level):
                events["level"] = {"old": int(cel_level), "new": level}
                self.data["celebrated_level"] = level
                changed = True
            elif level < int(cel_level):
                self.data["celebrated_level"] = level
                changed = True

            # Rank-up — only celebrate an ascent, never a reset.
            if rank_now.get("image") != cel_rank_img:
                old_rank = next(
                    (r for r in RANKS if r.get("image") == cel_rank_img), None)
                if old_rank is None or rank_now["level"] > old_rank["level"]:
                    events["rank"] = {
                        "old_name":  old_rank.get("name") if old_rank else None,
                        "old_image": old_rank.get("image") if old_rank else None,
                        "new_name":  rank_now.get("name"),
                        "new_image": rank_now.get("image"),
                        "level":     level,
                    }
                self.data["celebrated_rank_image"] = rank_now.get("image")
                changed = True

            # Daily challenge achieved (independent of claiming the XP).
            today = _anki_today_int()
            if (self.is_challenge_achieved()
                    and self.data.get("challenge_celebrated_day") != today):
                text, _unused = self.get_current_challenge()
                events["challenge"] = {"text": text,
                                       "xp": self.get_daily_challenge_xp()}
                self.data["challenge_celebrated_day"] = today
                changed = True

            if changed:
                self.save_data()
        except Exception as e:
            print(f"SynapsePro: celebration event check failed: {e}")
            return {}
        return events

    def get_level(self) -> int: return self.data.get("level", 1)
    def get_streak(self) -> int:
        if self._streak_cache is None:
            return self.refresh_streak_cache(persist=False)
        return self._streak_cache

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
            elif mw.state == "review":
                # Never yank the user out of an active review (debug helpers
                # used to switch to the deck browser here). The new state is
                # picked up on the next deck-browser visit anyway.
                pass
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
        self._streak_cache = None
        self._challenge_progress_cache = None
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
            lpm.reset_plan_status(refresh=False)
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
        chall_cur, chall_target = self.get_challenge_progress()
        chall_claimed = self.is_challenge_completed_today()
        chall_achieved = chall_cur >= chall_target
        chall_progress_pct = max(
            0.0,
            min(100.0, (float(chall_cur) / max(1, chall_target)) * 100.0),
        )
        chall_xp = self.get_daily_challenge_xp()
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
                --challenge-ready: {_tint_hex(_c_light["blue"], 0.45)};
                --rank-color: var(--level-accent); --level-icon-text: #ffffff;
            }}
            body.night_mode {{
                --stat-bg: {_c_dark["surface"]}; --stat-border: {_c_dark["grey_mid"]};
                --text-color: {_c_dark["text"]}; --text-color-light: {_c_dark["text_muted"]};
                --progress-bg: {_c_dark["grey_mid"]}; --primary-blue: {_c_dark["blue_bright"]};
                --level-accent: {_c_dark["blue"]};
                --challenge-ready: {_tint_hex(_c_dark["blue_bright"], 0.35)};
            }}
            .gamewidget {{
                background-color: var(--stat-bg); border-radius: 12px; padding: 15px;
                border: 1px solid var(--stat-border); text-align: left;
                flex: 1 1 auto; min-width: 0; box-sizing: border-box;
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

        # Scale the rank title down for long names so it never bursts the box,
        # even when the neighbouring widgets leave it little room. The names
        # break into two fixed lines via <br>; what must never happen is a
        # single WORD wrapping onto a third line (e.g. "Knowledge" at level
        # 70+), so the longest word decides when to step the font down.
        rank_len = len(rank)
        rank_words = [w for w in rank.replace("<br/>", "<br>").split("<br>") if w.strip()]
        longest_word = max((len(w.strip()) for w in rank_words), default=0)
        if longest_word >= 9:
            rank_font = "0.82em"
        elif rank_len <= 16:
            rank_font = "1.05em"
        elif rank_len <= 24:
            rank_font = "0.92em"
        else:
            rank_font = "0.82em"
        rank_name_html = f'<span style="font-weight:bold; color: var(--rank-color); font-size:{rank_font}; line-height:1.2; overflow-wrap:break-word;">{rank}</span>'

        # Tooltip must not show the layout "<br>" literally.
        rank_tooltip = rank.replace("<br/>", " ").replace("<br>", " ")

        # flex-basis:max-content lets the box grow with the title (capped at
        # 280px); the flexible challenge widget gives up that space. Under
        # pressure it can still shrink back to 160px, where the title wraps.
        lvl_wid = f'''<div class="gamewidget level-widget" style="flex-direction:row; align-items:center; flex: 0 1 auto; flex-basis:max-content; min-width:160px; max-width:280px; padding:10px 15px; gap: 10px;" title="{rank_tooltip}">
                        {lvl_icon}
                        <div style="flex-grow: 1; min-width: 0;">{rank_name_html}</div>
                    </div>'''
        
        strk_wid=f'<div class="gamewidget streak-widget" style="text-align:center; flex-grow:0; flex-shrink:1; flex-basis:95px; min-width:90px;"><h5 style="{title_style_gam}">{label_streak}</h5><p style="{cont_style_gam}">{streak} {label_days}</p></div>'

        challenge_font_size = "0.9em" if len(chall_txt) <= 55 else ("0.82em" if len(chall_txt) <= 85 else "0.74em")
        challenge_text_style = f"font-size:{challenge_font_size}; color: var(--text-color); margin:5px 0 0 0; line-height:1.3; overflow-wrap:anywhere;"

        # ── Minimal status indicator (not clickable) ───────────────────────
        # grey + dark check          → goal not reached yet
        # light theme tint + white   → goal reached, XP not claimed yet
        # theme primary + white      → claimed (XP collected in the sidebar)
        if chall_claimed:
            circle_bg, check_color = "var(--primary-blue)", "#ffffff"
            status_tip = _("Completed")
        elif chall_achieved:
            circle_bg, check_color = "var(--challenge-ready)", "#ffffff"
            status_tip = _("Claim +{} XP").format(chall_xp)
        else:
            circle_bg, check_color = "var(--progress-bg)", "var(--text-color)"
            status_tip = f"{chall_cur}/{chall_target}"

        chall_indicator = (
            f'<div title="{status_tip}" style="width:22px; height:22px; border-radius:50%; '
            f'background-color: {circle_bg}; display:flex; align-items:center; '
            f'justify-content:center; flex-shrink:0; user-select:none; position:relative;">'
            f'<svg aria-hidden="true" width="26" height="26" viewBox="0 0 26 26" '
            f'style="position:absolute; width:26px; height:26px; left:-2px; top:-2px; '
            f'overflow:visible; pointer-events:none;">'
            f'<circle cx="13" cy="13" r="11.25" fill="none" '
            f'stroke="var(--stat-border)" stroke-width="1.5" opacity="0.75"/>'
            f'<circle cx="13" cy="13" r="11.25" fill="none" '
            f'stroke="var(--primary-blue)" stroke-width="1.5" stroke-linecap="round" '
            f'pathLength="100" stroke-dasharray="{chall_progress_pct:.1f} 100" '
            f'transform="rotate(-90 13 13)"/></svg>'
            f'<svg width="11" height="11" viewBox="0 0 24 24" fill="none" '
            f'stroke="{check_color}" style="stroke: {check_color};" stroke-width="3.5" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<polyline points="20 6 9 17 4 12"/></svg>'
            f'</div>'
        )

        chall_wid = f'''<div class="gamewidget challenge-widget" style="flex:1 1 300px; min-width:0; flex-direction:row; align-items:center; gap:12px;">
                          <div style="flex:1 1 auto; min-width:0;">
                            <h5 style="{title_style_gam.replace("margin:0 0 5px 0;", "margin:0;")}">{label_daily_challenge}</h5>
                            <p style="{challenge_text_style}">{chall_txt}</p>
                          </div>
                          {chall_indicator}
                        </div>'''

        xp_current_str = f"{xp_current:,}"; needed_str = "MAX" if needed == float('inf') else f"{needed:,}"; rem_xp_disp = "N/A" if needed == float('inf') else f"{rem_xp:,}";
        prog_bar_title = label_max_reached_tpl.format(xp_current_str) if needed == float('inf') else f"{xp_current_str} / {needed_str} XP"
        prog_bar=f'<div class="progress-bar-outer" style="width:100%; height:{bar_h}; background-color: var(--progress-bg); border-radius:{bar_h}; overflow:hidden; margin-top:8px;" title="{prog_bar_title}"><div class="progress-bar-inner" style="height:100%; width:{prog}%; background-color: var(--primary-blue); border-radius:{bar_h}; transition:width 0.3s ease-out;"></div></div>'

        next_lvl_wid=f'<div class="gamewidget next-level-widget" style="flex:0 1 280px; min-width:190px;"><div style="display:flex; justify-content:space-between; align-items:baseline; width:100%;"><h5 style="{title_style_gam}">{label_next_level}</h5><span style="{sec_style_gam}">{label_remaining_tpl.format(rem_xp_disp)}</span></div>{prog_bar}</div>'
        
        gamification_container_style = f""" display: flex; justify-content: center; align-items: stretch; flex-wrap: nowrap; gap: {gap}; max-width: {WIDGET_CONTAINER_MAX_WIDTH}; margin: 0 auto {margin_b} auto; padding: 0 10px; box-sizing: border-box; """
        
        html = f'<div id="gamification-widgets-container" style="{gamification_container_style}">{lvl_wid}{strk_wid}{chall_wid}{next_lvl_wid}</div>'

        return css + html
