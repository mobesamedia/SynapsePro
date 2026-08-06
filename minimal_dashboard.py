# -*- coding: utf-8 -*-
"""Compact, single-card renderer for the optional minimal home dashboard."""

from __future__ import annotations

import html
import time
from typing import Any, Optional

from .locales import _
from .theme import palette
from . import statistics_widget


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _percent(value: Any) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _day_label(days: int) -> str:
    template = _("{} Day") if days == 1 else _("{} Days")
    return template.format(days)


def _study_plan_snapshot(manager: Optional[Any]) -> tuple[list[dict], int, int, float]:
    if not manager:
        return [], 0, 0, 0.0
    try:
        plan = manager.get_plan_for_display() or []
    except Exception:
        return [], 0, 0, 0.0

    total = len(plan)
    done = sum(1 for item in plan if item.get("state") == "Done")
    target_seconds = sum(max(0, _int(item.get("target_seconds"))) for item in plan)
    elapsed_seconds = sum(
        min(
            max(0, _int(item.get("elapsed_seconds"))),
            max(0, _int(item.get("target_seconds"))),
        )
        for item in plan
    )
    if target_seconds > 0:
        progress = (elapsed_seconds / target_seconds) * 100.0
    elif total > 0:
        progress = (done / total) * 100.0
    else:
        progress = 0.0
    return plan, done, total, _percent(progress)


def _number_size_class(value: Any) -> str:
    digits = len(str(abs(_int(value))))
    if digits >= 6:
        return " sp-min-number-6"
    if digits >= 5:
        return " sp-min-number-5"
    if digits >= 4:
        return " sp-min-number-4"
    return ""


def _format_plan_countdown(seconds: int) -> str:
    seconds = max(0, _int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}min"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def render_minimal_dashboard_sections(
    gamification_manager: Optional[Any],
    learning_plan_manager: Optional[Any],
    deadline_manager: Optional[Any],
    stats_days: int = 7,
    fact_theme: str = "Medical",
    daily_fact_html: str = "",
) -> tuple[str, str]:
    """Return the compact overview (above decks) and statistics (below decks)."""
    level = streak = challenge_current = 0
    challenge_target = 1
    next_level_progress = 0.0
    remaining_xp = 0

    if gamification_manager:
        try:
            level = max(1, _int(gamification_manager.get_level(), 1))
            streak = max(0, _int(gamification_manager.get_streak()))
            challenge_current, challenge_target = gamification_manager.get_challenge_progress()
            challenge_current = max(0, _int(challenge_current))
            challenge_target = max(1, _int(challenge_target, 1))
            next_level_progress = _percent(gamification_manager.get_progress_percentage())
            remaining_xp = max(0, _int(gamification_manager.get_remaining_xp()))
        except Exception as exc:
            print(f"SynapsePro: minimal gamification render error: {exc}")

    challenge_progress = _percent(
        (challenge_current / max(1, challenge_target)) * 100.0
    )
    challenge_done = challenge_current >= challenge_target

    plan_items, plan_done, plan_total, plan_progress = _study_plan_snapshot(
        learning_plan_manager
    )
    ordered_plan = sorted(
        plan_items,
        key=lambda item: 0 if item.get("state") == "Running" else 1,
    )
    running_item = next(
        (item for item in ordered_plan if item.get("state") == "Running"),
        None,
    )
    timer_remaining = 0
    if running_item:
        timer_remaining = max(
            0,
            _int(running_item.get("target_seconds"))
            - _int(running_item.get("elapsed_seconds")),
        )

    deadline_title = _("Deadline")
    deadline_days = "—"
    deadline_progress = 0.0
    deadline_tooltip = ""
    deadline_has_multiple = False
    if deadline_manager:
        try:
            deadline_has_multiple = len(deadline_manager.get_all_deadlines()) > 1
            deadline = deadline_manager.calculate_progress()
            if deadline:
                deadline_title = deadline.get("title") or _("Deadline")
                days_remaining = deadline.get("days_remaining")
                if days_remaining is not None:
                    deadline_days = _day_label(max(0, _int(days_remaining)))
                deadline_progress = _percent(deadline.get("progress", 0))
                deadline_tooltip = deadline.get("tooltip") or deadline_title
        except Exception as exc:
            print(f"SynapsePro: minimal deadline render error: {exc}")

    try:
        stats = statistics_widget.get_minimal_statistics_data(
            max(1, _int(stats_days, 7))
        )
        chart_html = stats.get("chart_html", "")
        retention = _percent(stats.get("retention_percent", 0))
        new_cards = _percent(stats.get("new_cards_percent", 0))
    except Exception as exc:
        print(f"SynapsePro: minimal statistics render error: {exc}")
        chart_html = ""
        retention = 0.0
        new_cards = 0.0

    light = palette(False)
    dark = palette(True)
    shared = f"""
    <style>
      :root {{
        --sp-min-surface: {light['surface']};
        --sp-min-border: {light['grey_light']};
        --sp-min-muted: {light['text_muted']};
        --sp-min-text: {light['text']};
        --sp-min-track: {light['grey_light']};
        --sp-min-accent: {light['blue']};
        --sp-min-deadline-start: {light['blue']};
        --sp-min-deadline-end: {light['blue_bright']};
        --sp-min-accent-hover: {light['blue_hover']};
        --sp-min-success: {light['green']};
        --main-blue: {light['blue']};
        --gray: {light['grey_light']};
        --stat-bg: {light['surface']};
        --stat-border: {light['grey_light']};
        --text-color: {light['text']};
        --text-color-light: {light['text_muted']};
      }}
      body.night_mode, body.nightMode {{
        --sp-min-surface: {dark['surface']};
        --sp-min-border: {dark['grey_mid']};
        --sp-min-muted: {dark['text_muted']};
        --sp-min-text: {dark['text']};
        --sp-min-track: {dark['grey_mid']};
        --sp-min-accent: {dark['blue_bright']};
        --sp-min-deadline-start: {dark['blue']};
        --sp-min-deadline-end: {dark['blue_bright']};
        --sp-min-accent-hover: {dark['blue']};
        --sp-min-success: {dark['green']};
        --main-blue: {dark['blue_bright']};
        --gray: {dark['grey_mid']};
        --stat-bg: {dark['surface']};
        --stat-border: {dark['grey_mid']};
        --text-color: {dark['text']};
        --text-color-light: {dark['text_muted']};
      }}
      .sp-min-box {{
        width: min(760px, calc(100% - 24px)); max-width: calc(100vw - 24px);
        margin-left: auto; margin-right: auto; padding: 14px 16px;
        box-sizing: border-box; border: 1px solid var(--sp-min-border);
        border-radius: 12px;
        background: var(--sp-min-surface); color: var(--sp-min-text);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      }}
      .sp-min-overview {{ margin-top: 3px; margin-bottom: 7px; padding: 8px 10px; }}
      .sp-min-deadline-box {{
        min-height: 32px; margin-bottom: 12px; padding: 4px 10px;
        display: grid; grid-template-columns: minmax(58px, auto) 14px minmax(90px, 1fr) auto;
        align-items: center; gap: 7px; cursor: pointer; user-select: none;
      }}
      .sp-min-deadline-box.sp-min-deadline-no-nav {{
        grid-template-columns: minmax(58px, auto) minmax(90px, 1fr) auto;
      }}
      .sp-min-statistics {{
        margin-top: 16px; margin-bottom: 12px; display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(144px, 156px); align-items: stretch; gap: 8px;
        cursor: pointer;
      }}
      .sp-min-primary {{
        display: grid; grid-template-columns: .82fr .70fr 1.65fr 2fr;
        align-items: stretch; gap: 7px;
      }}
      .sp-min-metric-card {{
        min-width: 0; height: 52px; padding: 5px 9px;
        box-sizing: border-box; display: flex; flex-direction: column;
        justify-content: center; border: 1px solid var(--sp-min-border); border-radius: 8px;
      }}
      .sp-min-interactive {{
        cursor: pointer; user-select: none;
        transition: border-color .15s ease, background .15s ease;
      }}
      .sp-min-interactive:hover, .sp-min-interactive:focus-visible {{
        outline: none; border-color: var(--sp-min-accent);
        background: color-mix(in srgb, var(--sp-min-accent) 6%, transparent);
      }}
      .sp-min-primary:hover .sp-min-metric-card,
      .sp-min-primary:has(.sp-min-metric-card:focus-visible) .sp-min-metric-card {{
        border-color: var(--sp-min-accent);
        background: color-mix(in srgb, var(--sp-min-accent) 6%, transparent);
      }}
      .sp-min-statistics:hover > .sp-min-chart,
      .sp-min-statistics:hover > .sp-min-circle-group,
      .sp-min-statistics:focus-visible > .sp-min-chart,
      .sp-min-statistics:focus-visible > .sp-min-circle-group {{
        border-color: var(--sp-min-accent);
        background: color-mix(in srgb, var(--sp-min-accent) 6%, transparent);
      }}
      .sp-min-statistics:focus-visible {{ outline: none; }}
      .sp-min-label {{
        color: var(--sp-min-muted); font-size: 10.5px; font-weight: 650;
        line-height: 1.2; margin-bottom: 5px; white-space: nowrap;
        overflow: hidden; text-overflow: ellipsis;
      }}
      .sp-min-value {{ font-size: 17px; font-weight: 700; line-height: 1.2; }}
      .sp-min-value-small {{ font-size: 12.5px; font-weight: 650; }}
      .sp-min-metric-card .sp-min-label {{ font-size: 10px; line-height: 1.15; margin-bottom: 3px; }}
      .sp-min-simple-metric {{ align-items: center; text-align: center; }}
      .sp-min-simple-metric .sp-min-label {{ margin-bottom: 3px; }}
      .sp-min-level-badge {{
        max-width: 100%; min-width: 42px; padding: 3px 6px;
        box-sizing: border-box; border-radius: 999px;
        color: white; background: var(--sp-min-accent);
        font-size: 13px; font-weight: 750; line-height: 1;
        font-variant-numeric: tabular-nums;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }}
      .sp-min-streak-value {{
        max-width: 100%; font-size: 13px; font-weight: 750; line-height: 1;
        font-variant-numeric: tabular-nums;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }}
      .sp-min-number-4 {{ font-size: 12px !important; }}
      .sp-min-number-5 {{ font-size: 11px !important; }}
      .sp-min-number-6 {{ font-size: 10px !important; }}
      .sp-min-metric-head {{
        min-width: 0; display: flex; align-items: baseline;
        justify-content: space-between; gap: 6px; margin-bottom: 4px;
      }}
      .sp-min-metric-title {{
        min-width: 0; color: var(--sp-min-muted); font-size: 10px; font-weight: 650;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }}
      .sp-min-metric-count {{
        flex: none; color: var(--sp-min-text); font-size: 10px; font-weight: 650;
        font-variant-numeric: tabular-nums; white-space: nowrap;
      }}
      .sp-min-challenge-count {{ font-size: 10px; }}
      .sp-min-progress-row {{ display: grid; grid-template-columns: minmax(0,1fr); align-items: center; }}
      .sp-min-deadline-box .sp-min-track {{
        height: 8px !important; min-height: 8px !important; margin: 0 !important;
      }}
      .sp-min-deadline-box .sp-min-fill {{
        background: linear-gradient(90deg, var(--sp-min-deadline-start), var(--sp-min-deadline-end)) !important;
      }}
      .sp-min-deadline-box:hover .sp-min-track,
      .sp-min-deadline-box:focus-visible .sp-min-track {{ background: #fff !important; }}
      .sp-min-track {{
        position: relative !important; display: block !important;
        width: 100% !important; height: 5px !important;
        min-height: 5px !important; margin: 5px 0 0 !important;
        padding: 0 !important; overflow: hidden !important;
        border: 0 !important; border-radius: 999px !important;
        background: var(--sp-min-track) !important;
      }}
      .sp-min-fill {{
        position: absolute !important; display: block !important;
        left: 0 !important; right: auto !important; top: 0 !important; bottom: 0 !important;
        width: var(--sp-min-progress, 0%) !important; height: 100% !important;
        min-width: 0 !important; margin: 0 !important; padding: 0 !important;
        border: 0 !important; border-radius: inherit !important;
        transform: none !important; background: var(--sp-min-accent) !important;
      }}
      .sp-min-challenge-done .sp-min-value {{ color: var(--sp-min-success); }}
      .sp-min-plan-fact-row {{
        display: grid; grid-template-columns: minmax(0, 1fr) minmax(82px, 95px);
        gap: 7px; margin-top: 7px;
      }}
      .sp-min-study-plan {{
        min-width: 0; min-height: 34px; padding: 4px 8px; box-sizing: border-box;
        display: grid; grid-template-columns: auto auto minmax(0, 1fr) auto;
        align-items: center; gap: 7px;
        border: 1px solid var(--sp-min-border); border-radius: 7px;
      }}
      .sp-min-study-title {{
        color: var(--sp-min-text); font-size: 12px; font-weight: 750; white-space: nowrap;
      }}
      .sp-min-plan-timer {{
        padding: 3px 6px; border-radius: 999px; background: var(--sp-min-track);
        color: var(--sp-min-text); font-size: 8.5px; font-weight: 650; white-space: nowrap;
      }}
      .sp-min-subjects {{
        min-width: 0; display: flex; align-items: center; gap: 5px;
        overflow: hidden; white-space: nowrap;
      }}
      .sp-min-subject-chip {{
        min-width: 0; max-width: 110px; flex: none; padding: 4px 8px;
        box-sizing: border-box; border-radius: 6px;
        color: var(--sp-min-text); background: var(--sp-min-track);
        font-size: 10px; font-weight: 650; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }}
      .sp-min-subject-chip.sp-min-subject-running {{ color: white; background: var(--sp-min-accent); }}
      .sp-min-subject-chip.sp-min-subject-done {{ color: white; background: var(--sp-min-success); }}
      .sp-min-subject-chip.sp-min-subject-hidden {{ display: none; }}
      .sp-min-subject-empty {{
        min-width: 0; color: var(--sp-min-muted); font-size: 10px; font-weight: 500;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }}
      .sp-min-subject-more {{
        display: none; color: var(--sp-min-border); font-size: 14px;
        font-weight: 800; letter-spacing: 2px; line-height: 1; white-space: nowrap;
      }}
      .sp-min-fact-button {{
        min-height: 34px; padding: 4px 9px; box-sizing: border-box;
        display: flex; align-items: center; justify-content: center;
        border-radius: 7px; color: white; background: var(--sp-min-accent);
        font-size: 12px; font-weight: 700; text-align: center;
      }}
      .sp-min-fact-button:hover, .sp-min-fact-button:focus-visible {{
        outline: none; background: var(--sp-min-accent-hover);
      }}
      .sp-min-deadline-name {{
        min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        font-size: 10px; font-weight: 750;
      }}
      .sp-min-deadline-next {{
        color: var(--sp-min-accent); font-size: 14px; font-weight: 800; line-height: 1;
        text-align: center; cursor: pointer; border-radius: 5px;
      }}
      .sp-min-deadline-next:hover, .sp-min-deadline-next:focus-visible {{
        outline: none; background: color-mix(in srgb, var(--sp-min-accent) 10%, transparent);
      }}
      .sp-min-deadline-days {{ color: var(--sp-min-muted); font-size: 10px; white-space: nowrap; }}
      .sp-min-chart {{
        min-width: 0; min-height: 84px; padding: 8px 10px; box-sizing: border-box;
        border: 1px solid var(--sp-min-border); border-radius: 8px;
      }}
      .sp-min-chart-head {{ display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }}
      .sp-min-chart-scope {{ color: var(--sp-min-muted); font-size: 10px; white-space: nowrap; }}
      .sp-min-statistics .sp-min-label {{ font-size: 10px; }}
      .sp-min-statistics .spark {{ width: 100%; height: 45px; margin-top: 4px; display: block; }}
      .sp-min-statistics .spark line {{ display: none; }}
      .sp-min-circle-group {{
        min-width: 0; min-height: 84px; padding: 4px; box-sizing: border-box;
        display: grid; grid-template-columns: 1fr 1fr; align-items: stretch;
        border: 1px solid var(--sp-min-border); border-radius: 8px;
      }}
      .sp-min-circle-stat {{
        min-width: 0; min-height: 74px; padding: 4px 2px;
        display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px;
      }}
      .sp-min-ring {{
        --sp-min-ring-value: 0%; width: 50px; height: 50px; flex: none;
        border-radius: 50%; display: grid; place-items: center;
        background: conic-gradient(var(--sp-min-accent) var(--sp-min-ring-value), var(--sp-min-track) 0);
      }}
      .sp-min-ring::before {{
        content: ""; width: 38px; height: 38px; border-radius: 50%;
        grid-area: 1 / 1; background: var(--sp-min-surface);
      }}
      .sp-min-ring strong {{ position: relative; grid-area: 1 / 1; font-size: 13px; font-weight: 750; }}
      .sp-min-circle-title {{
        color: var(--sp-min-muted); font-size: 10px; font-weight: 650;
        line-height: 1.1; text-align: center; white-space: nowrap;
      }}
      .sp-min-fact-overlay {{
        position: fixed; inset: 0; z-index: 10000; display: none;
        align-items: center; justify-content: center; padding: 18px;
        box-sizing: border-box; background: transparent;
      }}
      .sp-min-fact-overlay.sp-min-open {{ display: flex; }}
      .sp-min-fact-dialog {{
        position: relative; width: min(720px, 100%); max-height: calc(100vh - 36px);
        overflow: auto; padding: 14px; box-sizing: border-box;
        border: 1px solid var(--sp-min-border); border-radius: 14px;
        background: var(--sp-min-surface); box-shadow: 0 18px 55px rgba(0,0,0,.28);
      }}
      .sp-min-fact-close {{
        position: sticky; z-index: 3; top: 0; margin: 0 0 6px auto;
        width: 30px; height: 30px; box-sizing: border-box; border-radius: 50%;
        display: flex; align-items: center; justify-content: center; cursor: pointer;
        color: var(--sp-min-text); background: var(--sp-min-surface);
        border: 1px solid var(--sp-min-border); font-size: 18px; font-weight: 500; line-height: 1;
      }}
      .sp-min-fact-dialog .fact-widget {{
        width: 100% !important; min-width: 0 !important; max-width: none !important;
        min-height: 0 !important; box-sizing: border-box !important;
        border: 0 !important; box-shadow: none !important;
      }}
      @media (max-width: 720px) {{
        .sp-min-primary {{ grid-template-columns: 1fr 1fr; }}
        .sp-min-metric-card {{ height: 50px; }}
      }}
      @media (max-width: 560px) {{
        .sp-min-plan-fact-row {{ grid-template-columns: 1fr; }}
        .sp-min-fact-button {{ min-height: 32px; }}
        .sp-min-study-plan {{ grid-template-columns: auto minmax(0, 1fr) auto; }}
        .sp-min-plan-timer {{ display: none; }}
      }}
      @media (max-width: 460px) {{
        .sp-min-statistics {{ grid-template-columns: 1fr; }}
        .sp-min-deadline-box {{ grid-template-columns: minmax(52px, auto) 13px minmax(64px, 1fr) auto; gap: 5px; }}
        .sp-min-deadline-box.sp-min-deadline-no-nav {{ grid-template-columns: minmax(52px, auto) minmax(64px, 1fr) auto; }}
      }}
    </style>
    <script>
      (function() {{
        function deckBox() {{
          return document.querySelector('.decks-container') ||
                 document.querySelector('body.deckbrowser > center > table') ||
                 document.querySelector('center > table');
        }}
        function syncWidth() {{
          var target = deckBox();
          if (!target) return;
          var width = Math.round(target.getBoundingClientRect().width);
          if (width < 240) return;
          width = Math.min(width, Math.max(240, window.innerWidth - 24));
          document.querySelectorAll('.sp-min-box').forEach(function(box) {{
            box.style.width = width + 'px';
          }});
        }}
        function syncStatisticsGap() {{
          var overview = document.querySelector('.sp-min-deadline-box') || document.querySelector('.sp-min-overview');
          var target = deckBox();
          var statistics = document.querySelector('.sp-min-statistics');
          if (!overview || !target || !statistics) return;
          statistics.style.transform = 'none';
          statistics.style.marginBottom = '12px';
          var upperGap = Math.max(0, target.getBoundingClientRect().top - overview.getBoundingClientRect().bottom);
          var lowerGap = statistics.getBoundingClientRect().top - target.getBoundingClientRect().bottom;
          var offset = Math.round(upperGap - lowerGap);
          if (Math.abs(offset) > 1) {{
            statistics.style.transform = 'translateY(' + offset + 'px)';
            statistics.style.marginBottom = (12 + offset) + 'px';
          }}
        }}
        function fitStudySubjects() {{
          var holder = document.querySelector('.sp-min-subjects');
          var more = document.querySelector('.sp-min-subject-more');
          if (!holder || !more) return;
          var chips = Array.prototype.slice.call(holder.querySelectorAll('.sp-min-subject-chip'));
          chips.forEach(function(chip) {{ chip.classList.remove('sp-min-subject-hidden'); }});
          more.style.display = 'none';
          if (holder.scrollWidth <= holder.clientWidth + 1) return;
          more.style.display = 'inline-block';
          for (var index = chips.length - 1; index > 0; index--) {{
            chips[index].classList.add('sp-min-subject-hidden');
            if (holder.scrollWidth <= holder.clientWidth + 1) break;
          }}
        }}
        function updateStudyTimer() {{
          var timer = document.querySelector('[data-sp-plan-remaining]');
          if (!timer) return;
          var started = parseInt(timer.getAttribute('data-sp-plan-started') || '0', 10);
          var initial = parseInt(timer.getAttribute('data-sp-plan-remaining') || '0', 10);
          var elapsed = started ? Math.floor((Date.now() - started) / 1000) : 0;
          var remaining = Math.max(0, initial - elapsed);
          var hours = Math.floor(remaining / 3600);
          var minutes = Math.floor((remaining % 3600) / 60);
          var seconds = remaining % 60;
          timer.textContent = hours
            ? hours + 'h ' + String(minutes).padStart(2, '0') + 'min'
            : (minutes ? minutes + 'm ' + String(seconds).padStart(2, '0') + 's' : seconds + 's');
        }}
        function syncLayout() {{
          syncWidth();
          requestAnimationFrame(function() {{
            fitStudySubjects();
            syncStatisticsGap();
          }});
        }}
        window.synapseOpenDailyFact = function(trigger) {{
          var modal = document.getElementById('sp-min-fact-overlay');
          if (!modal) return;
          window.__synapseFactTrigger = trigger || document.activeElement;
          modal.classList.add('sp-min-open');
          modal.setAttribute('aria-hidden', 'false');
          var trigger = document.querySelector('[data-sp-min-fact-trigger]');
          if (trigger) trigger.setAttribute('aria-expanded', 'true');
          requestAnimationFrame(function() {{
            var close = document.getElementById('sp-min-fact-close');
            if (close) close.focus();
          }});
        }};
        window.synapseCloseDailyFact = function() {{
          var modal = document.getElementById('sp-min-fact-overlay');
          if (!modal || !modal.classList.contains('sp-min-open')) return;
          modal.classList.remove('sp-min-open');
          modal.setAttribute('aria-hidden', 'true');
          var trigger = document.querySelector('[data-sp-min-fact-trigger]');
          if (trigger) trigger.setAttribute('aria-expanded', 'false');
          var previous = window.__synapseFactTrigger;
          window.__synapseFactTrigger = null;
          if (previous && previous.focus) previous.focus();
        }};
        window.synapseToggleDailyFact = function(trigger) {{
          var modal = document.getElementById('sp-min-fact-overlay');
          if (!modal) return;
          if (modal.classList.contains('sp-min-open')) window.synapseCloseDailyFact();
          else window.synapseOpenDailyFact(trigger);
        }};
        var commandTimes = {{}};
        window.synapseDashboardCommand = function(command, key) {{
          var token = key || command;
          var now = Date.now();
          if (now - (commandTimes[token] || 0) < 300) return;
          commandTimes[token] = now;
          if (window.pycmd) window.pycmd(command);
        }};
        if (!window.__synapseMinimalWidthSyncInstalled) {{
          window.__synapseMinimalWidthSyncInstalled = true;
          var observed = null;
          var resizeObserver = window.ResizeObserver ? new ResizeObserver(syncLayout) : null;
          function attach() {{
            var target = deckBox();
            if (resizeObserver && target && target !== observed) {{
              if (observed) resizeObserver.unobserve(observed);
              resizeObserver.observe(target); observed = target;
            }}
            syncLayout();
          }}
          new MutationObserver(attach).observe(document.body, {{childList:true, subtree:true}});
          window.addEventListener('resize', syncLayout);
          document.addEventListener('keydown', function(event) {{
            if (event.key === 'Escape') window.synapseCloseDailyFact();
          }});
          setInterval(updateStudyTimer, 1000);
          document.addEventListener('DOMContentLoaded', attach);
          requestAnimationFrame(attach);
          setTimeout(attach, 100);
          setTimeout(attach, 500);
          updateStudyTimer();
        }} else {{
          requestAnimationFrame(syncLayout);
        }}
      }})();
    </script>
    """

    done_class = " sp-min-challenge-done" if challenge_done else ""
    challenge_value = f"{challenge_current}/{challenge_target}"
    missing_xp_text = f"-{remaining_xp:,} XP" if remaining_xp > 0 else "0 XP"
    fact_content = daily_fact_html or f'<div style="padding:28px;color:var(--sp-min-muted);text-align:center">{_esc(_("No daily facts available."))}</div>'
    gamification_click = "window.synapseDashboardCommand('pycmd:synapsepro:gamification_viewer','gamification')"
    level_size_class = _number_size_class(level)
    streak_size_class = _number_size_class(streak)

    subject_chips = []
    for item in ordered_plan:
        state = item.get("state")
        state_class = ""
        if state == "Running":
            state_class = " sp-min-subject-running"
        elif state == "Done":
            state_class = " sp-min-subject-done"
        subject_chips.append(
            f'<span class="sp-min-subject-chip{state_class}" title="{_esc(item.get("subject") or _("Unknown Subject"))}">'
            f'{_esc(item.get("subject") or _("Unknown Subject"))}</span>'
        )
    if not subject_chips:
        subject_chips.append(
            f'<span class="sp-min-subject-empty">{_esc(_("Add subjects"))}</span>'
        )
    subjects_html = "".join(subject_chips)
    timer_html = ""
    if running_item:
        timer_html = (
            f'<span class="sp-min-plan-timer" data-sp-plan-remaining="{timer_remaining}" '
            f'data-sp-plan-started="{int(time.time() * 1000)}">'
            f'{_esc(_format_plan_countdown(timer_remaining))}</span>'
        )

    deadline_nav_class = "" if deadline_has_multiple else " sp-min-deadline-no-nav"
    deadline_nav_html = ""
    if deadline_has_multiple:
        deadline_nav_html = (
            f'<span class="sp-min-deadline-next" role="button" tabindex="0" '
            f'aria-label="{_esc(_("Next"))}" '
            'onclick="event.stopPropagation();window.synapseDashboardCommand('
            "'pycmd:synapsepro:deadline_next','deadline-next')\" "
            'onkeydown="if(event.key===\'Enter\'||event.key===\' \')'
            '{event.preventDefault();event.stopPropagation();this.click();}">›</span>'
        )

    top_markup = f"""
    <section class="sp-min-box sp-min-overview" aria-label="{_esc(_('Dashboard'))}">
      <div class="sp-min-primary">
        <div class="sp-min-metric-card sp-min-simple-metric sp-min-interactive" role="button" tabindex="0"
             onclick="{gamification_click}"
             onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();this.click();}}">
          <div class="sp-min-label">{_esc(_('Level'))}</div>
          <div class="sp-min-level-badge{level_size_class}">{level}</div>
        </div>
        <div class="sp-min-metric-card sp-min-simple-metric sp-min-interactive" role="button" tabindex="0"
             onclick="{gamification_click}"
             onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();this.click();}}">
          <div class="sp-min-label">{_esc(_('Streak'))}</div>
          <div class="sp-min-streak-value{streak_size_class}">{streak}</div>
        </div>
        <div class="sp-min-metric-card sp-min-interactive{done_class}" role="button" tabindex="0"
             onclick="{gamification_click}"
             onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();this.click();}}">
          <div class="sp-min-metric-head">
            <span class="sp-min-metric-title">{_esc(_('Daily Challenge'))}</span>
            <span class="sp-min-metric-count sp-min-challenge-count">{_esc(challenge_value)}</span>
          </div>
          <div class="sp-min-progress-row">
            <div class="sp-min-track"><i class="sp-min-fill" style="--sp-min-progress:{challenge_progress:.1f}%"></i></div>
          </div>
        </div>
        <div class="sp-min-metric-card sp-min-interactive" role="button" tabindex="0"
             onclick="{gamification_click}"
             onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();this.click();}}">
          <div class="sp-min-metric-head">
            <span class="sp-min-metric-title">{_esc(_('Next Level'))}</span>
            <span class="sp-min-metric-count">{_esc(missing_xp_text)}</span>
          </div>
          <div class="sp-min-track"><i class="sp-min-fill" style="--sp-min-progress:{next_level_progress:.1f}%"></i></div>
        </div>
      </div>

      <div class="sp-min-plan-fact-row">
        <div class="sp-min-study-plan sp-min-interactive" role="button" tabindex="0"
             onclick="window.synapseDashboardCommand('pycmd:synapsepro:study_plan_viewer','study-plan')"
             onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();this.click();}}">
          <span class="sp-min-study-title">{_esc(_('Study Plan'))}</span>
          {timer_html}
          <span class="sp-min-subjects">{subjects_html}</span>
          <span class="sp-min-subject-more" aria-label="{_esc(_('More'))}">•••</span>
        </div>
        <div class="sp-min-fact-button" role="button" tabindex="0" data-sp-min-fact-trigger aria-expanded="false"
             onclick="window.synapseToggleDailyFact(this)"
             onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();this.click();}}">
          {_esc(_('Daily Fact'))}
        </div>
      </div>
    </section>
    <section class="sp-min-box sp-min-deadline-box sp-min-interactive{deadline_nav_class}" role="button" tabindex="0"
             aria-label="{_esc(_('Deadline'))}" title="{_esc(deadline_tooltip)}"
             onclick="window.synapseDashboardCommand('pycmd:synapsepro:deadline_settings','deadline')"
             onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();this.click();}}">
      <span class="sp-min-deadline-name">{_esc(deadline_title)}</span>
      {deadline_nav_html}
      <div class="sp-min-track"><i class="sp-min-fill" style="--sp-min-progress:{deadline_progress:.1f}%"></i></div>
      <span class="sp-min-deadline-days">{_esc(deadline_days)}</span>
    </section>
    <div id="sp-min-fact-overlay" class="sp-min-fact-overlay" aria-hidden="true"
         onclick="if(event.target===this)window.synapseCloseDailyFact()">
      <div class="sp-min-fact-dialog" role="dialog" aria-modal="true" aria-label="{_esc(_('Daily Fact'))}">
        <div id="sp-min-fact-close" class="sp-min-fact-close" role="button" tabindex="0" aria-label="{_esc(_('Close'))}"
             onclick="window.synapseCloseDailyFact()"
             onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();this.click();}}">×</div>
        {fact_content}
      </div>
    </div>
    """

    stats_markup = f"""
    <section class="sp-min-box sp-min-statistics" role="button" tabindex="0"
             aria-label="{_esc(_('Statistics'))}"
             onclick="window.synapseDashboardCommand('pycmd:synapsepro:stats_info','statistics')"
             onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();this.click();}}">
        <div class="sp-min-chart">
          <div class="sp-min-chart-head">
            <div class="sp-min-label">{_esc(_('Consistency'))}</div>
            <div class="sp-min-chart-scope">{_esc(_('Last 30 Days'))}</div>
          </div>
          {chart_html}
        </div>
        <div class="sp-min-circle-group">
          <div class="sp-min-circle-stat">
            <span class="sp-min-circle-title">{_esc(_('Retention'))}</span>
            <div class="sp-min-ring" style="--sp-min-ring-value:{retention:.1f}%"><strong>{retention:.0f}%</strong></div>
          </div>
          <div class="sp-min-circle-stat">
            <span class="sp-min-circle-title">{_esc(_('New Cards'))}</span>
            <div class="sp-min-ring" style="--sp-min-ring-value:{new_cards:.1f}%"><strong>{new_cards:.0f}%</strong></div>
          </div>
        </div>
    </section>
    """
    return shared + top_markup, stats_markup


def render_minimal_dashboard_html(
    gamification_manager: Optional[Any],
    learning_plan_manager: Optional[Any],
    deadline_manager: Optional[Any],
    stats_days: int = 7,
    fact_theme: str = "Medical",
    daily_fact_html: str = "",
) -> str:
    """Compatibility helper for callers that need the two sections together."""
    top, bottom = render_minimal_dashboard_sections(
        gamification_manager, learning_plan_manager, deadline_manager, stats_days,
        fact_theme, daily_fact_html,
    )
    return top + bottom
