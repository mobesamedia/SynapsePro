# -*- coding: utf-8 -*-

import os
import base64
import traceback
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, TYPE_CHECKING

# --- Anki/Qt Imports ---
from aqt import mw
from aqt.qt import QWidget, QDate, Qt
from aqt.utils import tooltip, showInfo

# --- Relative Addon Imports ---
try:
    from . import get_addon_config_dir_path, ADDON_NAME
except ImportError:
    print("deadline_bar.py: WARN - Could not import get_addon_config_dir_path or ADDON_NAME from __init__.py")
    def get_addon_config_dir_path() -> Optional[str]:
        print("deadline_bar.py: Using fallback get_addon_config_dir_path")
        if mw and hasattr(mw, 'addonManager'):
             try:
                  addon_package_name = mw.addonManager.addonFromModule(__name__)
                  if addon_package_name:
                       return os.path.join(mw.addonManager.addonsFolder(), addon_package_name)
             except Exception: pass
        return None
    ADDON_NAME = "GamificationPlusDailyWidgets_DeadlineBar"

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
    def _palette(night): return {"blue": "#0071D3", "blue_bright": "#40A8FF" if night else "#007AFF", "surface": "#ffffff", "grey_light": "#e0e0e0"}  # type: ignore
    _FONT_FAMILY = "sans-serif"

if TYPE_CHECKING:
    pass

# --- Konstanten ---
DEADLINE_CONFIG_KEY = f"addon_{ADDON_NAME}_deadline_data"
DEADLINE_ICON_FILENAME = "deadline.svg"
DEADLINE_BAR_MAX_WIDTH = "860px"


# ---------------------------------------------------------------------------
# DeadlineManager
# ---------------------------------------------------------------------------

class DeadlineManager:
    DATE_FORMAT = "%Y-%m-%d"

    def __init__(self):
        self._config_dir_path: Optional[str] = get_addon_config_dir_path()
        self.data: Dict = self._default_data()
        self.load_data()
        self.svg_icon_base64: Optional[str] = self._load_svg_icon()

    # ── Defaults & Migration ────────────────────────────────────────────────

    def _default_data(self) -> Dict:
        return {
            "deadlines": [],
            "pinned_id": None,
            "enabled": True,
        }

    def _migrate_old_format(self, conf: dict) -> dict:
        """Convert single-deadline format (pre-multi) to list format."""
        if "title" in conf or "start_date" in conf:
            deadline = {
                "id": str(uuid.uuid4())[:8],
                "name": conf.get("title", _("My Deadline")),
                "start_date": conf.get("start_date", date.today().strftime(self.DATE_FORMAT)),
                "end_date": conf.get("end_date", (date.today() + timedelta(days=7)).strftime(self.DATE_FORMAT)),
            }
            return {
                "deadlines": [deadline],
                "pinned_id": None,
                "enabled": conf.get("enabled", True),
            }
        return conf

    # ── SVG Icon ────────────────────────────────────────────────────────────

    def _load_svg_icon(self) -> Optional[str]:
        if not self._config_dir_path:
            return self._fallback_svg_icon()
        icon_path = os.path.join(self._config_dir_path, "images", DEADLINE_ICON_FILENAME)
        if os.path.exists(icon_path):
            try:
                with open(icon_path, "rb") as f:
                    svg_bytes = f.read()
                encoded = base64.b64encode(svg_bytes).decode("utf-8")
                return f"data:image/svg+xml;base64,{encoded}"
            except Exception as e:
                print(f"{ADDON_NAME} (Deadline): ERROR reading SVG: {e}")
        return self._fallback_svg_icon()

    def _fallback_svg_icon(self) -> str:
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">'
               '<path d="M8 16A8 8 0 1 0 8 0a8 8 0 0 0 0 16M8 12.5a.5.5 0 0 1-.5-.5v-4a.5.5 0 0 1 1 0v4'
               'a.5.5 0 0 1-.5-.5M8 8a.5.5 0 1 1 0-1 .5.5 0 0 1 0 1"/></svg>')
        try:
            return f"data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}"
        except Exception:
            return ""

    # ── Persistence ─────────────────────────────────────────────────────────

    def load_data(self):
        if not mw or not mw.col:
            self.data = self._default_data()
            return
        conf = mw.col.conf.get(DEADLINE_CONFIG_KEY)
        if conf and isinstance(conf, dict):
            conf = self._migrate_old_format(conf)
            merged = self._default_data()
            merged.update(conf)
            self.data = merged
        else:
            self.data = self._default_data()
            if conf is None:
                self.save_data()

    def save_data(self):
        if mw and mw.col:
            try:
                mw.col.conf[DEADLINE_CONFIG_KEY] = self.data
            except Exception as e:
                print(f"{ADDON_NAME} (Deadline): ERROR saving: {e}")
                traceback.print_exc()
        else:
            print(f"{ADDON_NAME} (Deadline): WARN - Cannot save, mw.col not available.")

    # ── Multi-Deadline CRUD ─────────────────────────────────────────────────

    def get_all_deadlines(self) -> List[Dict]:
        """Return deadlines sorted by end_date ascending."""
        deadlines = self.data.get("deadlines", [])
        try:
            return sorted(deadlines, key=lambda d: d.get("end_date", "9999-12-31"))
        except Exception:
            return list(deadlines)

    def add_deadline(self, name: str, start_date: str, end_date: str) -> Dict:
        entry = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "start_date": start_date,
            "end_date": end_date,
        }
        self.data.setdefault("deadlines", []).append(entry)
        self.save_data()
        return entry

    def remove_deadline(self, deadline_id: str):
        self.data["deadlines"] = [
            d for d in self.data.get("deadlines", []) if d.get("id") != deadline_id
        ]
        if self.data.get("pinned_id") == deadline_id:
            self.data["pinned_id"] = None
        self.save_data()

    def set_pinned(self, deadline_id: Optional[str]):
        """Pin a specific deadline (None = auto-select nearest upcoming)."""
        self.data["pinned_id"] = deadline_id
        self.save_data()

    def get_active_deadline(self) -> Optional[Dict]:
        """Return pinned deadline, or nearest upcoming, or most recent past."""
        deadlines = self.get_all_deadlines()
        if not deadlines:
            return None

        pinned_id = self.data.get("pinned_id")
        if pinned_id:
            for d in deadlines:
                if d.get("id") == pinned_id:
                    return d
            # Pinned ID no longer exists — fall through to auto
            self.data["pinned_id"] = None

        # Auto: nearest upcoming (end_date >= today)
        today = date.today()
        upcoming = []
        for d in deadlines:
            try:
                if datetime.strptime(d["end_date"], self.DATE_FORMAT).date() >= today:
                    upcoming.append(d)
            except Exception:
                pass
        if upcoming:
            return upcoming[0]  # sorted by end_date, so first = nearest
        return deadlines[-1]   # all past → show most recent

    def cycle_deadline(self, direction: int):
        """Advance active deadline by +1 or -1 through the sorted list."""
        deadlines = self.get_all_deadlines()
        if len(deadlines) <= 1:
            return
        active = self.get_active_deadline()
        ids = [d["id"] for d in deadlines]
        try:
            current_index = ids.index(active["id"]) if active else 0
        except ValueError:
            current_index = 0
        new_index = (current_index + direction) % len(deadlines)
        self.set_pinned(deadlines[new_index]["id"])

    # ── Progress Calculation ─────────────────────────────────────────────────

    def get_deadline_info(self) -> Optional[Dict]:
        if not self.data.get("enabled", False):
            return None
        return self.get_active_deadline()

    def calculate_progress(self) -> Optional[Dict]:
        info = self.get_deadline_info()
        if not info:
            return None
        try:
            today = date.today()
            start = datetime.strptime(info["start_date"], self.DATE_FORMAT).date()
            end   = datetime.strptime(info["end_date"],   self.DATE_FORMAT).date()
            title_display = info.get("name") or _("Deadline")

            if start > end:
                return {"title": _("Deadline Error"), "progress": 0,
                        "tooltip": _("Error: Start date is after end date")}

            total_days   = (end - start).days
            elapsed_days = (today - start).days

            if today < start:
                progress      = 0
                days_remaining = (end - today).days
                start_delta   = (start - today).days
                tip = _("{} | Starts in {} day(s) | Ends in {} day(s)").format(
                    title_display, start_delta, days_remaining)
            elif today > end:
                progress      = 100
                days_remaining = 0
                end_delta     = (today - end).days
                tip = _("{} | Ended {} day(s) ago").format(title_display, end_delta)
            else:
                days_remaining = (end - today).days
                if total_days <= 0:
                    progress = 100 if today >= start else 0
                else:
                    progress = max(0, min(100, int((max(0, elapsed_days) / total_days) * 100)))
                tip = _("{} | {} day(s) remaining").format(title_display, days_remaining)

            return {
                "title": title_display, "progress": progress,
                "tooltip": tip, "days_remaining": days_remaining,
                "deadline_id": info.get("id"),
            }
        except (ValueError, TypeError, KeyError) as e:
            return {"title": _("Deadline Error"), "progress": 0,
                    "tooltip": _("Error: Invalid date configuration ({})").format(e)}
        except Exception as e:
            traceback.print_exc()
            return {"title": _("Deadline Error"), "progress": 0,
                    "tooltip": _("Error: {}").format(e)}

    # ── HTML Rendering ───────────────────────────────────────────────────────

    def get_icon_html_for_deck_browser(self) -> str:
        """Deadline icon — clicking opens the DeadlineViewerDialog via pycmd."""
        icon_style = ("flex-shrink: 0; width: 24px; height: 24px; opacity: 0.7; "
                      "transition: opacity 0.2s ease; cursor: pointer;")
        tip = _("View Deadlines")
        onclick = "pycmd('pycmd:synapsepro:deadline_viewer')"
        if self.svg_icon_base64:
            return (f'<img src="{self.svg_icon_base64}" style="{icon_style}" title="{tip}" '
                    f'onclick="{onclick}" onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.7">')
        return (f'<span style="{icon_style} font-size:18px;" title="{tip}" onclick="{onclick}" '
                f'onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.7">📋</span>')

    def render_deadline_bar_html(self) -> str:
        """Full HTML + CSS for the deadline bar, including multi-deadline navigation."""
        progress_data = self.calculate_progress()
        if not progress_data:
            return ""

        progress       = progress_data.get("progress", 0)
        tooltip_text   = progress_data.get("tooltip", "")
        days_remaining = progress_data.get("days_remaining")
        title          = progress_data.get("title", "")
        config_icon    = self.get_icon_html_for_deck_browser()

        _cl = _palette(False)
        _cd = _palette(True)
        _c  = _palette(is_night_mode)
        lighter_blue = _c.get("blue_bright", "#40A8FF")

        # Show "next →" only when there are multiple deadlines
        deadlines = self.get_all_deadlines()
        show_nav  = len(deadlines) > 1

        nav_html = ""
        if show_nav:
            nav_html = (
                f'<button onclick="pycmd(\'pycmd:synapsepro:deadline_next\')" '
                f'title="{_("Next deadline")}" '
                f'style="background:none;border:none;cursor:pointer;font-size:16px;'
                f'color:#aaa;padding:0 2px;line-height:1;flex-shrink:0;">&#8250;</button>'
            )

        css = f"""
        <style>
            :root {{
                --stat-bg: {_cl["surface"]};
                --stat-border: {_cl["grey_light"]};
                --progress-bg: {_cl["grey_light"]};
                --deadline-fill-color: {_cl["blue"]};
            }}
            body.night_mode {{
                --stat-bg: {_cd["surface"]};
                --stat-border: {_cd.get("grey_mid", "#444")};
                --progress-bg: {_cd.get("grey_mid", "#444")};
                --deadline-fill-color: {_cd["blue"]};
            }}
            .deadline-bar-container {{
                display: flex;
                align-items: center;
                gap: 8px;
                background-color: var(--stat-bg);
                border-radius: 12px;
                padding: 10px 16px;
                margin: 0px auto 15px;
                max-width: {DEADLINE_BAR_MAX_WIDTH};
                border: 1px solid var(--stat-border);
                box-sizing: border-box;
            }}
            body.night_mode .deadline-bar-container {{
                border: 1px solid {_cd.get("grey_mid", "#444")};
            }}
            .deadline-title-label {{
                font-size: 12px;
                font-weight: 600;
                color: #888;
                white-space: nowrap;
                flex-shrink: 0;
                max-width: 140px;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .deadline-progress-bg {{
                flex-grow: 1;
                height: 12px;
                background-color: var(--progress-bg);
                border-radius: 6px;
                overflow: hidden;
                text-align: left;
            }}
            .deadline-progress-fill {{
                height: 100%;
                border-radius: 6px;
                transition: width 0.3s ease-in-out;
                background-image: linear-gradient(
                    90deg,
                    var(--deadline-fill-color),
                    {lighter_blue}
                );
            }}
            .deadline-days-label {{
                font-size: 12px;
                color: #888;
                white-space: nowrap;
                flex-shrink: 0;
                line-height: 1;
            }}
        </style>"""

        days_label_html = ""
        if days_remaining is not None:
            days_label_html = f'<span class="deadline-days-label">{days_remaining} {_("Days")}</span>'

        html = f"""
        <div class="deadline-bar-container" title="{tooltip_text}">
            <span class="deadline-title-label">{title}</span>
            {nav_html}
            <div class="deadline-progress-bg">
                <div class="deadline-progress-fill" style="width: {progress}%;"></div>
            </div>
            {days_label_html}
            {config_icon}
        </div>"""

        return css + html
