from typing_extensions import Iterable, TypedDict


class GuildAttackListenerRoutingConfigType(TypedDict):
    username: str
    server: str
    channel_ids: dict[str, int]  # List


class RouteChannels(TypedDict):
    guild_id: int
    channel_ids: Iterable[int]
