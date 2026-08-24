from typing_extensions import Iterable, NotRequired, TypedDict


class GuildAttackListenerRoutingConfigType(TypedDict):
    username: str
    server: str
    channel_ids: dict[str, int]  # List
    mention_role_ids: NotRequired[dict[str, int]]  # List


class RouteChannels(TypedDict):
    guild_id: int
    channel_ids: Iterable[int]
    mention_role_ids: Iterable[int]


class ValidRouteChannels(TypedDict):
    channel_ids: set[int]
    mention_role_ids: set[int]


class RouteTargetInfo(TypedDict):
    channel_ids: Iterable[int]
    mention_role_ids: Iterable[int]
