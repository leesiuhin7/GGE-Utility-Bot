import asyncio
from websockets.asyncio.client import ClientConnection
import websockets
import logging
import time
import json
from typing import Literal, Any, TypedDict, Union

from auth import Auth


logger = logging.getLogger(__name__)


class SucceedResponseContentType(TypedDict):
    response: Any


class FailedResponseContentType(TypedDict):
    error: str


ResponseContentType = Union[
    SucceedResponseContentType,
    FailedResponseContentType,
]


class ServerResponseType(TypedDict):
    content: ResponseContentType
    msg_id: int


def init() -> None:
    from config import cfg
    ServerComm.RECONNECT_COOLDOWN = (
        cfg["server"]["reconnect_cooldown"]
    )
    ServerComm.URL = cfg["server"]["url"]


class Request:
    def __init__(
        self,
        *,
        username: str,
        password: str,
        server: str,
        command: Literal[
            "disconnect",
            "reconnect",
            "info",
            "send",
            "search",
            "login",
        ],
        args: dict[str, Any],
        timestamp: float,
        msg_id: int,
    ) -> None:
        self.username = username
        self.password = password
        self.server = server
        self.command = command
        self.args = args
        self.timestamp = timestamp
        self.msg_id = msg_id

    @property
    def message(self) -> str:
        content = {
            "username": self.username,
            "server": self.server,
            "command": self.command,
            "args": self.args,
            "timestamp": self.timestamp,
            "msg_id": self.msg_id,
        }

        content_bytes = json.dumps(content).encode()
        if self.command in ["disconnect", "reconnect"]:
            digest = Auth.control_digest(content_bytes)
        else:
            digest = Auth.client_digest(
                content_bytes,
                self.password.encode(),
            )

        request = {
            "content": content,
            "digest": digest,
        }
        request_msg = json.dumps(request)
        return request_msg


class ServerComm:
    RECONNECT_COOLDOWN: float
    URL: str

    def __init__(self) -> None:
        # Will be set if started
        self._start_flag = asyncio.Event()

        self._request_queue: asyncio.PriorityQueue[
            tuple[int, websockets.Data],
        ] = asyncio.PriorityQueue()

        self._next_msg_id = 0
        self._response_register: dict[
            str, asyncio.Queue[ResponseContentType],
        ] = {}

    async def start(self) -> None:
        if not self._start_flag.is_set():
            asyncio.create_task(self._connect_loop())
            self._start_flag.set()

    async def send_request(
        self,
        *,
        username: str,
        password: str,
        server: str,
        command: Literal[
            "disconnect",
            "reconnect",
            "info",
            "send",
            "search",
            "login",
        ],
        args: dict,
    ) -> ResponseContentType:
        timestamp = time.time()
        msg_id = self._get_msg_id()

        request = Request(
            username=username,
            password=password,
            server=server,
            command=command,
            args=args,
            timestamp=timestamp,
            msg_id=msg_id,
        )
        return await self._send_request(request)

    async def _connect_loop(self) -> None:
        while True:
            logger.info(f"Initiating connection with API server.")
            try:
                await self._connect()
            except Exception as e:
                logger.exception(
                    f"Error when connecting to server: {e}",
                )

            await asyncio.sleep(self.RECONNECT_COOLDOWN)

    async def _connect(self) -> None:
        async with websockets.connect(self.URL) as ws:
            msg_task = asyncio.create_task(self._send_msg_loop(ws))
            recv_task = asyncio.create_task(self._recv_loop(ws))
            await asyncio.wait(
                [msg_task, recv_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

    async def _send_msg_loop(self, ws: ClientConnection) -> None:
        try:
            while True:
                msg_id, msg = await self._request_queue.get()
                await ws.send(msg)
        except websockets.ConnectionClosed:
            pass
        except Exception as e:
            logger.exception(f"Error sending requests: {e}")

    async def _recv_loop(self, ws: ClientConnection) -> None:
        try:
            async for msg in ws:
                await self._process_response(msg)
        except websockets.ConnectionClosed:
            pass
        except Exception as e:
            logger.exception(f"Error receiving responses: {e}")

    async def _process_response(self, response: websockets.Data) -> None:
        try:
            response_obj: ServerResponseType = json.loads(response)
            content = response_obj["content"]
            msg_id = response_obj["msg_id"]
        except:
            return

        response_queue = self._response_register.get(str(msg_id))
        if response_queue is None:
            return

        await response_queue.put(content)

    def _get_msg_id(self) -> int:
        msg_id = self._next_msg_id
        self._next_msg_id += 1
        return msg_id

    async def _send_request(
        self,
        request: Request,
    ) -> ResponseContentType:
        request_msg = request.message
        msg_id = request.msg_id
        key = str(msg_id)

        # Initialize response queue
        response_queue = asyncio.Queue()
        self._response_register[key] = response_queue

        await self._request_queue.put((msg_id, request_msg))
        # Wait for response
        response_msg = await self._response_register[key].get()
        del self._response_register[key]
        return response_msg
