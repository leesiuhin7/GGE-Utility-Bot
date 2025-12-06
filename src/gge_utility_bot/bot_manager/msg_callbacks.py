import io

import discord

from gge_utility_bot import utils
from gge_utility_bot.bot_services import (
    ConfigManager,
    summarize_battle_report,
)
from gge_utility_bot.messages import MESSAGES

from .utils import BotUtils


class MessageCallbacks:
    def __init__(
        self,
        bot_utils: BotUtils,
        config_manager: ConfigManager,
    ) -> None:
        self._bot_utils = bot_utils
        self._config_manager = config_manager

    async def on_config_msg(self, message: discord.Message) -> None:
        """
        Update config manager if a config message is sent.

        :param message: The message object to be used
        :type message: discord.Message
        """
        if not self._is_config_msg(message):
            return

        channel_id = message.channel.id
        guild_id = self._bot_utils.get_config_guild_id(channel_id)
        if guild_id is None:
            return

        parsed = utils.parse_config_input(message.content)
        if parsed is not None:
            self._config_manager.update(guild_id, parsed)

    async def on_battle_report_msg(
        self,
        message: discord.Message,
    ) -> None:
        """
        Generate a battle report summary if a battle report message
        is sent.

        :param message: The message object to be used
        :type message: discord.Message
        """
        if not self._is_battle_report_msg(message):
            return

        if message.guild is None:
            return
        guild_id = message.guild.id

        try:
            summary_enabled = self._config_manager.get(
                guild_id,
                ["services", "battle_report", "summary", "enabled"],
            )
            # summary enabled MUST be True
            if summary_enabled is not True:
                return
        except:
            return

        for attachment in message.attachments:
            if not self._is_image(attachment):
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

    def _is_config_msg(self, message: discord.Message) -> bool:
        """
        Check if the message is a config message.

        :param message: The message object
        :type message: discord.Message
        :return: True of the message is a config message, False 
            otherwise
        :rtype: bool
        """
        channel_id = message.channel.id
        return self._bot_utils.get_config_guild_id(
            channel_id,
        ) is not None

    def _is_battle_report_msg(
        self,
        message: discord.Message,
    ) -> bool:
        """
        Check if the message is a battle report message.

        :param message: The message object
        :type message: discord.Message
        :return: True if the message is a battle report message,
            False otherwise
        :rtype: bool
        """
        if message.guild is None:
            return False
        guild_id = message.guild.id
        channel_id = message.channel.id
        attachments = message.attachments

        try:
            # Check if message is from a battle report channel
            channel_ids: dict[str, int] = self._config_manager.get(
                guild_id,
                ["services", "battle_report", "channel_ids"],
            )
            if channel_id not in channel_ids.values():
                return False
        except:
            return False

        # Check if there are image attachments
        for attachment in attachments:
            if self._is_image(attachment):
                break
        else:
            return False

        return True

    def _is_image(self, attachment: discord.Attachment) -> bool:
        """
        Check if a message attachment is an image.

        :param attachment: The attackment of a message
        :type attachment: discord.Attachment
        :return: True if the attachment is an image, False otherwise
        :rtype: bool
        """
        if attachment.content_type is None:
            return False
        if not attachment.content_type.startswith("image"):
            return False

        return True
