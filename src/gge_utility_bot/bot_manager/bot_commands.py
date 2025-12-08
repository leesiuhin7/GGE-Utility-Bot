import discord
from discord import app_commands
from typing_extensions import AsyncGenerator

from gge_utility_bot import data_process as dp
from gge_utility_bot import utils
from gge_utility_bot.bot_services import ConfigManager, StatusMonitor
from gge_utility_bot.messages import MESSAGES

from .utils import BotUtils, user_input_to_obj


class ConfigCommandGroup(
    app_commands.Group,
    name="config",
    description="Manage bot configurations",
):
    def __init__(
        self,
        bot_utils: BotUtils,
        config_manager: ConfigManager,
    ) -> None:
        super().__init__()
        self._bot_utils = bot_utils
        self._config_manager = config_manager

        self.get_config.autocomplete("path")(
            self._path_autocomplete,
        )
        self.set_config.autocomplete("path")(
            self._path_autocomplete,
        )
        self.remove_config.autocomplete("path")(
            self._path_autocomplete,
        )

    @app_commands.command(
        name="get",
        description="Display active bot configuration at the specified path",
    )
    async def get_config(
        self,
        interaction: discord.Interaction,
        path: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        guild_id = self._get_target_guild_id(interaction)
        if guild_id is None:
            await interaction.followup.send(
                MESSAGES.config.get.bad_channel,
                ephemeral=True,
            )
            return

        try:
            config = await self._config_manager.get(guild_id, path)
        except ConfigManager.InvalidPathError:
            await interaction.followup.send(
                MESSAGES.config.get.bad_path,
                ephemeral=True,
            )
            return

        # Serialize config for display
        # JSON serialization should work since the write operation
        # uses JSON deserialization
        buffer = utils.serialize_as_display_buffer(
            config, sort_keys=True,
        )
        file = discord.File(buffer, filename="config.json")

        # Send config as json file
        await interaction.followup.send(
            MESSAGES.config.get.success,
            file=file,
            ephemeral=True,
        )

    @app_commands.command(
        name="set",
        description="Modify bot configuration at the specified path",
    )
    async def set_config(
        self,
        interaction: discord.Interaction,
        path: str,
        value: str,
    ) -> None:
        await interaction.response.defer()

        guild_id = self._get_target_guild_id(interaction)
        if guild_id is None:
            await interaction.followup.send(
                MESSAGES.config.set.bad_channel,
            )
            return

        try:
            input_obj = user_input_to_obj(value)
        except ValueError:
            await interaction.followup.send(
                MESSAGES.config.set.bad_input,
            )
            return

        success = await self._config_manager.update(
            guild_id, path, input_obj,
        )
        if success:
            await interaction.followup.send(
                MESSAGES.config.set.success,
            )
        else:
            await interaction.followup.send(
                MESSAGES.config.set.failed,
            )

    @app_commands.command(
        name="remove",
        description="Remove bot configuration at the specified path",
    )
    async def remove_config(
        self,
        interaction: discord.Interaction,
        path: str,
    ) -> None:
        await interaction.response.defer()

        guild_id = self._get_target_guild_id(interaction)
        if guild_id is None:
            await interaction.followup.send(
                MESSAGES.config.remove.bad_channel,
            )
            return

        success = await self._config_manager.delete(guild_id, path)
        if success:
            # Displayed to all members in the channel
            await interaction.followup.send(
                MESSAGES.config.remove.success,
            )
        else:
            await interaction.followup.send(
                MESSAGES.config.remove.failed,
            )

    def _get_target_guild_id(
        self,
        interaction: discord.Interaction,
    ) -> int | None:
        """
        Get the id of the guild that can be configured by the
        interaction.

        :param interaction: A discord interaction
        :type interaction: discord.Interaction
        :return: None if there are no guilds that can be configured
            by the interaction, the id of the guild otherwise
        :rtype: int | None
        """
        channel_id = interaction.channel_id
        if channel_id is None:
            return
        return self._bot_utils.get_config_guild_id(channel_id)

    async def _path_autocomplete(
        self,
        interaction: discord.Interaction,
        path_input: str,
    ) -> list[app_commands.Choice[str]]:
        """
        Provide autocomplete suggestions based on the given path 
        input. The suggestions will include valid paths that are 
        siblings to the input path, i.e. all child nodes of the 
        parent of the input path.

        For example, if the existing paths are "abc.def.x" and 
        "abc.def.y", and the input path is "abc.def.z", the 
        mentioned paths will be suggested. Note that the input path
        itself is not required to exist, as long as its parent path 
        exists. However, if the parent path of the input path is 
        not valid, no suggestions will be provided.

        :param interaction: A discord interaction
        :type interaction: discord.Interaction
        :param path_input: The current path that is inputted
        :type path_input: str
        :return: A list of autocomplete options for potential
            paths
        :rtype: list[app_commands.Choice[str]]
        """
        guild_id = self._get_target_guild_id(interaction)
        if guild_id is None:
            return []

        choices = [
            app_commands.Choice(name=path_option, value=path_option)
            async for path_option in self._path_options(
                path_input, guild_id,
            )
        ]
        return choices

    async def _path_options(
        self,
        path: str,
        guild_id: int,
    ) -> AsyncGenerator[str]:
        """
        Return an asynchronous generator that returns all sibling 
        paths of the given path that exists in the configuration
        of the specified guild with the given id.

        :param path: The path to use as reference
        :type path: str
        :param guild_id: The id of the guild
        :type guild_id: int
        :return: An asynchronous generator that returns the viald
            siblings paths
        :rtype: AsyncGenerator[str]
        :yield: A sibling path that exists in the guild 
            configuration
        :rtype: Iterator[AsyncGenerator[str]]
        """
        index = path.rfind(".")
        dir_path = path[:index] if index != -1 else ""
        try:
            dir_value = await self._config_manager.get(
                guild_id, dir_path,
            )
        except ConfigManager.InvalidPathError:
            return
        if not isinstance(dir_value, dict):
            return
        for key in dir_value.keys():
            yield f"{dir_path}.{key}" if dir_path else key


class PuppetCommandGroup(
    app_commands.Group,
    name="puppet",
    description="Manage Puppets",
):
    def __init__(self, status_monitor: StatusMonitor) -> None:
        super().__init__()
        self._status_monitor = status_monitor

    @app_commands.command(
        name="status",
        description="Get current status of puppets",
    )
    async def get_puppet_status(
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
            MESSAGES.puppet.status.success,
            file=file,
            ephemeral=True,
        )
