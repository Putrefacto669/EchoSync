# echo_sync/local_manager.py
from pathlib import Path
import mutagen

SUPPORTED = {'.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.opus'}

class LocalManager:
    def __init__(self):
        self.tracks = []

    def scan_folder(self, folder_path):
        folder = Path(folder_path)
        found = []
        for f in folder.rglob('*'):
            if f.suffix.lower() in SUPPORTED:
                info = self._extract_metadata(f)
                found.append(info)
        self.tracks.extend(found)
        return found

    def _extract_metadata(self, path):
        try:
            audio = mutagen.File(path)
            title = str(audio.get('TIT2', path.stem)) if audio else path.stem
            artist = str(audio.get('TPE1', 'Unknown Artist')) if audio else 'Unknown Artist'
            duration = int(audio.info.length) if audio and hasattr(audio, 'info') else 0
        except Exception:
            title = path.stem
            artist = 'Unknown Artist'
            duration = 0
        return {
            'id': f"local_{hash(str(path))}",
            'name': title,
            'artist': artist,
            'album': '',
            'duration_ms': duration*1000,
            'duration': f"{duration//60}:{duration%60:02d}",
            'file_path': str(path),
            'is_local': True
        }
