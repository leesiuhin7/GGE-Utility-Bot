import discord
from discord.ext import commands
from typing_extensions import AsyncGenerator, Union

from gge_utility_bot import utils
from gge_utility_bot.bot_services import ConfigManager
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


async def get_msg_history(
    messageable: discord.abc.Messageable,
) -> AsyncGenerator[discord.Message]:
    """
    Returns an asynchronous generator that allows message history
    of the target to be accessed.

    :param messageable: The target to access message history from
    :type messageable: discord.abc.Messageable
    :return: An asynchronous generator
    :rtype: AsyncGenerator[discord.Message]
    :yield: A message object starting from the latest to oldest
    :rtype: Iterator[AsyncGenerator[discord.Message]]
    """
    prev_msg: discord.Message | None = None
    while True:
        no_msg = True
        async for msg in messageable.history(before=prev_msg):
            prev_msg = msg
            no_msg = False
            yield msg

        if no_msg:  # Exits if remaining history is empty
            return


async def load_config_from_channel(
    bot_utils: BotUtils,
    config_manager: ConfigManager,
    guild_id: int,
    config_channel: int,
) -> bool:
    """
    Load configuration for a guild with the specified guild id
    where configuration is read from the channel with the 
    specified channel id.

    :param bot_utils: A BotUtils object
    :type bot_utils: BotUtils
    :param config_manager: A ConfigManager object used for
        configuration
    :type config_manager: ConfigManager
    :param guild_id: The guild id of the target guild
    :type guild_id: int
    :param config_channel: The channel id of the channel where
        configuration read from
    :type config_channel: int
    :return: True if configuration is successfully loaded, False
        otherwise
    :rtype: bool
    """
    channel = await bot_utils.get_channel(config_channel)
    if channel is None:
        return False
    if isinstance(channel, (
        discord.abc.PrivateChannel,
        discord.ForumChannel,
        discord.CategoryChannel
    )):
        return False

    # Load and parse config messages
    parsed_msgs: list[utils.ParsedConfigInput] = []
    async for msg in get_msg_history(channel):
        parsed = utils.parse_config_input(msg.content)
        if parsed is not None:
            parsed_msgs.append(parsed)
            # Operation on the entire config, hence stop here
            if parsed["path"] == []:
                break

    # Update config
    config_manager.load(
        guild_id,
        # Reversing so that it starts with the oldest
        list(reversed(parsed_msgs)),
    )
    return True
