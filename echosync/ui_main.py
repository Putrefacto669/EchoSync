# echo_sync/ui_main.py
import os
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLineEdit, QSlider, QFileDialog, QTextEdit, QMessageBox
)
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt, Slot

from .spotify_api import SpotifyAPI
from .player import HybridPlayer
from .local_manager import LocalManager
from .lyrics_manager import LyricsManager
from .workers import SearchWorker, RecommendationsWorker, YTDLWorker

ASSETS = os.path.join(os.path.dirname(__file__), '..', 'assets')

class EchoSyncApp(QWidget):
    def __init__(self):
        super().__init__()
        # Spotify keys: pon las tuyas aquí,estas son las mias,necsitas cambiarlas
        client_id = "cf4379a10a984c4e9f7eda9ebdce9add"
        client_secret = "92db1f6d12a4477082ae44c96855bdd3"

        self.spotify = SpotifyAPI(client_id, client_secret)
        self.player = HybridPlayer()
        self.local = LocalManager()
        self.lyrics = LyricsManager()
        self.current_track_list = []
        self.current_playing = None

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        self.setWindowTitle("EchoSync")
        root_layout = QVBoxLayout(self)

        # Top: search + logo
        top = QHBoxLayout()
        logo_lbl = QLabel()
        logo_path = os.path.join(ASSETS, 'logo.png')
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaled(80,80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
        top.addWidget(logo_lbl)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar canciones, artistas o álbumes...")
        top.addWidget(self.search_input)
        search_btn = QPushButton("Buscar")
        search_btn.clicked.connect(self.on_search)
        top.addWidget(search_btn)

        root_layout.addLayout(top)

        # Middle: results + lyrics
        mid = QHBoxLayout()
        self.results_list = QListWidget()
        mid.addWidget(self.results_list, 65)

        right_col = QVBoxLayout()
        self.lyrics_view = QTextEdit()
        self.lyrics_view.setReadOnly(True)
        right_col.addWidget(QLabel("Letras"))
        right_col.addWidget(self.lyrics_view)
        mid.addLayout(right_col, 35)

        root_layout.addLayout(mid, 85)

        # Bottom: player controls
        bottom = QHBoxLayout()
        self.prev_btn = QPushButton("⏮")
        self.play_btn = QPushButton("▶")
        self.next_btn = QPushButton("⏭")
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0,100)
        self.volume.setValue(60)
        bottom.addWidget(self.prev_btn)
        bottom.addWidget(self.play_btn)
        bottom.addWidget(self.next_btn)
        bottom.addWidget(QLabel("Vol"))
        bottom.addWidget(self.volume)
        self.progress = QSlider(Qt.Horizontal)
        self.progress.setRange(0, 100)
        root_layout.addWidget(self.progress)
        root_layout.addLayout(bottom)

    def _connect_signals(self):
        self.search_input.returnPressed.connect(self.on_search)
        self.results_list.itemDoubleClicked.connect(self.on_play_selected)
        self.play_btn.clicked.connect(self.on_toggle_play)
        self.prev_btn.clicked.connect(self.on_prev)
        self.next_btn.clicked.connect(self.on_next)
        self.volume.valueChanged.connect(self.on_volume_change)
        # Player signals
        self.player.position_changed.connect(self.on_position_update)
        self.player.state_changed.connect(self.on_state_change)

    @Slot()
    def on_search(self):
        q = self.search_input.text().strip()
        if not q:
            return
        self.results_list.clear()
        self.results_list.addItem("Buscando...")
        self.search_worker = SearchWorker(self.spotify, q)
        self.search_worker.finished_search.connect(self.display_search_results)
        self.search_worker.start()

    @Slot(list)
    def display_search_results(self, results):
        self.results_list.clear()
        self.current_track_list = results
        if not results:
            self.results_list.addItem("No results")
            return
        for t in results:
            item = QListWidgetItem(f"{t['name']} — {t['artist']} ({t['duration']})")
            item.setData(Qt.UserRole, t)
            self.results_list.addItem(item)

    @Slot()
    def on_play_selected(self, item: QListWidgetItem):
        track = item.data(Qt.UserRole)
        self.play_track(track)

    def play_track(self, track):
        # If track is from spotify search we try to resolve via yt-dlp in background
        self.current_playing = track
        q = f"{track['name']} {track['artist']} audio"
        # spawn YTDL worker
        self.yt_worker = YTDLWorker(q)
        self.yt_worker.resolved.connect(lambda url: self._play_resolved_url(url, track))
        self.yt_worker.failed.connect(lambda e: QMessageBox.warning(self, "YT Error", f"No se resolvió: {e}"))
        self.yt_worker.start()

    def _play_resolved_url(self, url, track):
        ok = self.player.play_url(url)
        if ok:
            self.play_btn.setText("⏸")
            # load lyrics async-lite
            l = self.lyrics.get_lyrics(track['name'], track['artist'])
            self.lyrics_view.setPlainText(l)

    @Slot()
    def on_toggle_play(self):
        if self.player.is_playing:
            self.player.pause()
            self.play_btn.setText("▶")
        else:
            # If nothing loaded, try play selected
            if not self.current_playing and self.results_list.currentItem():
                self.on_play_selected(self.results_list.currentItem())
            else:
                self.player.pause()  # it toggles
                self.play_btn.setText("⏸" if self.player.is_playing else "▶")

    @Slot(int, int)
    def on_position_update(self, cur, tot):
        if tot > 0:
            self.progress.setMaximum(tot)
            self.progress.setValue(cur)

    @Slot(bool)
    def on_state_change(self, playing):
        self.play_btn.setText("⏸" if playing else "▶")

    @Slot(int)
    def on_volume_change(self, v):
        self.player.set_volume(v)

    @Slot()
    def on_prev(self):
        # basic previous behaviour
        try:
            idx = next(i for i,t in enumerate(self.current_track_list) if t['id']==self.current_playing['id'])
            prev = self.current_track_list[idx-1] if idx>0 else self.current_track_list[-1]
            self.play_track(prev)
        except Exception:
            pass

    @Slot()
    def on_next(self):
        try:
            idx = next(i for i,t in enumerate(self.current_track_list) if t['id']==self.current_playing['id'])
            nxt = self.current_track_list[(idx+1)%len(self.current_track_list)]
            self.play_track(nxt)
        except Exception:
            pass
