import asyncio

from gge_utility_bot import data_process as dp
from gge_utility_bot.config import PlayerConfigType
from gge_utility_bot.server_comm import ServerComm


class StatusMonitor:
    PLAYER_CONFIGS: list[PlayerConfigType]

    def __init__(self, server_comm: ServerComm) -> None:
        self._server_comm = server_comm

    async def get_status(
        self,
    ) -> list[tuple[dp.PuppetStatusType, list[int]]]:
        coros = [
            asyncio.create_task(self._get_status(player_config))
            for player_config in self.PLAYER_CONFIGS
        ]
        status_list = await asyncio.gather(*coros)
        return status_list

    async def _get_status(
        self,
        player_config: PlayerConfigType,
    ) -> tuple[dp.PuppetStatusType, list[int]]:
        username = player_config["info"]["username"]
        password = player_config["info"]["password"]
        server = player_config["info"]["server"]
        attack_warnings = (
            player_config["services"]["attack_listener"]["enabled"]
        )
        routes = player_config["visibility"]

        connected = await self._get_active_status(
            username=username,
            password=password,
            server=server,
            timeout=30,
        )

        status: dp.PuppetStatusType = {
            "username": username,
            "server": server,
            "connected": connected,
            "attack_warnings": attack_warnings,
        }
        return status, routes

    async def _get_active_status(
        self,
        *,
        username: str,
        password: str,
        server: str,
        timeout: float,
    ) -> bool | None:
        response = await self._server_comm.send_request(
            username=username,
            password=password,
            server=server,
            command="info",
            args={
                "name": "connected",
            },
            timeout=timeout,
        )
        if response is None:
            return None
        if "error" in response:
            return None

        active = response["response"]
        if active is True:
            return True
        elif active is False:
            return False
        else:
            return None
