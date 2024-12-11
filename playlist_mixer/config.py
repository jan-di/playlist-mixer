"""
Config
"""

from os import path, unlink
from zoneinfo import ZoneInfo
from dataclasses import dataclass, asdict
import json
from typing import Self

CLI_ENVVAR_PREFIX = "MIXER"
USER_CONFIG_FILE = "user-config.json"


class Config:
    """
    Global application configuration
    """

    CONFIG_DIR_ENV = f"{CLI_ENVVAR_PREFIX}_CONFIG_DIR"
    CACHE_DIR_ENV = f"{CLI_ENVVAR_PREFIX}_CACHE_DIR"
    TMEZONE_ENV = f"{CLI_ENVVAR_PREFIX}_TIMEZONE"
    SPOTIFY_CLIENT_ID_ENV = f"{CLI_ENVVAR_PREFIX}_SPOTIFY_CLIENT_ID"
    SPOTIFY_CLIENT_SECRET_ENV = f"{CLI_ENVVAR_PREFIX}_SPOTIFY_CLIENT_SECRET"
    SPOTIFY_REDIRECT_URI_ENV = f"{CLI_ENVVAR_PREFIX}_SPOTIFY_REDIRECT_URI"

    config_dir: str = None
    cache_dir: str = None
    timezone: ZoneInfo = None


@dataclass
class UserConfig:
    """
    User related config file
    """

    user_id: str
    spotify_client_id: str
    spotify_client_secret: str
    spotify_client_redirect_uri: str

    @classmethod
    def store_user_config(cls: type, user_config: Self) -> None:
        """
        Store user config to file
        """

        user_config_path = path.join(Config.config_dir, USER_CONFIG_FILE)

        with open(user_config_path, "w", encoding="utf8") as f:
            user_config_json = asdict(user_config)
            f.write(json.dumps(user_config_json))

    @classmethod
    def load_user_config(cls: type) -> Self | None:
        """
        Load user config from file
        """

        user_config_path = path.join(Config.config_dir, USER_CONFIG_FILE)

        if not path.exists(user_config_path):
            return None

        with open(user_config_path, "r", encoding="utf8") as f:
            user_config_json = json.load(f)
            user_config = UserConfig(**user_config_json)

        return user_config

    @classmethod
    def delete_user_config(cls: type) -> None:
        """
        Delete user config file
        """

        user_config_path = path.join(Config.config_dir, USER_CONFIG_FILE)
        if path.exists(user_config_path):
            unlink(user_config_path)
