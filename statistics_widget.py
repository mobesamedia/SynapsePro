# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from aqt import mw

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
    def _palette(night): return {"blue": "#0071D3", "blue_bright": "#40A5FF" if night else "#007AFF"}  # type: ignore
    _FONT_FAMILY = "sans-serif"

try:
    from .locales import _
except ImportError:
    def _(text):  # type: ignore
        return text

WIDGET_MAX_WIDTH = "860px"

def get_statistics_data(stats_days=7):
    """
    Sammelt und berechnet alle Statistiken.
    Erhält den Zeitraum (stats_days) als Argument von __init__.py.
    """
    
    if not isinstance(stats_days, int) or stats_days < 1: 
        stats_days = 7

    studied_days = []
    for i in range(6, -1, -1):
        day = datetime.now().date() - timedelta(days=i)
        day_start_ts = int(datetime(day.year, day.month, day.day).timestamp())

        count = mw.col.db.scalar(
            "SELECT COUNT(*) FROM revlog WHERE id >= ? AND id < ?",
            day_start_ts * 1000,
            (day_start_ts + 86400) * 1000,
        )
        studied_days.append(count > 0)

    colors = ['gray'] * 7

    last_study_day_idx = -1
    for i in range(6, -1, -1):
        if studied_days[i]:
            last_study_day_idx = i
            break

    if last_study_day_idx != -1:
        streak_len = 0
        for i in range(last_study_day_idx, -1, -1):
            if studied_days[i]:
                streak_len += 1
            else:
                break

        days_since_streak_ended = 6 - last_study_day_idx
        num_green = max(0, streak_len - days_since_streak_ended)

        for i in range(num_green):
            colors[i] = 'green'

        is_broken = days_since_streak_ended > 0
        if is_broken and num_green < streak_len:
            orange_idx = num_green
            if orange_idx < 7:
                 colors[orange_idx] = 'orange'

    consistency_days = colors

    stats_start_ts = int((datetime.now() - timedelta(days=stats_days)).timestamp()) * 1000

    retention_stats = mw.col.db.first(
        """
        SELECT
            SUM(CASE WHEN ease > 1 THEN 1 ELSE 0 END),
            COUNT(*)
        FROM revlog
        WHERE type = 1 AND id > ?
        """,
        stats_start_ts
    )
    
    correct_reviews, total_reviews = retention_stats or (0, 0)
    correct_reviews = correct_reviews or 0

    retention_percent = (correct_reviews / total_reviews * 100) if total_reviews > 0 else 0

    efficiency_stats = mw.col.db.first(
        """
        SELECT
            SUM(CASE WHEN ease > 1 THEN 1 ELSE 0 END),
            COUNT(*),
            SUM(CASE WHEN time > 45000 THEN 45000 ELSE time END)
        FROM revlog
        WHERE id > ?
        """,
        stats_start_ts
    )
    
    correct_cards, total_cards, total_ms = efficiency_stats or (0, 0, 0)
    correct_cards = correct_cards or 0
    total_ms = total_ms or 0

    total_minutes = (total_ms / 1000.0) / 60.0
    
    efficiency_score = (correct_cards / total_minutes) if total_minutes > 0 else 0
    accuracy_percent = (correct_cards / total_cards * 100) if total_cards > 0 else 0

    TARGET_CARDS_PER_MIN = 7.5
    efficiency_bar_percent_raw = (efficiency_score / TARGET_CARDS_PER_MIN) * 100

    total_active_cards = mw.col.db.scalar("SELECT COUNT(*) FROM cards WHERE queue != -1")
    total_new_cards = mw.col.db.scalar("SELECT COUNT(*) FROM cards WHERE queue = 0")
    
    new_cards_percent = (total_new_cards / total_active_cards * 100) if total_active_cards > 0 else 0

    return {
        "consistency": consistency_days,
        "efficiency_raw": efficiency_bar_percent_raw,
        "accuracy_raw": accuracy_percent,
        "retention_percent": retention_percent,
        "new_cards_percent": new_cards_percent,
        "days_scope": stats_days 
    }

def render_widget_html_internal(stats):
    """Interne Funktion zum Bauen des HTMLs."""
    retention_val = stats['retention_percent']
    new_cards_val = stats['new_cards_percent']
    days_scope = stats['days_scope']
    
    if days_scope == 1:
        period_text = _("Last 24 hours")
    else:
        period_text = _("Last {} days").format(days_scope)

    acc_real = stats['accuracy_raw']
    if acc_real >= 90:
        acc_visual = 100
    elif acc_real >= 80:
        acc_visual = 85 + ((acc_real - 80) * 1.5)
    elif acc_real >= 70:
        acc_visual = 50 + ((acc_real - 70) * 3.5)
    else:
        acc_visual = max(10, acc_real / 1.5)
    acc_visual = min(100, acc_visual)

    eff_raw = stats['efficiency_raw']
    eff_visual = min(100, eff_raw)
    
    MAIN_BLUE = _palette(is_night_mode)["blue"]
    
    efficiency_color = MAIN_BLUE
    accuracy_color = MAIN_BLUE
    retention_color = MAIN_BLUE

    tooltip_consistency = _("Your study activity (Last 7 days). Blue = Streak, Gray = Rest.")
    tooltip_efficiency = _("Cards per minute ({}). Time capped at 45s/card.").format(period_text)
    tooltip_accuracy = _("Correct answers: {:.1f}% ({}).").format(acc_real, period_text)
    tooltip_retention = _("Retention on reviews ({}).").format(period_text)
    tooltip_new_cards = _("Percentage of unseen cards in collection.")

    # Pre-computed translated labels for HTML
    label_statistics = _("Statistics")
    label_consistency = _("Consistency")
    label_efficiency = _("Efficiency")
    label_eff_short = _("Eff.")
    label_acc_short = _("Acc.")
    label_retention = _("Retention")
    label_new_cards = _("New Cards")


    _cl = _palette(False)
    _cd = _palette(True)
    css = f"""
    <style>
        :root {{
            --spacer-height-stats: 8px;
            --spacer-height-efficiency: 10px;
            --stat-bg: {_cl["surface"]};
            --stat-border: {_cl["grey_light"]};
            --text-color: {_cl["text"]};
            --text-color-light: {_cl["text_muted"]};
            --progress-bg: {_cl["grey_light"]};
            --gray: {_cl["grey_light"]};
            --main-blue: {_cl["blue"]};
            --warning-blue: {_cl["streak_warn"]};
        }}
        body.night_mode {{
            --stat-bg: {_cd["surface"]};
            --stat-border: {_cd["grey_mid"]};
            --text-color: {_cd["text"]};
            --text-color-light: {_cd["text_muted"]};
            --progress-bg: {_cd["grey_mid"]};
            --gray: {_cd["grey_mid"]};
            --main-blue: {_cd["blue_bright"]};
            --warning-blue: {_cd["streak_warn"]};
        }}
        .stats-widget-container {{
            display: grid;
            grid-template-columns: 1.2fr 1.1fr 0.9fr;
            gap: 16px;
            align-items: start;
            background-color: var(--stat-bg);
            border-radius: 12px;
            padding: 16px;
            margin: -15px auto 20px;
            max-width: {WIDGET_MAX_WIDTH};
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: var(--text-color);
            border: 1px solid var(--stat-border);
            box-sizing: border-box;
        }}
        body.night_mode .stats-widget-container {{
            border: 1px solid {_cd["grey_mid"]};
        }}
        .stat-block {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            text-align: left;
        }}
        .stat-block.circle-group {{
            flex-direction: row;
            justify-content: center;
            gap: 20px;
            border-left: 1px solid var(--stat-border);
            padding-left: 24px;
        }}
        .stat-block h3 {{
            margin: 0 0 4px 0;
            font-size: 16px;
            font-weight: 600;
        }}
        .stat-block h3.subtle-title {{
            color: var(--text-color-light);
            font-size: 14px;
            font-weight: normal;
        }}
        .stat-block .label {{
            color: var(--text-color-light);
            font-size: 14px;
        }}
        .consistency-grid {{
            display: flex;
            gap: 4px;
            height: 20px;
        }}
        .consistency-box {{
            flex-grow: 1;
            border-radius: 4px;
        }}
        /* Hier die spezifischen Farbzuweisungen */
        .consistency-box.green {{ background-color: {_palette(False)["blue"]}; }}
        .consistency-box.orange {{ background-color: {_cl["streak_warn"]}; }}
        .consistency-box.gray {{ background-color: var(--gray); }}

        /* Darkmode Overrides für die Boxen, damit es lesbar bleibt */
        body.night_mode .consistency-box.green {{ background-color: {_palette(True)["blue_bright"]}; }}
        body.night_mode .consistency-box.orange {{ background-color: {_cd["streak_warn"]}; }}

        .progress-row {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .progress-row .label {{
            width: 30px;
        }}
        .progress-bar-bg {{
            flex-grow: 1;
            height: 12px;
            background-color: var(--progress-bg);
            border-radius: 6px;
            overflow: hidden;
        }}
        .progress-bar-fill {{
            height: 100%;
            border-radius: 6px;
            transition: width 0.5s ease-out;
        }}
        .single-circle-stat {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
        }}
        .retention-circle {{
            width: 70px;
            height: 70px;
            border-radius: 50%;
            display: grid;
            place-items: center;
            font-size: 18px;
            font-weight: 600;
        }}
    </style>
    """

    consistency_html = "".join(f'<div class="consistency-box {color}"></div>' for color in stats['consistency'])

    html = f"""
    <div class="stats-widget-container">
        <!-- Block 1: Statistics / Consistency -->
        <div class="stat-block">
            <h3>{label_statistics}</h3>
            <div style="height: var(--spacer-height-stats);"></div>
            <span class="label">{label_consistency}</span>
            <div class="consistency-grid" title="{tooltip_consistency}">
                {consistency_html}
            </div>
        </div>

        <!-- Block 2: Efficiency -->
        <div class="stat-block">
            <h3 class="subtle-title">{label_efficiency}</h3>
            <div style="height: var(--spacer-height-efficiency);"></div>

            <div class="progress-row" title="{tooltip_efficiency}">
                <span class="label">{label_eff_short}</span>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width: {eff_visual:.1f}%; background-color: {efficiency_color};"></div>
                </div>
            </div>

            <div class="progress-row" title="{tooltip_accuracy}">
                <span class="label">{label_acc_short}</span>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width: {acc_visual:.1f}%; background-color: {accuracy_color};"></div>
                </div>
            </div>
        </div>

        <!-- Block 3: Circles -->
        <div class="stat-block circle-group">
            <div class="single-circle-stat" title="{tooltip_retention}">
                <h3 class="subtle-title">{label_retention}</h3>
                <div class="retention-circle-container">
                    <div class="retention-circle" style="background: radial-gradient(closest-side, var(--stat-bg) 79%, transparent 80% 100%), conic-gradient({retention_color} {retention_val:.1f}%, var(--progress-bg) 0);">{retention_val:.0f}%</div>
                </div>
            </div>

            <div class="single-circle-stat" title="{tooltip_new_cards}">
                <h3 class="subtle-title">{label_new_cards}</h3>
                <div class="retention-circle-container">
                    <div class="retention-circle" style="background: radial-gradient(closest-side, var(--stat-bg) 79%, transparent 80% 100%), conic-gradient({MAIN_BLUE} {new_cards_val:.1f}%, var(--progress-bg) 0);">{new_cards_val:.0f}%</div>
                </div>
            </div>
        </div>

    </div>
    """
    
    return css + html

def render_statistics_widget_html(stats_days=7):
    """
    Hauptfunktion, die von __init__.py aufgerufen wird.
    Akzeptiert den Zeitraum und gibt das HTML zurück.
    """
    data = get_statistics_data(stats_days)
    return render_widget_html_internal(data)