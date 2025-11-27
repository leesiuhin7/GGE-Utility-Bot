import asyncio

from gge_utility_bot.bot_services import ConfigManager, RoutingInfo

from .types import GuildAttackListenerRoutingConfigType, RouteChannels
from .utils import BotUtils


class AtkWarningRouter:
    def __init__(
        self,
        bot_utils: BotUtils,
        config_manager: ConfigManager,
    ) -> None:
        self._bot_utils = bot_utils
        self._config_manager = config_manager

    async def get_route(self, routing_info: RoutingInfo) -> set[int]:
        """
        Get the id of each unique valid channels that is configured
        to receive the specific attack warning.

        :param routing_info: _description_
        :type routing_info: RoutingInfo
        :return: _description_
        :rtype: set[int]
        """
        routes = self._get_atk_listener_routes(routing_info)
        channel_ids: set[int] = set()

        # Update channel_ids with all valid channels
        # for every route_channels
        channel_ids.update(
            *(await asyncio.gather(
                *[
                    self._get_valid_channels(route_channels)
                    for route_channels in routes
                ],
            )),
        )
        return channel_ids

    def _get_atk_listener_routes(
        self,
        routing_info: RoutingInfo,
    ) -> list[RouteChannels]:
        """
        For each guild, find all channels configured to receive the
        specific attack warning.

        :param routing_info: The information used for routing
        :type routing_info: RoutingInfo
        :return: A list of routing information for each guild
        :rtype: list[RouteChannels]
        """
        route_channels: list[RouteChannels] = []

        for guild_id in routing_info["routes"]:
            try:
                # Get configs, skip guild if config is malformed
                enabled: bool = self._config_manager.get(
                    guild_id,
                    ["services", "attack_listener", "enabled"],
                )
                routes: dict[
                    str,
                    GuildAttackListenerRoutingConfigType,
                ] = self._config_manager.get(
                    guild_id,
                    ["services", "attack_listener", "routes"]
                )
            except (
                ConfigManager.GuildNotFoundError,
                KeyError,
                TypeError,
            ):
                continue

            if not enabled:
                continue

            # Append all channels needed routing in a guild
            route_channels.append({
                "guild_id": guild_id,
                "channel_ids": self._get_route_target_channel_ids(
                    config_routes=routes,
                    routing_info=routing_info,
                ),
            })

        return route_channels

    def _get_route_target_channel_ids(
        self,
        config_routes: dict[
            str, GuildAttackListenerRoutingConfigType,
        ],
        routing_info: RoutingInfo,
    ) -> set[int]:
        """
        Find all channels that is configured (by users) to receive
        attack warnings.

        :param config_routes: the routing configuration set by users
        :type config_routes: 
            dict[str, GuildAttackListenerRoutingConfigType]
        :param routing_info: The information used for routing
        :type routing_info: RoutingInfo
        :return: _description_
        :rtype: set[int]
        """
        channels: set[int] = set()
        for routing_config in config_routes.values():
            try:
                # Skip if config is malformed
                username = routing_config["username"]
                server = routing_config["server"]
                channel_ids = routing_config["channel_ids"]
            except KeyError:
                continue

            if (
                username == routing_info["username"]
                and server == routing_info["server"]
            ):  # Match
                channels.update(channel_ids.values())

        return channels

    async def _get_valid_channels(
        self,
        route_channels: RouteChannels,
    ) -> set[int]:
        """
        Get all channels that are in the guild with the specified id.

        :param route_channels: _description_
        :type route_channels: RouteChannels
        :return: _description_
        :rtype: set[int]
        """
        guild_id = route_channels["guild_id"]
        channel_ids = route_channels["channel_ids"]

        # Get the id of the guild where each channel is in
        channel_guild_ids = await asyncio.gather(
            *[
                self._bot_utils.get_channel_guild_id(channel_id)
                for channel_id in channel_ids
            ],
        )
        # Find all channels that is in the guild with
        # the given guild id
        valid_channel_ids: set[int] = set([
            channel_id
            for channel_id, channel_guild_id in zip(
                channel_ids, channel_guild_ids,
            )
            if channel_guild_id == guild_id
        ])
        return valid_channel_ids
