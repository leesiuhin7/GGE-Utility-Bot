from typing import Sequence

import pytest
import pytest_mock

from gge_utility_bot.bot_services import AttackListener, RoutingInfo
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
    "current_index, request_response",
    [
        [
            0,
            [{"response": [["msg1"], 1]}],
        ],
        [
            0,
            [{"response": [["msg1", "msg2"], 4]}],
        ],
        [
            0,
            [
                {"response": [["msg1"], 4]},
                {"response": [["msg2", "msg3"], 6]},
                {"response": [["msg4", "msg5"], 8]},
            ],
        ],
        [
            11,
            [{"response": [["msg1", "msg2"], 13]}],
        ],
        [
            5,
            [],
        ],
    ]
)
async def test_listener(
    mocker: pytest_mock.MockerFixture,
    attack_listener: AttackListener,
    current_index: int,
    request_response: list[ResponseContentType | None],
) -> None:
    encode_msg_output: list[list[str]] = []
    expected_output: list[list[str]] = []
    for response in request_response:
        if response is None:
            continue
        if "error" in response:
            continue
        expected_output.append(response["response"][0])
        for msg in response["response"][0]:
            encode_msg_output.append([msg])

    mock_get_current_index = mocker.patch.object(
        attack_listener,
        "_get_current_index",
        new_callable=mocker.AsyncMock,
    )
    mock_get_current_index.return_value = current_index

    # Mocking asyncio.sleep so there will be no pauses
    mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)

    mocker.patch.object(
        attack_listener._server_comm,
        "send_request",
        new_callable=mocker.AsyncMock,
        side_effect=request_response,
    )
    mocker.patch.object(
        attack_listener,
        "_encode_msg",
        side_effect=encode_msg_output,
    )

    # Expect StopAsyncIteration from mock functions being exhausted
    with pytest.raises(StopAsyncIteration):
        await attack_listener._listener(
            username="user",
            password="pwd123",
            server="server_1",
            routes=[0, 1, 2],
        )

    output: list[tuple[RoutingInfo, list[str]]] = []
    try:
        while True:
            output.append(attack_listener._output_queue.get_nowait())
    except:
        pass

    assert len(output) == len(expected_output)
    for (routing_info, atk_msgs), expected_msgs in zip(
        output, expected_output,
    ):
        assert routing_info == {
            "username": "user",
            "server": "server_1",
            "routes": [0, 1, 2],
        }
        assert atk_msgs == expected_msgs


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
