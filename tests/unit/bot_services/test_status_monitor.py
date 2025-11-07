from typing import Any

import pytest
import pytest_mock

from gge_utility_bot.bot_services.status_monitor import StatusMonitor


@pytest.fixture
def status_monitor(
    mocker: pytest_mock.MockFixture,
) -> StatusMonitor:
    mock_ServerComm = mocker.patch(
        "gge_utility_bot.server_comm.ServerComm",
    )
    mock_server_comm = mock_ServerComm.return_value

    status_monitor = StatusMonitor(server_comm=mock_server_comm)
    status_monitor.PLAYER_CONFIGS = [
        {
            "info": {
                "server": "server_1",
                "username": "Alice",
                "password": "Alice123",
            },
            "services": {
                "attack_listener": {
                    "enabled": False,
                },
                "storm_searcher": {
                    "enabled": True,
                }
            },
            "visibility": [1234, 2468],
        },
        {
            "info": {
                "server": "server_2",
                "username": "Bob",
                "password": "MyPass",
            },
            "services": {
                "attack_listener": {
                    "enabled": True,
                },
                "storm_searcher": {
                    "enabled": True,
                }
            },
            "visibility": [1357, 89],
        },
    ]
    return status_monitor


@pytest.mark.asyncio
@pytest.mark.parametrize("server_response", [True, False, "invalid"])
async def test_get_status(
    mocker: pytest_mock.MockerFixture,
    status_monitor: StatusMonitor,
    server_response: Any,
) -> None:
    mock_send_request = mocker.patch.object(
        target=status_monitor._server_comm,
        attribute="send_request",
        new_callable=mocker.AsyncMock,
    )
    mock_send_request.return_value = {"response": server_response}

    status_list = await status_monitor.get_status()

    for i, player_config in enumerate(status_monitor.PLAYER_CONFIGS):
        assert status_list[i][0]["username"] == (
            player_config["info"]["username"]
        )
        assert status_list[i][0]["server"] == (
            player_config["info"]["server"]
        )
        assert status_list[i][0]["connected"] == (
            {True: True, False: False}.get(server_response)
        )
        assert status_list[i][0]["attack_warnings"] == (
            player_config
            ["services"]
            ["attack_listener"]
            ["enabled"]
        )
        assert status_list[i][1] == player_config["visibility"]
