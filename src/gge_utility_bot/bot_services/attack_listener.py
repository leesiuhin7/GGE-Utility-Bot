import asyncio
import logging

from typing_extensions import TypedDict

from gge_utility_bot import data_process as dp
from gge_utility_bot.config import PlayerConfigType
from gge_utility_bot.server_comm import ResponseContentType, ServerComm
from gge_utility_bot.utils import validate_type

logger = logging.getLogger(__name__)


class RoutingInfo(TypedDict):
    username: str
    server: str
    routes: list[int]


class AttackListener:
    REQUEST_COOLDOWN: float
    REQUEST_TIMEOUT: float
    PLAYER_CONFIGS: list[PlayerConfigType]

    def __init__(self, server_comm: ServerComm) -> None:
        self._server_comm = server_comm

        self._output_queue: asyncio.Queue[tuple[
            RoutingInfo, list[str],
        ]] = asyncio.Queue()
        self._prev_atk_ids: set[int] = set()

        self._started = False
        self._tasks: set[asyncio.Task] = set()

    async def get(self) -> tuple[RoutingInfo, list[str]]:
        """
        Get the oldest messages and its respective routing 
        information that were dispatched but haven't been accessed
        yet.

        :return: The oldest messages and its routing information
        :rtype: tuple[RoutingInfo, list[str]]
        """
        return await self._output_queue.get()

    async def start(self) -> None:
        """
        Start and initialize all listeners.
        """
        if not self._started:
            for player_config in self.PLAYER_CONFIGS:
                await self._setup_listener(player_config)

            self._started = True

    async def _setup_listener(self, config: PlayerConfigType) -> None:
        """
        Initialize a listener based on its configuration.

        :param config: The configuration of the listener
        :type config: PlayerConfigType
        """
        player_info = config["info"]
        atk_listener_config = config["services"]["attack_listener"]
        routes = config["visibility"]
        if not atk_listener_config["enabled"]:
            return

        task = asyncio.create_task(self._listener(
            username=player_info["username"],
            password=player_info["password"],
            server=player_info["server"],
            routes=routes,
        ))
        # Store a reference so that it won't be garbage collected
        self._tasks.add(task)

    async def _listener(
        self,
        *,
        username: str,
        password: str,
        server: str,
        routes: list[int],
    ) -> None:
        index = await self._get_current_index(
            username=username,
            password=password,
            server=server,
        )
        while True:
            await asyncio.sleep(self.REQUEST_COOLDOWN)
            response = await self._server_comm.send_request(
                username=username,
                password=password,
                server=server,
                command="search",
                args={
                    "start_index": index,
                    "msg_type": "gam",
                },
                timeout=self.REQUEST_TIMEOUT,
            )
            unpacked = self._unpack_response(response)
            if unpacked is None:
                continue

            # Unpack to get message and update index
            msg_list, index = unpacked

            atk_msgs: list[str] = []
            for msg in msg_list:
                atk_msgs.extend(self._encode_msg(msg))

            self._dispatch_atk_msgs(
                username=username,
                server=server,
                routes=routes,
                atk_msgs=atk_msgs,
            )

    async def _get_current_index(
        self,
        *,
        username: str,
        password: str,
        server: str,
    ) -> int:
        while True:
            index = await self._request_current_index(
                username=username,
                password=password,
                server=server,
            )
            if index is not None:
                return index
            await asyncio.sleep(self.REQUEST_COOLDOWN)

    async def _request_current_index(
        self,
        *,
        username: str,
        password: str,
        server: str,
    ) -> int | None:
        response = await self._server_comm.send_request(
            username=username,
            password=password,
            server=server,
            command="search",
            args={
                "start_index": 0,
                "msg_type": "",
            },
            timeout=self.REQUEST_TIMEOUT,
        )

        if response is None:
            return
        elif "error" in response:
            error = response["error"]
            logger.error(
                f"Failed to fetch current index, error: {error}",
            )
            return

        try:
            index = response["response"][1]
            if isinstance(index, int):
                return index
        except:
            return

    def _unpack_response(
        self,
        response: ResponseContentType | None,
    ) -> tuple[list[str], int] | None:
        """
        Unpack and validate the response from the server.

        :param response: The server's response
        :type response: ResponseContentType | None
        :return: The unpacked data if it is valid, None otherwise
        :rtype: tuple[list[str], int] | None
        """
        if response is None:
            return
        if "error" in response:
            return
        try:
            # Enforce types
            if not validate_type(
                tuple(response["response"]),
                tuple[list[str], int],
            ):
                return
        except:
            return

        return response["response"]

    def _encode_msg(self, msg: str) -> list[str]:
        """
        Decode a raw message and encode it into useful messages.

        :param msg: A raw message received from the request
        :type msg: str
        :return: The messages that are useful for users
        :rtype: list[str]
        """
        deserialized = dp.AttackListener.deserialize(msg)
        if deserialized is None:
            return []

        atk_msgs: list[str] = []
        for atk_data in deserialized:
            # Prevent duplicates
            if atk_data["atk_id"] not in self._prev_atk_ids:
                self._prev_atk_ids.add(atk_data["atk_id"])
                atk_msgs.append(
                    dp.AttackListener.serialize(atk_data),
                )
        return atk_msgs

    def _dispatch_atk_msgs(
        self,
        *,
        username: str,
        server: str,
        routes: list[int],
        atk_msgs: list[str],
    ) -> None:
        # Check if atk_msgs is empty
        if not atk_msgs:
            return

        routing_info: RoutingInfo = {
            "username": username,
            "server": server,
            "routes": routes,
        }
        self._output_queue.put_nowait((routing_info, atk_msgs))
