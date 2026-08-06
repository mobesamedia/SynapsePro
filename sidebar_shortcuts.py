# -*- coding: utf-8 -*-
"""Safe, central keyboard-shortcut handling for launcher tools.

Shortcuts are stored as Qt ``PortableText`` so the same profile configuration
survives a move between macOS, Windows and Linux.  Qt converts that portable
form to the platform's native symbols for display and key matching.
"""

import re
from functools import partial
from typing import Any, Dict, Optional

from . import constants

try:
    from .locales import _
except Exception:
    def _(text):  # type: ignore
        return text


_QT_AVAILABLE = False
QAction = QKeySequence = QShortcut = object
Qt = None
try:
    from aqt.qt import QAction, QKeySequence, QShortcut, Qt
    from aqt import mw
    from aqt.utils import tooltip
    _QT_AVAILABLE = True
except ImportError:
    mw = None
    tooltip = lambda *_a, **_k: None


FEATURE_LABELS = {
    "mindmap_enabled": "Mind Map",
    "gamification_sidebar_enabled": "Gamification Sidebar",
    "music_player_enabled": "Music Player",
    "pomodoro_enabled": "Pomodoro Timer",
    "ai_assistant_enabled": "AI Assistant",
    "website_viewer_enabled": "Website Viewer",
    "notebook_enabled": "Notebook",
}

_registered: Dict[str, Any] = {}
_settings: Dict[str, Any] = {}


def _sequence(raw: Any):
    if not _QT_AVAILABLE or not isinstance(raw, str) or not raw.strip():
        return None
    try:
        seq = QKeySequence.fromString(
            raw.strip(), QKeySequence.SequenceFormat.PortableText
        )
        return None if seq.isEmpty() else seq
    except Exception:
        return None


def normalise_sequence(raw: Any) -> str:
    """Return one canonical Qt shortcut chord, or an empty string."""
    seq = _sequence(raw)
    if seq is None:
        return ""
    try:
        if seq.count() != 1:
            return ""
        return seq.toString(QKeySequence.SequenceFormat.PortableText).strip()
    except Exception:
        return ""


def is_safe_sequence(raw: Any) -> bool:
    """Disallow bare typing keys while accepting modifiers and F-keys."""
    portable = normalise_sequence(raw)
    if not portable:
        return False
    parts = [part.strip() for part in portable.split("+") if part.strip()]
    modifiers = {"Ctrl", "Alt", "Meta"}
    has_modifier = any(part in modifiers for part in parts[:-1])
    is_function_key = bool(re.fullmatch(r"F(?:[1-9]|1[0-9]|2[0-4])", parts[-1]))
    return has_modifier or is_function_key


def normalise_shortcut_map(raw: Any) -> Dict[str, str]:
    """Sanitize persisted/user-provided shortcut data and remove duplicates."""
    if not isinstance(raw, dict):
        return {}
    result: Dict[str, str] = {}
    used = set()
    for key in constants.SIDEBAR_SHORTCUT_KEYS:
        value = normalise_sequence(raw.get(key))
        if not value or not is_safe_sequence(value) or value in used:
            continue
        result[key] = value
        used.add(value)
    return result


def display_sequence(raw: Any) -> str:
    """Return a native-looking label, e.g. ``⌘N`` on macOS."""
    seq = _sequence(normalise_sequence(raw))
    if seq is None:
        return ""
    try:
        return seq.toString(QKeySequence.SequenceFormat.NativeText).strip()
    except Exception:
        return normalise_sequence(raw)


def find_existing_conflict(raw: Any, parent=None) -> Optional[str]:
    """Best-effort detection of an existing Anki/Qt shortcut.

    SynapsePro's own registrations are ignored so editing an existing value is
    possible.  WebView-only JavaScript shortcuts cannot be enumerated by Qt,
    so runtime ambiguity is also reported through ``activatedAmbiguously``.
    """
    target = _sequence(normalise_sequence(raw))
    owner = parent or mw
    if target is None or owner is None or not hasattr(owner, "findChildren"):
        return None
    try:
        for action in owner.findChildren(QAction):
            if action.property("synapseSidebarShortcut"):
                continue
            candidates = list(action.shortcuts()) if hasattr(action, "shortcuts") else []
            for candidate in candidates:
                if candidate == target:
                    text = (action.text() or "").replace("&", "").strip()
                    return text or _("Anki action")
        for shortcut in owner.findChildren(QShortcut):
            if shortcut.property("synapseSidebarShortcut"):
                continue
            if shortcut.key() == target:
                name = shortcut.objectName().strip() if shortcut.objectName() else ""
                return name or _("Anki shortcut")
    except Exception:
        return None
    return None


def _trigger(feature_key: str) -> None:
    if not _settings.get(feature_key, True):
        return
    try:
        if feature_key == "mindmap_enabled":
            from .mindmap_sidebar import toggle_mindmap_dock
            toggle_mindmap_dock()
        elif feature_key == "gamification_sidebar_enabled":
            from .study_plan_trigger import trigger_gamification_sidebar_action
            trigger_gamification_sidebar_action()
        elif feature_key == "music_player_enabled":
            from .background_music import toggle_music_menu
            toggle_music_menu(None)
        elif feature_key == "pomodoro_enabled":
            from .pomodoro import open_pomodoro_config
            open_pomodoro_config()
        elif feature_key == "ai_assistant_enabled":
            from .ai_assistant import toggle_ai_assistant_dock
            toggle_ai_assistant_dock()
        elif feature_key == "website_viewer_enabled":
            from .website_sidebar import toggle_website_dock
            toggle_website_dock()
        elif feature_key == "notebook_enabled":
            from .notebook_sidebar import toggle_notebook_dock
            toggle_notebook_dock()
    except Exception as exc:
        print(f"SynapsePro shortcut '{feature_key}' failed: {exc}")
        try:
            tooltip(_("Could not open this sidebar tool."))
        except Exception:
            pass


def _ambiguous(feature_key: str, portable: str) -> None:
    label = _(FEATURE_LABELS.get(feature_key, "Sidebar"))
    try:
        tooltip(
            _("Shortcut {shortcut} for {feature} conflicts with another Anki shortcut.").format(
                shortcut=display_sequence(portable) or portable,
                feature=label,
            )
        )
    except Exception:
        pass


def cleanup() -> None:
    """Disable and dispose all shortcut objects owned by the active profile."""
    global _registered
    for shortcut in list(_registered.values()):
        try:
            shortcut.setEnabled(False)
            shortcut.setParent(None)
            shortcut.deleteLater()
        except (RuntimeError, AttributeError):
            pass
    _registered = {}


def refresh(settings: Optional[Dict[str, Any]]) -> None:
    """Atomically rebuild shortcuts from the latest saved settings."""
    global _settings
    cleanup()
    _settings = dict(settings or {})
    if not _QT_AVAILABLE or mw is None:
        return

    values = normalise_shortcut_map(_settings.get("sidebar_shortcuts", {}))
    for feature_key in constants.SIDEBAR_SHORTCUT_KEYS:
        portable = values.get(feature_key, "")
        if not portable or not _settings.get(feature_key, True):
            continue
        try:
            shortcut = QShortcut(_sequence(portable), mw)
            shortcut.setObjectName(f"SynapseSidebarShortcut_{feature_key}")
            shortcut.setProperty("synapseSidebarShortcut", True)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(partial(_trigger, feature_key))
            shortcut.activatedAmbiguously.connect(
                partial(_ambiguous, feature_key, portable)
            )
            _registered[feature_key] = shortcut
        except Exception as exc:
            print(f"SynapsePro: could not register shortcut {portable}: {exc}")
