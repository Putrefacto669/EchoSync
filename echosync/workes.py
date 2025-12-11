# echo_sync/workers.py
from PySide6.QtCore import QThread, Signal
from .spotify_api import SpotifyAPI
import yt_dlp

class SearchWorker(QThread):
    finished_search = Signal(list)  # results

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
        self.seeds = seed_ids

    def run(self):
        res = self.spotify.get_recommendations(self.seeds, limit=15)
        self.finished.emit(res)

class YTDLWorker(QThread):
    resolved = Signal(str)  # direct URL or path
    failed = Signal(str)

    def __init__(self, query):
        super().__init__()
        self.query = query

    def run(self):
        opts = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.query, download=False)
                # If search returned entries, pick first
                video = info['entries'][0] if 'entries' in info else info
                url = video.get('url') or f"https://www.youtube.com/watch?v={video.get('id')}"
                self.resolved.emit(url)
        except Exception as e:
            self.failed.emit(str(e))
