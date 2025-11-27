from typing_extensions import Any, Sequence, TypedDict

from gge_utility_bot.utils import ParsedConfigInput, PathDict


class AttackListenerRoutingConfigType(TypedDict):
    username: str
    server: str
    channel_ids: dict[str, int]


class BattleReportSummaryConfigType(TypedDict):
    enabled: bool


class AttackListenerConfigType(TypedDict):
    enabled: bool
    routes: list[AttackListenerRoutingConfigType]


class BattleReportConfigType(TypedDict):
    channel_ids: dict[str, int]
    summary: BattleReportSummaryConfigType


class StormSearcherConfigType(TypedDict):
    enabled: bool


class ServiceConfigType(TypedDict):
    attack_listener: AttackListenerConfigType
    battle_report: BattleReportConfigType
    storm_searcher: StormSearcherConfigType


class ConfigType(TypedDict):
    services: ServiceConfigType


class ConfigManager:
    class GuildNotFoundError(KeyError):
        """Raised when a guild is not registered."""

    def __init__(self) -> None:
        self._guild_configs: dict[str, PathDict] = {}

    def get(self, guild_id: int, path: Sequence[str]) -> Any:
        """
        Get the config of the specified guild at the specified path.

        :param guild_id: The id of the guild
        :type guild_id: int
        :param path: A list of keys that defines the path of the
            target value within the entire config
        :type path: Sequence[str]
        :raises ConfigManager.GuildNotFoundError: If guild has not 
            been registered
        :raises KeyError: If path is not valid
        :raises TypeError: If path is not valid
        :return: The taregt value at the given path
        :rtype: Any
        """
        guild_config = self._guild_configs.get(str(guild_id))
        if guild_config is None:
            raise ConfigManager.GuildNotFoundError

        return guild_config.get(path)

    def load(
        self,
        guild_id: int,
        parsed_inputs: list[ParsedConfigInput],
    ) -> bool:
        """
        Clear and load the config of the given guild.

        :param guild_id: The id of the guild
        :type guild_id: int
        :param parsed_inputs: A list of update operations that will
            be carried out in order after clearing the config. The
            first element will be carried out first, hence it should
            be the oldest operation.
        :type parsed_inputs: list[ParsedConfigInput]
        :return: True if all operations succeeded, False otherwise
        :rtype: bool
        """
        # Clear loaded config
        self.update(
            guild_id,
            {"action": "delete", "path": [], "value": None},
        )

        # Using "success = result and success" so that any fails
        # would lead to success being False
        success = True

        # Update config
        for parsed in parsed_inputs:
            success = self.update(guild_id, parsed) and success

        return success

    def update(
        self,
        guild_id: int,
        parsed_input: ParsedConfigInput,
    ) -> bool:
        """
        Update the config of the given guild.

        :param guild_id: The id of the guild
        :type guild_id: int
        :param parsed_input: The update operation that will
            be carried out
        :type parsed_input: ParsedConfigInput
        :return: True if the operation succeeded, False otherwise
        :rtype: bool
        """
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
