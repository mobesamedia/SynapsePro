# -*- coding: utf-8 -*-
"""
SynapsePro – Central Theme Module
==================================

All design tokens (colours, fonts) live here.
UI modules must NOT hardcode hex colours or font names; they import this
module and reference tokens by semantic key.

Usage in any UI file
--------------------

    from .theme import palette, FONT_FAMILY

    def _build_style(night: bool) -> str:
        c = palette(night)
        return f\"\"\"
        QDialog {{
            background-color: {c['bg']};
            font-family: {FONT_FAMILY};
            color: {c['text']};
        }}
        \"\"\"

    LIGHT_STYLE = _build_style(False)
    DARK_STYLE   = _build_style(True)

Adding a new theme
------------------
1.  Define a new palette dict following the same keys as LIGHT / DARK.
2.  Update :func:`palette` to return the new dict when requested.
3.  Expose a setting in Settings → Theme to let the user choose.
    No individual UI file needs to be touched.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Typography
# ─────────────────────────────────────────────────────────────────────────────

FONT_FAMILY: str = (
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
)

# ─────────────────────────────────────────────────────────────────────────────
# Light palette
# ─────────────────────────────────────────────────────────────────────────────

LIGHT: dict = {
    # ── Backgrounds ───────────────────────────────────────────────────────────
    "bg":           "#F5F5F7",   # Page / scroll-area background
    "surface":      "#FFFFFF",   # Cards, inputs, modals, white areas
    "grey_light":   "#E5E5EA",   # Button fills, borders, progress bars, grooves
    "grey_mid":     "#D1D1D6",   # Button hovers, input borders, slider handles
    "grey_dark":    "#AEAEB2",   # Pressed states
    "hover_subtle": "#F0F0F0",   # Very subtle hover backgrounds (calendar toolbar)
    "selection_bg": "#E4F2FF",   # Table row selection highlight

    # ── Text ──────────────────────────────────────────────────────────────────
    "text":         "#1D1D1F",   # Primary body text and button labels
    "text_muted":   "#86868B",   # Secondary labels, section titles, hints
    "text_faint":   "#AAAAAA",   # Placeholder, disabled, credits
    "text_browser": "#333333",   # QTextBrowser / changelog body

    # ── Blue (primary brand) ──────────────────────────────────────────────────
    "blue":         "#0071D3",   # Primary CTA buttons, checkboxes, progress fill
    "blue_hover":   "#0062C4",
    "blue_pressed": "#004990",
    "blue_border":  "none",      # Full CSS border value for primary buttons
    "blue_bright":  "#007AFF",   # Focus rings, calendar highlights, active accents
    "blue_accent":  "#0071D3",   # Prominent accent (= blue in light, brighter in dark)

    # ── Red (danger / destructive) ────────────────────────────────────────────
    "red":          "#FF3B30",
    "red_hover":    "#D7261E",
    "red_border":   "none",
    "red_bg":       "#FFEBEB",   # Destructive button background
    "red_text":     "#D32F2F",   # Destructive button label

    # ── Green (success / positive) ────────────────────────────────────────────
    "green":        "#28CD41",   # XP gains, streak highlights
    "green_bg":     "#E8F8F5",   # Completed challenge card background
    "green_border": "#C1E1D9",   # Completed challenge card border

    # ── Info card (neutral pending state) ─────────────────────────────────────
    "info_bg":      "#F0F8FF",   # Pending challenge card background
    "info_border":  "#D6E8F6",

    # ── Streak warning (broken/interrupted streak indicator) ──────────────────
    "streak_warn":  "#B9B9B9",   # Neutral gray highlight for broken streak day

    # ── Special accents ───────────────────────────────────────────────────────
    "sep_accent":   "#888888",   # Sidebar separator line + timer label colour
}

# ─────────────────────────────────────────────────────────────────────────────
# Dark palette
# ─────────────────────────────────────────────────────────────────────────────

DARK: dict = {
    # ── Backgrounds ───────────────────────────────────────────────────────────
    "bg":           "#191919",
    "surface":      "#2C2C2C",
    "grey_light":   "#303030",
    "grey_mid":     "#404040",
    "grey_dark":    "#505050",
    "hover_subtle": "#404040",
    "selection_bg": "#404040",

    # ── Text ──────────────────────────────────────────────────────────────────
    "text":         "#E0E0E0",
    "text_muted":   "#AAAAAA",
    "text_faint":   "#888888",
    "text_browser": "#D0D0D0",

    # ── Blue (primary brand) ──────────────────────────────────────────────────
    "blue":         "#0071D3",
    "blue_hover":   "#0062C4",
    "blue_pressed": "#004990",
    "blue_border":  "1px solid #0056A4",
    "blue_bright":  "#4FACFE",   # Brighter blue for dark-mode focus / accents
    "blue_accent":  "#4FACFE",   # Prominent accent (brighter in dark mode)

    # ── Red (danger / destructive) ────────────────────────────────────────────
    "red":          "#FF3B30",
    "red_hover":    "#D7261E",
    "red_border":   "1px solid #A00000",
    "red_bg":       "#5A1E1E",
    "red_text":     "#FFCCCC",

    # ── Green (success / positive) ────────────────────────────────────────────
    "green":        "#28CD41",
    "green_bg":     "#1E3A2E",
    "green_border": "#2D5A45",

    # ── Info card (neutral pending state) ─────────────────────────────────────
    "info_bg":      "#1A2A3A",
    "info_border":  "#2A3A4A",

    # ── Streak warning (broken/interrupted streak indicator) ──────────────────
    "streak_warn":  "#777777",   # Neutral gray for broken streak day (dark mode)

    # ── Special accents ───────────────────────────────────────────────────────
    "sep_accent":   "#888888",
}


# ─────────────────────────────────────────────────────────────────────────────
# Color-theme overrides  (only the 6 "blue-family" tokens differ per theme)
# ─────────────────────────────────────────────────────────────────────────────

#  Structure:  COLOR_THEMES[theme_name][night_mode_bool] = {overrides}
COLOR_THEMES: dict = {
    "ocean": {
        False: {
            "blue":         "#0071D3",
            "blue_hover":   "#0062C4",
            "blue_pressed": "#004990",
            "blue_border":  "none",
            "blue_bright":  "#007AFF",
            "blue_accent":  "#0071D3",
        },
        True: {
            "blue":         "#0071D3",
            "blue_hover":   "#0062C4",
            "blue_pressed": "#004990",
            "blue_border":  "1px solid #0056A4",
            "blue_bright":  "#4FACFE",
            "blue_accent":  "#4FACFE",
        },
    },
    "orchid": {
        False: {
            "blue":         "#E95ACC",
            "blue_hover":   "#E159C6",
            "blue_pressed": "#CB51B3",
            "blue_border":  "none",
            "blue_bright":  "#FCABEC",
            "blue_accent":  "#E95ACC",
        },
        True: {
            "blue":         "#E95ACC",
            "blue_hover":   "#E159C6",
            "blue_pressed": "#CB51B3",
            "blue_border":  "1px solid #B8459F",
            "blue_bright":  "#FCABEC",
            "blue_accent":  "#FCABEC",
        },
    },
    "forest": {
        False: {
            "blue":         "#619971",
            "blue_hover":   "#598C68",
            "blue_pressed": "#477154",
            "blue_border":  "none",
            "blue_bright":  "#84CC99",
            "blue_accent":  "#619971",
        },
        True: {
            "blue":         "#619971",
            "blue_hover":   "#598C68",
            "blue_pressed": "#477154",
            "blue_border":  "1px solid #3C5E43",
            "blue_bright":  "#84CC99",
            "blue_accent":  "#84CC99",
        },
    },
    "deluge": {
        False: {
            "blue":         "#7961A9",
            "blue_hover":   "#6D5798",
            "blue_pressed": "#65508D",
            "blue_border":  "none",
            "blue_bright":  "#987AD2",
            "blue_accent":  "#7961A9",
        },
        True: {
            "blue":         "#7961A9",
            "blue_hover":   "#6D5798",
            "blue_pressed": "#65508D",
            "blue_border":  "1px solid #573F7A",
            "blue_bright":  "#987AD2",
            "blue_accent":  "#987AD2",
        },
    },
    "horizon": {
        False: {
            "blue":         "#6183A9",
            "blue_hover":   "#59799D",
            "blue_pressed": "#4B6683",
            "blue_border":  "none",
            "blue_bright":  "#7FABDC",
            "blue_accent":  "#6183A9",
        },
        True: {
            "blue":         "#6183A9",
            "blue_hover":   "#59799D",
            "blue_pressed": "#4B6683",
            "blue_border":  "1px solid #3D596F",
            "blue_bright":  "#7FABDC",
            "blue_accent":  "#7FABDC",
        },
    },
    "dusty": {
        False: {
            "blue":         "#5A9491",
            "blue_hover":   "#528885",
            "blue_pressed": "#4E8280",
            "blue_border":  "none",
            "blue_bright":  "#7CCDC9",
            "blue_accent":  "#5A9491",
        },
        True: {
            "blue":         "#5A9491",
            "blue_hover":   "#528885",
            "blue_pressed": "#4E8280",
            "blue_border":  "1px solid #3E6B69",
            "blue_bright":  "#7CCDC9",
            "blue_accent":  "#7CCDC9",
        },
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Active theme state  (set at profile-open time by __init__.py)
# ─────────────────────────────────────────────────────────────────────────────

_ACTIVE_THEME: str = "ocean"

# Custom theme: stores the 4 user-chosen colour keys.
# Only populated when _ACTIVE_THEME == "custom".
_CUSTOM_COLORS: dict = {}


def set_custom_theme_colors(colors: dict) -> None:
    """Store user-chosen colours for the 'custom' theme.

    Accepts a dict with any subset of the four user-facing keys:
    ``blue``, ``blue_hover``, ``blue_pressed``, ``blue_bright``.
    Unknown keys are silently ignored.
    """
    global _CUSTOM_COLORS
    _ALLOWED = {"blue", "blue_hover", "blue_pressed", "blue_bright"}
    _CUSTOM_COLORS = {k: v for k, v in colors.items() if k in _ALLOWED}


def set_active_theme(name: str) -> None:
    """Persist the chosen colour-theme name for all subsequent palette() calls.

    Called once by ``__init__.py`` after loading addon settings so every later
    ``palette()`` invocation (widget creation, webview render) returns the
    correct colour tokens without any individual UI file needing to know about
    the user's preference.

    Valid names: ``"blue"``, ``"pink"``, ``"green"``, ``"custom"``.
    Unknown names are silently ignored (falls back to 'blue').
    """
    global _ACTIVE_THEME
    if name in COLOR_THEMES or name == "custom":
        _ACTIVE_THEME = name


def get_active_theme() -> str:
    """Return the currently active theme name (e.g. ``'ocean'``, ``'custom'``)."""
    return _ACTIVE_THEME


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def palette(night_mode: bool) -> dict:
    """Return the colour-token dict for *night_mode* with the active theme applied.

    Starts from the LIGHT or DARK base palette and overlays the six
    blue-family tokens for whichever colour theme the user has chosen
    (blue / pink / green / custom).  All other tokens (backgrounds, text,
    greys …) are always taken from the base palette and are unaffected.

    Call ``set_active_theme(name)`` (and optionally ``set_custom_theme_colors()``)
    once at startup; no individual UI file needs to be modified.
    """
    base = (DARK if night_mode else LIGHT).copy()

    if _ACTIVE_THEME == "custom" and _CUSTOM_COLORS:
        # Derive all six tokens from the four user-chosen values.
        primary  = _CUSTOM_COLORS.get("blue",         "#0071D3")
        hover    = _CUSTOM_COLORS.get("blue_hover",   "#0062C4")
        pressed  = _CUSTOM_COLORS.get("blue_pressed", "#004990")
        bright   = _CUSTOM_COLORS.get("blue_bright",  "#007AFF")
        overrides = {
            "blue":         primary,
            "blue_hover":   hover,
            "blue_pressed": pressed,
            "blue_bright":  bright,
            # In dark mode the accent is the bright colour; in light it is
            # the primary (mirrors the built-in blue preset behaviour).
            "blue_accent":  bright if night_mode else primary,
            # Border only visible in dark mode; derive from the pressed tone.
            "blue_border":  f"1px solid {pressed}" if night_mode else "none",
        }
        base.update(overrides)
    else:
        overrides = COLOR_THEMES.get(_ACTIVE_THEME, COLOR_THEMES["ocean"])[night_mode]
        base.update(overrides)

    return base
