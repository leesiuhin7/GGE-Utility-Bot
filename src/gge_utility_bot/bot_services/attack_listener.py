import asyncio
import logging

from typing_extensions import TypedDict

from gge_utility_bot import data_process as dp
from gge_utility_bot.config import PlayerConfigType
from gge_utility_bot.server_comm import ServerComm
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

    async def get(self) -> tuple[RoutingInfo, list[str]]:
        return await self._output_queue.get()

    async def start(self) -> None:
        if not self._started:
            for player_config in self.PLAYER_CONFIGS:
                player_info = player_config["info"]
                atk_listener_config = (
                    player_config
                    ["services"]
                    ["attack_listener"]
                )
                routes = player_config["visibility"]
                if not atk_listener_config["enabled"]:
                    continue

                asyncio.create_task(self._listener(
                    username=player_info["username"],
                    password=player_info["password"],
                    server=player_info["server"],
                    routes=routes,
                ))

            self._started = True

    async def _listener(
        self,
        *,
        username: str,
        password: str,
        server: str,
        routes: list[int],
    ) -> None:
        index = None
        while index is None:
            index = await self._get_current_index(
                username=username,
                password=password,
                server=server,
            )
            await asyncio.sleep(self.REQUEST_COOLDOWN)

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
            if response is None:
                continue
            if "error" in response:
                continue
            try:
                # Enforce types
                if not validate_type(
                    tuple(response["response"]),
                    tuple[list[str], int],
                ):
                    continue
            except:
                continue

            msg_list: list[str]
            msg_list, index = response["response"]

            atk_msgs: list[str] = []
            for msg in msg_list:
                deserialized = dp.AttackListener.deserialize(msg)
                if deserialized is None:
                    continue

                for atk_data in deserialized:
                    # Prevent duplicates
                    if atk_data["atk_id"] not in self._prev_atk_ids:
                        self._prev_atk_ids.add(atk_data["atk_id"])
                        atk_msgs.append(
                            dp.AttackListener.serialize(atk_data),
                        )

            if len(atk_msgs) > 0:
                routing_info = self._serialize_routing_info(
                    username=username,
                    server=server,
                    routes=routes,
                )
                await self._output_queue.put((routing_info, atk_msgs))

    async def _get_current_index(
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

    def _serialize_routing_info(
        self,
        *,
        username: str,
        server: str,
        routes: list[int],
    ) -> RoutingInfo:
        return {
            "username": username,
            "server": server,
            "routes": routes,
        }
