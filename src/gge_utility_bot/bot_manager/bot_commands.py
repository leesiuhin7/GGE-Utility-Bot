import discord
from discord import app_commands
from typing_extensions import Any

from gge_utility_bot import data_process as dp
from gge_utility_bot import utils
from gge_utility_bot.bot_services import ConfigManager, StatusMonitor
from gge_utility_bot.messages import MESSAGES

from .utils import BotUtils, load_config_from_channel


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

    @app_commands.command(
        name="reload",
        description="Reload bot configurations",
    )
    async def reload_config(
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

        guild_id = self._bot_utils.get_config_guild_id(channel_id)
        if guild_id is None:
            await interaction.followup.send(
                MESSAGES["config"]["reload"]["not_registered"],
            )
            return

        success = await load_config_from_channel(
            bot_utils=self._bot_utils,
            config_manager=self._config_manager,
            guild_id=guild_id,
            config_channel=channel_id,
        )
        if success:
            await interaction.followup.send(
                MESSAGES["config"]["reload"]["success"],
            )
            return
        else:
            await interaction.followup.send(
                MESSAGES["config"]["reload"]["failed"],
            )

    @app_commands.command(
        name="dump",
        description="Display active bot configurations",
    )
    async def dump_config(
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

        guild_id = self._bot_utils.get_config_guild_id(channel_id)
        if guild_id is None:
            await interaction.followup.send(
                MESSAGES["config"]["dump"]["not_registered"],
                ephemeral=True,
            )
            return

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
            MESSAGES["puppet"]["status"]["success"],
            file=file,
            ephemeral=True,
        )
