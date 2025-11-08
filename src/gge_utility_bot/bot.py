import asyncio
import io
import logging

import discord
from discord import app_commands
from discord.ext import commands
from typing_extensions import Any, Literal, TypedDict, Union

from gge_utility_bot import data_process as dp
from gge_utility_bot import utils
from gge_utility_bot.bot_services import (
    AttackListener,
    ConfigManager,
    RoutingInfo,
    StatusMonitor,
    summarize_battle_report,
)
from gge_utility_bot.config import GuildInfoConfigType
from gge_utility_bot.messages import MESSAGES

logger = logging.getLogger(__name__)


def init() -> None:
    from config import cfg
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


class RouteChannels(TypedDict):
    guild_id: int
    channel_ids: list[int]


MsgResponseType = set[Literal["config", "battle_report"]]


class BotManager:
    GUILD_INFOS: list[GuildInfoConfigType]

    def __init__(
        self,
        *,
        bot: commands.Bot,
        attack_listener: AttackListener,
        status_monitor: StatusMonitor,
        config_manager: ConfigManager,
    ) -> None:
        self._bot = bot
        self._bot.add_listener(self._on_ready, "on_ready")
        self._bot.add_listener(self._on_message, "on_message")
        self._load_bot_commands()

        self._atk_listener = attack_listener
        self._status_monitor = status_monitor
        self._config_manager = config_manager

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
        msg_response_type = self._get_msg_response_type(message)

        # "Dispatching" the message to different callbacks
        if "config" in msg_response_type:
            self._on_config_msg(message)
        if "battle_report" in msg_response_type:
            await self._on_battle_report_msg(message)

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

    def _get_msg_response_type(
        self,
        message: discord.Message,
    ) -> MsgResponseType:
        msg_response_type: MsgResponseType = set()

        # Prevents reacting to message from itself
        if message.author == self._bot.user:
            return msg_response_type

        channel_id = message.channel.id
        guild_id = message.guild.id if message.guild else None

        # Config
        for guild_info in self.GUILD_INFOS:
            if guild_info["config_channel"] == channel_id:
                msg_response_type.add("config")
                break

        # Battle report
        try:
            is_battle_report = True

            # Check if message is from a battle report channel
            channel_ids: dict[str, int] = self._config_manager.get(
                guild_id,
                ["services", "battle_report", "channel_ids"],
            ) if guild_id else {}

            if channel_id not in channel_ids.values():
                is_battle_report = False

            # Check if there are image attachments
            for attachment in message.attachments:
                if attachment.content_type is None:
                    continue
                if attachment.content_type.startswith("image"):
                    break
            else:
                is_battle_report = False

            if is_battle_report:
                msg_response_type.add("battle_report")
        except:
            pass

        return msg_response_type

    def _on_config_msg(self, message: discord.Message) -> None:
        channel_id = message.channel.id
        for guild_info in self.GUILD_INFOS:
            if guild_info["config_channel"] == channel_id:
                break
        else:
            return

        guild_id = guild_info["guild_id"]
        parsed = utils.parse_config_input(message.content)
        if parsed is not None:
            self._config_manager.update(guild_id, parsed)

    async def _on_battle_report_msg(
        self,
        message: discord.Message,
    ) -> None:
        if message.guild is None:
            return
        guild_id = message.guild.id

        try:
            summary_enabled = self._config_manager.get(
                guild_id,
                ["services", "battle_report", "summary", "enabled"],
            )
        except:
            return

        if summary_enabled is not True:
            return

        for attachment in message.attachments:
            if attachment.content_type is None:
                continue
            if not attachment.content_type.startswith("image"):
                continue

            # Save image file to buffer
            buffer = io.BytesIO()
            await attachment.save(buffer, seek_begin=True)

            # Summarize battle report image
            out_buffer = summarize_battle_report(buffer)
            if out_buffer is None:
                continue

            await message.reply(
                content=MESSAGES["battle_report"]["summary"],
                file=discord.File(out_buffer, filename="summary.png"),
                mention_author=False,
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
        try:
            config_dict: dict[Any, Any] = (
                self._config_manager.get(guild_id, [])
            )
        except ConfigManager.GuildNotFoundError:
            config_dict = {}  # Defaulting to empty dict

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
        # Latest to oldest
        parsed_msgs: list[utils.ParsedConfigInput] = []
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

        # Update config
        self._config_manager.load(
            guild_id,
            # Reversing so that it starts with the oldest
            list(reversed(parsed_msgs)),
        )

        return True

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
