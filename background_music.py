# -*- coding: utf-8 -*-
"""SynapsePro — Focus Music player.

The dialog hosts a web-based Apple-style UI (music_player.html) in a
QWebEngineView.  Audio itself is played natively via QMediaPlayer (local
tracks) or through the embedded SoundCloud widget (soundcloud_player.html)
shown in a second web view below the UI when SoundCloud mode is active.

Bridge (JS -> Python):  console.log('SYNAPSEPRO_MUSIC:' + JSON.stringify({...}))
Bridge (Python -> JS):  initMusic(payload) / musicState(s) / userTracks(list)
                        / scState(s) / applyColors(c)
"""

import json
import os
import shutil
import threading
import traceback
import urllib.parse
import urllib.request
from typing import Optional

# --- Local Imports ---
from . import constants

# --- PyQt Imports ---
_music_window: Optional['MiniMusicPlayer'] = None
_has_multimedia = False
InfiniteLoop = -1

try:
    from aqt.qt import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                        QLabel, QLineEdit, QFileDialog, QPixmap, QPainter,
                        QPainterPath, QUrl, Qt, QTimer, QRectF)
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    _has_multimedia = True
    InfiniteLoop = QMediaPlayer.Loops.Infinite
except ImportError:
    _has_multimedia = False
    QDialog = object

# --- QtWebEngine (powers the whole UI and the SoundCloud streaming mode) ------
_has_webengine = False
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings
    _has_webengine = True
except ImportError:
    _has_webengine = False
    QWebEngineView = QWebEngineProfile = QWebEnginePage = QWebEngineSettings = object  # type: ignore

# --- Anki Imports ---
try:
    from aqt import mw
    from aqt.utils import tooltip
except ImportError:
    mw = None
    tooltip = lambda *args: print("Tooltip:", args)

try:
    from .locales import _
except ImportError:
    def _(text):  # type: ignore
        return text


# --- Theme ---
try:
    from .theme import palette as _palette, FONT_FAMILY as _FONT_FAMILY
except ImportError:
    def _palette(night): return {}  # type: ignore
    _FONT_FAMILY = "sans-serif"

# --- Files -------------------------------------------------------------------
UI_HTML_FILENAME = "music_player.html"
SC_HTML_FILENAME = "soundcloud_player.html"

# --- SoundCloud streaming config ---------------------------------------------
DEFAULT_SC_URL = "https://soundcloud.com/synapse-pro/sets/focus"
SC_STATIONS = [
    ("Lo-Fi Focus", DEFAULT_SC_URL),
    ("Meditation",  "https://soundcloud.com/synapse-pro/sets/delta"),
    ("Brainwaves", "https://soundcloud.com/synapse-pro/sets/brainwaves"),
]
SC_STATION_URLS = frozenset(url for _label, url in SC_STATIONS)
LEGACY_SC_URLS = {
    "https://soundcloud.com/chillhopdotcom/sets/lofihiphop",
    "https://soundcloud.com/lofi_girl",
    "https://soundcloud.com/chill-playlister/sets/chillhop-radio-jazzy-lofi-hip",
}
CK_SC_URL = "synapse_music_sc_url"
CK_SC_CUSTOM_URLS = "synapse_music_sc_custom_urls"
MAX_SC_CUSTOM_URLS = 30

# --- Persisted player state --------------------------------------------------
# {"track": id, "vol": 0-100, "scVol": 0-100, "resume": bool,
#  "mode": "local"|"soundcloud", "pos": ms, "playing": bool}
CK_STATE = "synapse_music_state"

# Built-in ambient tracks: (audio file, display name, cover image)
BUILTIN_TRACKS = [
    ("alpha_waves.mp3",    _("Alpha Waves"), "alpha.png"),
    ("beta_waves.mp3",     _("Beta Waves"),  "beta.png"),
    ("library_sounds.mp3", _("Library"),     "library.png"),
    ("jazz.mp3",           _("Jazz"),        "jazz.png"),
    ("rain.mp3",           _("Rain"),        "rain.png"),
    ("cozy.mp3",           _("Cozy"),        "cozy.png"),
]

FADE_MS = 450          # play / pause fade duration
FADE_SWAP_MS = 280     # fade-out before a track change


def _normalize_sc_url(raw_url: str, _depth: int = 0) -> Optional[str]:
    """Return a canonical, widget-safe SoundCloud URL or ``None``.

    Direct track, profile, set and short-share URLs are accepted. SoundCloud
    embed URLs are unwrapped to their actual ``url`` parameter so pasting an
    iframe/player link does not feed a player URL back into ``SC.Widget.load``.
    No network request is made here, keeping the UI responsive and private.
    """
    if not isinstance(raw_url, str) or _depth > 1:
        return None
    value = raw_url.strip()
    if not value or any(char in value for char in "<>\r\n"):
        return None
    if "://" not in value:
        value = "https://" + value.lstrip("/")

    try:
        parsed = urllib.parse.urlsplit(value)
    except Exception:
        return None
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower().rstrip(".")
    if scheme not in ("http", "https"):
        return None
    if host != "soundcloud.com" and not host.endswith(".soundcloud.com"):
        return None

    # Users sometimes paste the iframe src rather than the underlying track or
    # playlist URL. Unwrap the official player URL before passing it to Widget.
    if host == "w.soundcloud.com" and parsed.path.rstrip("/") == "/player":
        embedded = urllib.parse.parse_qs(parsed.query).get("url", [])
        return _normalize_sc_url(embedded[0], _depth + 1) if embedded else None

    path = parsed.path.rstrip("/")
    if not path:
        return None
    if host in ("www.soundcloud.com", "m.soundcloud.com"):
        host = "soundcloud.com"

    # Drop share/tracking parameters but retain private-track access tokens.
    query = urllib.parse.urlencode([
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
        if key == "secret_token"
    ])
    return urllib.parse.urlunsplit(("https", host, path, query, ""))


def _sc_url_label(url: str) -> str:
    """Create a compact, stable label from a canonical SoundCloud URL."""
    try:
        parts = [urllib.parse.unquote(p) for p in urllib.parse.urlsplit(url).path.split("/") if p]
        if "sets" in parts and parts.index("sets") + 1 < len(parts):
            slug = parts[parts.index("sets") + 1]
        else:
            slug = parts[-1] if parts else "SoundCloud"
        words = " ".join(slug.replace("_", "-").split("-")).strip()
        label = words.title() or "SoundCloud"
    except Exception:
        label = "SoundCloud"
    return label if len(label) <= 28 else label[:27].rstrip() + "…"


def _load_state() -> dict:
    try:
        if mw and mw.col:
            v = mw.col.get_config(CK_STATE, default=None)
            if isinstance(v, str):
                v = json.loads(v)
            if isinstance(v, dict):
                return v
    except Exception as e:
        print(f"Music: could not load state: {e}")
    return {}


def _save_state(state: dict) -> None:
    try:
        if mw and mw.col:
            mw.col.set_config(CK_STATE, state)
    except Exception as e:
        print(f"Music: could not save state: {e}")


def _load_sc_url() -> str:
    try:
        if mw and mw.col:
            v = mw.col.get_config(CK_SC_URL, default=DEFAULT_SC_URL)
            if isinstance(v, str) and v.strip():
                normalized = _normalize_sc_url(v)
                # Migrate the former built-in examples only once. If the new
                # custom list exists, the user may have deliberately saved one
                # of those URLs and it must remain selectable.
                custom_value = mw.col.get_config(CK_SC_CUSTOM_URLS, default=None)
                if normalized in LEGACY_SC_URLS and custom_value is None:
                    return DEFAULT_SC_URL
                if normalized:
                    return normalized
    except Exception as e:
        print(f"Music: could not load SoundCloud URL: {e}")
    return DEFAULT_SC_URL


def _save_sc_url(url: str) -> None:
    try:
        if mw and mw.col:
            mw.col.set_config(CK_SC_URL, url)
    except Exception as e:
        print(f"Music: could not save SoundCloud URL: {e}")


def _load_sc_custom_urls() -> list[str]:
    """Load, validate and deduplicate the saved custom SoundCloud URLs."""
    try:
        if not (mw and mw.col):
            return []
        value = mw.col.get_config(CK_SC_CUSTOM_URLS, default=[])
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, list):
            return []
        result = []
        seen = set()
        for item in value:
            raw_url = item.get("url") if isinstance(item, dict) else item
            normalized = _normalize_sc_url(raw_url)
            if (not normalized or normalized in SC_STATION_URLS
                    or normalized in seen):
                continue
            seen.add(normalized)
            result.append(normalized)
            if len(result) >= MAX_SC_CUSTOM_URLS:
                break
        return result
    except Exception as e:
        print(f"Music: could not load custom SoundCloud URLs: {e}")
        return []


def _save_sc_custom_urls(urls: list[str]) -> None:
    try:
        if mw and mw.col:
            mw.col.set_config(CK_SC_CUSTOM_URLS, list(urls[:MAX_SC_CUSTOM_URLS]))
    except Exception as e:
        print(f"Music: could not save custom SoundCloud URLs: {e}")


# --- Persistent web profile (keeps a SoundCloud login across restarts) -------
_music_web_profile: Optional['QWebEngineProfile'] = None


def _get_music_web_profile() -> Optional['QWebEngineProfile']:
    global _music_web_profile
    if _music_web_profile is not None:
        return _music_web_profile
    if not _has_webengine or mw is None:
        return None
    try:
        profile_root = mw.pm.profileFolder() if mw and mw.pm else None
        if not profile_root:
            raise RuntimeError("Anki profile folder is unavailable")
        profile_dir = os.path.join(
            profile_root, "SynapsePro_Data", "web_profiles", "music")
        os.makedirs(profile_dir, exist_ok=True)
        prof = QWebEngineProfile(f"profile_{constants.ADDON_NAME_LAUNCHER}_Music_v1", mw)
        prof.setPersistentStoragePath(profile_dir)
        try:
            prof.setPersistentCookiesPolicy(
                QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        except Exception:
            try:
                prof.setPersistentCookiesPolicy(QWebEngineProfile.AllowPersistentCookies)
            except Exception:
                pass
        # Let us start playback programmatically (station picker auto-play) without
        # requiring a click *inside* the embedded page.
        try:
            st = prof.settings()
            st.setAttribute(
                QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        except Exception:
            pass
        _music_web_profile = prof
    except Exception:
        traceback.print_exc()
        _music_web_profile = None
    return _music_web_profile


def _set_web_attr(settings_obj, name: str, value: bool) -> bool:
    """Set a Qt6 QWebEngineSettings attribute by name."""
    if settings_obj is None or QWebEngineSettings is object:
        return False
    try:
        attr = getattr(QWebEngineSettings.WebAttribute, name)
    except AttributeError:
        return False
    try:
        settings_obj.setAttribute(attr, value)
        return True
    except Exception:
        return False


# --- Bridge page: routes prefixed console.log messages to a Python callback ---
if _has_webengine and QWebEnginePage is not object:

    class _ConsoleBridgePage(QWebEnginePage):  # type: ignore[misc]
        def __init__(self, profile, parent, prefix, on_message):
            super().__init__(profile, parent)
            self._prefix = prefix
            self._on_message = on_message

        def javaScriptConsoleMessage(self, level, message, line, source):  # type: ignore[override]
            msg = str(message or "")
            if msg.startswith(self._prefix):
                try:
                    data = json.loads(msg[len(self._prefix):])
                except Exception:
                    return
                cb = getattr(self, "_on_message", None)
                if cb:
                    try:
                        cb(data)
                    except Exception:
                        traceback.print_exc()
                return
else:
    _ConsoleBridgePage = object  # type: ignore


# --- Helper Functions ---

def _rounded_pixmap(pix: 'QPixmap', radius: int = 16) -> 'QPixmap':
    """Return a copy of *pix* with rounded corners (Apple-style artwork)."""
    try:
        if pix.isNull():
            return pix
        rounded = QPixmap(pix.size())
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, pix.width(), pix.height()), radius, radius)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pix)
        painter.end()
        return rounded
    except Exception:
        return pix


def _get_music_file_path(filename: str) -> Optional[str]:
    if not constants.icons_folder: return None
    full_path = os.path.join(constants.icons_folder, filename)
    return full_path if os.path.isfile(full_path) else None

def _get_image_path(image_name: str) -> Optional[str]:
    base_dir = os.path.dirname(__file__)
    media_dir = os.path.join(base_dir, "media")
    full_path = os.path.join(media_dir, image_name)
    return full_path if os.path.isfile(full_path) else None

# --- User track storage (survives addon & Anki updates) ---

def _get_user_music_folder() -> Optional[str]:
    """Returns (and creates) a folder in the Anki profile dir for user MP3s."""
    try:
        if mw and mw.pm and mw.pm.profileFolder():
            folder = os.path.join(mw.pm.profileFolder(), "synapse_user_music")
            os.makedirs(folder, exist_ok=True)
            return folder
    except Exception:
        pass
    return None

def _load_user_tracks() -> list:
    """Loads user track metadata from Anki config."""
    try:
        if mw and mw.col:
            raw = mw.col.get_config("synapse_user_tracks", default="[]")
            data = json.loads(raw) if isinstance(raw, str) else raw
            return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
    except Exception as e:
        print(f"Music: could not load user tracks: {e}")
    return []

def _save_user_tracks(tracks: list) -> None:
    """Persists user track metadata in Anki config."""
    try:
        if mw and mw.col:
            mw.col.set_config("synapse_user_tracks", json.dumps(tracks))
    except Exception as e:
        print(f"Music: could not save user tracks: {e}")

# --- Add Track Dialog ---

def _build_add_dialog_style(night: bool) -> str:
    c = _palette(night)
    return f"""
    QDialog {{ background-color: {c.get('bg', '#F5F5F7')}; font-family: {_FONT_FAMILY};
               color: {c.get('text', '#1D1D1F')}; }}
    QLabel {{ color: {c.get('text', '#1D1D1F')}; font-weight: 600; font-size: 13px; }}
    QLineEdit {{
        background-color: {c.get('surface', '#FFF')}; color: {c.get('text', '#1D1D1F')};
        border: 1px solid {c.get('grey_mid', '#D1D1D6')};
        border-radius: 8px; padding: 4px 8px; min-height: 20px; font-size: 12px;
    }}
    QPushButton {{
        background-color: {c.get('surface', '#FFF')}; border: 1px solid {c.get('grey_mid', '#D1D1D6')};
        border-radius: 8px; padding: 6px; min-width: 30px; color: {c.get('text', '#1D1D1F')};
    }}
    QPushButton:hover {{ background-color: {c.get('grey_light', '#E5E5EA')}; }}
    """


class AddTrackDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Import Track"))
        self.setFixedSize(340, 150)
        self._filepath = ""

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 14, 14, 14)

        # Title row
        title_row = QHBoxLayout()
        title_lbl = QLabel(_("Title:"))
        title_lbl.setFixedWidth(44)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText(_("Track name…"))
        title_row.addWidget(title_lbl)
        title_row.addWidget(self.title_edit)
        layout.addLayout(title_row)

        # File row
        file_row = QHBoxLayout()
        file_lbl = QLabel(_("File:"))
        file_lbl.setFixedWidth(44)
        self.file_label = QLabel(_("No file selected"))
        self.file_label.setStyleSheet("font-size: 11px; color: #888;")
        browse_btn = QPushButton(_("Browse…"))
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse)
        file_row.addWidget(file_lbl)
        file_row.addWidget(self.file_label, 1)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(70)
        cancel_btn.clicked.connect(self.reject)
        self.import_btn = QPushButton(_("Import"))
        self.import_btn.setFixedWidth(70)
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.import_btn)
        layout.addLayout(btn_row)

    def _browse(self):
        path, _filter = QFileDialog.getOpenFileName(
            self, "Select Audio File", "",
            "Audio Files (*.mp3 *.m4a *.ogg *.wav *.flac *.aac)"
        )
        if path:
            self._filepath = path
            fname = os.path.basename(path)
            display = fname if len(fname) <= 36 else fname[:33] + "…"
            self.file_label.setText(display)
            if not self.title_edit.text():
                auto_title = os.path.splitext(fname)[0].replace("_", " ").replace("-", " ").title()
                self.title_edit.setText(auto_title)
            self.import_btn.setEnabled(True)

    def get_data(self):
        title = self.title_edit.text().strip() or os.path.splitext(os.path.basename(self._filepath))[0]
        return title, self._filepath

# --- Music Player (web UI + native audio backend) ----------------------------

class MiniMusicPlayer(QDialog):
    SIZE_LOCAL = (316, 636)
    SIZE_SC    = (340, 620)
    SC_CHROME_H = 258   # height of the web UI (chrome) while in SoundCloud mode

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Focus Music"))
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowCloseButtonHint)

        self.player: Optional[QMediaPlayer] = None
        self.audio_output: Optional['QAudioOutput'] = None
        self._backend_error = False

        # State (restored from config)
        st = _load_state()
        self._mode = st.get("mode", "local") if st.get("mode") in ("local", "soundcloud") else "local"
        self._user_vol = int(st.get("vol", 50))
        self._sc_vol = int(st.get("scVol", st.get("vol", 50)))
        self._resume_enabled = bool(st.get("resume", True))
        self._track_id = st.get("track") or None
        self._want_playing = False          # target play state (survives fades)
        self._pending_pos = 0               # ms to seek to after next load
        self._swap_autoplay = False
        self._fade_timer: Optional[QTimer] = None
        self._save_timer: Optional[QTimer] = None
        self._loaded_track: Optional[str] = None

        # SoundCloud state
        self._sc_loaded = False
        self._sc_playing = False
        self._sc_boot_done = False     # saved volume/URL applied once after READY
        self._sc_poll: Optional[QTimer] = None
        self._sc_url = _load_sc_url()
        self._sc_custom_urls = _load_sc_custom_urls()
        # Preserve the one custom URL used by older versions by migrating it
        # into the new multi-URL list on first launch.
        if (self._sc_url not in SC_STATION_URLS
                and self._sc_url not in self._sc_custom_urls
                and len(self._sc_custom_urls) < MAX_SC_CUSTOM_URLS):
            self._sc_custom_urls.append(self._sc_url)
            _save_sc_custom_urls(self._sc_custom_urls)
        self._sc_now = "SoundCloud"
        self._sc_artwork_url = ""      # remote cover URL of the current track
        self._sc_artwork_path = None   # local cached copy for the sidebar icon

        # UI readiness
        self._ui_ready = False

        self.init_backend()
        self.init_ui()

        # Validate the restored track id and pre-load it (paused).
        if self._track_id is None or self._find_track(self._track_id) is None:
            first = self._all_tracks()
            self._track_id = first[0]["id"] if first else None
        if self._track_id:
            self._pending_pos = int(st.get("pos", 0) or 0)
            self._begin_swap(self._track_id, autoplay=False)

        self._apply_dialog_style()
        if self._mode == "soundcloud":
            self._enter_sc_layout()
        else:
            self._enter_local_layout()

    # --- small helpers -------------------------------------------------------

    def is_playing(self):
        if not self.player: return False
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def _apply_dialog_style(self):
        night = self._is_night()
        c = _palette(night)
        self.setStyleSheet(f"QDialog {{ background-color: {c.get('bg', '#F5F5F7')}; }}")

    @staticmethod
    def _is_night() -> bool:
        try:
            if mw and mw.pm.night_mode(): return True
        except Exception:
            pass
        return False

    # --- Audio backend -------------------------------------------------------

    def init_backend(self):
        if not _has_multimedia:
            return
        try:
            self.player = QMediaPlayer()
            self.audio_output = QAudioOutput()
            self.player.setAudioOutput(self.audio_output)
            self.audio_output.setVolume(self._user_vol / 100.0)
            self.player.playbackStateChanged.connect(self._on_state_changed)
            # Seek bar: keep the web UI in sync with the playback position.
            try:
                self.player.positionChanged.connect(lambda _p: self._push_position())
                self.player.durationChanged.connect(lambda _d: self._push_position(force=True))
            except Exception:
                pass
        except Exception:
            traceback.print_exc()
            self._backend_error = True

    def _set_raw_vol(self, frac: float):
        """0.0 … 1.0 regardless of Qt version."""
        frac = max(0.0, min(1.0, frac))
        try:
            if self.audio_output:
                self.audio_output.setVolume(frac)
        except Exception:
            pass

    def _get_raw_vol(self) -> float:
        try:
            if self.audio_output:
                return float(self.audio_output.volume())
        except Exception:
            pass
        return 0.0

    def _stop_fade(self):
        if self._fade_timer is not None:
            try:
                self._fade_timer.stop()
                self._fade_timer.deleteLater()
            except Exception:
                pass
            self._fade_timer = None

    def _fade_to(self, target: float, duration_ms: int, done=None):
        """Smoothly ramp the raw output volume to *target* (0.0 … 1.0)."""
        self._stop_fade()
        start = self._get_raw_vol()
        if abs(start - target) < 0.01 or duration_ms <= 0:
            self._set_raw_vol(target)
            if done: done()
            return
        steps = max(2, duration_ms // 35)
        self._fade_step = 0

        timer = QTimer(self)
        self._fade_timer = timer

        def tick():
            self._fade_step += 1
            f = self._fade_step / steps
            # ease-in-out curve for an Apple-like feel
            eased = f * f * (3 - 2 * f)
            self._set_raw_vol(start + (target - start) * eased)
            if self._fade_step >= steps:
                if self._fade_timer is timer:
                    self._stop_fade()
                else:
                    timer.stop(); timer.deleteLater()
                if done: done()

        timer.timeout.connect(tick)
        timer.start(35)

    # --- Track model ---------------------------------------------------------

    def _builtin_tracks(self) -> list:
        out = []
        for fname, title, img in BUILTIN_TRACKS:
            path = _get_music_file_path(fname)
            if not path:
                continue
            cover = _get_image_path(img)
            out.append({
                "id": fname, "title": title, "file": path,
                "cover": QUrl.fromLocalFile(cover).toString() if cover else "",
                "cover_path": cover,
            })
        return out

    def _user_track_entries(self) -> list:
        out = []
        folder = _get_user_music_folder()
        own_cover = _get_image_path("own.png")
        for ut in _load_user_tracks():
            f = ut.get("file")
            if not isinstance(f, str) or not f or os.path.basename(f) != f:
                continue
            path = os.path.join(folder, f) if folder else None
            out.append({
                "id": "u:" + f, "title": ut.get("title") or f, "file": path,
                "cover": QUrl.fromLocalFile(own_cover).toString() if own_cover else "",
                "cover_path": own_cover, "user": True,
            })
        return out

    def _all_tracks(self) -> list:
        return self._builtin_tracks() + self._user_track_entries()

    def _find_track(self, tid) -> Optional[dict]:
        for t in self._all_tracks():
            if t["id"] == tid:
                return t
        return None

    def get_image_for_file(self, tid) -> Optional[str]:
        """Cover path for the sidebar artwork callback."""
        t = self._find_track(tid)
        return t.get("cover_path") if t else None

    # --- UI ------------------------------------------------------------------

    def init_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        prof = _get_music_web_profile()

        # Main web UI
        self.ui_view = QWebEngineView() if _has_webengine else None
        if self.ui_view is not None and prof is not None:
            self._ui_page = _ConsoleBridgePage(prof, self.ui_view,
                                               "SYNAPSEPRO_MUSIC:", self._on_ui_message)
            self.ui_view.setPage(self._ui_page)
            s = self._ui_page.settings()
            _set_web_attr(s, "LocalContentCanAccessRemoteUrls", True)
            _set_web_attr(s, "LocalContentCanAccessFileUrls", True)
            _set_web_attr(s, "PlaybackRequiresUserGesture", False)
            html_path = os.path.join(constants.addon_path, UI_HTML_FILENAME)
            if os.path.isfile(html_path):
                self.ui_view.setUrl(QUrl.fromLocalFile(html_path))
            lay.addWidget(self.ui_view, 1)
        else:
            warn = QLabel(_("QtWebEngine is required for the music player."))
            warn.setWordWrap(True)
            lay.addWidget(warn)

        # SoundCloud widget view (below the chrome, only visible in SC mode)
        self.sc_view = None
        self._sc_page = None
        if _has_webengine and prof is not None:
            self.sc_view = QWebEngineView()
            self._sc_page = _ConsoleBridgePage(prof, self.sc_view,
                                               "SCBRIDGE:", self._on_sc_message)
            self.sc_view.setPage(self._sc_page)
            self.sc_view.loadFinished.connect(self._on_sc_load_finished)
            s = self._sc_page.settings()
            _set_web_attr(s, "LocalContentCanAccessRemoteUrls", True)
            _set_web_attr(s, "LocalContentCanAccessFileUrls", True)
            _set_web_attr(s, "PlaybackRequiresUserGesture", False)
            self.sc_view.setVisible(False)
            lay.addWidget(self.sc_view, 1)

    def _enter_local_layout(self):
        if self.ui_view is not None:
            self.ui_view.setMinimumHeight(0)
            self.ui_view.setMaximumHeight(16777215)
        if self.sc_view is not None:
            self.sc_view.setVisible(False)
        self.setFixedSize(*self.SIZE_LOCAL)

    def _enter_sc_layout(self):
        if self.ui_view is not None:
            self.ui_view.setFixedHeight(self.SC_CHROME_H)
        if self.sc_view is not None:
            self.sc_view.setVisible(True)
        self.setFixedSize(*self.SIZE_SC)
        self._ensure_sc_loaded()

    # --- JS push helpers -----------------------------------------------------

    def _ui_js(self, code: str):
        try:
            if self.ui_view and self.ui_view.page():
                self.ui_view.page().runJavaScript(code)
        except Exception:
            pass

    def _sc_js(self, code: str):
        try:
            if self.sc_view and self.sc_view.page():
                self.sc_view.page().runJavaScript(code)
        except Exception:
            pass

    def _on_sc_load_finished(self, ok: bool) -> None:
        if not ok:
            return
        sources = (
            "Could not load the SoundCloud player.", "Check your internet connection.",
            "SoundCloud could not load this URL", "Widget API failed to load",
            "SynapsePro error", "Show details", "Hide details", "Copy error",
            "Copied!", "Dismiss", "Unexpected error", "Unexpected error (async)",
            "Your data is safe. Please screenshot the details and send them to help.synapse.pro@gmail.com.",
            "(no stack trace available)",
        )
        payload = {source: _(source) for source in sources}
        payload["__isDark"] = self._is_night()
        self._sc_js("window.initSoundCloudI18n && initSoundCloudI18n(%s);" % json.dumps(payload))

    def _push_music_state(self):
        self._ui_js("window.musicState && musicState(%s);" % json.dumps(
            {"current": self._track_id, "playing": bool(self._want_playing)}))

    def _push_user_tracks(self):
        lst = [{"id": t["id"], "title": t["title"], "cover": t["cover"]}
               for t in self._user_track_entries()]
        self._ui_js("window.userTracks && userTracks(%s);" % json.dumps(lst))

    def _push_position(self, force: bool = False):
        if not self._ui_ready or not self.isVisible():
            return
        import time as _time
        now = _time.monotonic()
        if not force and (now - getattr(self, "_last_pos_push", 0.0)) < 0.25:
            return
        self._last_pos_push = now
        try:
            pos = int(self.player.position()) if self.player else 0
            dur = int(self.player.duration()) if self.player else 0
        except Exception:
            pos = dur = 0
        self._ui_js("window.positionState && positionState(%s);"
                    % json.dumps({"pos": pos, "dur": dur}))

    def _push_sc_state(self, **kw):
        self._ui_js("window.scState && scState(%s);" % json.dumps(kw))

    def _custom_sc_station_payload(self) -> list[dict]:
        return [
            {"label": _sc_url_label(url), "url": url}
            for url in self._sc_custom_urls
        ]

    # --- Init payload --------------------------------------------------------

    def _theme_colors(self) -> dict:
        night = self._is_night()
        c = _palette(night)
        return {
            "accent": c.get("blue_accent", c.get("blue", "#0071D3")),
            "bg": c.get("bg", "#191919" if night else "#F5F5F7"),
            "card": c.get("surface", "#2C2C2C" if night else "#FFFFFF"),
            "text": c.get("text", "#E0E0E0" if night else "#1D1D1F"),
            "muted": c.get("text_muted", "#AAAAAA" if night else "#86868B"),
            "track": c.get("grey_light", "#303030" if night else "#E5E5EA"),
        }

    def _send_init(self):
        payload = {
            "isDark": self._is_night(),
            "colors": self._theme_colors(),
            "labels": {
                "local": _("Local"),
                "subtitle": _("Focus Music"),
                "sounds": _("Sounds"),
                "myTracks": _("My Tracks"),
                "resume": _("Resume playback on startup"),
                "play": _("Play / Pause"),
                "prev": _("Previous track"),
                "next": _("Next track"),
                "add": _("Add"),
                "remove": _("Remove"),
                "customUrl": _("Custom URL…"),
                "addTrack": _("Add your own track"),
                "removeTrack": _("Remove this track"),
                "volume": _("Volume"),
                "scHint": _("Player loads below"),
                "scUnavailable": _("Requires QtWebEngine (not available in this Anki build)."),
            },
            "tracks": [{"id": t["id"], "title": t["title"], "cover": t["cover"]}
                       for t in self._builtin_tracks()],
            "userTracks": [{"id": t["id"], "title": t["title"], "cover": t["cover"]}
                           for t in self._user_track_entries()],
            "state": {
                "current": self._track_id,
                "playing": bool(self._want_playing),
                "volume": self._user_vol,
                "scVolume": self._sc_vol,
                "resume": self._resume_enabled,
                "mode": self._mode,
            },
            "sc": {
                "enabled": self.sc_view is not None,
                "stations": [{"label": _(l), "url": u} for l, u in SC_STATIONS],
                "customStations": self._custom_sc_station_payload(),
                "url": self._sc_url,
                "playing": self._sc_playing,
                "now": self._sc_now,
            },
        }
        self._ui_js("window.initMusic && initMusic(%s);" % json.dumps(payload))

    # --- Bridge: messages from the UI ---------------------------------------

    def _on_ui_message(self, data: dict):
        a = data.get("a")
        if a == "ready":
            self._ui_ready = True
            self._send_init()
        elif a == "select":
            self.select_track(data.get("id"))
        elif a == "play":
            self.play_with_fade()
        elif a == "pause":
            self.pause_with_fade()
        elif a == "step":
            self.step_track(1 if int(data.get("d", 1)) >= 0 else -1)
        elif a == "volume":
            self.change_volume(int(data.get("v", 50)))
        elif a == "seek":
            self.seek_to(int(data.get("ms", 0)))
        elif a == "resume":
            self._resume_enabled = bool(data.get("on"))
            self.save_state()
        elif a == "addTrack":
            self._open_add_track_dialog()
        elif a == "delTrack":
            self._delete_user_track(data.get("id"))
        elif a == "mode":
            self._set_mode(data.get("m") or "local")
        elif a == "sc":
            cmd = data.get("cmd")
            if cmd == "toggle": self._sc_js("scToggle();")
            elif cmd == "prev": self._sc_js("scPrev();")
            elif cmd == "next": self._sc_js("scNext();")
        elif a == "scVolume":
            self._sc_vol = int(data.get("v", 50))
            self._sc_js(f"scVolume({self._sc_vol});")
            self._save_soon()
        elif a == "scStation":
            self._set_sc_url(data.get("url") or "")
        elif a == "scCustom":
            self._set_sc_url(
                data.get("url") or "",
                show_validation_error=True,
                save_custom=True,
            )
        elif a == "scDeleteCustom":
            self._delete_sc_custom_url(data.get("url") or "")
        elif a == "err":
            print(f"Music UI error: {data.get('m')}")

    # --- Local playback ------------------------------------------------------

    def select_track(self, tid):
        if not tid or self._find_track(tid) is None:
            return
        if tid == self._track_id:
            # Tapping the active tile toggles play/pause (Apple-like).
            if self.is_playing():
                self.pause_with_fade()
            else:
                self.play_with_fade()
            return
        was_playing = self.is_playing() or self._want_playing
        self._track_id = tid
        self._pending_pos = 0
        self._push_music_state()
        if was_playing and self.is_playing():
            # Fade the old track out, then swap and fade the new one in.
            self._fade_to(0.0, FADE_SWAP_MS,
                          done=lambda: self._begin_swap(tid, autoplay=True))
        else:
            self._begin_swap(tid, autoplay=was_playing)

    def step_track(self, direction: int):
        tracks = self._all_tracks()
        if not tracks:
            return
        ids = [t["id"] for t in tracks]
        try:
            idx = ids.index(self._track_id)
        except ValueError:
            idx = 0
        self.select_track(ids[(idx + direction) % len(ids)])

    def _begin_swap(self, tid, autoplay: bool):
        """Safe 3-phase source swap (mirrors the old, proven QTimer sequence)."""
        if not self.player:
            return
        self._swap_autoplay = autoplay
        self._want_playing = autoplay
        try:
            self.player.stop()
        except Exception:
            pass
        QTimer.singleShot(120, self._swap_phase_clear)

    def _swap_phase_clear(self):
        if not self.player: return
        try:
            self.player.setSource(QUrl(""))
        except Exception:
            pass
        QTimer.singleShot(180, self._swap_phase_load)

    def _swap_phase_load(self):
        if not self.player: return
        t = self._find_track(self._track_id)
        path = t.get("file") if t else None
        if path and os.path.isfile(path):
            url = QUrl.fromLocalFile(path)
            try:
                self.player.setSource(url)
                self.player.setLoops(InfiniteLoop)
                self._loaded_track = self._track_id
            except Exception:
                traceback.print_exc()
        QTimer.singleShot(280, self._swap_phase_finish)

    def _swap_phase_finish(self):
        if not self.player: return
        if self._swap_autoplay:
            self._start_faded_playback()
        self._push_music_state()
        _notify_artwork()
        self.save_state()

    def _start_faded_playback(self):
        if not self.player: return
        self._want_playing = True
        self._set_raw_vol(0.0)
        try:
            self.player.play()
        except Exception:
            traceback.print_exc()
            return
        # Resume-at-position: seek once playback has actually started
        # (seeking a stopped player is unreliable on some backends).
        if self._pending_pos > 0:
            pos = int(self._pending_pos)
            self._pending_pos = 0
            try:
                QTimer.singleShot(60, lambda: self.player and self.player.setPosition(pos))
            except Exception:
                pass
        self._fade_to(self._user_vol / 100.0, FADE_MS)

    def play_with_fade(self):
        if not self.player: return
        if self._loaded_track != self._track_id:
            self._begin_swap(self._track_id, autoplay=True)
            return
        self._start_faded_playback()
        self._push_music_state()

    def pause_with_fade(self):
        if not self.player: return
        self._want_playing = False
        self._push_music_state()

        def do_pause():
            try:
                self.player.pause()
            except Exception:
                pass
            self.save_state()

        self._fade_to(0.0, FADE_MS, done=do_pause)

    def seek_to(self, ms: int):
        """Jump to a position in the current track (from the seek bar)."""
        if not self.player:
            return
        if self._loaded_track != self._track_id:
            # Track not loaded yet — remember the target for the next load.
            self._pending_pos = max(0, int(ms))
            return
        try:
            self.player.setPosition(max(0, int(ms)))
        except Exception:
            pass
        self._push_position(force=True)
        self._save_soon()

    def change_volume(self, value: int):
        self._user_vol = max(0, min(100, int(value)))
        self._stop_fade()
        self._set_raw_vol(self._user_vol / 100.0)
        self._save_soon()

    def _on_state_changed(self, state):
        self._push_music_state()
        _notify_artwork()

    # --- State persistence ---------------------------------------------------

    def _current_position(self) -> int:
        try:
            if self.player:
                return int(self.player.position())
        except Exception:
            pass
        return 0

    def _save_soon(self):
        """Debounced save (volume sliders fire on every pixel of a drag)."""
        try:
            if self._save_timer is None:
                self._save_timer = QTimer(self)
                self._save_timer.setSingleShot(True)
                self._save_timer.timeout.connect(self.save_state)
            self._save_timer.start(800)
        except Exception:
            pass

    def save_state(self):
        _save_state({
            "track": self._track_id,
            "vol": self._user_vol,
            "scVol": self._sc_vol,
            "resume": self._resume_enabled,
            "mode": self._mode,
            "pos": self._current_position(),
            "playing": bool(self.is_playing() or self._want_playing),
        })

    # --- SoundCloud mode -----------------------------------------------------

    def _set_mode(self, mode: str):
        if mode not in ("local", "soundcloud"):
            mode = "local"
        self._mode = mode
        if mode == "soundcloud":
            if self.is_playing():
                self.pause_with_fade()
            self._enter_sc_layout()
            self._sc_js(f"scVolume({self._sc_vol});")
        else:
            self._sc_js("scPause();")
            self._sc_playing = False
            self._push_sc_state(playing=False)
            self._enter_local_layout()
        self.save_state()

    def _ensure_sc_loaded(self):
        if self._sc_loaded or self.sc_view is None:
            return
        path = os.path.join(constants.addon_path, SC_HTML_FILENAME)
        if not os.path.isfile(path):
            if tooltip:
                tooltip(_("SoundCloud player file is missing."))
            return
        self.sc_view.setUrl(QUrl.fromLocalFile(path))
        self._sc_loaded = True
        # Poll the widget state as a robust fallback (console-message bridging
        # can be unreliable on some platforms). Runs as long as SC is loaded —
        # the query is a trivial JS read.
        if self._sc_poll is None:
            self._sc_poll = QTimer(self)
            self._sc_poll.timeout.connect(self._sc_poll_tick)
        self._sc_poll.start(800)

    def _sc_poll_tick(self):
        if self.sc_view is None or not self._sc_loaded:
            return
        def got(res):
            try:
                if not res:
                    return
                st = json.loads(res)
                if isinstance(st, dict):
                    self._apply_sc_status(st)
            except Exception:
                pass
        try:
            page = self.sc_view.page()
            if page:
                page.runJavaScript("JSON.stringify(window._scStatus || null)", got)
        except Exception:
            pass

    def _apply_sc_status(self, st: dict):
        """Single source of truth for SC state (fed by bridge events + polling)."""
        # One-time bootstrap once the widget reports READY.
        if st.get("ready") and not self._sc_boot_done:
            self._sc_boot_done = True
            self._sc_js(f"scVolume({self._sc_vol});")
            if self._sc_url and self._sc_url != DEFAULT_SC_URL:
                self._sc_js(f"scLoad({json.dumps(self._sc_url)}, false);")

        if "playing" in st:
            playing = bool(st.get("playing"))
            if playing != self._sc_playing:
                self._sc_playing = playing
                self._push_sc_state(playing=playing)
                _notify_artwork()

        title = (st.get("title") or "").strip()
        artist = (st.get("artist") or "").strip()
        if title:
            now = f"{title} — {artist}" if artist else title
            if now != self._sc_now:
                self._sc_now = now
                self._push_sc_state(now=now)
            art = (st.get("artwork") or "").strip()
            if art and art != self._sc_artwork_url:
                self._sc_artwork_url = art
                self._fetch_sc_artwork(art)
            elif not art and self._sc_artwork_url:
                self._sc_artwork_url = ""
                self._sc_artwork_path = None
                _notify_artwork()

    def _set_sc_url(
        self,
        url: str,
        show_validation_error: bool = False,
        save_custom: bool = False,
    ) -> bool:
        normalized = _normalize_sc_url(url)
        if not normalized:
            if show_validation_error and tooltip:
                tooltip(_("Please paste a valid SoundCloud URL."))
            return False
        custom_changed = False
        if (save_custom and normalized not in SC_STATION_URLS
                and normalized not in self._sc_custom_urls):
            if len(self._sc_custom_urls) >= MAX_SC_CUSTOM_URLS:
                if tooltip:
                    tooltip(
                        _("You can save up to {count} custom SoundCloud URLs.").format(
                            count=MAX_SC_CUSTOM_URLS
                        )
                    )
                return False
            self._sc_custom_urls.append(normalized)
            _save_sc_custom_urls(self._sc_custom_urls)
            custom_changed = True
        self._sc_url = normalized
        _save_sc_url(normalized)
        self._ensure_sc_loaded()
        self._sc_js(f"scLoad({json.dumps(normalized)}, true);")
        state = {"url": normalized}
        if custom_changed:
            state["customStations"] = self._custom_sc_station_payload()
        self._push_sc_state(**state)
        return True

    def _delete_sc_custom_url(self, url: str) -> None:
        normalized = _normalize_sc_url(url)
        if not normalized or normalized not in self._sc_custom_urls:
            return
        self._sc_custom_urls = [
            saved for saved in self._sc_custom_urls if saved != normalized
        ]
        _save_sc_custom_urls(self._sc_custom_urls)

        state = {"customStations": self._custom_sc_station_payload()}
        if self._sc_url == normalized:
            # A deleted active URL must not reappear through the migration on
            # the next start. Return to the first built-in station instead.
            self._sc_url = DEFAULT_SC_URL
            _save_sc_url(DEFAULT_SC_URL)
            self._ensure_sc_loaded()
            self._sc_js(
                f"scLoad({json.dumps(DEFAULT_SC_URL)}, "
                f"{'true' if self._sc_playing else 'false'});"
            )
            state.update(url=DEFAULT_SC_URL, now="SoundCloud")
        self._push_sc_state(**state)

    def _on_sc_message(self, data: dict):
        """Receives bridge events from soundcloud_player.html (main thread)."""
        t = data.get("type")
        if t == "ready":
            self._apply_sc_status({"ready": True})
        elif t in ("track", "loaded"):
            self._apply_sc_status({
                "ready": True,
                "title": data.get("title"), "artist": data.get("artist"),
                "artwork": data.get("artwork"),
            })
        elif t == "state":
            self._apply_sc_status({"playing": bool(data.get("playing"))})
        elif t == "finish":
            self._apply_sc_status({"playing": False})
        elif t == "error":
            msg = data.get("message") or "SoundCloud error"
            print(f"Music: SoundCloud bridge error: {msg}")
            self._sc_playing = False
            self._push_sc_state(
                playing=False,
                now=_("SoundCloud could not load this URL."),
            )

    def _fetch_sc_artwork(self, url: str):
        """Download the track cover in the background, then update the sidebar."""
        # Only fetch images from SoundCloud's own hosts.
        try:
            parsed = urllib.parse.urlsplit(url)
            host = (parsed.hostname or "").lower().rstrip(".")
        except Exception:
            return
        if (parsed.scheme != "https" or not
                (host == "soundcloud.com" or host.endswith(".soundcloud.com")
                 or host == "sndcdn.com" or host.endswith(".sndcdn.com"))):
            return
        dest = _sc_artwork_cache_path()
        if not dest:
            return

        def worker():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    img = resp.read(5 * 1024 * 1024 + 1)
                if len(img) > 5 * 1024 * 1024:
                    return
                if not img:
                    return
                tmp = dest + ".tmp"
                with open(tmp, "wb") as f:
                    f.write(img)
                os.replace(tmp, dest)
            except Exception as e:
                print(f"Music: SC artwork download failed: {e}")
                return

            def apply():
                try:
                    # Only apply if this is still the current track's cover.
                    if url == self._sc_artwork_url:
                        self._sc_artwork_path = dest
                        _notify_artwork()
                except Exception:
                    pass

            # Marshal back to the main thread.
            try:
                mw.taskman.run_on_main(apply)
            except Exception:
                try:
                    QTimer.singleShot(0, apply)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    # --- Add / remove user tracks (local) ------------------------------------

    def _open_add_track_dialog(self):
        dlg = AddTrackDialog(self)
        dlg.setStyleSheet(_build_add_dialog_style(self._is_night()))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        title, src_path = dlg.get_data()
        if not title or not src_path or not os.path.isfile(src_path):
            return
        folder = _get_user_music_folder()
        if not folder:
            if tooltip: tooltip("Could not access user music folder.")
            return
        # Copy file, avoid name collisions
        fname = os.path.basename(src_path)
        base, ext = os.path.splitext(fname)
        dest_path = os.path.join(folder, fname)
        counter = 1
        while os.path.exists(dest_path):
            fname = f"{base}_{counter}{ext}"
            dest_path = os.path.join(folder, fname)
            counter += 1
        try:
            shutil.copy2(src_path, dest_path)
        except Exception as e:
            if tooltip: tooltip(f"Import failed: {e}")
            return
        # Save metadata, refresh UI and start playing the new track
        tracks = _load_user_tracks()
        tracks.append({"title": title, "file": fname})
        _save_user_tracks(tracks)
        self._push_user_tracks()
        self.select_track("u:" + fname)
        if tooltip: tooltip(f'"{title}" imported successfully!')

    def _delete_user_track(self, tid):
        if not tid or not str(tid).startswith("u:"):
            return
        fname = str(tid)[2:]
        if not fname or os.path.basename(fname) != fname:
            return
        entry = next((t for t in _load_user_tracks() if t.get("file") == fname), None)
        title = entry.get("title") if entry else fname
        # Remove from saved list
        tracks = [t for t in _load_user_tracks() if t.get("file") != fname]
        _save_user_tracks(tracks)
        # Delete file from disk
        folder = _get_user_music_folder()
        if folder:
            try:
                fp = os.path.join(folder, fname)
                if os.path.isfile(fp):
                    os.remove(fp)
            except Exception:
                pass
        self._push_user_tracks()
        # If it was the active track, fall back to the first built-in sound.
        if self._track_id == tid:
            first = self._builtin_tracks()
            if first:
                was = self.is_playing()
                self._track_id = first[0]["id"]
                self._push_music_state()
                self._begin_swap(self._track_id, autoplay=was)
        if tooltip: tooltip(f'"{title}" removed.')

    # --- Theme / lifecycle ---------------------------------------------------

    def refresh_theme(self) -> None:
        """Re-apply the current theme (called after a colour-theme change)."""
        self._apply_dialog_style()
        if self._ui_ready:
            self._ui_js("document.documentElement.classList.toggle('dark', %s);"
                        % ("true" if self._is_night() else "false"))
            self._ui_js("window.applyColors && applyColors(%s);"
                        % json.dumps(self._theme_colors()))

    def showEvent(self, event):
        super().showEvent(event)
        # Position pushes are skipped while hidden — sync the bar on show.
        QTimer.singleShot(150, lambda: self._push_position(force=True))

    def closeEvent(self, event):
        self.save_state()
        event.ignore()
        self.hide()

# --- Sidebar artwork notification -------------------------------------------
# The launcher sidebar can register a callback to show the current track's
# cover on its music button while something is playing.
_artwork_cb: Optional[callable] = None


def set_artwork_callback(cb) -> None:
    """Register cb(path_or_None); called whenever playback/track changes."""
    global _artwork_cb
    _artwork_cb = cb


def _sc_artwork_cache_path() -> Optional[str]:
    """Local cache file for the current SoundCloud cover (profile folder)."""
    try:
        if mw and mw.pm and mw.pm.profileFolder():
            folder = os.path.join(mw.pm.profileFolder(), "SynapsePro_Data")
            os.makedirs(folder, exist_ok=True)
            return os.path.join(folder, "sc_cover.jpg")
    except Exception:
        pass
    return None


def _notify_artwork() -> None:
    if _artwork_cb is None:
        return
    try:
        path = None
        w = _music_window
        if w is not None:
            if w._mode == "local" and w.player is not None and w.is_playing():
                path = w.get_image_for_file(w._track_id)
            elif w._mode == "soundcloud" and w._sc_playing:
                p = getattr(w, "_sc_artwork_path", None)
                if p and os.path.isfile(p):
                    path = p
        _artwork_cb(path)
    except RuntimeError:
        pass  # button/widget already deleted (profile close)
    except Exception:
        traceback.print_exc()


# --- Global Control ---

def _ensure_window() -> Optional['MiniMusicPlayer']:
    global _music_window
    if not _has_multimedia:
        return None
    if _music_window is None:
        _music_window = MiniMusicPlayer(mw if mw else None)
    return _music_window


def toggle_music_menu(button_widget: Optional['QWidget']):
    if not _has_multimedia:
        if tooltip: tooltip(_("Multimedia libs missing."))
        return
    w = _ensure_window()
    if w is None:
        return
    if w.isVisible():
        w.hide()
        w.save_state()
    else:
        w.show()
        w.activateWindow()


def maybe_autoresume_music() -> None:
    """Resume local playback on Anki startup if the user opted in and music
    was playing when the previous session ended.  (Local tracks only —
    SoundCloud never auto-plays on startup.)"""
    try:
        if not _has_multimedia:
            return
        st = _load_state()
        if not st.get("resume", True):
            return
        if not st.get("playing"):
            return
        if st.get("mode", "local") != "local":
            return
        if not st.get("track"):
            return
        w = _ensure_window()
        if w is None:
            return
        # The constructor already restored track + position (paused);
        # start playback with a gentle fade-in, without showing the window.
        QTimer.singleShot(900, w.play_with_fade)
    except Exception:
        traceback.print_exc()


def refresh_music_player_theme() -> None:
    """Re-apply the current theme to the open music player dialog (if any)."""
    if _music_window is not None:
        try:
            _music_window.refresh_theme()
        except Exception:
            pass


def cleanup_music_player():
    global _music_window, _artwork_cb, _music_web_profile
    try:
        if _artwork_cb:
            _artwork_cb(None)
    except Exception:
        pass
    _artwork_cb = None
    if _music_window:
        try:
            _music_window.save_state()
        except Exception:
            pass
        try:
            if _music_window._sc_poll is not None:
                _music_window._sc_poll.stop()
        except Exception:
            pass
        if _music_window.player:
            try:
                _music_window.player.stop()
            except Exception:
                pass
        try:
            _music_window._sc_js("scPause();")
        except Exception:
            pass
        for attr in ("sc_view", "ui_view"):
            v = getattr(_music_window, attr, None)
            if v is not None:
                try:
                    v.deleteLater()
                except Exception:
                    pass
        _music_window.close()
        _music_window = None
    if _music_web_profile is not None:
        try: _music_web_profile.deleteLater()
        except Exception: pass
        _music_web_profile = None
