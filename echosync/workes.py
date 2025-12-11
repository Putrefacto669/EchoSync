# echo_sync/workers.py  (añadir/actualizar)
from PySide6.QtCore import QThread, Signal
from .spotify_api import SpotifyAPI
import yt_dlp
import json
from pathlib import Path

class SearchWorker(QThread):
    finished_search = Signal(list)
    def __init__(self, spotify: SpotifyAPI, query: str):
        super().__init__()
        self.spotify = spotify
        self.query = query
    def run(self):
        res = self.spotify.search_tracks(self.query, limit=25)
        self.finished_search.emit(res)

class RecommendationsWorker(QThread):
    finished = Signal(list)
    def __init__(self, spotify: SpotifyAPI, seed_ids):
        super().__init__()
        self.spotify = spotify
        self.seeds = seed_ids or []
    def run(self):
        try:
            res = self.spotify.get_recommendations(self.seeds, limit=15)
        except Exception as e:
            res = []
        self.finished.emit(res)

class YTDLWorker(QThread):
    resolved = Signal(str)
    failed = Signal(str)
    def __init__(self, query):
        super().__init__()
        self.query = query
    def run(self):
        opts = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'skip_download': True}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.query, download=False)
                video = info['entries'][0] if 'entries' in info else info
                # Prefer 'url' if direct stream, fallback to watch url
                url = video.get('url') or f"https://www.youtube.com/watch?v={video.get('id')}"
                self.resolved.emit(url)
        except Exception as e:
            self.failed.emit(str(e))

class PersistenceWorker(QThread):
    finished = Signal(bool, str)  # success, path
    def __init__(self, path: str, payload):
        super().__init__()
        self.path = Path(path)
        self.payload = payload
    def run(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.payload, f, indent=2, ensure_ascii=False)
            self.finished.emit(True, str(self.path))
        except Exception as e:
            self.finished.emit(False, f"{e}")
