import asyncio

from gge_utility_bot.bot_services import ConfigManager, RoutingInfo
from gge_utility_bot.utils import validate_type

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

        :param routing_info: The information used for routing
        :type routing_info: RoutingInfo
        :return: The ids of all channels that should receive the
            specific attack warning
        :rtype: set[int]
        """
        routes = await self._get_atk_listener_routes(routing_info)
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

    async def _get_atk_listener_routes(
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
        # Using asyncio.gather here to allow faster reads
        results = await asyncio.gather(
            *[
                self._get_guild_atk_listener_routes(
                    guild_id, routing_info,
                )
                for guild_id in routing_info["routes"]
            ],
        )
        # Only include the ones that succeeded
        return [
            route_channels for route_channels in results
            if route_channels is not None
        ]

    async def _get_guild_atk_listener_routes(
        self,
        guild_id: int,
        routing_info: RoutingInfo,
    ) -> RouteChannels | None:
        """
        Find all channels that are configured in the guild with the
        specified id to receive the specific attack warning.

        :param guild_id: The id of the guild
        :type guild_id: int
        :param routing_info: The information used for routing
        :type routing_info: RoutingInfo
        :return: The ids of all channels that are configured to 
            receive the attack warning, and the id of the guild
            that is responsible for the configuration
        :rtype: RouteChannels | None
        """
        try:
            enabled = await self._config_manager.get(
                guild_id,
                "services.attack_listener.enabled",
            )
            routes = await self._config_manager.get(
                guild_id,
                "services.attack_listener.routes",
            )
        except ConfigManager.InvalidPathError:
            return

        # Validate type
        if enabled is not True:
            return
        try:
            if not validate_type(
                routes,
                dict[str, GuildAttackListenerRoutingConfigType],
            ):
                return
        except:
            return

        return {
            "channel_ids": self._get_route_target_channel_ids(
                config_routes=routes,
                routing_info=routing_info,
            ),
            "guild_id": guild_id,
        }

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
        :return: The ids of all channels that are configured to
            receive the attack warning
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

        :param route_channels: The ids of all channels that are 
            configured to receive the attack warning, and the id 
            of the guild that is responsible for the configuration
        :type route_channels: RouteChannels
        :return: The ids of all given channels that are also in
            the guild with the specified id
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
