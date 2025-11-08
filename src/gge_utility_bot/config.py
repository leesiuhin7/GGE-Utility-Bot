import json

from typing_extensions import TypedDict


class ServerConfigType(TypedDict):
    reconnect_cooldown: float
    url: str


class PlayerInfoConfigType(TypedDict):
    server: str
    username: str
    password: str


class AttackListenerServiceConfigType(TypedDict):
    enabled: bool


class StormSearcherServiceConfigType(TypedDict):
    enabled: bool


class ServiceConfigType(TypedDict):
    attack_listener: AttackListenerServiceConfigType
    storm_searcher: StormSearcherServiceConfigType


class PlayerConfigType(TypedDict):
    info: PlayerInfoConfigType
    services: ServiceConfigType
    visibility: list[int]  # Guild ids


class AttackListenerConfigType(TypedDict):
    request_cooldown: float
    request_timeout: float


class LoggingLevelConfigType(TypedDict):
    name: str | None
    level: int


class LoggingConfigType(TypedDict):
    level_configs: list[LoggingLevelConfigType]


class GuildInfoConfigType(TypedDict):
    guild_id: int
    config_channel: int  # Channel id


class DiscordConfigType(TypedDict):
    guilds: list[GuildInfoConfigType]


class ConfigType(TypedDict):
    server: ServerConfigType
    players: list[PlayerConfigType]
    attack_listener: AttackListenerConfigType
    logging: LoggingConfigType
    discord: DiscordConfigType


cfg: ConfigType


def init(config_path: str) -> None:
    global cfg
    with open(config_path, "r") as file:
        cfg = json.load(file)
