import pytest
import pytest_mock

from gge_utility_bot.bot_services import AttackListener
from gge_utility_bot.server_comm import ResponseContentType


@pytest.fixture
def attack_listener(
    mocker: pytest_mock.MockFixture,
) -> AttackListener:
    mock_ServerComm = mocker.patch(
        "gge_utility_bot.server_comm.ServerComm",
    )
    mock_server_comm = mock_ServerComm.return_value
    attack_listener = AttackListener(server_comm=mock_server_comm)
    attack_listener.REQUEST_COOLDOWN = 0
    attack_listener.REQUEST_TIMEOUT = 1
    attack_listener.PLAYER_CONFIGS = []
    return attack_listener


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "expected_count, expected_value, request_response",
    [
        [1, 5, [
            {"response": [["abc"], 5]},
        ]],
        [1, 2, [
            {"response": [["xyz"], 2]},
            {"response": [["def"], 6]},
        ]],
        [3, 5, [
            {"error": "UnknownError"},
            {"error": "RandomError"},
            {"response": [["qrs"], 5]},
            {"response": [["msg"], 6]},
        ]],
    ]
)
async def test_get_current_index(
    mocker: pytest_mock.MockFixture,
    attack_listener: AttackListener,
    expected_count: int,
    expected_value: int,
    request_response: list[ResponseContentType | None],
) -> None:
    mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)

    mock_send_request = mocker.patch.object(
        attack_listener._server_comm,
        "send_request",
        new_callable=mocker.AsyncMock,
        side_effect=request_response,
    )

    index = await attack_listener._get_current_index(
        username="user",
        password="pwd123",
        server="server_1",
    )

    assert index == expected_value
    assert mock_send_request.await_count == expected_count
