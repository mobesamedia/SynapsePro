# -*- coding: utf-8 -*-
"""
SynapsePro — Celebration popup (deck browser)
=============================================
Renders an in-page HTML modal in the same style as the study-plan timer
modal (transparent backdrop, centred card on --stat-bg). Shown ONLY on the
deck browser — never while reviewing — when the gamification manager reports
new events (rank-up / level-up / daily challenge achieved).

Contents by prominence:
  * Rank-up   -> prominent: old badge -> new badge with a pop-in animation.
  * Level-up  -> small, tidy row.
  * Challenge -> small, tidy row.

The "don't show again" checkbox reports back via pycmd
(``pycmd:synapsepro:celebrate_optout:1``); the option can be re-enabled from
the gamification sidebar.
"""

import html as _html
import os
from typing import Any, Dict, Optional

try:
    from aqt import mw
except Exception:  # pragma: no cover
    mw = None  # type: ignore

try:
    from . import constants
except Exception:  # pragma: no cover
    constants = None  # type: ignore

try:
    from .locales import _
except Exception:
    def _(text):  # type: ignore
        return text


def _media_url(filename: Optional[str]) -> str:
    """URL for a bundled media file inside Anki webviews (via webExports)."""
    if not filename or not mw:
        return ""
    try:
        pkg = mw.addonManager.addonFromModule(__name__)
        return f"/_addons/{pkg}/media/{filename}"
    except Exception:
        return ""


def _static_variant(filename: Optional[str]) -> Optional[str]:
    """Static .png sibling of a rank .gif (bundled for every rank).

    Used for the OLD badge so only the new rank animates. Falls back to the
    gif if the png is unexpectedly missing.
    """
    if filename and filename.endswith(".gif"):
        png = filename[:-4] + ".png"
        try:
            folder = getattr(constants, "icons_folder", "") if constants else ""
            if folder and os.path.exists(os.path.join(folder, png)):
                return png
        except Exception:
            pass
    return filename


def _clean_rank_name(name: Optional[str]) -> str:
    """Translated rank name without the layout <br>."""
    if not name:
        return ""
    return _html.escape(_(name).replace("<br>", " "))


def render_celebration_modal(events: Dict[str, Any]) -> str:
    """Build the modal HTML for the given events ({} -> empty string)."""
    if not events:
        return ""

    rank = events.get("rank")
    level = events.get("level")
    challenge = events.get("challenge")

    lbl_new_rank = _("New Rank!")
    lbl_level_up = _("Level Up!")
    lbl_challenge_done = _("Daily Challenge completed!")
    lbl_level_reached = _("Level {} reached")
    lbl_claim_hint = _("Claim your +{} XP in the sidebar.")
    lbl_dont_show = _("Don't show this again")
    lbl_ok = _("Nice!")

    body = ""

    if rank:
        # Old badge: static PNG. New badge: the animated GIF.
        old_img = _media_url(_static_variant(rank.get("old_image")))
        new_img = _media_url(rank.get("new_image"))
        old_name = _clean_rank_name(rank.get("old_name"))
        new_name = _clean_rank_name(rank.get("new_name"))
        old_half = (
            f'<div class="gcm-rank gcm-rank-old">'
            f'<img src="{old_img}" alt=""><span>{old_name}</span></div>'
            f'<div class="gcm-arrow">&#8250;</div>'
        ) if old_img else ""
        body += (
            f'<h3 class="gcm-title">{lbl_new_rank}</h3>'
            f'<div class="gcm-ranks">{old_half}'
            f'<div class="gcm-rank gcm-rank-new">'
            f'<img src="{new_img}" alt=""><span>{new_name}</span></div>'
            f'</div>'
        )
    elif level:
        body += f'<h3 class="gcm-title">{lbl_level_up}</h3>'
    elif challenge:
        body += f'<h3 class="gcm-title">{lbl_challenge_done}</h3>'

    rows = ""
    if level:
        rows += (
            f'<div class="gcm-row">'
            f'{_html.escape(lbl_level_reached.format(level["new"]))}</div>'
        )
    if challenge:
        chall_txt = _html.escape(str(challenge.get("text", "")))
        hint = _html.escape(lbl_claim_hint.format(challenge.get("xp", 0)))
        # When the challenge is the headline, don't repeat it as a row.
        if rank or level:
            rows += f'<div class="gcm-row">{_html.escape(lbl_challenge_done)}</div>'
        rows += f'<div class="gcm-sub">{chall_txt}<br>{hint}</div>'
    if rows:
        body += f'<div class="gcm-rows">{rows}</div>'

    return f'''
    <style>
        #gami-celebrate {{
            display: flex; position: fixed; z-index: 10001; left: 0; top: 0;
            width: 100%; height: 100%; background: transparent;
            align-items: center; justify-content: center;
        }}
        .gcm-card {{
            background-color: var(--stat-bg, #ffffff);
            color: var(--text-color, #1d1d1f);
            border: 1px solid var(--stat-border, rgba(0,0,0,0.12));
            border-radius: 10px; padding: 20px; width: 320px; text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.4); box-sizing: border-box;
            animation: gcmIn 0.25s ease;
        }}
        @keyframes gcmIn {{ from {{ opacity: 0; transform: scale(0.94); }}
                            to {{ opacity: 1; transform: none; }} }}
        .gcm-title {{ margin: 0 0 12px; font-size: 1.3em; color: var(--text-color, #1d1d1f); }}
        .gcm-ranks {{ display: flex; align-items: center; justify-content: center;
                      gap: 12px; margin-bottom: 6px; }}
        .gcm-rank {{ display: flex; flex-direction: column; align-items: center; gap: 4px;
                     font-size: 0.8em; color: var(--text-color-light, #8e8e93); }}
        .gcm-rank img {{ border-radius: 12px; }}
        .gcm-rank-old img {{ width: 52px; height: 52px; opacity: 0.55; filter: grayscale(0.4); }}
        .gcm-rank-new img {{ width: 92px; height: 92px; animation: gcmPop 0.6s cubic-bezier(.34,1.56,.64,1); }}
        .gcm-rank-new span {{ font-weight: 700; font-size: 1.15em; color: var(--main-blue, #0071D3); }}
        @keyframes gcmPop {{ 0% {{ transform: scale(0.2); opacity: 0; }}
                             60% {{ transform: scale(1.12); opacity: 1; }}
                             100% {{ transform: scale(1); }} }}
        .gcm-arrow {{ font-size: 26px; color: var(--text-color-light, #8e8e93); }}
        .gcm-rows {{ margin: 10px 0 0; }}
        .gcm-row {{ font-size: 0.95em; margin: 4px 0; color: var(--text-color, #1d1d1f); }}
        .gcm-sub {{ font-size: 0.8em; color: var(--text-color-light, #8e8e93);
                    margin-top: 4px; line-height: 1.45; }}
        .gcm-opt {{ display: flex; align-items: center; justify-content: center; gap: 6px;
                    font-size: 0.78em; color: var(--text-color-light, #8e8e93);
                    margin: 16px 0 10px; cursor: pointer; user-select: none; }}
        .gcm-btn {{ border-radius: 6px; padding: 9px 12px; font-weight: 500; font-size: 14px;
                    cursor: pointer; text-align: center; user-select: none; box-sizing: border-box;
                    background-color: var(--main-blue, #0071D3); color: #ffffff; }}
    </style>
    <div id="gami-celebrate">
        <div class="gcm-card">
            {body}
            <label class="gcm-opt"><input type="checkbox" id="gcm-optout">{_html.escape(lbl_dont_show)}</label>
            <div class="gcm-btn" onclick="(function(){{
                var opt = document.getElementById('gcm-optout');
                if (opt && opt.checked && window.pycmd) {{
                    pycmd('pycmd:synapsepro:celebrate_optout:1');
                }}
                var m = document.getElementById('gami-celebrate');
                if (m) m.style.display = 'none';
            }})()">{_html.escape(lbl_ok)}</div>
        </div>
    </div>
    <script>
        // Safety: the opt-out checkbox must never start checked, regardless
        // of any form-state restoring the webview might do.
        (function() {{
            var opt = document.getElementById('gcm-optout');
            if (opt) opt.checked = false;
        }})();
    </script>
    '''
