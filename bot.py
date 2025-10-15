import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
from typing import Any, TypedDict, Union

from server_comm import ServerComm
from config import PlayerConfigType, GuildInfoConfigType
import utils
from utils import ParsedConfigInput, PathDict
import data_process as dp
from messages import MESSAGES


logger = logging.getLogger(__name__)


def init() -> None:
    from config import cfg
    AttackListener.REQUEST_COOLDOWN = (
        cfg["attack_listener"]["request_cooldown"]
    )
    AttackListener.REQUEST_TIMEOUT = (
        cfg["attack_listener"]["request_timeout"]
    )
    AttackListener.PLAYER_CONFIGS = cfg["players"]
    StatusMonitor.PLAYER_CONFIGS = cfg["players"]
    BotManager.GUILD_INFOS = cfg["discord"]["guilds"]


class GuildAttackListenerRoutingConfigType(TypedDict):
    username: str
    server: str
    channel_ids: dict[str, int]  # List


class GuildAttackListenerConfigType(TypedDict):
    enabled: bool
    routes: dict[str, GuildAttackListenerRoutingConfigType]  # List


class GuildStormSearcherConfigType(TypedDict):
    enabled: bool


class GuildServiceConfigType(TypedDict):
    attack_listener: GuildAttackListenerConfigType
    storm_searcher: GuildStormSearcherConfigType


class GuildConfigType(TypedDict):
    services: GuildServiceConfigType


class RoutingInfo(TypedDict):
    username: str
    server: str
    routes: list[int]


class RouteChannels(TypedDict):
    guild_id: int
    channel_ids: list[int]


class BotManager:
    GUILD_INFOS: list[GuildInfoConfigType]

    def __init__(
        self,
        *,
        bot: commands.Bot,
        server_comm: ServerComm,
    ) -> None:
        self._bot = bot
        self._bot.add_listener(self._on_ready, "on_ready")
        self._bot.add_listener(self._on_message, "on_message")
        self._load_bot_commands()

        self._guild_configs: dict[str, PathDict] = {}
        self._atk_listener = AttackListener(server_comm)
        self._status_monitor = StatusMonitor(server_comm)

        self._send_queue: asyncio.Queue[tuple[str, int]] = (
            asyncio.Queue()
        )

    async def start(self, token: str) -> None:
        await self._atk_listener.start()

        async with self._bot:
            await self._bot.start(token)

    async def send_msg(self, msg: str, channel_id: int) -> None:
        await self._send_queue.put((msg, channel_id))

    async def _on_ready(self) -> None:
        await self._bot.tree.sync()

        self._bot.loop.create_task(self._start_bot_tasks())

        logger.info(f"{self._bot.user} is online!")

    async def _on_message(self, message: discord.Message) -> None:
        channel_id = message.channel.id
        for guild_info in self.GUILD_INFOS:
            if guild_info["config_channel"] == channel_id:
                break
        else:  # Exits if it doesn't match to any config channels
            return

        guild_id = guild_info["guild_id"]
        parsed = utils.parse_config_input(message.content)
        if parsed is None:
            return

        self._update_config(guild_id, parsed)

    def _load_bot_commands(self) -> None:
        config_group = app_commands.Group(
            name="config",
            description="Manage bot configurations",
        )

        config_reload = app_commands.Command(
            name="reload",
            description="Reload bot configurations",
            callback=self._reload_config,
            parent=config_group,
        )

        config_dump = app_commands.Command(
            name="dump",
            description="Display active bot configurations",
            callback=self._dump_config,
            parent=config_group,
        )

        config_group.add_command(config_reload)
        config_group.add_command(config_dump)

        puppet_group = app_commands.Group(
            name="puppet",
            description="Manage puppets",
        )

        puppet_status = app_commands.Command(
            name="status",
            description="Get current status of puppets",
            callback=self._get_puppet_status,
            parent=puppet_group,
        )

        puppet_group.add_command(puppet_status)

        self._bot.tree.add_command(config_group)
        self._bot.tree.add_command(puppet_group)

    async def _start_bot_tasks(self) -> None:
        """
        Starts all tasks related to the bot's life cycle.
        """
        bg_msg_coro = self._bg_msg_loop()
        atk_warning_coro = self._atk_warning_loop()

        load_config_coros = [
            self._load_config(
                guild_id=guild_info["guild_id"],
                config_channel=guild_info["config_channel"],
            )
            for guild_info in self.GUILD_INFOS
        ]

        all_coros = [
            bg_msg_coro,
            atk_warning_coro,
            *load_config_coros,
        ]

        # Wait for all task to complete
        try:
            await asyncio.gather(
                *all_coros,
                return_exceptions=True,
            )
        except asyncio.CancelledError:
            await asyncio.gather(
                *all_coros,
                return_exceptions=True,
            )

    async def _bg_msg_loop(self) -> None:
        while not self._bot.is_closed():
            msg, channel_id = await self._send_queue.get()
            await self._send_msg(msg, channel_id)

    async def _atk_warning_loop(self) -> None:
        while True:
            routing_info, atk_warnings = (
                await self._atk_listener.get()
            )
            await self._dispatch_atk_warning(
                routing_info, atk_warnings,
            )

    async def _reload_config(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await interaction.response.defer()

        channel_id = interaction.channel_id
        if channel_id is None:
            await interaction.followup.send(
                MESSAGES["config"]["reload"]["not_channel"],
            )
            return

        for guild_info in self.GUILD_INFOS:
            if guild_info["config_channel"] == channel_id:
                break
        else:
            await interaction.followup.send(
                MESSAGES["config"]["reload"]["not_registered"],
            )
            return

        guild_id = guild_info["guild_id"]
        success = await self._load_config(guild_id, channel_id)
        if success:
            await interaction.followup.send(
                MESSAGES["config"]["reload"]["success"],
            )
            return
        else:
            await interaction.followup.send(
                MESSAGES["config"]["reload"]["failed"],
            )

    async def _dump_config(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        channel_id = interaction.channel_id
        if channel_id is None:
            await interaction.followup.send(
                MESSAGES["config"]["dump"]["not_channel"],
                ephemeral=True,
            )
            return

        for guild_info in self.GUILD_INFOS:
            if guild_info["config_channel"] == channel_id:
                break
        else:
            await interaction.followup.send(
                MESSAGES["config"]["dump"]["not_registered"],
                ephemeral=True,
            )
            return

        guild_id = guild_info["guild_id"]
        guild_config = self._guild_configs.get(str(guild_id))
        # Defaulting to empty dict
        if guild_config is None:
            config_dict = {}
        else:
            config_dict: dict[Any, Any] = guild_config.get([])

        # Serialize config for display
        buffer = utils.serialize_as_display_buffer(
            config_dict, sort_keys=True,
        )
        file = discord.File(buffer, filename="config.json")

        # Send config as json file
        await interaction.followup.send(
            MESSAGES["config"]["dump"]["success"],
            file=file,
            ephemeral=True,
        )

    async def _get_puppet_status(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild_id

        status_list = await self._status_monitor.get_status()
        encoded_status_list = [  # Check if status should be visible
            dp.StatusMonitor.encode(out_status)
            for out_status, _ in filter(
                lambda status: guild_id in status[1],
                status_list,
            )
        ]

        # Searialize as display
        buffer = utils.serialize_as_display_buffer(
            encoded_status_list, sort_keys=False,
        )
        file = discord.File(buffer, filename="status.json")

        await interaction.followup.send(
            MESSAGES["puppet"]["status"]["success"],
            file=file,
            ephemeral=True,
        )

    async def _load_config(
        self,
        guild_id: int,
        config_channel: int,
    ) -> bool:
        channel = await self._get_channel(config_channel)
        if channel is None:
            return False
        if isinstance(channel, (
            discord.abc.PrivateChannel,
            discord.ForumChannel,
            discord.CategoryChannel
        )):
            return False

        # Load and parse config messages
        parsed_msgs: list[ParsedConfigInput] = []
        prev_msg = None
        end = False
        while not end:
            msgs = [
                msg async for msg in channel.history(
                    limit=100, before=prev_msg,
                )
            ]
            # No other config msgs remaining
            if len(msgs) != 0:
                prev_msg = msgs[-1]
            else:
                break

            for msg in msgs:
                parsed = utils.parse_config_input(msg.content)
                if parsed is not None:
                    parsed_msgs.append(parsed)
                else:
                    continue

                # Operation on the entire config, hence stop here
                if parsed["path"] == []:
                    end = True
                    break

        # Clear loaded config
        self._update_config(
            guild_id,
            {"action": "delete", "path": [], "value": None},
        )
        # Update config
        for parsed in reversed(parsed_msgs):
            self._update_config(guild_id, parsed)

        return True

    def _update_config(
        self,
        guild_id: int,
        parsed_input: ParsedConfigInput,
    ) -> bool:
        key = str(guild_id)
        if parsed_input["action"] == "set":
            if key not in self._guild_configs:
                self._guild_configs[key] = PathDict()

            return self._guild_configs[key].update(
                path=parsed_input["path"],
                action="set",
                value=parsed_input["value"],
            )
        else:
            if key not in self._guild_configs:
                return False

            return self._guild_configs[key].update(
                path=parsed_input["path"],
                action="delete",
            )

    async def _send_msg(self, msg: str, channel_id: int) -> None:
        channel = self._bot.get_channel(channel_id)
        if channel is None or isinstance(channel, (
            discord.ForumChannel,
            discord.CategoryChannel,
            discord.abc.PrivateChannel
        )):
            return

        await channel.send(msg)

    async def _dispatch_atk_warning(
        self,
        routing_info: RoutingInfo,
        atk_warnings: list[str],
    ) -> None:
        routes = self._get_atk_listener_routes(routing_info)
        # Check if channels belong to their respective guilds
        valid_channel_ids: set[int] = set()
        for route_channels in routes:
            route_guild_id = route_channels["guild_id"]
            for channel_id in route_channels["channel_ids"]:
                guild_id = await self._get_channel_guild_id(channel_id)
                if guild_id == route_guild_id:
                    valid_channel_ids.add(channel_id)

        # Send all messages to each valid channels
        for msg in atk_warnings:
            for channel_id in valid_channel_ids:
                await self.send_msg(msg, channel_id)

    def _get_atk_listener_routes(
        self,
        routing_info: RoutingInfo,
    ) -> list[RouteChannels]:
        route_channels: list[RouteChannels] = []

        for guild_id in routing_info["routes"]:
            try:
                # Get configs, skip guild if config is malformed
                key = str(guild_id)
                guild_config = self._guild_configs[key]

                enabled: bool = guild_config.get(
                    ["services", "attack_listener", "enabled"],
                )
                routes: dict[
                    str,
                    GuildAttackListenerRoutingConfigType,
                ] = guild_config.get(
                    ["services", "attack_listener", "routes"]
                )
            except (KeyError, TypeError):
                continue

            if not enabled:
                continue

            channels: set[int] = set()
            for routing_config in routes.values():
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

            # Append all channels needed routing in a guild
            route_channels.append({
                "guild_id": guild_id,
                "channel_ids": list(channels),
            })

        return route_channels

    async def _get_channel(
        self,
        channel_id: int,
    ) -> Union[
        discord.VoiceChannel,
        discord.StageChannel,
        discord.ForumChannel,
        discord.TextChannel,
        discord.CategoryChannel,
        discord.Thread,
        discord.abc.PrivateChannel,
        None,
    ]:
        """
        Finds the channel with the given channel id.

        :param channel_id: The id of the channel
        :type channel_id: int
        :return: The channel with the given channel id if found, 
            None otherwise
        :rtype: Union[
            discord.VoiceChannel,
            discord.StageChannel,
            discord.ForumChannel,
            discord.TextChannel,
            discord.CategoryChannel,
            discord.Thread,
            discord.abc.PrivateChannel,
            None
        ]
        """
        channel = self._bot.get_channel(channel_id)
        if channel is None:
            # Not available in cache, fetch from discord API instead
            try:
                channel = await self._bot.fetch_channel(channel_id)
            except:
                return

        return channel

    async def _get_channel_guild_id(self, channel_id: int) -> int | None:
        """
        Get the id of the guild that contains the channel with a 
        given channel id.

        :param channel_id: The channel id of the channel
        :type channel_id: int
        :return: None if unable to access the channel or the channel 
            does not belong to a guild, or the id of the guild that 
            the channel belongs to otherwise
        :rtype: int | None
        """
        channel = await self._get_channel(channel_id)
        if isinstance(channel, (discord.abc.PrivateChannel)):
            return
        if channel is None:
            return

        return channel.guild.id


class AttackListener:
    REQUEST_COOLDOWN: float
    REQUEST_TIMEOUT: float
    PLAYER_CONFIGS: list[PlayerConfigType]

    def __init__(self, server_comm: ServerComm) -> None:
        self._server_comm = server_comm

        self._output_queue: asyncio.Queue[tuple[
            RoutingInfo, list[str],
        ]] = asyncio.Queue()
        self._prev_atk_ids: set[int] = set()

        self._started = False

    async def get(self) -> tuple[RoutingInfo, list[str]]:
        return await self._output_queue.get()

    async def start(self) -> None:
        if not self._started:
            for player_config in self.PLAYER_CONFIGS:
                player_info = player_config["info"]
                atk_listener_config = (
                    player_config
                    ["services"]
                    ["attack_listener"]
                )
                routes = player_config["visibility"]
                if not atk_listener_config["enabled"]:
                    continue

                asyncio.create_task(self._listener(
                    username=player_info["username"],
                    password=player_info["password"],
                    server=player_info["server"],
                    routes=routes,
                ))

            self._started = True

    async def _listener(
        self,
        *,
        username: str,
        password: str,
        server: str,
        routes: list[int],
    ) -> None:
        index = None
        while index is None:
            index = await self._get_current_index(
                username=username,
                password=password,
                server=server,
            )
            await asyncio.sleep(self.REQUEST_COOLDOWN)

        while True:
            await asyncio.sleep(self.REQUEST_COOLDOWN)
            response = await self._server_comm.send_request(
                username=username,
                password=password,
                server=server,
                command="search",
                args={
                    "start_index": index,
                    "msg_type": "gam",
                },
                timeout=self.REQUEST_TIMEOUT,
            )
            if response is None:
                continue
            if "error" in response:
                continue

            msg_list, index = response["response"]
            atk_msgs: list[str] = []
            for msg in msg_list:
                deserialized = dp.AttackListener.deserialize(msg)
                if deserialized is None:
                    continue

                for atk_data in deserialized:
                    # Prevent duplicates
                    if atk_data["atk_id"] not in self._prev_atk_ids:
                        self._prev_atk_ids.add(atk_data["atk_id"])
                        atk_msgs.append(
                            dp.AttackListener.serialize(atk_data),
                        )

            if len(atk_msgs) > 0:
                routing_info = self._serialize_routing_info(
                    username=username,
                    server=server,
                    routes=routes,
                )
                await self._output_queue.put((routing_info, atk_msgs))

    async def _get_current_index(
        self,
        *,
        username: str,
        password: str,
        server: str,
    ) -> int | None:
        response = await self._server_comm.send_request(
            username=username,
            password=password,
            server=server,
            command="search",
            args={
                "start_index": 0,
                "msg_type": "",
            },
            timeout=self.REQUEST_TIMEOUT,
        )

        if response is None:
            return
        elif "error" in response:
            error = response["error"]
            logger.error(
                f"Failed to fetch current index, error: {error}",
            )
            return
        else:
            return response["response"][1]

    def _serialize_routing_info(
        self,
        *,
        username: str,
        server: str,
        routes: list[int],
    ) -> RoutingInfo:
        return {
            "username": username,
            "server": server,
            "routes": routes,
        }


class StatusMonitor:
    PLAYER_CONFIGS: list[PlayerConfigType]

    def __init__(self, server_comm: ServerComm) -> None:
        self._server_comm = server_comm

    async def get_status(
        self,
    ) -> list[tuple[dp.PuppetStatusType, list[int]]]:
        coros = [
            asyncio.create_task(self._get_status(player_config))
            for player_config in self.PLAYER_CONFIGS
        ]
        status_list = await asyncio.gather(*coros)
        return status_list

    async def _get_status(
        self,
        player_config: PlayerConfigType,
    ) -> tuple[dp.PuppetStatusType, list[int]]:
        username = player_config["info"]["username"]
        password = player_config["info"]["password"]
        server = player_config["info"]["server"]
        attack_warnings = (
            player_config["services"]["attack_listener"]["enabled"]
        )
        routes = player_config["visibility"]

        connected = await self._get_active_status(
            username=username,
            password=password,
            server=server,
            timeout=30,
        )

        status: dp.PuppetStatusType = {
            "username": username,
            "server": server,
            "connected": connected,
            "attack_warnings": attack_warnings,
        }
        return status, routes

    async def _get_active_status(
        self,
        *,
        username: str,
        password: str,
        server: str,
        timeout: float,
    ) -> bool | None:
        response = await self._server_comm.send_request(
            username=username,
            password=password,
            server=server,
            command="info",
            args={
                "name": "connected",
            },
            timeout=timeout,
        )
        if response is None:
            return None
        if "error" in response:
            return None

        active = response["response"]
        if active is True:
            return True
        elif active is False:
            return False
        else:
            return None
