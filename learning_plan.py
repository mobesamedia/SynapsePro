# -*- coding: utf-8 -*-

import time
import json
import traceback
import os
from typing import Dict, List, Optional, TypedDict, Literal
from datetime import date, datetime, timedelta

from aqt import mw
from aqt.utils import tooltip

try:
    from .locales import _
except ImportError:
    def _(text):  # type: ignore
        return text

ADDON_NAME_LP = "GamificationPlusDailyWidgets_StatusManager"


def _anki_today_key() -> str:
    """Return today's plan key using Anki's scheduler rollover."""
    try:
        cutoff = getattr(mw.col.sched, "day_cutoff", None)
        if cutoff is None:
            cutoff = getattr(mw.col.sched, "dayCutoff", None)
        if cutoff:
            return datetime.fromtimestamp(int(cutoff) - 86400).strftime("%Y%m%d")
        rollover = max(0, min(23, int(mw.col.conf.get("rollover", 4))))
        return (datetime.now() - timedelta(hours=rollover)).strftime("%Y%m%d")
    except Exception:
        return date.today().strftime("%Y%m%d")


PlanItemState = Literal["Not Started", "Running", "Paused", "Done"]

class PlanItemConfig(TypedDict):
    target_seconds: int

class PlanItemStatus(TypedDict):
    state: PlanItemState
    elapsed_seconds: float
    start_timestamp: Optional[float]

class LearningPlanManager:
    """
    Manages the *runtime status* (timers, progress) for the daily learning plan.
    Reads the plan *configuration* (subjects, target times) from a dedicated JSON file.
    """

    DATE_FORMAT = "%Y%m%d"

    def __init__(self, config_json_path: Optional[str]):
        """
        Initializes the status manager.

        :param config_json_path: Full path to the study_plan_config.json file.
        """
        self._config_json_path = config_json_path
        self._status: Dict[str, PlanItemStatus] = {}
        self._config_cache_key = None
        self._config_cache: Dict[str, Dict[str, PlanItemConfig]] = {}

        print(f"{ADDON_NAME_LP}: Initializing Status Manager...")
        if not self._config_json_path:
            print(f"{ADDON_NAME_LP}: ERROR - Configuration JSON path not provided during initialization.")
        else:
            self._initialize_status_for_today()
        print(f"{ADDON_NAME_LP}: Status initialized for today. Subjects: {list(self._status.keys())}")

    def _default_status(self) -> PlanItemStatus:
        """Returns the default status for a new or reset item."""
        return { "state": "Not Started", "elapsed_seconds": 0.0, "start_timestamp": None }

    def _read_config_file(self) -> Dict[str, Dict[str, PlanItemConfig]]:
        """Reads the entire configuration from the JSON file."""
        if not self._config_json_path or not os.path.exists(self._config_json_path):
            self._config_cache_key = None
            self._config_cache = {}
            return {}
        try:
            stat = os.stat(self._config_json_path)
            cache_key = (stat.st_mtime_ns, stat.st_size)
            if cache_key == self._config_cache_key:
                return self._config_cache
            with open(self._config_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                print(f"{ADDON_NAME_LP}: WARNING - Invalid format in JSON config file (expected dict). Returning empty.")
                return {}
            self._config_cache_key = cache_key
            self._config_cache = data
            return data
        except json.JSONDecodeError as e:
            print(f"{ADDON_NAME_LP}: ERROR decoding JSON config file '{self._config_json_path}': {e}")
            return {}
        except Exception as e:
            print(f"{ADDON_NAME_LP}: ERROR reading JSON config file '{self._config_json_path}': {e}")
            traceback.print_exc()
            return {}

    def _get_config_for_day(self, date_str: str) -> Dict[str, PlanItemConfig]:
        """Reads the config file and returns the plan for a specific date string.

        Defensive: the file may contain hand-edited or imported data with an
        unexpected shape. Non-dict day values / subject configs are skipped and
        target_seconds is coerced to a number, so downstream code (widgets,
        timers) can never crash on malformed config data.
        """
        full_config = self._read_config_file()
        day_config = full_config.get(date_str, {})
        if not isinstance(day_config, dict):
            print(f"{ADDON_NAME_LP}: WARNING - Plan for {date_str} has invalid format ({type(day_config).__name__}), ignoring it.")
            return {}
        clean: Dict[str, PlanItemConfig] = {}
        for subject, cfg in day_config.items():
            if not isinstance(cfg, dict):
                print(f"{ADDON_NAME_LP}: WARNING - Skipping subject '{subject}' on {date_str}: config must be an object, got {type(cfg).__name__}.")
                continue
            target = cfg.get("target_seconds", 0)
            if isinstance(target, str):
                try: target = float(target)
                except ValueError: target = 0
            if (isinstance(target, bool) or not isinstance(target, (int, float))
                    or target <= 0 or target > 86400):
                continue
            cfg = dict(cfg)
            cfg["target_seconds"] = int(target)
            subject_name = str(subject).strip()[:120]
            if subject_name:
                clean[subject_name] = cfg
        return clean

    def _initialize_status_for_today(self):
        """Initializes the status dict based on the plan for *today* read from the JSON file."""
        if not self._config_json_path:
             print(f"{ADDON_NAME_LP}: Cannot initialize status, config path missing.")
             self._status = {}
             return

        today_str = _anki_today_key()
        print(f"{ADDON_NAME_LP}: Initializing status for date: {today_str} from JSON: {self._config_json_path}")

        todays_plan_config = self._get_config_for_day(today_str)
        print(f"{ADDON_NAME_LP}: Config read for today: {todays_plan_config}")

        new_status: Dict[str, PlanItemStatus] = {}
        for subject in todays_plan_config.keys():
            print(f"{ADDON_NAME_LP}:   -> Setting default status for subject: {subject}")
            new_status[subject] = self._default_status()

        self._status = new_status
        print(f"{ADDON_NAME_LP}: Status initialized for {len(self._status)} subjects today. Status keys: {list(self._status.keys())}")

    def get_plan_for_display(self) -> List[Dict]:
        """
        Prepares the learning plan data *for the current day* for display.
        Reads the configuration from the JSON file and merges it with the current runtime status.
        """
        if not self._config_json_path:
             print(f"{ADDON_NAME_LP} WARN: Cannot get plan for display, config path missing.")
             return []

        today_str = _anki_today_key()
        

        todays_plan_config = self._get_config_for_day(today_str)
        
        display_list = []
        sorted_subjects = sorted(todays_plan_config.keys())

        for subject in sorted_subjects:
            config = todays_plan_config.get(subject)
            status = self._status.get(subject)

            if not config:
                 continue

            target_seconds = config.get("target_seconds", 0)

            if not status:
                 status = self._default_status()

            current_elapsed = status["elapsed_seconds"]
            if status["state"] == "Running" and status["start_timestamp"]:
                 try:
                    max_reasonable_elapsed_since_start = 24 * 3600
                    elapsed_since_start = min(time.time() - status["start_timestamp"], max_reasonable_elapsed_since_start)
                    if elapsed_since_start > 0:
                        current_elapsed += elapsed_since_start
                 except TypeError:
                      print(f"{ADDON_NAME_LP}: WARN - TypeError calculating elapsed time for '{subject}'. Start timestamp might be None.")

            effective_state = status["state"]
            if effective_state != "Done" and target_seconds > 0 and current_elapsed >= target_seconds:
                effective_state = "Done"
                current_elapsed = float(target_seconds)
                if status["state"] != "Done":
                    self._update_subject_status(subject, {
                        "state": "Done",
                        "elapsed_seconds": current_elapsed,
                        "start_timestamp": None
                    })

            item_to_display = {
                "subject": subject,
                "target_seconds": target_seconds,
                "state": effective_state,
                "elapsed_seconds": current_elapsed,
                "start_timestamp": status["start_timestamp"]
            }
            display_list.append(item_to_display)
        
        return display_list

    def _update_subject_status(self, subject: str, updates: Dict):
        """Updates the in-memory status for a given subject."""
        if subject not in self._status:
            print(f"{ADDON_NAME_LP}: WARN - Subject '{subject}' not found in today's status during update. Initializing default.")
            self._status[subject] = self._default_status()

        current_status = self._status[subject]
        new_status_data = current_status.copy()
        new_status_data.update(updates)

        if "elapsed_seconds" in new_status_data:
            try:
                new_status_data["elapsed_seconds"] = float(new_status_data["elapsed_seconds"])
            except (ValueError, TypeError):
                print(f"{ADDON_NAME_LP}: ERROR converting elapsed_seconds to float for '{subject}'. Keeping old value.")
                new_status_data["elapsed_seconds"] = current_status["elapsed_seconds"]

        self._status[subject] = new_status_data

    def start_timer(self, subject: str):
        """Starts the timer for a subject by updating its status."""
        today_str = _anki_today_key()
        todays_plan_config = self._get_config_for_day(today_str)
        if subject not in todays_plan_config:
            print(f"{ADDON_NAME_LP}: ERROR - Cannot start timer for subject '{subject}', not in today's plan (JSON).")
            tooltip(_("Cannot start timer: '{}' not planned for today.").format(subject))
            return

        status = self._status.get(subject, self._default_status())
        if status["state"] not in ["Done", "Running"]:
            print(f"{ADDON_NAME_LP}: Starting timer for '{subject}' (Today)")
            self._update_subject_status(subject, {"state": "Running", "start_timestamp": time.time()})
        elif status["state"] == "Done":
             tooltip(_("'{}' is already completed.").format(subject))
        elif status["state"] == "Running":
             tooltip(_("Timer for '{}' is already running.").format(subject))


    def pause_timer(self, subject: str):
        """Pauses the timer for a subject by updating its status."""
        today_str = _anki_today_key()
        todays_plan_config = self._get_config_for_day(today_str)
        if subject not in todays_plan_config:
            print(f"{ADDON_NAME_LP}: ERROR - Cannot pause timer for subject '{subject}', not in today's plan (JSON).")
            tooltip(_("Cannot pause timer: '{}' not planned for today.").format(subject))
            return

        status = self._status.get(subject)
        if not status:
            print(f"{ADDON_NAME_LP}: ERROR - Cannot pause timer for subject '{subject}', status not found.")
            tooltip(_("Error: Status for '{}' not found.").format(subject))
            return

        if status["state"] == "Running" and status["start_timestamp"]:
            print(f"{ADDON_NAME_LP}: Pausing timer for '{subject}' (Today)")
            elapsed_since_start = time.time() - status["start_timestamp"]
            new_total_elapsed = status["elapsed_seconds"] + max(0, elapsed_since_start)
            target_seconds = todays_plan_config[subject].get("target_seconds", 0)
            new_state: PlanItemState = "Paused"
            if target_seconds > 0 and new_total_elapsed >= target_seconds:
                new_state = "Done"
                new_total_elapsed = float(target_seconds)
                print(f"{ADDON_NAME_LP}: Subject '{subject}' marked as Done upon pausing (Today).")

            self._update_subject_status(subject, {
                "state": new_state,
                "elapsed_seconds": new_total_elapsed,
                "start_timestamp": None
            })
        elif status["state"] == "Paused":
            tooltip(_("Timer for '{}' is already paused.").format(subject))
        elif status["state"] == "Done":
            tooltip(_("'{}' is already completed.").format(subject))
        else:
            tooltip(_("Timer for '{}' has not been started yet.").format(subject))


    def mark_done(self, subject: str):
         """Marks a subject as done manually."""
         today_str = _anki_today_key()
         todays_plan_config = self._get_config_for_day(today_str)
         if subject not in todays_plan_config:
             print(f"{ADDON_NAME_LP}: ERROR - Cannot mark done subject '{subject}', not in today's plan (JSON).")
             tooltip(_("Cannot mark done: '{}' not planned for today.").format(subject))
             return

         status = self._status.get(subject, self._default_status())
         if status["state"] != "Done":
             print(f"{ADDON_NAME_LP}: Marking '{subject}' as done manually (Today).")
             target_seconds = todays_plan_config[subject].get("target_seconds", 0)
             self._update_subject_status(subject, {
                 "state": "Done",
                 "elapsed_seconds": float(target_seconds),
                 "start_timestamp": None
             })
         else:
             tooltip(_("'{}' is already marked as done.").format(subject))

    def set_subject_done(self, subject: str, done: bool):
        """Set or clear the completed state for one subject in today's plan."""
        today_str = _anki_today_key()
        todays_plan_config = self._get_config_for_day(today_str)
        if subject not in todays_plan_config:
            tooltip(_("Cannot mark done: '{}' not planned for today.").format(subject))
            return
        if done:
            target_seconds = todays_plan_config[subject].get("target_seconds", 0)
            self._update_subject_status(subject, {
                "state": "Done",
                "elapsed_seconds": float(target_seconds),
                "start_timestamp": None,
            })
        else:
            self._update_subject_status(subject, self._default_status())


    def reset_plan_status(self, refresh: bool = True):
        """Resets the status *only for today's planned items* based on the JSON config."""
        print(f"{ADDON_NAME_LP}: Resetting status for today's plan items (reading from JSON).")
        self._initialize_status_for_today()
        if refresh and hasattr(mw, 'gamification_manager') and mw.gamification_manager:
             mw.gamification_manager._force_refresh("lpm_reset_plan_status")
