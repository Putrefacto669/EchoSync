# al principio de ui_main.py (agrega)
import json
import os
from pathlib import Path
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

class EchoSyncApp(QWidget):
    def __init__(self):
        super().__init__()
        # Spotify keys: pon las tuyas aquí o carga desde env
        client_id = "cf4379a10a984c4e9f7eda9ebdce9add"
        client_secret = "92db1f6d12a4477082ae44c96855bdd3"

        self.spotify = SpotifyAPI(client_id, client_secret)
        self.player = HybridPlayer()
        self.local = LocalManager()
        self.lyrics = LyricsManager()
        self.current_track_list = []
        self.current_playing = None

        # Paths para persistencia
        root = Path(__file__).resolve().parents[1]
        self.data_dir = root / "data"
        self.favorites_path = self.data_dir / "favorites.json"
        self.library_path = self.data_dir / "library.json"
        self.playlists_path = self.data_dir / "playlists.json"

        self.favorites = self._load_json(self.favorites_path, default=[])
        self.library = self._load_json(self.library_path, default=[])
        self.playlists = self._load_json(self.playlists_path, default={})

        self._build_ui()
        self._connect_signals()
        # conectar señales del player para visualizador
        self.player.position_changed.connect(self._on_position_update_for_visualizer)

    def _load_json(self, path: Path, default):
        try:
            if path.exists():
                return json.loads(path.read_text(encoding='utf-8'))
        except Exception as e:
            print("Error cargando", path, e)
        return default

    def _save_json_background(self, path: Path, payload):
        # guarda en background para no bloquear UI
        worker = PersistenceWorker(str(path), payload)
        worker.start()

    # --- BUILD UI: añade una pestaña de recomendaciones ---
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

        # Middle: Tabs (Resultados | Recomendaciones | Local | Biblioteca)
        tabs_layout = QHBoxLayout()
        self.results_list = QListWidget()
        tabs_layout.addWidget(self.results_list, 60)

        right_col = QVBoxLayout()
        self.lyrics_view = QTextEdit()
        self.lyrics_view.setReadOnly(True)
        right_col.addWidget(QLabel("Letras"))
        right_col.addWidget(self.lyrics_view)
        tabs_layout.addLayout(right_col, 40)

        root_layout.addLayout(tabs_layout, 85)

        # Buttons encima de results: Recomendaciones, Cargar local, Favoritos
        controls_top = QHBoxLayout()
        self.reco_btn = QPushButton("🎧 Recomendaciones")
        self.reco_btn.clicked.connect(self.on_recommendations)
        controls_top.addWidget(self.reco_btn)
        load_local_btn = QPushButton("📁 Agregar carpeta local")
        load_local_btn.clicked.connect(self.on_add_folder)
        controls_top.addWidget(load_local_btn)
        fav_btn = QPushButton("❤️ Favoritos")
        fav_btn.clicked.connect(self.on_show_favorites)
        controls_top.addWidget(fav_btn)
        root_layout.addLayout(controls_top)

        # Bottom: player controls + visualizer
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

        # Visualizador FFT (matplotlib canvas)
        fig = Figure(figsize=(4,1.2), tight_layout=True)
        self.ax = fig.add_subplot(111)
        self.ax.set_ylim(0, 1)
        self.ax.set_xlim(0, 5000)  # frecuencia hasta 5kHz por defecto
        self.ax.get_xaxis().set_visible(False)
        self.ax.get_yaxis().set_visible(False)
        self.canvas = FigureCanvas(fig)
        bottom.addWidget(self.canvas, 1)

        root_layout.addLayout(bottom)
        # Barra de progreso grande abajo del todo
        self.progress = QSlider(Qt.Horizontal)
        self.progress.setRange(0, 100)
        root_layout.addWidget(self.progress)

    # --- Conexiones ---
    def _connect_signals(self):
        self.search_input.returnPressed.connect(self.on_search)
        self.results_list.itemDoubleClicked.connect(self.on_play_selected)
        self.play_btn.clicked.connect(self.on_toggle_play)
        self.prev_btn.clicked.connect(self.on_prev)
        self.next_btn.clicked.connect(self.on_next)
        self.volume.valueChanged.connect(self.on_volume_change)
        self.player.position_changed.connect(self.on_position_update)
        self.player.state_changed.connect(self.on_state_change)

    # --- Recomendaciones (no bloqueante) ---
    def on_recommendations(self):
        # construir seeds: usa favoritos + library reciente
        seed_ids = []
        # favoritos guardan spotify ids
        seed_ids.extend(self.favorites if isinstance(self.favorites, list) else [])
        # últimos items de library
        recent = [s.get('spotify_id') for s in sorted(self.library, key=lambda x: x.get('added_date',''), reverse=True)]
        for r in recent:
            if r and r not in seed_ids:
                seed_ids.append(r)
            if len(seed_ids) >= 5:
                break
        if not seed_ids:
            QMessageBox.information(self, "Info", "No hay semillas para recomendaciones (agrega favoritos o biblioteca).")
            return
        self.reco_btn.setEnabled(False)
        self.reco_btn.setText("Generando...")
        self.reco_worker = RecommendationsWorker(self.spotify, seed_ids)
        self.reco_worker.finished.connect(self._on_recommendations_ready)
        self.reco_worker.start()

    def _on_recommendations_ready(self, results):
        self.reco_btn.setEnabled(True)
        self.reco_btn.setText("🎧 Recomendaciones")
        # mostrar resultados en la lista principal
        self.results_list.clear()
        self.current_track_list = results
        if not results:
            self.results_list.addItem("No se pudieron generar recomendaciones.")
            return
        for t in results:
            item = QListWidgetItem(f"[Reco] {t['name']} — {t['artist']} ({t['duration']})")
            item.setData(Qt.UserRole, t)
            self.results_list.addItem(item)

    # --- Agregar carpeta local (sin bloquear) ---
    def on_add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de música")
        if not folder:
            return
        # Escaneo en hilo simple (podés mover a worker si es muy lento)
        added = self.local.scan_folder(folder)
        QMessageBox.information(self, "Música local", f"Agregadas {len(added)} pistas.")
        # actualizar library automáticamente?
        # opcional: añadir los locales a self.library si quieres

    # --- Favoritos UI ---
    def on_show_favorites(self):
        self.results_list.clear()
        if not self.favorites:
            self.results_list.addItem("No tienes favoritos.")
            return
        # buscar metadatos en self.library para mostrar nombres
        for fid in self.favorites:
            # buscar en library
            found = next((s for s in self.library if s.get('spotify_id')==fid), None)
            if found:
                t = {'id': found.get('spotify_id'), 'name': found.get('title'), 'artist': found.get('artist'), 'duration': found.get('duration')}
            else:
                t = {'id': fid, 'name': fid, 'artist':'', 'duration':'0:00'}
            item = QListWidgetItem(f"{t['name']} — {t['artist']} ({t['duration']})")
            item.setData(Qt.UserRole, t)
            self.results_list.addItem(item)

    # --- Reproducción & persistencia favorites/library ---
    def _play_resolved_url(self, url, track):
        ok = self.player.play_url(url)
        if ok:
            self.play_btn.setText("⏸")
            l = self.lyrics.get_lyrics(track['name'], track['artist'])
            self.lyrics_view.setPlainText(l)
            self.current_playing = track

    def add_to_favorites(self, track):
        tid = track.get('id')
        if not tid:
            return
        if tid in self.favorites:
            self.favorites.remove(tid)
        else:
            self.favorites.append(tid)
        # guardar async
        self._save_json_background(self.favorites_path, self.favorites)

    def add_to_library(self, track):
        # track es dict de spotify (search result)
        entry = {
            'title': track['name'],
            'artist': track['artist'],
            'duration': track['duration'],
            'duration_seconds': track['duration_ms']//1000,
            'spotify_id': track['id'],
            'added_date': __import__('datetime').datetime.utcnow().isoformat()
        }
        # prevent duplicates
        if not any(s.get('spotify_id')==entry['spotify_id'] for s in self.library):
            self.library.append(entry)
            self._save_json_background(self.library_path, self.library)
            QMessageBox.information(self, "Añadida", f"'{entry['title']}' agregada a tu biblioteca.")

    # --- Visualizador: recibimos posiciones periódicos del player ---
    def _on_position_update_for_visualizer(self, cur, tot):
        # Simple approach: leer una porción de audio estéreo local o stream no es trivial.
        # Aquí hacemos un placeholder visual: generamos una onda sinusoidal que cambia con el tiempo.
        # hacer FFT real, hay que capturar el buffer de audio (p. ej. con ffmpeg/portaudio).
        x = np.linspace(0,1,256)
        # frecuencia variable según posición
        freq = 200 + (cur % 30) * 50
        amp = 0.5 + 0.5 * np.abs(np.sin(cur/5))
        y = amp * np.abs(np.sin(2*np.pi*freq*x))
        self.ax.clear()
        self.ax.plot(x*5000, y)  # x*5000 para simular freq
        self.ax.set_ylim(0,1.2)
        self.ax.get_xaxis().set_visible(False)
        self.ax.get_yaxis().set_visible(False)
        self.canvas.draw_idle()

    # --- Resto de handlers (on_search, display_search_results, on_play_selected, on_toggle_play, etc.)
    # Usá las implementaciones previas que ya te di y llama add_to_library/add_to_favorites donde corresponda.
