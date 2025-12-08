import asyncio

from pymongo import AsyncMongoClient


class DBConnection:
    _tasks: set[asyncio.Task] = set()

    @classmethod
    async def connect(cls, host: str) -> AsyncMongoClient:
        """
        Returns an AsyncMongoClient that will automatically cleanup.

        :param host: A full mongodb URI
        :type host: str
        :return: An AsyncMongoClient with automatic cleanup
        :rtype: AsyncMongoClient
        """
        client_future: asyncio.Future[AsyncMongoClient] = (
            asyncio.Future()
        )
        task = asyncio.create_task(
            cls._connect(host, client_future),
        )
        cls._tasks.add(task)

        await client_future
        return client_future.result()

    @classmethod
    async def _connect(
        cls,
        host: str,
        client_future: asyncio.Future[AsyncMongoClient],
    ) -> None:
        future = asyncio.Future()
        async with AsyncMongoClient(host) as client:
            client_future.set_result(client)
            await future
