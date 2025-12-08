import pytest
import pytest_mock
from typing_extensions import Any, Literal, Self, Sequence

from gge_utility_bot.bot_services.config_manager import ConfigManager


class MockAsyncCommandCursor:
    def __init__(self, outputs: Sequence[Any]) -> None:
        self._outputs = outputs
        self._index = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> dict[Literal["output"], Any]:
        if self._index < len(self._outputs):
            value = self._outputs[self._index]
            self._index += 1
            return {"output": value}
        else:
            raise StopAsyncIteration


@pytest.fixture
def config_manager(mocker: pytest_mock.MockFixture) -> ConfigManager:
    mock_AsyncMongoClient = mocker.patch(
        "pymongo.AsyncMongoClient",
    )
    mock_db_client = mock_AsyncMongoClient.return_value
    config_manager = ConfigManager(mock_db_client)
    return config_manager


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "aggregate_outputs, path, is_valid_path",
    [
        [[1, 2, 3], "abc", True],
        [[4, 5, 6], "ab.c", True],
        [[], "abcd.efg", True],
        [[0, 7], "_id", False],
        [[8, 9], "$abc.def", False],
    ],
)
async def test_config_manager_get(
    mocker: pytest_mock.MockFixture,
    config_manager: ConfigManager,
    aggregate_outputs: Sequence[Any],
    path: str,
    is_valid_path: bool,
) -> None:
    mocker.patch.object(
        config_manager._collection,
        "aggregate",
        side_effect=lambda *args, **kwargs: (
            MockAsyncCommandCursor(aggregate_outputs)
        ),
        new_callable=mocker.AsyncMock,
    )
    if not aggregate_outputs:
        # Expects error as the iterable will be empty which
        # means no results received
        with pytest.raises(ConfigManager.InvalidPathError):
            await config_manager.get(0, path)
    elif not is_valid_path:
        # Expects error as it should not allow an invalid path
        with pytest.raises(ConfigManager.InvalidPathError):
            await config_manager.get(0, path)
    else:
        # Expects the first result received by the function
        # (from the iterable) to be returned
        result = await config_manager.get(0, path)
        assert result == aggregate_outputs[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path, is_valid_path, fail_update",
    [
        ["abc", True, False],
        ["ab.cd", True, True],
        ["_id", False, True],
        ["$xyz.abc", False, False],
    ],
)
async def test_config_manager_update(
    mocker: pytest_mock.MockFixture,
    config_manager: ConfigManager,
    path: str,
    is_valid_path: bool,
    fail_update: bool,
) -> None:
    mocker.patch.object(
        config_manager._collection,
        "update_one",
        side_effect=(Exception if fail_update else None),
        new_callable=mocker.AsyncMock,
    )

    result = await config_manager.update(0, path, None)
    if not is_valid_path:
        assert result is False
    elif fail_update:
        assert result is False
    else:
        assert result is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path, is_valid_path, fail_update",
    [
        ["xyz", True, False],
        ["ab.pq", True, True],
        ["_id", False, True],
        ["$abc.def", False, False],
    ],
)
async def test_config_manager_delete(
    mocker: pytest_mock.MockFixture,
    config_manager: ConfigManager,
    path: str,
    is_valid_path: bool,
    fail_update: bool,
) -> None:
    mocker.patch.object(
        config_manager._collection,
        "update_one",
        side_effect=(Exception if fail_update else None),
        new_callable=mocker.AsyncMock,
    )

    result = await config_manager.delete(0, path)
    if not is_valid_path:
        assert result is False
    elif fail_update:
        assert result is False
    else:
        assert result is True
