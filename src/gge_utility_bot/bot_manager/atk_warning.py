import asyncio

from gge_utility_bot.bot_services import ConfigManager, RoutingInfo
from gge_utility_bot.utils import validate_type

from .types import (
    GuildAttackListenerRoutingConfigType,
    RouteChannels,
    RouteTargetInfo,
    ValidRouteChannels,
)
from .utils import BotUtils


class AtkWarningRouter:
    def __init__(
        self,
        bot_utils: BotUtils,
        config_manager: ConfigManager,
    ) -> None:
        self._bot_utils = bot_utils
        self._config_manager = config_manager

    async def get_route(
        self, routing_info: RoutingInfo
    ) -> list[ValidRouteChannels]:
        """
        Get the id of channels that are configured to receive the
        attack warning and the id of roles that should are mentioned
        respectively.

        :param routing_info: The information used for routing
        :type routing_info: RoutingInfo
        :return: A collection of channel ids paired with role ids
        :rtype: list[ValidRouteChannels]
        """
        routes = await self._get_atk_listener_routes(routing_info)
        return await asyncio.gather(
            *(
                self._get_valid_channels(route_channels)
                for route_channels in routes
            )
        )

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

        target_info = self._get_route_target_info(
            config_routes=routes,
            routing_info=routing_info,
        )
        return {
            "channel_ids": target_info["channel_ids"],
            "guild_id": guild_id,
            "mention_role_ids": target_info["mention_role_ids"],
        }

    def _get_route_target_info(
        self,
        config_routes: dict[
            str,
            GuildAttackListenerRoutingConfigType,
        ],
        routing_info: RoutingInfo,
    ) -> RouteTargetInfo:
        """
        Find all channels that are configured (by users) to receive
        attack warnings and roles that need to be mentioned.

        :param config_routes: The configuration set by users
        :type config_routes:
            dict[str, GuildAttackListenerRoutingConfigType]
        :param routing_info: The information used for routing
        :type routing_info: RoutingInfo
        :return: The ids of all channels and roles that are needed
        :rtype: RouteTargetInfo
        """
        channels: set[int] = set()
        mention_roles: set[int] = set()
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
                mention_role_ids = routing_config.get("mention_role_ids", {})
                mention_roles.update(mention_role_ids.values())

        return {
            "channel_ids": channels,
            "mention_role_ids": mention_roles,
        }

    async def _get_valid_channels(
        self,
        route_channels: RouteChannels,
    ) -> ValidRouteChannels:
        """
        Validate channel ids to ensure they originate from the given
        guild.

        :param route_channels: Information about the channels that are
            configured to receive the attack warning
        :type route_channels: RouteChannels
        :return: The validated version of RouteChannels where channels
            are guaranteed to originate from the given guild. Channels
            that violate this prerequisite are ignored.
        :rtype: ValidRouteChannels
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

        return {
            # Find all channels that are in the guild
            "channel_ids": {
                channel_id
                for channel_id, channel_guild_id in zip(
                    channel_ids, channel_guild_ids
                )
                if channel_guild_id == guild_id
            },
            "mention_role_ids": set(
                route_channels.get("mention_role_ids", [])
            ),
        }
