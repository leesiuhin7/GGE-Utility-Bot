import pytest
import pytest_mock

from gge_utility_bot.bot_services.config_manager import ConfigManager
from gge_utility_bot.utils import ParsedConfigInput


@pytest.fixture
def config_manager(mocker: pytest_mock.MockFixture) -> ConfigManager:
    config_manager = ConfigManager()

    mock_path_dict = mocker.MagicMock()
    config_manager._guild_configs = {
        "1234": mock_path_dict,
    }
    return config_manager


@pytest.mark.parametrize("guild_id, path", [
    (1234, []),
    (1234, ["key", ""]),
])
def test_config_manager_get_valid(
    mocker: pytest_mock.MockFixture,
    config_manager: ConfigManager,
    guild_id: int,
    path: list[str],
) -> None:
    mock_get = mocker.patch.object(
        target=config_manager._guild_configs["1234"],
        attribute="get",
    )

    config_manager.get(guild_id, path)
    mock_get.assert_called_once_with(path)


@pytest.mark.parametrize("guild_id, path", [
    (0, ["key"]),
])
def test_config_manager_get_invalid(
    config_manager: ConfigManager,
    guild_id: int,
    path: list[str],
) -> None:
    with pytest.raises(ConfigManager.GuildNotFoundError):
        config_manager.get(guild_id, path)


@pytest.mark.parametrize("guild_id, parsed_inputs, success", [
    (1234, [], True),
    (
        1234,
        [{
            "path": ["key"],
            "action": "set",
            "value": 1,
        }, {
            "path": ["key2", "abc"],
            "action": "delete",
        }],
        False,
    ),
])
def test_config_manager_load(
    mocker: pytest_mock.MockFixture,
    config_manager: ConfigManager,
    guild_id: int,
    parsed_inputs: list[ParsedConfigInput],
    success: bool,
) -> None:
    mock_update = mocker.patch.object(
        target=config_manager,
        attribute="update",
        return_value=success,
    )
    assert config_manager.load(guild_id, parsed_inputs) is success


@pytest.mark.parametrize("guild_id, parsed_input, success", [
    (1234, {"path": [""], "action": "set", "value": ""}, True),
    (1234, {"path": [], "action": "delete", "value": None}, True),
    (5678, {"path": ["key"], "action": "set", "value": 0}, True),
    (5678, {"path": [""], "action": "delete", "value": None}, False),
])
def test_config_manager_update(
    mocker: pytest_mock.MockFixture,
    config_manager: ConfigManager,
    guild_id: int,
    parsed_input: ParsedConfigInput,
    success: bool,
) -> None:
    mock_update = mocker.patch.object(
        target=config_manager._guild_configs["1234"],
        attribute="update",
        return_value=True,
    )

    assert config_manager.update(guild_id, parsed_input) == success

    if guild_id == 1234:
        mock_update.assert_called_once()
    else:
        mock_update.assert_not_called()
