import asyncio
import logging

import discord
from discord.ext import commands

from gge_utility_bot import utils
from gge_utility_bot.bot_services import (
    AttackListener,
    ConfigManager,
    StatusMonitor,
)
from gge_utility_bot.config import GuildInfoConfigType

from .atk_warning import AtkWarningRouter
from .bot_commands import ConfigCommandGroup, PuppetCommandGroup
from .msg_callbacks import MessageCallbacks
from .utils import BotUtils

logger = logging.getLogger(__name__)


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
        self._atk_listener = attack_listener
        self._status_monitor = status_monitor
        self._config_manager = config_manager

        self._bot_utils = BotUtils(self._bot)

        self._atk_warning_router = AtkWarningRouter(
            bot_utils=self._bot_utils,
            config_manager=self._config_manager,
        )

        self._msg_callback_manager: (
            utils.AsyncCallbackManager[discord.Message]
        ) = utils.AsyncCallbackManager()

        self._msg_callbacks = MessageCallbacks(
            config_manager=self._config_manager,
        )
        self._msg_callback_manager.add_callback(
            self._msg_callbacks.on_battle_report_msg,
        )

        # Prepare bot
        self._bot.add_listener(self._on_ready, "on_ready")
        self._bot.add_listener(
            self._msg_callback_manager.on_event,
            "on_message",
        )
        self._load_bot_commands()

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

    def _load_bot_commands(self) -> None:
        self._bot.tree.add_command(
            ConfigCommandGroup(
                bot_utils=self._bot_utils,
                config_manager=self._config_manager,
            ),
        )
        self._bot.tree.add_command(
            PuppetCommandGroup(status_monitor=self._status_monitor),
        )

    async def _start_bot_tasks(self) -> None:
        """
        Starts all tasks related to the bot's life cycle.
        """
        bg_msg_coro = self._bg_msg_loop()
        atk_warning_coro = self._atk_warning_loop()

        all_coros = [
            bg_msg_coro,
            atk_warning_coro,
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
            channel_ids = await (
                self._atk_warning_router.get_route(routing_info)
            )
            for msg in atk_warnings:
                for channel_id in channel_ids:
                    await self.send_msg(msg, channel_id)

    async def _send_msg(self, msg: str, channel_id: int) -> None:
        channel = self._bot.get_channel(channel_id)
        if channel is None or isinstance(channel, (
            discord.ForumChannel,
            discord.CategoryChannel,
            discord.abc.PrivateChannel
        )):
            return

        await channel.send(msg)
