# echo_sync/spotify_api.py
import base64, requests
from cachetools import TTLCache
from datetime import datetime, timedelta

class SpotifyAPI:
    def __init__(self, client_id, client_secret, market='US'):
        self.client_id = client_id
        self.client_secret = client_secret
        self.market = market
        self._cache = TTLCache(maxsize=100, ttl=300)  # small cache

    def _get_token(self):
        key = 'access_token'
        cached = self._cache.get(key)
        if cached and cached.get('expiry') > datetime.utcnow():
            return cached['token']
        creds = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(creds.encode()).decode()
        headers = {'Authorization': f'Basic {encoded}'}
        try:
            r = requests.post('https://accounts.spotify.com/api/token',
                              headers=headers,
                              data={'grant_type': 'client_credentials'}, timeout=10)
            r.raise_for_status()
            d = r.json()
            token = d['access_token']
            expiry = datetime.utcnow() + timedelta(seconds=d.get('expires_in', 3600)-60)
            self._cache[key] = {'token': token, 'expiry': expiry}
            return token
        except Exception as e:
            print("Spotify token error:", e)
            return None

    def search_tracks(self, q, limit=20):
        token = self._get_token()
        if not token: return []
        headers = {'Authorization': f'Bearer {token}'}
        params = {'q': q, 'type': 'track', 'limit': limit, 'market': self.market}
        try:
            r = requests.get('https://api.spotify.com/v1/search', headers=headers, params=params, timeout=12)
            r.raise_for_status()
            data = r.json()
            out = []
            for item in data.get('tracks', {}).get('items', []):
                out.append({
                    'id': item['id'],
                    'name': item['name'],
                    'artist': ', '.join([a['name'] for a in item['artists']]),
                    'album': item['album']['name'],
                    'duration_ms': item['duration_ms'],
                    'duration': f"{(item['duration_ms']//1000)//60}:{(item['duration_ms']//1000)%60:02d}",
                    'image_url': item['album']['images'][0]['url'] if item['album']['images'] else None,
                    'external_url': item['external_urls']['spotify'],
                })
            return out
        except Exception as e:
            print("Spotify search error:", e)
            return []

    def get_recommendations(self, seed_tracks, limit=15):
        token = self._get_token()
        if not token or not seed_tracks:
            return []
        headers = {'Authorization': f'Bearer {token}'}
        params = {'seed_tracks': ','.join(seed_tracks[:5]), 'limit': limit, 'market': self.market}
        try:
            r = requests.get('https://api.spotify.com/v1/recommendations', headers=headers, params=params, timeout=12)
            r.raise_for_status()
            data = r.json()
            out = []
            for item in data.get('tracks', []):
                out.append({
                    'id': item['id'],
                    'name': item['name'],
                    'artist': ', '.join([a['name'] for a in item['artists']]),
                    'album': item['album']['name'],
                    'duration_ms': item['duration_ms'],
                    'duration': f"{(item['duration_ms']//1000)//60}:{(item['duration_ms']//1000)%60:02d}",
                    'image_url': item['album']['images'][0]['url'] if item['album']['images'] else None,
                    'external_url': item['external_urls']['spotify']
                })
            return out
        except Exception as e:
            print("Spotify recommendations error:", e)
            return []
