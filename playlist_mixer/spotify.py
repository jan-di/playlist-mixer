"""
Auth Utils for Spotify
"""

from os import path

from spotipy.oauth2 import CacheFileHandler, SpotifyOAuth
from spotipy import Spotify as Spotipy

from playlist_mixer.config import Config, UserConfig


class SpotifyAuth:
    """
    Helper Utility for Spotify Auth
    """

    def __init__(
        self,
        spotify_client_id: str,
        spotify_client_secret: str,
        spotify_client_redirect_uri: str,
    ):
        self.spotify_client_id = spotify_client_id
        self.spotify_client_secret = spotify_client_secret
        self.spotify_client_redirect_uri = spotify_client_redirect_uri

    def get_token(self):
        """Get token, show interactive prompt if required"""
        cache_path = path.join(Config.cache_dir, "user-auth.json")
        cache_handler = CacheFileHandler(cache_path=cache_path)
        auth_manager = SpotifyOAuth(
            scope="playlist-modify-private,playlist-modify-public",
            cache_handler=cache_handler,
            client_id=self.spotify_client_id,
            client_secret=self.spotify_client_secret,
            redirect_uri=self.spotify_client_redirect_uri,
            show_dialog=True,
            open_browser=True,
        )

        token_info = auth_manager.validate_token(
            auth_manager.cache_handler.get_cached_token()
        )

        if not token_info:
            code = auth_manager.get_auth_response()
            token = auth_manager.get_access_token(code, as_dict=False)
        else:
            return token_info["access_token"]

        # Auth'ed API request
        if token:
            return token
        else:
            return None

    @classmethod
    def get_client(cls: type) -> Spotipy:
        """
        Get Spotify Client
        """

        user_config = UserConfig.load_user_config()
        if not user_config:
            raise RuntimeError("No user config found. Please login first")

        spotify_auth = cls(
            user_config.spotify_client_id,
            user_config.spotify_client_secret,
            user_config.spotify_client_redirect_uri,
        )

        token = spotify_auth.get_token()

        if not token:
            raise RuntimeError("Failed to get valid token. Pleas login again")

        return Spotipy(auth=token)
