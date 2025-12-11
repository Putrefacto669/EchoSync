# echo_sync/player.py
import vlc
from PySide6.QtCore import QObject, Signal, QTimer

class HybridPlayer(QObject):
    position_changed = Signal(int, int)  # current_seconds, total_seconds
    state_changed = Signal(bool)  # is_playing

    def __init__(self):
        super().__init__()
        # Create VLC instance
        self.instance = vlc.Instance('--quiet')
        self.player = self.instance.media_player_new()
        self.is_playing = False
        self.current_media_meta = None
        self._timer = QTimer()
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._emit_position)
        # attach end callback
        ev = self.player.event_manager()
        ev.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end)

    def _on_end(self, event):
        self.is_playing = False
        self.state_changed.emit(False)

    def _emit_position(self):
        if self.is_playing:
            ms = self.player.get_time()
            total = self.player.get_length()
            cur_s = int(ms/1000) if ms and ms>0 else 0
            tot_s = int(total/1000) if total and total>0 else 0
            self.position_changed.emit(cur_s, tot_s)

    def play_url(self, url, start_paused=False):
        try:
            media = self.instance.media_new(url)
            self.player.set_media(media)
            self.player.play()
            # wait briefly to pick state
            self.is_playing = True
            self.state_changed.emit(True)
            self._timer.start()
            if start_paused:
                self.pause()
            return True
        except Exception as e:
            print("Error play_url:", e)
            return False

    def play_local(self, file_path):
        return self.play_url(file_path)

    def pause(self):
        if self.player:
            self.player.pause()
            self.is_playing = not self.is_playing
            self.state_changed.emit(self.is_playing)
            # keep timer running to allow resumed updates

    def stop(self):
        try:
            self.player.stop()
            self.is_playing = False
            self.state_changed.emit(False)
            self._timer.stop()
        except:
            pass

    def set_volume(self, vol):
        try:
            self.player.audio_set_volume(max(0, min(100, int(vol))))
        except:
            pass

    def seek(self, seconds):
        try:
            self.player.set_time(int(seconds * 1000))
        except:
            pass
