"""
Playlist Mixer
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import random
import os
from os import path

import click
import spotipy
from spotipy.oauth2 import SpotifyOAuth, CacheFileHandler, SpotifyOauthError
from spotipy.exceptions import SpotifyException

CLI_ENVVAR_PREFIX = "MIXER"


def add_spotify_client_options(f):
    """Common options for using a spotify api client"""
    f = click.option(
        "-u",
        "--username",
        help="Spotify Username (env: {CLI_ENVVAR_PREFIX}_SPOTIFY_USERNAME)",
        envvar=f"{CLI_ENVVAR_PREFIX}_SPOTIFY_USERNAME",
        required=True,
    )(f)
    f = click.option(
        "--spotify-client-id",
        help=f"Spotify Client ID (env: {CLI_ENVVAR_PREFIX}_SPOTIFY_CLIENT_ID)",
        envvar=f"{CLI_ENVVAR_PREFIX}_SPOTIFY_CLIENT_ID",
        required=True,
    )(f)
    f = click.option(
        "--spotify-client-secret",
        help=f"Spotify Client Secret (env: {CLI_ENVVAR_PREFIX}_SPOTIFY_CLIENT_SECRET)",
        envvar=f"{CLI_ENVVAR_PREFIX}_SPOTIFY_CLIENT_SECRET",
        required=True,
    )(f)
    f = click.option(
        "--spotify-client-redirect-uri",
        help=f"Spotify Client Secret (env: {CLI_ENVVAR_PREFIX}_SPOTIFY_REDIRECT_URI)",
        envvar=f"{CLI_ENVVAR_PREFIX}_SPOTIFY_REDIRECT_URI",
        required=True,
    )(f)
    return f


@click.group()
@click.option(
    "-tz",
    "--timezone",
    help=f"Timezone to use. (env: {CLI_ENVVAR_PREFIX}_TIMEZONE)",
    default="UTC",
)
def cli(timezone):
    """
    Playlist Mixer for Spotify.
    """


@cli.command(name="mix")
@add_spotify_client_options
@click.option("-p", "--playlist-id", required=True, help="Playlist ID to mix")
def cli_mix(
    username,
    spotify_client_id,
    spotify_client_secret,
    spotify_client_redirect_uri,
    playlist_id,
):
    """Command: Mix playlist"""
    cli_util = CliUtil(
        spotify_client_id=spotify_client_id,
        spotify_client_secret=spotify_client_secret,
        spotify_client_redirect_uri=spotify_client_redirect_uri,
    )
    click.echo(f"Logging in as {username}..")
    token = cli_util.get_token(username)

    if token:
        click.echo("Mixing playlist..")
        sp = spotipy.Spotify(auth=token)

        zoneinfo = ZoneInfo("Europe/Berlin")

        now = datetime.now(tz=zoneinfo)
        # subtract one week
        two_weeks_ago = now - timedelta(weeks=2)

        pm = PlaylistMixer(sp)
        track_pool1 = pm.get_playlist_tracks(
            playlist_id, added_after=two_weeks_ago, date_inclusive=True
        )
        track_pool2 = pm.get_playlist_tracks(
            playlist_id, added_before=two_weeks_ago, date_inclusive=False
        )

        random.shuffle(track_pool1)
        random.shuffle(track_pool2)

        managed_playlist_id = ensure_playlist(
            sp, path.join(cli_util.data_dir, "playlist_id.txt")
        )

        dts = now.strftime("%Y-%m-%d %H:%M:%S")
        sp.playlist_change_details(managed_playlist_id, name=f"Mixed {dts}")

        track_ids = [track["id"] for track in track_pool1 + track_pool2]

        clear_playlist(sp, managed_playlist_id)

        for i in range(0, len(track_ids), 100):
            sp.playlist_add_items(managed_playlist_id, track_ids[i : i + 100])

        managed_playlist = sp.playlist(managed_playlist_id)
        click.echo(
            f"Playlist mixed successfully: {managed_playlist['external_urls']['spotify']}"
        )


@cli.command(name="login")
@add_spotify_client_options
def cli_login(
    username, spotify_client_id, spotify_client_secret, spotify_client_redirect_uri
):
    """Command: Login to Spotify"""
    cli_util = CliUtil(
        spotify_client_id=spotify_client_id,
        spotify_client_secret=spotify_client_secret,
        spotify_client_redirect_uri=spotify_client_redirect_uri,
    )
    try:
        cli_util.get_token(username, open_browser=True)
        click.echo("Logged in successfully.")
    except SpotifyOauthError as e:
        click.echo("Failed to login to spotify.")
        click.echo(e)


class CliUtil:
    """
    Utility class for CLI
    """

    def __init__(
        self, spotify_client_id: str, spotify_client_secret, spotify_client_redirect_uri
    ):
        self.data_dir = ".playlist-mixer/data"
        self.cache_dir = ".playlist-mixer/cache"

        self.spotify_client_id = spotify_client_id
        self.spotify_client_secret = spotify_client_secret
        self.spotify_client_redirect_uri = spotify_client_redirect_uri

        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_token(self, username, open_browser=False):
        """Get token, show interactive prompt if required"""
        cache_path = path.join(self.cache_dir, f"user-{username}.json")
        cache_handler = CacheFileHandler(cache_path=cache_path, username=username)
        auth_manager = SpotifyOAuth(
            scope="playlist-modify-private,playlist-modify-public",
            cache_handler=cache_handler,
            client_id=self.spotify_client_id,
            client_secret=self.spotify_client_secret,
            redirect_uri=self.spotify_client_redirect_uri,
            show_dialog=True,
            open_browser=open_browser,
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

        # Inject audio features to all tracks
        # self.__inject_audio_features(tracks)

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

    def __inject_audio_features(self, tracks: list[dict]):
        """
        Retreives and injects audio features into a given track list
        """
        track_ids = [track["track"]["id"] for track in tracks]

        for i in range(0, len(track_ids), 100):
            audio_features = self.sp.audio_features(track_ids[i : i + 100])
            for track, af in zip(tracks[i : i + 100], audio_features):
                track["audio_features"] = af


def show_tracks(tracks):
    for i, item in enumerate(tracks["items"]):
        track = item["track"]
        print("   %d %32.32s %s" % (i, track["artists"][0]["name"], track["name"]))


def ensure_playlist(sp: spotipy.Spotify, playlist_id_file: str) -> str:
    try:
        with open(playlist_id_file, "r", encoding="utf8") as f:
            playlist_id = f.read()
            sp.playlist(playlist_id)
    except FileNotFoundError:
        playlist_id = None
    except SpotifyException as e:
        if e.http_status == 404:
            playlist_id = None
        else:
            raise e

    if playlist_id is None:
        playlist = sp.user_playlist_create(
            sp.me()["id"], "Mixed Playlist123", public=False
        )
        with open(playlist_id_file, "w", encoding="utf8") as f:
            f.write(playlist["id"])

    return playlist_id


def clear_playlist(sp: spotipy.Spotify, playlist_id: str):
    sp.playlist_replace_items(playlist_id, [])


def main():
    """Main entrypoint"""
    cli(
        auto_envvar_prefix="MIXER",
        max_content_width=160,
    )


if __name__ == "__main__":
    main()
