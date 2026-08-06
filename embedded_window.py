# -*- coding: utf-8 -*-
"""Embed a tool's web view directly into Anki's main window.

Instead of opening a separate, free-floating popup window, this places a
widget into Anki's central content area – right below the normal top
toolbar – so it feels like a view *inside* Anki rather than an extra
window. Anki's main web view and bottom bar are temporarily hidden while
the embedded view is active and restored when it closes.

Only one embedded view can be active at a time (across all tools).
"""

from __future__ import annotations

from typing import Callable, List, Optional

try:
    from aqt import mw
except Exception:  # pragma: no cover - Anki not available
    mw = None  # type: ignore

from aqt.qt import (
    Qt, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy,
    QTimer,
)

try:
    from .locales import _
except ImportError:
    def _(text):  # type: ignore
        return text


# ── Module state (only one embed at a time) ───────────────────────────
_container: Optional[QWidget] = None
_on_close: Optional[Callable[[], None]] = None
_hidden_widgets: List[QWidget] = []
# Widgets whose height we forcibly collapse to 0 while embedded, paired with
# the maximum height to restore afterwards. Hiding a web view normally lets
# the layout reclaim its space, but Anki's top toolbar keeps reserving its
# slot (an empty grey band), so we also clamp its height.
_collapsed: List[tuple] = []
_QWIDGETSIZE_MAX = 16777215  # Qt's QWIDGETSIZE_MAX sentinel


def repair_top_toolbar() -> None:
    """Restore Anki's toolbar geometry and redraw its web content.

    Anki animates the toolbar height internally.  A height sampled while that
    animation is running is not a safe value to persist: restoring such an
    intermediate value can leave only a thin empty strip.  Let Anki calculate
    its natural height again instead.
    """
    if mw is None or _container is not None:
        return
    toolbar_web = getattr(mw, "toolbarWeb", None)
    if toolbar_web is None:
        toolbar = getattr(mw, "toolbar", None)
        toolbar_web = getattr(toolbar, "web", None)
    if toolbar_web is not None:
        try:
            toolbar_web.setMinimumHeight(0)
            toolbar_web.setMaximumHeight(_QWIDGETSIZE_MAX)
            toolbar_web.setVisible(True)
        except (RuntimeError, AttributeError):
            pass
    try:
        toolbar = getattr(mw, "toolbar", None)
        if toolbar is not None:
            toolbar.draw()
    except (RuntimeError, AttributeError) as exc:
        print(f"SynapsePro: could not restore top toolbar: {exc}")


def is_active() -> bool:
    """True if a tool is currently embedded in the Anki main window."""
    return _container is not None


def _main_layout():
    """Return Anki's central QVBoxLayout (toolbar / web / bottom), or None."""
    return getattr(mw, "mainLayout", None) if mw is not None else None


def _build_header(title: str, on_close: Callable[[], None]) -> QWidget:
    """A slim top bar with an optional title and a close button."""
    header = QWidget()
    header.setObjectName("synapseEmbedHeader")
    h = QHBoxLayout(header)
    h.setContentsMargins(10, 4, 8, 4)
    h.setSpacing(6)

    if title:
        lbl = QLabel(title)
        lbl.setObjectName("synapseEmbedTitle")
        h.addWidget(lbl)
    h.addStretch(1)

    close_btn = QPushButton("\u2715")  # ✕
    close_btn.setObjectName("synapseEmbedClose")
    close_btn.setToolTip(_("Back to Anki"))
    close_btn.setFixedSize(28, 24)
    try:
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    except Exception:
        pass
    close_btn.clicked.connect(lambda: on_close())
    h.addWidget(close_btn)

    night = False
    try:
        night = bool(mw and hasattr(mw, "pm") and mw.pm.night_mode())
    except Exception:
        night = False
    if night:
        bg, fg, line, hover = "#2c2c2e", "#e6e6e6", "rgba(255,255,255,0.12)", "#3a3a3c"
    else:
        bg, fg, line, hover = "#f2f2f2", "#37352f", "rgba(0,0,0,0.10)", "#e2e2e2"
    header.setStyleSheet(
        f"#synapseEmbedHeader {{ background:{bg}; border-bottom:1px solid {line}; }}"
        f"#synapseEmbedTitle {{ color:{fg}; font-weight:600; font-size:13px; }}"
        f"#synapseEmbedClose {{ border:none; border-radius:6px; background:transparent;"
        f" color:{fg}; font-size:14px; }}"
        f"#synapseEmbedClose:hover {{ background:{hover}; }}"
    )
    return header


def embed(inner_widget: QWidget, on_close: Callable[[], None],
          title: str = "", show_header: bool = True) -> bool:
    """Embed ``inner_widget`` into Anki's main content area.

    ``on_close`` is invoked when the user clicks the close button. The
    caller is responsible for reparenting ``inner_widget`` out again and
    then calling :func:`restore` (typically from within ``on_close``).

    If ``show_header`` is False, no title/close bar is drawn – the embedded
    view fills the whole area edge to edge. Use this when the borrowed
    widget already provides its own way to leave the embedded mode (e.g. an
    in-app toggle button), so no extra chrome is needed.

    Returns True on success, False if embedding is not possible (e.g. the
    main layout is missing or another view is already embedded).
    """
    global _container, _on_close, _hidden_widgets, _collapsed
    if _container is not None:
        return False
    layout = _main_layout()
    if layout is None or QWidget is object:
        return False

    container = QWidget()
    try:
        container.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Expanding)
    except Exception:
        pass
    v = QVBoxLayout(container)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(0)
    if show_header:
        v.addWidget(_build_header(title, on_close))
    # Force the borrowed view to fill the area. Some web views (e.g. the
    # notebook/mindmap ones) ship with a non-expanding size policy and would
    # otherwise collapse to zero height, leaving only the header visible.
    try:
        inner_widget.setSizePolicy(QSizePolicy.Policy.Expanding,
                                   QSizePolicy.Policy.Expanding)
    except Exception:
        pass
    v.addWidget(inner_widget, 1)
    try:
        inner_widget.show()
    except Exception:
        pass

    # Hide Anki's normal central widgets, including the top toolbar
    # (Decks / Add / Browse …) which isn't needed in this focused view.
    #
    # Do not call ``hide()`` here.  Anki's TopWebView/BottomWebView override
    # that method: instead of hiding the QWidget, they start DOM/height
    # animations.  A delayed BottomWebView callback can then expand the deck
    # browser bar again after our embedded view is already visible.  Calling
    # QWidget's inherited setVisible(False) keeps the widget physically out of
    # the layout and is stable across supported Anki versions on every platform.
    hidden: List[QWidget] = []
    collapsed: List[tuple] = []
    for name in ("toolbarWeb", "web", "bottomWeb"):
        w = getattr(mw, name, None)
        if w is None:
            continue
        try:
            if w.isVisible():
                w.setVisible(False)
                hidden.append(w)
        except Exception:
            pass
        # Some widgets (notably Anki's top toolbar) keep reserving their
        # vertical slot even when hidden, leaving an empty grey band. Clamp
        # both min and max height to 0 so the layout truly reclaims the space.
        try:
            collapsed.append((name, w, w.maximumHeight(), w.minimumHeight()))
            w.setMinimumHeight(0)
            w.setMaximumHeight(0)
        except Exception:
            pass

    # Take over the whole central area.
    try:
        layout.addWidget(container, 1)
    except Exception:
        layout.addWidget(container)

    _container = container
    _on_close = on_close
    _hidden_widgets = hidden
    _collapsed = collapsed
    return True


def restore() -> None:
    """Remove the embedded container and restore Anki's normal widgets.

    The caller must already have reparented the inner widget out of the
    container, otherwise it would be destroyed together with it.
    """
    global _container, _on_close, _hidden_widgets, _collapsed
    container = _container
    if container is None:
        return
    layout = _main_layout()
    if layout is not None:
        try:
            layout.removeWidget(container)
        except Exception:
            pass
    try:
        container.setParent(None)
        container.deleteLater()
    except Exception:
        pass

    # Undo the height clamp first, then re-show, so widgets regain their slot.
    toolbar_was_collapsed = False
    for name, w, old_max, old_min in _collapsed:
        try:
            if name == "toolbarWeb":
                # Never restore a sampled animation height for the toolbar.
                # Anki must remain free to calculate its natural height.
                w.setMinimumHeight(0)
                w.setMaximumHeight(_QWIDGETSIZE_MAX)
                toolbar_was_collapsed = True
            else:
                w.setMinimumHeight(old_min)
                w.setMaximumHeight(old_max if old_max else _QWIDGETSIZE_MAX)
        except Exception:
            pass
    for w in _hidden_widgets:
        try:
            # See the matching comment in embed(): setVisible() bypasses
            # Anki's asynchronous toolbar show()/height animation override.
            w.setVisible(True)
        except Exception:
            pass

    _container = None
    _on_close = None
    _hidden_widgets = []
    _collapsed = []
    if toolbar_was_collapsed:
        # Run after Qt has processed the visibility/layout changes above.
        try:
            QTimer.singleShot(0, repair_top_toolbar)
        except Exception:
            repair_top_toolbar()


def force_close() -> None:
    """Invoke the active close callback (used during cleanup)."""
    cb = _on_close
    if cb is not None:
        try:
            cb()
        except Exception:
            restore()
