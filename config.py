import json
from typing import TypedDict


class ServerConfigType(TypedDict):
    reconnect_cooldown: float
    url: str


class PlayerInfoConfigType(TypedDict):
    server: str
    username: str
    password: str


class AttackListenerServiceConfigType(TypedDict):
    enabled: bool
    guild_routes: list[int]


class StormSearcherServiceConfigType(TypedDict):
    enabled: bool


class ServiceConfigType(TypedDict):
    attack_listener: AttackListenerServiceConfigType
    storm_searcher: StormSearcherServiceConfigType


class PlayerConfigType(TypedDict):
    info: PlayerInfoConfigType
    services: ServiceConfigType


class AttackListenerConfigType(TypedDict):
    request_cooldown: float


class LoggingLevelConfigType(TypedDict):
    name: str | None
    level: int


class LoggingConfigType(TypedDict):
    level_configs: list[LoggingLevelConfigType]


class GuildInfoConfigType(TypedDict):
    guild_id: int
    config_channel: int


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
