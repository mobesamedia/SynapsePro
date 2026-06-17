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
        from PyQt6.QtGui import QAction, QIcon, QPixmap
        from PyQt6.QtCore import QUrl, Qt, QSize, QTimer
        from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
        _has_multimedia = True
        InfiniteLoop = QMediaPlayer.Loops.Infinite

    elif constants.qt_version == 5:
        from PyQt5.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout,
                                     QPushButton, QLabel, QSlider, QComboBox, QFrame,
                                     QLineEdit, QFileDialog)
        from PyQt5.QtGui import QAction, QIcon, QPixmap
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
        self.setFixedSize(260, 470 if _has_webengine else 375)
        
        self.player: Optional[QMediaPlayer] = None
        self.audio_output: Optional[QAudioOutput] = None
        self._was_playing_before_change = False
        self._backend_error = False

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

        self.track_combo = QComboBox()
        self.populate_tracks()
        self.track_combo.setCursor(cursor)
        self.track_combo.currentIndexChanged.connect(self.on_track_changed)
        card_layout.addWidget(self.track_combo)

        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(10)
        self.btn_play = QPushButton()
        self.btn_play.setCheckable(True)
        self.btn_play.setCursor(cursor)
        self.btn_play.clicked.connect(self.toggle_playback)
        self.update_play_icon(False)

        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addStretch()
        card_layout.addLayout(ctrl_layout)

        vol_layout = QHBoxLayout()
        self.slider_vol = QSlider(Qt.Orientation.Horizontal)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setValue(50)
        self.slider_vol.valueChanged.connect(self.change_volume)
        vol_layout.addWidget(self.slider_vol)
        card_layout.addLayout(vol_layout)

        # --- Streaming services (only when QtWebEngine is available) ---
        if _has_webengine:
            card_layout.addSpacing(4)
            divider = QFrame()
            divider.setObjectName("StreamDivider")
            divider.setFrameShape(QFrame.Shape.HLine if constants.qt_version == 6 else QFrame.HLine)
            card_layout.addWidget(divider)

            stream_lbl = QLabel(_("STREAMING"))
            stream_lbl.setObjectName("StreamLabel")
            card_layout.addWidget(stream_lbl)

            stream_row = QHBoxLayout()
            stream_row.setSpacing(8)
            self.btn_soundcloud = QPushButton(_("SoundCloud"))
            self.btn_soundcloud.setObjectName("BtnStream")
            self.btn_soundcloud.setCursor(cursor)
            self.btn_soundcloud.clicked.connect(lambda: self._open_stream("soundcloud"))
            self.btn_ytmusic = QPushButton(_("YT Music"))
            self.btn_ytmusic.setObjectName("BtnStream")
            self.btn_ytmusic.setCursor(cursor)
            self.btn_ytmusic.clicked.connect(lambda: self._open_stream("ytmusic"))
            stream_row.addWidget(self.btn_soundcloud)
            stream_row.addWidget(self.btn_ytmusic)
            card_layout.addLayout(stream_row)

        main_layout.addWidget(self.card)
        
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

    def _open_stream(self, service_id: str) -> None:
        """Open a streaming service, pausing local playback to avoid overlap."""
        try:
            if self.player and self.is_playing():
                self.player.pause()
        except Exception:
            pass
        open_streaming_service(service_id)

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

    def __init__(self, title: str, url: str, blocked_hosts=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        flags = (Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint
                 | Qt.WindowType.WindowMinMaxButtonsHint)
        self.setWindowFlags(flags)
        self.resize(480, 720)
        self.setMinimumSize(360, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(self)
        prof = _get_music_web_profile()
        if prof is not None:
            self.view.setPage(_MusicWebPage(prof, self.view, blocked_hosts))
        self.view.setUrl(QUrl(url))
        layout.addWidget(self.view)

    def closeEvent(self, event):
        # Hide instead of close so playback continues in the background.
        event.ignore()
        self.hide()


def open_streaming_service(service_id: str) -> None:
    if not _has_webengine:
        if tooltip:
            tooltip(_("Streaming player unavailable (QtWebEngine missing)."))
        return
    info = STREAMING_SERVICES.get(service_id)
    if not info:
        return
    title, url, blocked = info
    win = _web_music_windows.get(service_id)
    if win is None:
        win = WebMusicWindow(title, url, blocked, mw if mw else None)
        _web_music_windows[service_id] = win
    win.show()
    win.raise_()
    win.activateWindow()


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