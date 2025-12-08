import json

import discord
from discord.ext import commands
from typing_extensions import Any, AsyncGenerator, Union

from gge_utility_bot.config import GuildInfoConfigType


class BotUtils:
    GUILD_INFOS: list[GuildInfoConfigType]

    def __init__(self, bot: commands.Bot) -> None:
        self._bot = bot

    async def get_channel(
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

    async def get_channel_guild_id(
        self,
        channel_id: int,
    ) -> int | None:
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
        channel = await self.get_channel(channel_id)
        if isinstance(channel, (discord.abc.PrivateChannel)):
            return
        if channel is None:
            return

        return channel.guild.id

    def get_config_guild_id(
        self,
        config_channel_id: int,
    ) -> int | None:
        """
        Get the id of the guild that is configured by the channel 
        with the given channel id.

        :param config_channel_id: The channel id of the config
            channel
        :type config_channel_id: int
        :return: None if no guild is found, the id of the guild
            otherwise
        :rtype: int | None
        """
        for guild_info in self.GUILD_INFOS:
            if guild_info["config_channel"] == config_channel_id:
                return guild_info["guild_id"]


def user_input_to_obj(value: str) -> Any:
    """
    Convert user input into an object.

    :param value: User input
    :type value: str
    :raises ValueError: When user input cannot be converted
    :return: The converted object
    :rtype: Any
    """
    try:
        return json.loads(value)
    except:
        raise ValueError
