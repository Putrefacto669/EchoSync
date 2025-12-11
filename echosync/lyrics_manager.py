# echo_sync/lyrics_manager.py
import requests
from pathlib import Path

class LyricsManager:
    def __init__(self):
        pass

    def get_lyrics_ovh(self, track, artist):
        try:
            r = requests.get(f"https://api.lyrics.ovh/v1/{artist}/{track}", timeout=6)
            if r.status_code == 200:
                return r.json().get('lyrics')
        except:
            pass
        return None

    def get_local(self, track, artist):
        filename = Path("lyrics") / f"{artist} - {track}.txt"
        if filename.exists():
            return filename.read_text(encoding='utf-8')
        return None

    def get_lyrics(self, track, artist):
        l = self.get_local(track, artist)
        if l: return l
        l = self.get_lyrics_ovh(track, artist)
        if l: return l
        return "Letras no disponibles"
