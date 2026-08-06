# -*- coding: utf-8 -*-
"""
SynapsePro – Theme Editor Dialog
=================================

A compact popup that lets the user pick custom primary-colour tokens
for the addon UI, or quickly apply one of the three built-in presets.

Exported:
    ThemeEditorDialog – QDialog subclass
"""

from typing import Dict, Optional

# ── Anki / PyQt imports ──────────────────────────────────────────────────────
try:
    from aqt import mw
    from aqt.qt import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                        QLabel, QPushButton, QFrame, QSizePolicy, QColorDialog,
                        QColor, Qt)
except Exception as _e:
    print(f"ThemeEditorDialog: Qt import error: {_e}")
    QDialog = object  # type: ignore

# ── Local imports ─────────────────────────────────────────────────────────────
try:
    from .theme import palette as _palette, COLOR_THEMES, FONT_FAMILY as _FONT_FAMILY
except ImportError:
    def _palette(n): return {}  # type: ignore
    COLOR_THEMES = {}
    _FONT_FAMILY = "sans-serif"

try:
    from .locales import _
except ImportError:
    def _(text): return text  # type: ignore

# ── Night-mode detection ──────────────────────────────────────────────────────
is_night_mode = False
try:
    if mw and mw.pm.night_mode():
        is_night_mode = True
except Exception:
    pass

# ── Four user-facing colour keys ──────────────────────────────────────────────
# (blue_accent and blue_border are auto-derived in theme.palette())
_PICKER_DEFS = [
    ("blue",         "Primary color"),
    ("blue_hover",   "Hover color"),
    ("blue_pressed", "Pressed color"),
    ("blue_bright",  "Bright accent"),
]

# Quick-preset colours (light-mode values used to fill the pickers)
_PRESETS: Dict[str, Dict[str, str]] = {
    "ocean":   {"blue": "#0071D3", "blue_hover": "#0062C4",  "blue_pressed": "#004990", "blue_bright": "#007AFF"},
    "orchid":  {"blue": "#E95ACC", "blue_hover": "#E159C6",  "blue_pressed": "#CB51B3", "blue_bright": "#FCABEC"},
    "forest":  {"blue": "#619971", "blue_hover": "#598C68",  "blue_pressed": "#477154", "blue_bright": "#84CC99"},
    "deluge":  {"blue": "#7961A9", "blue_hover": "#6D5798",  "blue_pressed": "#65508D", "blue_bright": "#987AD2"},
    "horizon": {"blue": "#6183A9", "blue_hover": "#59799D",  "blue_pressed": "#4B6683", "blue_bright": "#7FABDC"},
    "dusty":   {"blue": "#5A9491", "blue_hover": "#528885",  "blue_pressed": "#4E8280", "blue_bright": "#7CCDC9"},
}

_PRESET_DISPLAY = [
    ("ocean",   "Ocean",   "#0071D3", "#004990"),
    ("orchid",  "Orchid",  "#E95ACC", "#CB51B3"),
    ("forest",  "Forest",  "#619971", "#477154"),
    ("deluge",  "Deluge",  "#7961A9", "#65508D"),
    ("horizon", "Horizon", "#6183A9", "#4B6683"),
    ("dusty",   "Dusty",   "#5A9491", "#4E8280"),
]


# ── Dialog stylesheet ─────────────────────────────────────────────────────────
def _build_editor_style(night: bool) -> str:
    c = _palette(night)
    if not c:
        return ""
    return f"""
    QDialog {{
        background-color: {c['bg']};
        font-family: {_FONT_FAMILY};
        font-size: 13px;
        color: {c['text']};
    }}
    QFrame#SectionFrame {{
        background-color: {c['surface']};
        border: 1px solid {c['grey_light']};
        border-radius: 10px;
    }}
    QLabel {{
        color: {c['text']};
        background-color: transparent;
    }}
    QLabel#Muted {{
        color: {c['text_muted']};
        font-size: 11px;
    }}
    QPushButton#ApplyBtn {{
        background-color: {c['blue']};
        color: white;
        border-radius: 8px;
        padding: 6px 20px;
        font-weight: 600;
        border: {c['blue_border']};
    }}
    QPushButton#ApplyBtn:hover  {{ background-color: {c['blue_hover']}; }}
    QPushButton#ApplyBtn:pressed {{ background-color: {c['blue_pressed']}; }}
    QPushButton#CancelBtn {{
        background-color: {c['grey_light']};
        color: {c['text']};
        border-radius: 8px;
        padding: 6px 20px;
        font-weight: 600;
        border: none;
    }}
    QPushButton#CancelBtn:hover {{ background-color: {c['grey_mid']}; }}
    """


class ThemeEditorDialog(QDialog):
    """Popup editor for SynapsePro's primary colour tokens.

    Parameters
    ----------
    initial_colors:
        Dict with any of: ``blue``, ``blue_hover``, ``blue_pressed``,
        ``blue_bright``.  Pre-fills the colour pickers.
    parent:
        Optional parent widget.
    """

    def __init__(
        self,
        initial_colors: Optional[Dict[str, str]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._colors: Dict[str, str] = (
            _PRESETS["ocean"].copy() if not initial_colors
            else {**_PRESETS["ocean"], **initial_colors}
        )
        self._swatch_btns: Dict[str, QPushButton] = {}
        self._hex_labels:  Dict[str, QLabel]      = {}

        self.setWindowTitle(_("Theme Editor"))
        self.setStyleSheet(_build_editor_style(is_night_mode))
        self.setMinimumWidth(380)
        self.setMaximumWidth(480)
        self.setSizeGripEnabled(False)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        root.addWidget(self._build_presets_section())
        root.addWidget(self._build_pickers_section())
        root.addLayout(self._build_button_row())

    # ── Section builders ──────────────────────────────────────────────────────

    def _build_presets_section(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("SectionFrame")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        hdr = QLabel(_("Quick Presets"))
        hdr.setStyleSheet("font-weight: 600; font-size: 13px;")
        lay.addWidget(hdr)

        grid = QGridLayout()
        grid.setSpacing(6)
        for idx, (key, label_key, bg, pressed) in enumerate(_PRESET_DISPLAY):
            btn = QPushButton(label_key)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: white;
                    border-radius: 6px;
                    border: 2px solid transparent;
                    font-weight: 600;
                    font-size: 11px;
                    padding: 2px 6px;
                }}
                QPushButton:hover {{
                    background-color: {pressed};
                    border: 2px solid rgba(255,255,255,0.5);
                }}
            """)
            btn.clicked.connect(lambda _, k=key: self._apply_preset(k))
            grid.addWidget(btn, idx // 3, idx % 3)
        lay.addLayout(grid)
        return frame

    def _build_pickers_section(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("SectionFrame")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)

        hdr = QLabel(_("Custom Colors"))
        hdr.setStyleSheet("font-weight: 600; font-size: 13px;")
        lay.addWidget(hdr)

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnStretch(0, 1)
        grid.setColumnMinimumWidth(1, 36)
        grid.setColumnMinimumWidth(2, 80)

        for i, (key, label_key) in enumerate(_PICKER_DEFS):
            lbl = QLabel(_(label_key))
            lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            grid.addWidget(lbl, i, 0)

            color = self._colors.get(key, "#0071D3")
            swatch = QPushButton()
            swatch.setFixedSize(32, 32)
            swatch.setCursor(Qt.CursorShape.PointingHandCursor)
            swatch.setToolTip(_("Click to choose a color"))
            self._apply_swatch_style(swatch, color)
            swatch.clicked.connect(lambda _, k=key, b=swatch: self._pick_color(k, b))
            self._swatch_btns[key] = swatch
            grid.addWidget(swatch, i, 1)

            hex_lbl = QLabel(color.upper())
            c = _palette(is_night_mode)
            hex_lbl.setStyleSheet(
                f"color: {c.get('text_muted','#888')};"
                f"font-family: monospace; font-size: 12px;"
            )
            self._hex_labels[key] = hex_lbl
            grid.addWidget(hex_lbl, i, 2)

        lay.addLayout(grid)

        note = QLabel(_("Colors apply to both Light and Dark mode."))
        note.setObjectName("Muted")
        note.setWordWrap(True)
        lay.addWidget(note)
        return frame

    def _build_button_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.setObjectName("CancelBtn")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        apply_btn = QPushButton(_("Apply"))
        apply_btn.setObjectName("ApplyBtn")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self.accept)

        row.addStretch()
        row.addWidget(cancel_btn)
        row.addWidget(apply_btn)
        return row

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _apply_swatch_style(btn: QPushButton, color: str) -> None:
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border-radius: 6px;
                border: 1px solid rgba(0,0,0,0.22);
            }}
            QPushButton:hover {{
                border: 2px solid rgba(255,255,255,0.75);
            }}
        """)

    def _pick_color(self, key: str, swatch: QPushButton) -> None:
        """Open QColorDialog and update swatch + hex label on confirmation."""
        try:
            initial = QColor(self._colors.get(key, "#0071D3"))
            color = QColorDialog.getColor(initial, self, _("Click to choose a color"))
            if color.isValid():
                hex_str = color.name().upper()
                self._colors[key] = hex_str
                self._apply_swatch_style(swatch, hex_str)
                if key in self._hex_labels:
                    self._hex_labels[key].setText(hex_str)
        except Exception as e:
            print(f"ThemeEditorDialog: color pick error: {e}")

    def _apply_preset(self, preset_key: str) -> None:
        """Fill all pickers with values from the chosen built-in preset."""
        preset = _PRESETS.get(preset_key, _PRESETS["blue"])
        for key, val in preset.items():
            self._colors[key] = val
            if key in self._swatch_btns:
                self._apply_swatch_style(self._swatch_btns[key], val)
            if key in self._hex_labels:
                self._hex_labels[key].setText(val.upper())

    # ── Public API ────────────────────────────────────────────────────────────

    def get_colors(self) -> Dict[str, str]:
        """Return the confirmed colour dict (call only after exec() → Accepted)."""
        return self._colors.copy()
