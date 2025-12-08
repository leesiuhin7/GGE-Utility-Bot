from pymongo import AsyncMongoClient
from typing_extensions import Any, TypedDict


class AttackListenerRoutingConfigType(TypedDict):
    username: str
    server: str
    channel_ids: dict[str, int]


class BattleReportSummaryConfigType(TypedDict):
    enabled: bool


class AttackListenerConfigType(TypedDict):
    enabled: bool
    routes: list[AttackListenerRoutingConfigType]


class BattleReportConfigType(TypedDict):
    channel_ids: dict[str, int]
    summary: BattleReportSummaryConfigType


class StormSearcherConfigType(TypedDict):
    enabled: bool


class ServiceConfigType(TypedDict):
    attack_listener: AttackListenerConfigType
    battle_report: BattleReportConfigType
    storm_searcher: StormSearcherConfigType


class ConfigType(TypedDict):
    services: ServiceConfigType


class ConfigManager:
    class InvalidPathError(Exception):
        """Raised when an invalid path is received."""

    def __init__(
        self,
        db_client: AsyncMongoClient[dict[str, Any]],
    ) -> None:
        self._db_client = db_client
        self._database = (
            self._db_client.get_database("GGE-utility-bot")
        )
        self._collection = (
            self._database.get_collection("user-config")
        )

    async def get(self, guild_id: int, path: str) -> Any:
        """
        Read the value of a field specified by the given path,
        from the configuration of the guild with the given id.

        :param guild_id: The id of the guild
        :type guild_id: int
        :param path: The path to the field to be read from
        :type path: str
        :raises self.InvalidPathError: When the given path cannot
            access any fields
        :return: The value of the specified field
        :rtype: Any
        """
        if not self._validate_path(path):
            # Allow empty path as reference to root
            if path != "":
                raise self.InvalidPathError

        # Matches if the path is valid for the specified guild
        if path != "":
            pipeline = [
                {"$match": {
                    "_id": guild_id,
                    path: {"$exists": True},
                }},
                {"$project": {"output": f"${path}"}},
            ]
        else:
            # path refers to the root path instead if empty
            pipeline = [
                {"$match": {
                    "_id": guild_id,
                }},
                {"$project": {"_id": 0}},  # Remove _id field
                {"$project": {"output": "$$ROOT"}},
            ]

        try:
            async with (
                await self._collection.aggregate(pipeline)
            ) as cursor:
                async for result in cursor:
                    return result["output"]
        except:  # AsyncCollection.aggregate may raise unknown errors
            pass

        # Raise exception if no result is found
        raise self.InvalidPathError

    async def update(
        self,
        guild_id: int,
        path: str,
        value: Any,
    ) -> bool:
        """
        Overwrite the value of a field specified by the given path
        with the given value, from the configuration of the guild
        with the given id.

        :param guild_id: The id of the guild
        :type guild_id: int
        :param path: The path to the field to be overwritten
        :type path: str
        :param value: The value to overwrite with
        :type value: Any
        :return: False if the operation failed, True otherwise
        :rtype: bool
        """
        if not self._validate_path(path):
            return False
        try:
            await self._collection.update_one(
                filter={"_id": guild_id},
                update={"$set": {path: value}},
                upsert=True,
            )
        except:
            return False
        return True

    async def delete(
        self,
        guild_id: int,
        path: str,
    ) -> bool:
        """
        Remove a field specified by the given path, from the
        configuration of the guild with the given id.

        :param guild_id: The id of the guild
        :type guild_id: int
        :param path: The path to the field to be removed
        :type path: str
        :return: False if the operation failed, True otherwise
        :rtype: bool
        """
        if not self._validate_path(path):
            return False
        try:
            await self._collection.update_one(
                filter={"_id": guild_id},
                update={"$unset": {path: ""}},
            )
        except:
            return False
        return True

    def _validate_path(self, path: str) -> bool:
        """
        Validate the given path to ensure it is safe to pass
        onto the database to avoid security issues.

        :param path: The path to be validated
        :type path: str
        :return: False if the path is unsafe to be used, 
            True otherwise
        :rtype: bool
        """
        if path == "_id":
            # The _id field should be hidden from users
            return False
        if path.startswith("$"):
            # Field paths cannot begin with "$"
            return False
        if path == "":
            # Field paths cannot be empty
            return False
        return True
