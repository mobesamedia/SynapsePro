# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
import time
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

# DeckBrowser.refresh() can be requested more than once while Anki is settling
# its startup layout.  Keep the expensive, read-only collection snapshot for a
# very short window so those duplicate renders do not repeat the SQL snapshot.
# One second is deliberately short: it coalesces a startup burst without making
# normal review/deck changes appear stale to the user.
_STATISTICS_CACHE_TTL_SECONDS = 1.0
_statistics_cache = {}


def invalidate_statistics_cache() -> None:
    """Drop all cached dashboard snapshots (profile/review boundary)."""
    _statistics_cache.clear()

# ── Review activity helpers ───────────────────────────────────────────────────
def _get_rollover_hour() -> int:
    """Anki's day-rollover hour (default 4 a.m.)."""
    try:
        return int(mw.col.get_config("rollover", 4) or 4)
    except Exception:
        return 4


def anki_today():
    """Today as an 'Anki day' (a day runs from rollover to rollover)."""
    return (datetime.now() - timedelta(hours=_get_rollover_hour())).date()


def get_daily_review_counts(since_days=None):
    """Reviews per day, keyed by ISO date string, respecting the rollover hour.

    since_days=None returns the whole collection history; an int restricts
    the query for cheap dashboard renders.
    """
    if not mw or not mw.col:
        return {}
    offset = _get_rollover_hour() * 3600
    try:
        if since_days is None:
            rows = mw.col.db.all(
                "SELECT strftime('%Y-%m-%d', id/1000 - ?, 'unixepoch', 'localtime') AS d, "
                "COUNT(*) FROM revlog GROUP BY d",
                offset,
            )
        else:
            start = datetime.now() - timedelta(days=int(since_days))
            rows = mw.col.db.all(
                "SELECT strftime('%Y-%m-%d', id/1000 - ?, 'unixepoch', 'localtime') AS d, "
                "COUNT(*) FROM revlog WHERE id >= ? GROUP BY d",
                offset,
                int(start.timestamp()) * 1000,
            )
        return {r[0]: r[1] for r in rows}
    except Exception as e:
        print(f"SynapsePro: review activity query failed: {e}")
        return {}


CHART_DAYS = 30  # days shown in the mini activity sparkline


def _build_mini_chart():
    """Inline-SVG sparkline: reviews per day, last CHART_DAYS days.

    The y-axis is relative to the window: the best day in the window is 100%,
    a day with no reviews sits on the baseline. Native per-day tooltips via
    invisible full-height hover rects (hit target ≫ mark).
    """
    today = anki_today()
    counts = get_daily_review_counts(since_days=CHART_DAYS + 2)
    start = today - timedelta(days=CHART_DAYS - 1)
    days, values = [], []
    for i in range(CHART_DAYS):
        d = start + timedelta(days=i)
        days.append(d)
        values.append(counts.get(d.isoformat(), 0))
    vmax = max(values) or 1

    W, H, PAD = 300.0, 62.0, 4.0
    PAD_R = 5.0  # right inset so the "today" dot isn't clipped at the edge
    step = (W - PAD_R) / (CHART_DAYS - 1)
    y_lo, y_hi = H - PAD, PAD  # baseline / peak
    pts = [(i * step, y_lo - (v / vmax) * (y_lo - y_hi)) for i, v in enumerate(values)]

    def _clamp_y(y):
        return max(y_hi, min(y_lo, y))

    def _smooth_path(p):
        """Catmull-Rom → cubic Bézier, control-y clamped so zero-runs never
        dip below the baseline."""
        if len(p) < 3:
            return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in p)
        d = f"M{p[0][0]:.1f},{p[0][1]:.1f}"
        for i in range(len(p) - 1):
            p0 = p[i - 1] if i > 0 else p[i]
            p1, p2 = p[i], p[i + 1]
            p3 = p[i + 2] if i + 2 < len(p) else p2
            c1y = _clamp_y(p1[1] + (p2[1] - p0[1]) / 6.0)
            c2y = _clamp_y(p2[1] - (p3[1] - p1[1]) / 6.0)
            d += (f" C{p1[0] + (p2[0] - p0[0]) / 6.0:.1f},{c1y:.1f}"
                  f" {p2[0] - (p3[0] - p1[0]) / 6.0:.1f},{c2y:.1f}"
                  f" {p2[0]:.1f},{p2[1]:.1f}")
        return d

    line = _smooth_path(pts)
    # Close the area on the baseline (the x-axis), ending at the last point.
    area = line + f" L{pts[-1][0]:.1f},{y_lo:.1f} L0,{y_lo:.1f} Z"
    # Subtle x/y axes as hairlines in the neutral grey.
    axes = (
        f'<line x1="0.5" y1="{y_hi:.1f}" x2="0.5" y2="{y_lo:.1f}" '
        f'stroke="var(--gray)" stroke-width="1" vector-effect="non-scaling-stroke"/>'
        f'<line x1="0" y1="{y_lo:.1f}" x2="{W:.1f}" y2="{y_lo:.1f}" '
        f'stroke="var(--gray)" stroke-width="1" vector-effect="non-scaling-stroke"/>'
    )

    hover = []
    for i, (d, v) in enumerate(zip(days, values)):
        hover.append(
            f'<rect x="{i * step - step / 2:.1f}" y="0" width="{step:.1f}" '
            f'height="{H:.0f}" fill="transparent">'
            f'<title>{d.strftime("%d.%m.%Y")}: {v}</title></rect>'
        )

    last = pts[-1]
    return (
        f'<svg class="spark" viewBox="0 0 {W:.0f} {H:.0f}" '
        f'preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">'
        f'{axes}'
        f'<path d="{area}" fill="var(--main-blue)" fill-opacity="0.12" stroke="none"/>'
        f'<path d="{line}" fill="none" stroke="var(--main-blue)" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>'
        f'<circle cx="{last[0]:.1f}" cy="{last[1]:.1f}" r="3" fill="var(--main-blue)"/>'
        f'{"".join(hover)}'
        f'</svg>'
    )


def get_statistics_data(stats_days=7):
    """
    Sammelt und berechnet alle Statistiken.
    Erhält den Zeitraum (stats_days) als Argument von __init__.py.
    """

    if not isinstance(stats_days, int) or stats_days < 1:
        stats_days = 7

    now = time.monotonic()
    cached = _statistics_cache.get(stats_days)
    if cached and now - cached[0] <= _STATISTICS_CACHE_TTL_SECONDS:
        return cached[1]

    chart_html = _build_mini_chart()

    stats_start_ts = int((datetime.now() - timedelta(days=stats_days)).timestamp()) * 1000

    combined_stats = mw.col.db.first(
        """
        SELECT
            SUM(CASE WHEN type = 1 AND ease > 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN type = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN ease > 1 THEN 1 ELSE 0 END),
            COUNT(*),
            SUM(CASE WHEN time > 45000 THEN 45000 ELSE time END)
        FROM revlog
        WHERE id > ? AND ease > 0
        """,
        stats_start_ts
    )

    (correct_reviews, total_reviews, correct_cards,
     total_cards, total_ms) = combined_stats or (0, 0, 0, 0, 0)
    correct_reviews = correct_reviews or 0
    total_reviews = total_reviews or 0
    correct_cards = correct_cards or 0
    total_cards = total_cards or 0
    total_ms = total_ms or 0

    retention_percent = (correct_reviews / total_reviews * 100) if total_reviews > 0 else 0

    total_minutes = (total_ms / 1000.0) / 60.0
    
    efficiency_score = (correct_cards / total_minutes) if total_minutes > 0 else 0
    accuracy_percent = (correct_cards / total_cards * 100) if total_cards > 0 else 0

    TARGET_CARDS_PER_MIN = 7.5
    efficiency_bar_percent_raw = (efficiency_score / TARGET_CARDS_PER_MIN) * 100

    card_counts = mw.col.db.first(
        "SELECT "
        "SUM(CASE WHEN queue != -1 THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN queue = 0 THEN 1 ELSE 0 END) FROM cards"
    )
    total_active_cards, total_new_cards = card_counts or (0, 0)
    total_active_cards = total_active_cards or 0
    total_new_cards = total_new_cards or 0
    
    new_cards_percent = (total_new_cards / total_active_cards * 100) if total_active_cards > 0 else 0

    result = {
        "chart_html": chart_html,
        "efficiency_raw": efficiency_bar_percent_raw,
        "accuracy_raw": accuracy_percent,
        "retention_percent": retention_percent,
        "new_cards_percent": new_cards_percent,
        "days_scope": stats_days 
    }
    _statistics_cache[stats_days] = (time.monotonic(), result)
    return result


def get_minimal_statistics_data(stats_days=7):
    """Return only the metrics used by the minimal dashboard.

    Efficiency and accuracy remain excluded; the requested New Cards share
    is fetched with one small aggregate query.
    """
    if not isinstance(stats_days, int) or stats_days < 1:
        stats_days = 7

    cache_key = ("minimal", stats_days)
    now = time.monotonic()
    cached = _statistics_cache.get(cache_key)
    if cached and now - cached[0] <= _STATISTICS_CACHE_TTL_SECONDS:
        return cached[1]

    chart_html = _build_mini_chart()
    stats_start_ts = int(
        (datetime.now() - timedelta(days=stats_days)).timestamp()
    ) * 1000
    retention_row = mw.col.db.first(
        "SELECT "
        "SUM(CASE WHEN type = 1 AND ease > 1 THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN type = 1 THEN 1 ELSE 0 END) "
        "FROM revlog WHERE id > ? AND ease > 0",
        stats_start_ts,
    )
    correct_reviews, total_reviews = retention_row or (0, 0)
    correct_reviews = correct_reviews or 0
    total_reviews = total_reviews or 0
    retention_percent = (
        (correct_reviews / total_reviews) * 100.0 if total_reviews > 0 else 0.0
    )
    card_counts = mw.col.db.first(
        "SELECT "
        "SUM(CASE WHEN queue != -1 THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN queue = 0 THEN 1 ELSE 0 END) FROM cards"
    )
    total_active_cards, total_new_cards = card_counts or (0, 0)
    total_active_cards = total_active_cards or 0
    total_new_cards = total_new_cards or 0
    new_cards_percent = (
        (total_new_cards / total_active_cards) * 100.0
        if total_active_cards > 0 else 0.0
    )
    result = {
        "chart_html": chart_html,
        "retention_percent": retention_percent,
        "new_cards_percent": new_cards_percent,
        "days_scope": stats_days,
    }
    _statistics_cache[cache_key] = (time.monotonic(), result)
    return result

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

    tooltip_consistency = _("Reviews per day (last 30 days). The best day in this period is the top of the curve.")
    tooltip_efficiency = _("Cards per minute ({}). Time capped at 45s/card.").format(period_text)
    tooltip_accuracy = _("Correct answers: {:.1f}% ({}).").format(acc_real, period_text)
    tooltip_retention = _("Retention on reviews ({}).").format(period_text)
    tooltip_new_cards = _("Percentage of unseen cards in collection.")
    tooltip_info = _("What do these statistics show?")

    # Pre-computed translated labels for HTML
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
            /* anchor for the absolutely positioned info button (top right) */
            position: relative;
            display: grid;
            grid-template-columns: 1.2fr 1.1fr 0.9fr;
            gap: 16px;
            /* stretch: all three blocks share the tallest height, so their
               contents can bottom-align flush via the flexible spacers */
            align-items: stretch;
            background-color: var(--stat-bg);
            border-radius: 12px;
            /* extra right padding nudges the stats slightly left and leaves
               room for the info button; outer box dimensions are unchanged */
            padding: 16px 42px 16px 16px;
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
        }}
        /* Divider before the middle and right blocks. With the grid gap of
           16px and 16px padding after the line, the spacing is symmetric on
           both sides of each divider. */
        .stat-block.divided {{
            border-left: 1px solid var(--stat-border);
            padding-left: 16px;
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
        /* ── Mini activity sparkline: reviews/day, last 30 days ── */
        .spark-wrap {{
            width: 100%;
            line-height: 0;
        }}
        .spark {{
            width: 100%;
            height: 62px;
            display: block;
        }}

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
        /* ── Info button (top right): opens the statistics explanations ── */
        .stats-info-btn {{
            position: absolute;
            top: 12px;
            right: 12px;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            display: grid;
            place-items: center;
            font-size: 12px;
            font-weight: 600;
            line-height: 1;
            color: var(--text-color-light);
            background-color: var(--progress-bg);
            cursor: pointer;
            user-select: none;
            opacity: 0.8;
            transition: opacity 0.2s ease;
        }}
        .stats-info-btn:hover {{
            opacity: 1;
        }}
    </style>
    """

    html = f"""
    <div class="stats-widget-container">
        <!-- Info button: opens a dialog explaining every statistic -->
        <div class="stats-info-btn" title="{tooltip_info}" onclick="pycmd('pycmd:synapsepro:stats_info')">i</div>

        <!-- Block 1: Consistency (activity sparkline) -->
        <div class="stat-block">
            <h3 class="subtle-title" title="{tooltip_consistency}" style="margin:0;">{label_consistency}</h3>
            <div style="flex: 1 1 auto;"></div>
            <div class="spark-wrap">
                {stats['chart_html']}
            </div>
        </div>

        <!-- Block 2: Efficiency -->
        <div class="stat-block divided">
            <h3 class="subtle-title">{label_efficiency}</h3>
            <div style="flex: 1 1 auto; min-height: var(--spacer-height-efficiency);"></div>

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
        <div class="stat-block circle-group divided">
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


def show_statistics_info_dialog(parent=None, stats_days=7):
    """Info dialog for the dashboard statistics widget ("i" button).

    Explains every statistic shown in the widget. Opened from the deck
    browser via pycmd ('synapsepro:stats_info'), see __init__.py.
    """
    from aqt.qt import QDialog, QVBoxLayout, QLabel, QDialogButtonBox

    if not isinstance(stats_days, int) or stats_days < 1:
        stats_days = 7
    if stats_days == 1:
        period_text = _("Last 24 hours")
    else:
        period_text = _("Last {} days").format(stats_days)

    sections = [
        (_("Consistency"),
         _("Your reviews per day over the last 30 days. The curve is relative "
           "to this period: the day with the most reviews forms the peak, days "
           "without reviews sit on the baseline. The dot marks today.")),
        (_("Efficiency (Eff.)"),
         _("How many cards you answer correctly per minute of study time "
           "({}). A full bar equals 7.5 correct cards per minute. Time per "
           "card is capped at 45 seconds so breaks don't distort the "
           "value.").format(period_text)),
        (_("Accuracy (Acc.)"),
         _("The percentage of all answered cards you got right ({}). The bar "
           "is scaled for readability — hover over it to see the exact "
           "value.").format(period_text)),
        (_("Retention"),
         _("The percentage of correct answers on review cards ({}) — cards "
           "you had already learned. This shows how well you retain content "
           "long-term.").format(period_text)),
        (_("New Cards"),
         _("The percentage of cards in your active collection that you have "
           "never studied.")),
    ]

    body = "".join(
        f"<p style='margin:0 0 12px 0;'><b>{title}</b><br>{text}</p>"
        for title, text in sections
    )
    footer = _("The time period ({}) can be changed in the SynapsePro settings.").format(period_text)
    html_text = (
        f"<h3 style='margin:0 0 12px 0;'>{_('Statistics')}</h3>"
        f"{body}"
        f"<p style='margin:0;color:#888;font-size:12px;'>{footer}</p>"
    )

    dialog = QDialog(parent)
    dialog.setWindowTitle(_("SynapsePro - Statistics"))
    dialog.setMinimumWidth(520)

    layout = QVBoxLayout()
    label = QLabel(html_text)
    label.setWordWrap(True)

    button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    button_box.rejected.connect(dialog.reject)

    layout.addWidget(label)
    layout.addWidget(button_box)
    dialog.setLayout(layout)
    dialog.exec()
