"""
Playlist Mixer
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import random
from os import path, environ
from pathlib import Path
import importlib

import click
import spotipy
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOauthError

from playlist_mixer.config import Config, UserConfig
from playlist_mixer.spotify import SpotifyAuth


@click.group()
@click.option(
    "--timezone",
    help=f"Timezone to use. (env: {Config.TMEZONE_ENV})",
    envvar=Config.TMEZONE_ENV,
    default="UTC",
)
@click.option(
    "--config-dir",
    help=f"Config directory. Defaults to $XDG_CONFIG_HOME/playlist-mixer or ~/.config/playlist-mixer (env: {Config.CONFIG_DIR_ENV})",
    envvar=Config.CONFIG_DIR_ENV,
)
@click.option(
    "--cache-dir",
    help=f"Cache directory. Defaults to $XDG_CACHE_HOME/playlist-mixer or ~/.cache/playlist-mixer (env: {Config.CACHE_DIR_ENV})",
    envvar=Config.CACHE_DIR_ENV,
)
def cli(
    timezone: str = None,
    config_dir: str = None,
    cache_dir: str = None,
):
    """
    Playlist Mixer for Spotify.
    """

    user_home = Path.home()

    # Determine and ensure config directory
    if config_dir is None:
        xdg_config_home = environ.get("XDG_CONFIG_HOME", None)
        if xdg_config_home is not None:
            config_dir = path.join(xdg_config_home, "playlist-mixer")

    if config_dir is None:
        config_dir = path.join(user_home, ".config/playlist-mixer")

    Config.config_dir = path.abspath(config_dir)
    Path(Config.config_dir).mkdir(parents=True, exist_ok=True)

    # Determine and ensure cache directory
    if cache_dir is None:
        xdg_cache_home = environ.get("XDG_CACHE_HOME", None)
        if xdg_cache_home is not None:
            cache_dir = path.join(xdg_cache_home, "playlist-mixer")

    if cache_dir is None:
        cache_dir = path.join(user_home, ".cache/playlist-mixer")

    Config.cache_dir = path.abspath(cache_dir)
    click.echo(Config.cache_dir)
    Path(Config.cache_dir).mkdir(parents=True, exist_ok=True)

    # Determine timezone
    Config.timezone = ZoneInfo(timezone)


@cli.command(name="mix")
@click.option("-p", "--playlist", help="Output playlist id")
@click.option("-s", "--source", "sources", help="Source playlist uri", multiple=True)
def cli_mix(
    playlist,
    sources: list[str],
):
    """Command: Mix playlist"""
    try:
        sp = SpotifyAuth.get_client()
    except RuntimeError as e:
        click.echo(click.style(f"Error: {e}", fg="red"))
        return

    click.echo("Mixing playlist..")
    pm = PlaylistMixer(sp)

    click.echo(f"Fetching {len(sources)} sources..")
    for source in sources:

        source_playlist = pm.get_playlist(source)
        click.echo(
            f"Fetched Playlist: {source_playlist['name']} ({source_playlist['id']}) with {len(source_playlist['tracks'])}"
        )

    now = datetime.now(tz=Config.timezone)
    # subtract two weeks
    two_weeks_ago = now - timedelta(weeks=2)

    track_pool1 = []
    track_pool2 = []

    for source in sources:
        track_pool1 += pm.get_playlist_tracks(
            source, added_after=two_weeks_ago, date_inclusive=True
        )
        track_pool2 += pm.get_playlist_tracks(
            source, added_before=two_weeks_ago, date_inclusive=False
        )

    random.shuffle(track_pool1)
    random.shuffle(track_pool2)

    click.echo(f"Track pool 1: {len(track_pool1)}")
    click.echo(f"Track pool 2: {len(track_pool2)}")

    try:
        managed_playlist = sp.playlist(playlist)
    except SpotifyException as e:
        click.echo(click.style(f"Error: {e}", fg="red"))
        return

    dts = now.strftime("%Y-%m-%d %H:%M:%S")
    sp.playlist_change_details(managed_playlist["id"], name=f"Mixed {dts}")

    track_ids = [track["id"] for track in track_pool1 + track_pool2]

    pm.clear_playlist(managed_playlist["id"])

    for i in range(0, len(track_ids), 100):
        sp.playlist_add_items(managed_playlist["id"], track_ids[i : i + 100])

    click.echo(
        f"Playlist mixed successfully: {managed_playlist['external_urls']['spotify']}"
    )


@cli.command(name="login")
@click.option(
    "--client-id",
    help=f"Spotify Client ID (env: {Config.SPOTIFY_CLIENT_ID_ENV})",
    envvar=Config.SPOTIFY_CLIENT_ID_ENV,
)
@click.option(
    "--client-secret",
    help=f"Spotify Client Secret (env: {Config.SPOTIFY_CLIENT_SECRET_ENV})",
    envvar=Config.SPOTIFY_CLIENT_SECRET_ENV,
)
@click.option(
    "--client-redirect-uri",
    help=f"Spotify Client Secret (env: {Config.SPOTIFY_REDIRECT_URI_ENV})",
    envvar=Config.SPOTIFY_REDIRECT_URI_ENV,
)
def cli_login(
    client_id: str = None,
    client_secret: str = None,
    client_redirect_uri: str = None,
):
    """Command: Login to Spotify"""

    if client_secret and not environ.get(Config.SPOTIFY_CLIENT_SECRET_ENV, None):
        click.echo(
            click.style(
                "Warning: Providing the Client Secret via command line is consided insecure. Please use environment variable or interactive input instead.",
                fg="yellow",
            )
        )

    if client_id is None:
        client_id = click.prompt("Spotify Client ID")

    if client_secret is None:
        client_secret = click.prompt("Spotify Client Secret", hide_input=True)

    if client_redirect_uri is None:
        client_redirect_uri = click.prompt("Spotify Client Redirect URI")

    spotify_auth = SpotifyAuth(
        spotify_client_id=client_id,
        spotify_client_secret=client_secret,
        spotify_client_redirect_uri=client_redirect_uri,
    )
    try:
        token = spotify_auth.get_token()
    except SpotifyOauthError as e:
        click.echo(click.style("Failed to login to spotify:", fg="red"))
        click.echo(click.style(e, fg="red"))
        return

    sp = spotipy.Spotify(auth=token)
    me = sp.me()

    user_config = UserConfig(
        user_id=me["id"],
        spotify_client_id=client_id,
        spotify_client_secret=client_secret,
        spotify_client_redirect_uri=client_redirect_uri,
    )
    UserConfig.store_user_config(user_config)

    click.echo(f"Logged in successfully as {me['display_name']} ({me['id']})")


@cli.command(name="logout")
def cli_logout():
    """Command: Logout from Spotify"""

    UserConfig.delete_user_config()
    click.echo("Logged out successfully")


@cli.command(name="version")
def cli_version():
    """Command: Show version"""

    version = importlib.metadata.version("playlist_mixer")

    click.echo(f"Playlist Mixer {version}")


class PlaylistMixer:
    """
    Class for managing and mixing playlists
    """

    def __init__(self, sp: spotipy.Spotify):
        self.sp = sp
        self.playlist_cache = {}

    def get_playlist(self, playlist_id: str):
        """
        Get full playlist, including all tracks and audio features.
        Uses cache if available.
        """
        if playlist_id in self.playlist_cache:
            return self.playlist_cache[playlist_id]

        # Playlist includes the first 100 tracks
        playlist = self.sp.playlist(playlist_id)

        # Retreive all remaining tracks
        track_results = playlist["tracks"]
        tracks = playlist["tracks"]["items"]
        while track_results["next"]:
            track_results = self.sp.next(track_results)
            tracks.extend(track_results["items"])

        # Remove local tracks, currently not supported
        tracks = list(filter(lambda d: not d["is_local"], tracks))
        playlist["tracks"] = tracks

        self.playlist_cache[playlist_id] = playlist
        return playlist

    def get_playlist_tracks(
        self,
        playlist_id: str,
        added_before: datetime = None,
        added_after: datetime = None,
        date_inclusive: bool = False,
    ) -> list[dict]:
        """
        Get tracks from a playlist, optionally filtered
        """
        playlist = self.get_playlist(playlist_id)

        result = []
        for track in playlist["tracks"]:

            if added_before and added_after and added_before < added_after:
                raise ValueError("added_before must be greater than added_after")

            if added_before or added_after:
                added_at = datetime.fromisoformat(track["added_at"])
                if added_after and (
                    date_inclusive
                    and added_at < added_after
                    or not date_inclusive
                    and added_at <= added_after
                ):
                    continue
                if added_before and (
                    date_inclusive
                    and added_at > added_before
                    or not date_inclusive
                    and added_at >= added_before
                ):
                    continue
            result.append(track["track"])

        return result

    def clear_playlist(self, playlist_id: str):
        """
        Clear all tracks from a playlist
        """

        self.sp.playlist_replace_items(playlist_id, [])


def main():
    """Main entrypoint"""

    cli(
        max_content_width=160,
    )


if __name__ == "__main__":
    main()
