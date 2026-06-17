# -*- coding: utf-8 -*-

import json
import os
import shutil
import traceback
from typing import Optional

# --- Local Imports ---
from . import constants

# --- PyQt Imports ---
_player: Optional['QMediaPlayer'] = None
_audio_output: Optional['QAudioOutput'] = None
_music_window: Optional['MiniMusicPlayer'] = None
_has_multimedia = False
InfiniteLoop = -1

try:
    if constants.qt_version == 6:
        from PyQt6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout,
                                     QPushButton, QLabel, QSlider, QComboBox, QFrame,
                                     QLineEdit, QFileDialog)
        from PyQt6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QFont
        from PyQt6.QtCore import QUrl, Qt, QSize, QTimer
        from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
        _has_multimedia = True
        InfiniteLoop = QMediaPlayer.Loops.Infinite

    elif constants.qt_version == 5:
        from PyQt5.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout,
                                     QPushButton, QLabel, QSlider, QComboBox, QFrame,
                                     QLineEdit, QFileDialog)
        from PyQt5.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QFont
        from PyQt5.QtCore import QUrl, Qt, QSize, QTimer
        try:
            from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
            _has_multimedia = True
            InfiniteLoop = -1 
        except ImportError:
            _has_multimedia = False
            QMediaPlayer = object
    else:
        _has_multimedia = False
        QDialog = object 
except ImportError:
    _has_multimedia = False
    QDialog = object

# --- QtWebEngine (for streaming services: SoundCloud / YouTube Music) ---
_has_webengine = False
try:
    if constants.qt_version == 6:
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
        _has_webengine = True
    elif constants.qt_version == 5:
        from PyQt5.QtWebEngineWidgets import (
            QWebEngineView, QWebEngineProfile, QWebEnginePage,
        )
        _has_webengine = True
except ImportError:
    _has_webengine = False
    QWebEngineView = QWebEngineProfile = QWebEnginePage = object  # type: ignore

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

# --- Stylesheets ---

def _build_music_style(night: bool) -> str:
    c = _palette(night)
    combo_arrow = f"""
    QComboBox::drop-down {{
        subcontrol-origin: padding; subcontrol-position: top right; width: 25px;
        background-color: {c['blue']};
        border-left-width: 1px; border-left-color: {c['blue']}; border-left-style: solid;
        border-top-right-radius: 8px; border-bottom-right-radius: 8px;
    }}
    QComboBox::down-arrow {{ width: 10px; height: 10px; image: none; }}
"""
    return f"""
    QDialog {{
        background-color: {c['bg']};
        font-family: {_FONT_FAMILY};
        color: {c['text']};
    }}
    QFrame#CardFrame {{
        background-color: {c['surface']};
        border-radius: 12px;
        border: 1px solid {c['grey_light']};
    }}
    QLabel {{ color: {c['text']}; font-weight: 600; font-size: 13px; }}
    QComboBox {{
        background-color: {c['surface']}; color: {c['text']}; border: 1px solid {c['grey_mid']};
        border-radius: 8px; padding: 2px 10px; min-height: 22px; font-size: 13px;
    }}
    {combo_arrow}
    QComboBox QAbstractItemView {{
        background-color: {c['surface']}; color: {c['text']};
        selection-background-color: {c['grey_mid']}; border: 1px solid {c['grey_light']};
    }}
    QPushButton {{
        background-color: {c['bg']}; border: 1px solid {c['grey_mid']}; border-radius: 8px;
        padding: 6px; min-width: 30px; color: {c['text']};
    }}
    QPushButton:hover {{ background-color: {c['grey_light']}; }}
    QPushButton:pressed {{ background-color: {c['grey_mid']}; }}
    QPushButton:checked {{ background-color: {c['grey_mid']}; border: 1px solid {c['grey_mid']}; }}
    QSlider::groove:horizontal {{ border: 1px solid {c['grey_mid']}; height: 4px; background: {c['grey_light']}; border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {c['blue']}; border-radius: 2px; }}
    QSlider::handle:horizontal {{
        background: {c['surface']}; border: 1px solid {c['grey_mid']}; width: 18px; height: 18px;
        margin: -7px 0; border-radius: 9px;
    }}
    QPushButton#BtnAddTrack, QPushButton#BtnDelTrack {{
        width: 24px; height: 24px;
        min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px;
        padding: 0px; margin: 0px;
        border-radius: 12px;
        font-size: 15px; font-weight: bold; line-height: 24px; text-align: center;
        border: 1px solid {c['grey_mid']}; background-color: {c['surface']};
    }}
    QPushButton#BtnAddTrack:hover, QPushButton#BtnDelTrack:hover {{
        background-color: {c['grey_light']};
    }}
    QPushButton#BtnDelTrack:disabled {{ color: {c['grey_mid']}; background-color: {c['surface']}; border-color: {c['grey_light']}; }}
    QFrame#StreamDivider {{ background-color: {c['grey_light']}; border: none; max-height: 1px; min-height: 1px; }}
    QLabel#StreamLabel {{ color: {c['grey_mid']}; font-size: 10px; font-weight: 700; }}
    QPushButton#BtnStream {{
        background-color: {c['surface']}; border: 1px solid {c['grey_mid']}; border-radius: 8px;
        padding: 7px 8px; min-height: 16px; font-size: 12px; font-weight: 600; color: {c['text']};
    }}
    QPushButton#BtnStream:hover {{ background-color: {c['grey_light']}; border-color: {c['blue']}; }}
    QPushButton#BtnStream:pressed {{ background-color: {c['grey_mid']}; }}
    QPushButton#BtnStream:checked {{ background-color: {c['blue']}; border-color: {c['blue']}; color: #ffffff; }}
    QLabel#NowPlayingLabel {{ color: {c['text']}; font-size: 11px; font-weight: 600; }}
    QPushButton#BtnStreamCtl {{
        background-color: {c['surface']}; border: 1px solid {c['grey_mid']}; border-radius: 16px;
        min-width: 32px; max-width: 32px; min-height: 32px; max-height: 32px; padding: 0px;
    }}
    QPushButton#BtnStreamCtl:hover {{ background-color: {c['grey_light']}; border-color: {c['blue']}; }}
    QPushButton#BtnStreamCtl:pressed {{ background-color: {c['grey_mid']}; }}
"""

# Styles computed per-instance at widget creation time (not cached here).

# --- Helper Functions ---

def _get_music_file_path(filename: str) -> Optional[str]:
    if not constants.icons_folder: return None
    full_path = os.path.join(constants.icons_folder, filename)
    return full_path if os.path.isfile(full_path) else None

def _get_image_path(image_name: str) -> Optional[str]:
    base_dir = os.path.dirname(__file__)
    media_dir = os.path.join(base_dir, "media")
    full_path = os.path.join(media_dir, image_name)
    return full_path if os.path.isfile(full_path) else None

_SERVICE_ART = {
    "soundcloud": ("#ff5500", "SoundCloud"),
    "ytmusic":    ("#ff0000", "YouTube\nMusic"),
}

def _make_service_art(service_id: str, size) -> Optional["QPixmap"]:
    """Draw a branded album-art tile for a streaming service (no logo assets)."""
    info = _SERVICE_ART.get(service_id)
    if info is None or QPixmap is object:
        return None
    color, label = info
    w, h = size.width(), size.height()
    try:
        transparent = Qt.GlobalColor.transparent if constants.qt_version == 6 else Qt.transparent
        no_pen = Qt.PenStyle.NoPen if constants.qt_version == 6 else Qt.NoPen
        center = Qt.AlignmentFlag.AlignCenter if constants.qt_version == 6 else Qt.AlignCenter
        antialias = QPainter.RenderHint.Antialiasing if constants.qt_version == 6 else QPainter.Antialiasing
        pix = QPixmap(w, h)
        pix.fill(transparent)
        p = QPainter(pix)
        p.setRenderHint(antialias)
        p.setPen(no_pen)
        p.setBrush(QColor(color))
        p.drawRoundedRect(0, 0, w, h, 12, 12)
        p.setPen(QColor("#ffffff"))
        f = QFont(_FONT_FAMILY)
        f.setPointSize(20)
        f.setBold(True)
        p.setFont(f)
        p.drawText(pix.rect(), center, label)
        p.end()
        return pix
    except Exception:
        traceback.print_exc()
        return None

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
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []

def _save_user_tracks(tracks: list) -> None:
    """Persists user track metadata in Anki config."""
    try:
        if mw and mw.col:
            mw.col.set_config("synapse_user_tracks", json.dumps(tracks))
    except Exception:
        pass

# --- Add Track Dialog ---

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
        path, _ = QFileDialog.getOpenFileName(
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

# --- Minimalistic Music Player ---

class MiniMusicPlayer(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Focus Music"))
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowCloseButtonHint)
        self.setFixedSize(260, 510 if _has_webengine else 375)
        
        self.player: Optional[QMediaPlayer] = None
        self.audio_output: Optional[QAudioOutput] = None
        self._was_playing_before_change = False
        self._backend_error = False
        self._mode = "local"          # "local" | "soundcloud" | "ytmusic"
        self._active_stream = None

        self.init_backend()
        self.init_ui()
        
        is_night = False
        try:
            if mw and mw.pm.night_mode(): is_night = True
        except Exception: pass
        self.setStyleSheet(_build_music_style(is_night))

    def init_backend(self):
        if not _has_multimedia:
            return
        try:
            self.player = QMediaPlayer()
            if constants.qt_version == 6:
                self.audio_output = QAudioOutput()
                self.player.setAudioOutput(self.audio_output)
                self.audio_output.setVolume(0.5)
                self.player.playbackStateChanged.connect(self._on_state_changed)
            else:
                self.player.setVolume(50)
                self.player.stateChanged.connect(self._on_state_changed)
        except Exception:
            traceback.print_exc()
            self._backend_error = True

    def get_current_state(self):
        if not self.player: return 0
        return self.player.playbackState() if constants.qt_version == 6 else self.player.state()

    def is_playing(self):
        playing_val = QMediaPlayer.PlaybackState.PlayingState if constants.qt_version == 6 else QMediaPlayer.PlayingState
        return self.get_current_state() == playing_val

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 15)
        main_layout.setSpacing(6)

        # ── Backend-error banner (Linux/missing gstreamer) ─────────────
        if self._backend_error or (not self._backend_error and _has_multimedia and self.player is None):
            warn = QLabel(
                _("Audio playback is not available on this system.\n"
                  "On Linux, please install the GStreamer plugins:\n"
                  "  gstreamer1.0-plugins-good\n"
                  "  gstreamer1.0-plugins-bad")
            )
            warn.setWordWrap(True)
            warn.setAlignment(
                Qt.AlignmentFlag.AlignCenter if constants.qt_version == 6
                else Qt.AlignCenter
            )
            warn.setStyleSheet(
                "color: #b45309; background: #fff8e7; border: 1px solid #fcd34d;"
                "border-radius: 8px; padding: 10px; font-size: 12px; font-weight: normal;"
            )
            main_layout.addWidget(warn)

        cursor = Qt.CursorShape.PointingHandCursor if constants.qt_version == 6 else Qt.PointingHandCursor

        # --- Top-right: + and − buttons ---
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(5)
        top_row.addStretch()
        self.btn_add_track = QPushButton("+")
        self.btn_add_track.setObjectName("BtnAddTrack")
        self.btn_add_track.setFixedSize(24, 24)
        self.btn_add_track.setToolTip(_("Import your own audio file"))
        self.btn_add_track.setCursor(cursor)
        self.btn_add_track.clicked.connect(self._open_add_track_dialog)
        self.btn_del_track = QPushButton("−")
        self.btn_del_track.setObjectName("BtnDelTrack")
        self.btn_del_track.setFixedSize(24, 24)
        self.btn_del_track.setToolTip(_("Remove this user track"))
        self.btn_del_track.setCursor(cursor)
        self.btn_del_track.setEnabled(False)
        self.btn_del_track.clicked.connect(self._delete_current_user_track)
        top_row.addWidget(self.btn_add_track)
        top_row.addWidget(self.btn_del_track)
        main_layout.addLayout(top_row)

        self.card = QFrame()
        self.card.setObjectName("CardFrame")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(15, 20, 15, 20)
        card_layout.setSpacing(15)

        self.img_label = QLabel()
        self.img_label.setFixedSize(200, 150)
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter if constants.qt_version == 6 else Qt.AlignCenter)
        self.img_label.setStyleSheet("background-color: transparent; border: none;")
        card_layout.addWidget(self.img_label, 0, Qt.AlignmentFlag.AlignCenter if constants.qt_version == 6 else Qt.AlignCenter)
        card_layout.addSpacing(14)

        center = Qt.AlignmentFlag.AlignCenter if constants.qt_version == 6 else Qt.AlignCenter

        self.track_combo = QComboBox()
        self.populate_tracks()
        self.track_combo.setCursor(cursor)
        self.track_combo.currentIndexChanged.connect(self.on_track_changed)
        card_layout.addWidget(self.track_combo)

        # Now-playing title — shown in place of the track list while streaming.
        self.now_playing_lbl = QLabel("")
        self.now_playing_lbl.setObjectName("NowPlayingLabel")
        self.now_playing_lbl.setAlignment(center)
        self.now_playing_lbl.setWordWrap(False)
        self.now_playing_lbl.setFixedHeight(self.track_combo.sizeHint().height())
        self.now_playing_lbl.setVisible(False)
        card_layout.addWidget(self.now_playing_lbl)

        # Unified transport row — prev / play / next, mode-aware.
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(12)
        self.btn_prev = QPushButton()
        self.btn_prev.setObjectName("BtnStreamCtl")
        self.btn_prev.setCursor(cursor)
        self.btn_prev.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_MediaSkipBackward))
        self.btn_prev.clicked.connect(self._on_prev)
        self.btn_play = QPushButton()
        self.btn_play.setCheckable(True)
        self.btn_play.setCursor(cursor)
        self.btn_play.clicked.connect(self._on_play)
        self.btn_next = QPushButton()
        self.btn_next.setObjectName("BtnStreamCtl")
        self.btn_next.setCursor(cursor)
        self.btn_next.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_MediaSkipForward))
        self.btn_next.clicked.connect(self._on_next)
        self.update_play_icon(False)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.btn_prev)
        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addWidget(self.btn_next)
        ctrl_layout.addStretch()
        card_layout.addLayout(ctrl_layout)

        vol_layout = QHBoxLayout()
        self.slider_vol = QSlider(Qt.Orientation.Horizontal)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setValue(50)
        self.slider_vol.valueChanged.connect(self.change_volume)
        vol_layout.addWidget(self.slider_vol)
        card_layout.addLayout(vol_layout)

        # --- Source selector (only when QtWebEngine is available) ---
        if _has_webengine:
            card_layout.addSpacing(4)
            divider = QFrame()
            divider.setObjectName("StreamDivider")
            divider.setFrameShape(QFrame.Shape.HLine if constants.qt_version == 6 else QFrame.HLine)
            card_layout.addWidget(divider)

            src_lbl = QLabel(_("SOURCE"))
            src_lbl.setObjectName("StreamLabel")
            card_layout.addWidget(src_lbl)

            self.btn_src_local = QPushButton(_("My Library"))
            self.btn_src_local.setObjectName("BtnStream")
            self.btn_src_local.setCheckable(True)
            self.btn_src_local.setCursor(cursor)
            self.btn_src_local.clicked.connect(lambda: self._set_mode("local"))
            card_layout.addWidget(self.btn_src_local)

            src_row = QHBoxLayout()
            src_row.setSpacing(8)
            self.btn_soundcloud = QPushButton(_("SoundCloud"))
            self.btn_soundcloud.setObjectName("BtnStream")
            self.btn_soundcloud.setCheckable(True)
            self.btn_soundcloud.setCursor(cursor)
            self.btn_soundcloud.clicked.connect(lambda: self._open_stream("soundcloud"))
            self.btn_ytmusic = QPushButton(_("YT Music"))
            self.btn_ytmusic.setObjectName("BtnStream")
            self.btn_ytmusic.setCheckable(True)
            self.btn_ytmusic.setCursor(cursor)
            self.btn_ytmusic.clicked.connect(lambda: self._open_stream("ytmusic"))
            src_row.addWidget(self.btn_soundcloud)
            src_row.addWidget(self.btn_ytmusic)
            card_layout.addLayout(src_row)

            # Poll the active stream for its current track title.
            self._np_timer = QTimer(self)
            self._np_timer.setInterval(1500)
            self._np_timer.timeout.connect(self._poll_now_playing)

        main_layout.addWidget(self.card)

        self._update_source_buttons()
        self._apply_track_change_step1()

    def populate_tracks(self):
        tracks = [
            ("alpha_waves.mp3", _("Alpha Waves")), ("beta_waves.mp3", _("Beta Waves")),
            ("library_sounds.mp3", _("Library")), ("jazz.mp3", _("Jazz")),
            ("rain.mp3", _("Rain")), ("cozy.mp3", _("Cozy")),
            ("focus.mp3", _("Deep Focus")), ("chill.mp3", _("Chill Vibes")),
            ("lofi.mp3", _("Lofi Beats"))
        ]
        for fname, dname in tracks:
            if _get_music_file_path(fname):
                self.track_combo.addItem(dname, fname)
        self._system_track_count = self.track_combo.count()
        self._add_user_tracks_to_combo()

    def _add_user_tracks_to_combo(self):
        user_tracks = _load_user_tracks()
        if user_tracks:
            self.track_combo.insertSeparator(self.track_combo.count())
        for ut in user_tracks:
            self.track_combo.addItem(ut["title"], {"user": True, "file": ut["file"]})

    def _refresh_user_tracks_in_combo(self):
        """Remove all user tracks (and separator) then re-add from saved list."""
        while self.track_combo.count() > self._system_track_count:
            self.track_combo.removeItem(self.track_combo.count() - 1)
        self._add_user_tracks_to_combo()

    def get_image_for_file(self, filename):
        if isinstance(filename, dict):
            return _get_image_path("own.png")   # image for user tracks
        mapping = {
            "alpha_waves.mp3": "alpha.png", "beta_waves.mp3": "beta.png",
            "library_sounds.mp3": "library.png", "rain.mp3": "rain.png",
            "jazz.mp3": "jazz.png", "cozy.mp3": "cozy.png",
            "focus.mp3": "beta.png", "chill.mp3": "alpha.png", "lofi.mp3": "cozy.png"
        }
        return _get_image_path(mapping.get(filename, "cozy.png"))


    def _is_current_user_track(self) -> bool:
        data = self.track_combo.currentData()
        return isinstance(data, dict) and bool(data.get("user"))

    def on_track_changed(self):
        """Phase 0: Stoppen und Sperren"""
        if not self.player: return
        self._was_playing_before_change = self.is_playing()
        self.btn_play.setEnabled(False)
        self.player.stop()
        if hasattr(self, "btn_del_track"):
            self.btn_del_track.setEnabled(self._is_current_user_track())
        QTimer.singleShot(200, self._apply_track_change_step1)

    def _apply_track_change_step1(self):
        """Phase 1: UI Update & Resource Free"""
        filename = self.track_combo.currentData()
        if not filename: return
        
        img_path = self.get_image_for_file(filename)
        if img_path:
            pix = QPixmap(img_path)
            if not pix.isNull():
                self.img_label.setPixmap(pix.scaled(self.img_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation if constants.qt_version == 6 else Qt.SmoothTransformation))

        if constants.qt_version == 6:
            self.player.setSource(QUrl(""))
        else:
            self.player.setMedia(QMediaContent())
        
        QTimer.singleShot(200, self._apply_track_change_step2)

    def _apply_track_change_step2(self):
        """Phase 2: Neue Source laden"""
        filename = self.track_combo.currentData()
        if isinstance(filename, dict) and filename.get("user"):
            folder = _get_user_music_folder()
            path = os.path.join(folder, filename["file"]) if folder else None
            if path and not os.path.isfile(path):
                path = None
        else:
            path = _get_music_file_path(filename)
        if path and self.player:
            url = QUrl.fromLocalFile(path)
            if constants.qt_version == 6:
                self.player.setSource(url)
                self.player.setLoops(InfiniteLoop)
            else:
                self.player.setMedia(QMediaContent(url))
        
        QTimer.singleShot(300, self._apply_track_change_step3)

    def _apply_track_change_step3(self):
        """Phase 3: Freigabe"""
        self.btn_play.setEnabled(True)
        if self._was_playing_before_change and self.player:
            self.player.play()
        self.update_play_icon(self.is_playing())

    # --- UI Updates ---

    def update_play_icon(self, is_playing):
        icon = self.style().standardIcon(self.style().StandardPixmap.SP_MediaPause if is_playing else self.style().StandardPixmap.SP_MediaPlay)
        self.btn_play.setIcon(icon)
        self.btn_play.setChecked(is_playing)

    def toggle_playback(self):
        if not self.player: return
        if self.is_playing():
            self.player.pause()
            self._was_playing_before_change = False
        else:
            self.player.play()
            self._was_playing_before_change = True

    def change_volume(self, value):
        if self._mode != "local" and self._active_stream:
            self._active_stream.set_volume(value / 100.0)
            return
        if constants.qt_version == 6 and self.audio_output:
            self.audio_output.setVolume(value / 100.0)
        elif self.player:
            self.player.setVolume(value)

    def _on_state_changed(self, state):
        playing = self.is_playing()
        self.update_play_icon(playing)
        if constants.qt_version == 5 and state == 0 and self._was_playing_before_change:
            self.player.play()

    def _open_add_track_dialog(self):
        dlg = AddTrackDialog(self)
        is_night = False
        try:
            if mw and mw.pm.night_mode(): is_night = True
        except Exception:
            pass
        dlg.setStyleSheet(_build_music_style(is_night))
        try:
            accepted = QDialog.DialogCode.Accepted  # Qt6
        except AttributeError:
            accepted = QDialog.Accepted              # Qt5
        if dlg.exec() != accepted:
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
        # Save metadata and refresh combo
        tracks = _load_user_tracks()
        tracks.append({"title": title, "file": fname})
        _save_user_tracks(tracks)
        self.track_combo.blockSignals(True)
        self._refresh_user_tracks_in_combo()
        self.track_combo.blockSignals(False)
        self.track_combo.setCurrentIndex(self.track_combo.count() - 1)
        if tooltip: tooltip(f'"{title}" imported successfully!')

    def _delete_current_user_track(self):
        if not self._is_current_user_track(): return
        data = self.track_combo.currentData()
        title = self.track_combo.currentText()
        # Remove from saved list
        tracks = [t for t in _load_user_tracks() if t.get("file") != data.get("file")]
        _save_user_tracks(tracks)
        # Delete file from disk
        folder = _get_user_music_folder()
        if folder:
            try:
                fp = os.path.join(folder, data["file"])
                if os.path.isfile(fp):
                    os.remove(fp)
            except Exception:
                pass
        # Refresh combo and switch to first track
        self.track_combo.blockSignals(True)
        self._refresh_user_tracks_in_combo()
        self.track_combo.blockSignals(False)
        self.track_combo.setCurrentIndex(0)
        self.on_track_changed()
        if tooltip: tooltip(f'"{title}" removed.')

    # --- Source mode & unified transport ---

    def _open_stream(self, service_id: str) -> None:
        """Open a streaming service window and switch the player into that mode."""
        win = open_streaming_service(service_id)
        if win is None:
            return
        self._active_stream = win
        self._set_mode(service_id)

    def _set_mode(self, mode: str) -> None:
        """Switch between local library and a streaming source."""
        self._mode = mode
        streaming = mode != "local"
        # Track list & user-track buttons belong to the local library only.
        self.track_combo.setVisible(not streaming)
        self.now_playing_lbl.setVisible(streaming)
        self.btn_add_track.setVisible(not streaming)
        self.btn_del_track.setVisible(not streaming)
        self._update_source_buttons()

        if streaming:
            try:
                if self.player and self.is_playing():
                    self.player.pause()
            except Exception:
                pass
            art = _make_service_art(mode, self.img_label.size())
            if art is not None and not art.isNull():
                self.img_label.setPixmap(art)
            self.now_playing_lbl.setText(_("Loading…"))
            self.update_play_icon(True)
            if hasattr(self, "_np_timer"):
                self._np_timer.start()
            self._poll_now_playing()
        else:
            if hasattr(self, "_np_timer"):
                self._np_timer.stop()
            # Stop any streaming audio so it doesn't overlap the local player.
            if self._active_stream is not None:
                try:
                    self._active_stream.media_pause()
                except Exception:
                    pass
            # Restore the current local track's artwork and state.
            self._apply_track_change_step1()
            self.update_play_icon(self.is_playing())

    def _update_source_buttons(self) -> None:
        if not hasattr(self, "btn_src_local"):
            return
        self.btn_src_local.setChecked(self._mode == "local")
        self.btn_soundcloud.setChecked(self._mode == "soundcloud")
        self.btn_ytmusic.setChecked(self._mode == "ytmusic")

    def _on_prev(self) -> None:
        if self._mode != "local" and self._active_stream:
            self._active_stream.media_prev()
            QTimer.singleShot(600, self._poll_now_playing)
        else:
            self._cycle_local(-1)

    def _on_next(self) -> None:
        if self._mode != "local" and self._active_stream:
            self._active_stream.media_next()
            QTimer.singleShot(600, self._poll_now_playing)
        else:
            self._cycle_local(1)

    def _on_play(self) -> None:
        if self._mode != "local" and self._active_stream:
            self._active_stream.media_play()
            self.update_play_icon(self.btn_play.isChecked())
        else:
            self.toggle_playback()

    def _cycle_local(self, delta: int) -> None:
        n = self.track_combo.count()
        if n <= 0:
            return
        i = self.track_combo.currentIndex()
        for _step in range(n):
            i = (i + delta) % n
            # Skip the separator row (no data, no text).
            if self.track_combo.itemData(i) is not None or self.track_combo.itemText(i):
                break
        self.track_combo.setCurrentIndex(i)

    def _poll_now_playing(self) -> None:
        win = self._active_stream
        if win is None or self._mode == "local":
            return
        def _set(title):
            text = (title or "").strip() or _("Streaming")
            metrics = self.now_playing_lbl.fontMetrics()
            elide = Qt.TextElideMode.ElideRight if constants.qt_version == 6 else Qt.ElideRight
            self.now_playing_lbl.setText(
                metrics.elidedText(text, elide, self.now_playing_lbl.width() or 220))
        try:
            win.query_title(_set)
        except Exception:
            pass

    def refresh_theme(self) -> None:
        """Re-apply the current theme stylesheet (called after a colour-theme change)."""
        is_night = False
        try:
            if mw and mw.pm.night_mode(): is_night = True
        except Exception:
            pass
        self.setStyleSheet(_build_music_style(is_night))

    def closeEvent(self, event):
        event.ignore()
        self.hide()

# --- Streaming services (SoundCloud / YouTube Music) ---

# id -> (display title, start URL, blocked main-frame hosts)
# Blocking main YouTube keeps the YouTube Music player a focus tool, not a
# doorway back into the YouTube rabbit hole.
STREAMING_SERVICES = {
    "soundcloud": ("SoundCloud", "https://soundcloud.com/discover", []),
    "ytmusic":    ("YouTube Music", "https://music.youtube.com/",
                   ["www.youtube.com", "m.youtube.com", "youtube.com", "youtu.be"]),
}

# DOM selectors used to drive each service's own transport controls.
CONTROL_SELECTORS = {
    "soundcloud": {"prev": ".skipControl__previous",
                   "play": ".playControl",
                   "next": ".skipControl__next"},
    "ytmusic":    {"prev": ".previous-button",
                   "play": "#play-pause-button",
                   "next": ".next-button"},
}

# Returns "Title — Artist" from the Media Session API (set by both services),
# falling back to the document title.
_TITLE_JS = (
    "(function(){try{var m=navigator.mediaSession&&navigator.mediaSession.metadata;"
    "if(m&&m.title){return m.title+(m.artist?(' \\u2014 '+m.artist):'');}}"
    "catch(e){}return document.title||'';})()"
)

_web_music_windows: dict = {}      # service_id -> WebMusicWindow
_music_web_profile: Optional["QWebEngineProfile"] = None


class _MusicWebPage(QWebEnginePage):
    """Web page that refuses to navigate the main frame to blocked hosts."""

    def __init__(self, profile, parent=None, blocked_hosts=None):
        super().__init__(profile, parent)
        self._blocked = set(blocked_hosts or [])

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):  # noqa: N802
        try:
            host = url.host()
        except Exception:
            host = ""
        if is_main_frame and host in self._blocked:
            if tooltip:
                tooltip(_("Stay focused — main YouTube is blocked here."))
            return False
        try:
            return super().acceptNavigationRequest(url, nav_type, is_main_frame)
        except Exception:
            return True


def _get_music_web_profile() -> Optional["QWebEngineProfile"]:
    """Return a persistent web profile so streaming-service logins survive
    restarts (mirrors the website sidebar's profile handling)."""
    global _music_web_profile
    if _music_web_profile is not None:
        return _music_web_profile
    if not _has_webengine or mw is None:
        return None
    try:
        profile_dir = os.path.join(constants.addon_path, "music_web_profile")
        os.makedirs(profile_dir, exist_ok=True)
        prof = QWebEngineProfile(f"profile_{constants.ADDON_NAME_LAUNCHER}_Music_v1", mw)
        prof.setPersistentStoragePath(profile_dir)
        prof.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
        )
        prof.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        _music_web_profile = prof
    except Exception:
        traceback.print_exc()
        _music_web_profile = None
    return _music_web_profile


class WebMusicWindow(QDialog):
    """A resizable window embedding a streaming-service web player."""

    def __init__(self, service_id: str, title: str, url: str, blocked_hosts=None, parent=None):
        super().__init__(parent)
        self.service_id = service_id
        self.setWindowTitle(title)
        # Stay on top so it surfaces above the always-on-top mini player when
        # opened; the user can minimise it and keep controlling via the player.
        flags = (Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.WindowCloseButtonHint
                 | Qt.WindowType.WindowMinMaxButtonsHint)
        self.setWindowFlags(flags)
        # Wide enough for the desktop layout so there's no horizontal scroll.
        self.resize(940, 680)
        self.setMinimumSize(480, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(self)
        prof = _get_music_web_profile()
        if prof is not None:
            self.view.setPage(_MusicWebPage(prof, self.view, blocked_hosts))
        self.view.setUrl(QUrl(url))
        layout.addWidget(self.view)

    # --- Transport control via the page's own buttons ---
    def _run_js(self, code: str, callback=None) -> None:
        try:
            page = self.view.page()
            if not page:
                return
            if callback is not None:
                page.runJavaScript(code, callback)
            else:
                page.runJavaScript(code)
        except Exception:
            pass

    def _click(self, action: str) -> None:
        sel = CONTROL_SELECTORS.get(self.service_id, {}).get(action)
        if not sel:
            return
        self._run_js(
            "(function(){var b=document.querySelector(%s);"
            "if(b){b.click();return true;}return false;})()" % json.dumps(sel)
        )

    def media_prev(self):  self._click("prev")
    def media_next(self):  self._click("next")
    def media_play(self):  self._click("play")

    def set_volume(self, frac: float) -> None:
        self._run_js(
            "(function(){var e=document.querySelector('video,audio');"
            "if(e){try{e.volume=%f;}catch(x){}}})()" % max(0.0, min(1.0, frac))
        )

    def media_pause(self) -> None:
        # Pause the actual media element (not a toggle) so audio truly stops.
        self._run_js(
            "(function(){var e=document.querySelector('video,audio');"
            "if(e){try{e.pause();}catch(x){}}})()"
        )

    def query_title(self, callback) -> None:
        self._run_js(_TITLE_JS, callback)

    def closeEvent(self, event):
        # Hide instead of close so playback continues in the background.
        event.ignore()
        self.hide()


def open_streaming_service(service_id: str) -> Optional["WebMusicWindow"]:
    if not _has_webengine:
        if tooltip:
            tooltip(_("Streaming player unavailable (QtWebEngine missing)."))
        return None
    info = STREAMING_SERVICES.get(service_id)
    if not info:
        return None
    title, url, blocked = info
    # Only one streaming service at a time: pause & hide any other open window.
    for other_id, other in _web_music_windows.items():
        if other_id != service_id and other is not None:
            try:
                other.media_pause()
                other.hide()
            except Exception:
                pass
    win = _web_music_windows.get(service_id)
    if win is None:
        win = WebMusicWindow(service_id, title, url, blocked, mw if mw else None)
        _web_music_windows[service_id] = win
    win.show()
    win.raise_()
    win.activateWindow()
    return win


# --- Global Control ---

def toggle_music_menu(button_widget: Optional[QWidget]):
    global _music_window, _has_multimedia
    if not _has_multimedia:
        if tooltip: tooltip(_("Multimedia libs missing."))
        return
    if _music_window is None:
        _music_window = MiniMusicPlayer(mw if mw else None)
    
    if _music_window.isVisible():
        _music_window.hide()
    else:
        _music_window.show()
        _music_window.activateWindow()

def refresh_music_player_theme() -> None:
    """Re-apply the current theme to the open music player dialog (if any)."""
    if _music_window is not None:
        try:
            _music_window.refresh_theme()
        except Exception:
            pass

def cleanup_music_player():
    global _music_window
    if _music_window:
        if _music_window.player:
            _music_window.player.stop()
        _music_window.close()
        _music_window = None
    for win in list(_web_music_windows.values()):
        try:
            win.hide()
            win.deleteLater()
        except Exception:
            pass
    _web_music_windows.clear()