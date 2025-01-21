# Playlist Mixer for Spotify

Playlist Mixer is a CLI tool for Spotify to achieve true randomness. Because bultin shuffle is not really random.
It works by using existing playlists to update other ones. Tracks ary randomly added to the playlist, which is designed to be played without shuffle/smart shuffle enabled.

## Install

1. Install playlist-mixer from pypi. Its recommended to use [pipx](https://pipx.pypa.io/stable/) instead of pip, to prevent any dependency conflicts.

```shell
# pipx
pipx install playlist-mixer

# pip
pip install playlist-mixer
```

2. Ensure playlist-mixer is installed successfully

```shell
playlist-mixer version
```

3. Create a new Spotify App in [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)

- App name: _choose for yourself_
- App description: _choose for yourself_
- Redirect URIs: `http://localhost:8000`
- APIs intended to use: Web API

## Usage

1. Login with your Spotify account and App. You need to login only once, credentials are persisted in your home folder.
You need the following information:

- App ID (see Spotify Developer Dashboard)
- App Secret (see Spotify Developer Dashboard)
- Redirect URL: `http://localhost:8000`

```shell
playlist-mixer login
```
A browser will open and allow you to Login with your Spotify Account.

2. Create a playlist. This playlist will be filled with your tracks in a random order. Create it and setup your privacy, title etc.

After creating the playlist, copy a link to the playlist (share > link). This link is used as a playlist target.

3. Mix playlists

```shell
# Use a playlist as source, and mix all tracks in another playlist
playlist-mixer mix --source <source-playlist> --playlist <target-playlist>

# A source/playlist can be either a link to a playlist
# https://open.spotify.com/playlist/playlistid
# or a URI to playlist
# spotify:playlist:playlistid

# Mix a playlist with multiple sources
playlist-mixer mix --source <source-playlist> --source <source-playlist> --playlist <target-playlist>

# Focus on the last x days. Focussing means, that tracks that were added in the last x days, are on top of the mixed playlist.
playlist-mixer mix --source <source-playlist> --playlist <target-playlist> --focus 10
```