import copy
import json
import logging

from typing_extensions import Any, Literal, Self, TypedDict

from gge_utility_bot import utils

logger = logging.getLogger(__name__)


class UnpackedAttackDataType(TypedDict):
    atk_id: int
    remaining_time: int
    kid: int
    target_x: int
    target_y: int
    target_name: str
    target_player_name: str
    attacker_x: int
    attacker_y: int
    attacker_name: str
    attacker_player_name: str
    est_count: int


class PuppetStatusType(TypedDict):
    username: str
    server: str
    connected: bool | None
    attack_warnings: bool


class PuppetStatusOutputType(TypedDict):
    username: str
    server: str
    status: Literal["enabled", "disabled", "unknown"]
    attack_warnings: Literal["enabled", "disabled"]


class AttackWarningBuilder:
    def __init__(self) -> None:
        self._remaining_time: int | None = None
        self._kid: int | None = None
        self._target_x: int | None = None
        self._target_y: int | None = None
        self._target_name: str | None = None
        self._target_player_name: str | None = None
        self._attacker_x: int | None = None
        self._attacker_y: int | None = None
        self._attacker_name: str | None = None
        self._attacker_player_name: str | None = None
        self._est_count: int | None = None
        self._mention_role_ids: list[int] = []

    def serialize(self) -> str | None:
        if (
            self._remaining_time is None
            or self._kid is None
            or self._target_x is None
            or self._target_y is None
            or self._target_name is None
            or self._target_player_name is None
            or self._attacker_x is None
            or self._attacker_y is None
            or self._attacker_name is None
            or self._attacker_player_name is None
        ):
            return None

        # Convert seconds into time string
        compound_time = utils.as_compound_time(self._remaining_time)
        kingdom_name = utils.kid_to_name(self._kid)

        components: list[str] = []
        if self._mention_role_ids:
            components.append(
                "".join(
                    f"<@&{mention_role_ids}>"
                    for mention_role_ids in self._mention_role_ids
                )
            )
        components.extend(
            [
                f"Incoming attack in approx. {compound_time}",
                f'at "{self._target_name}" of "{self._target_player_name}"',
                f"({self._target_x}:{self._target_y})",
                f'from "{self._attacker_name}" of "{self._attacker_player_name}"',
                f"({self._attacker_x}:{self._attacker_y})",
            ]
        )
        if self._est_count is not None and self._est_count != -1:
            components.append(f"with approx. {self._est_count} troop(s)")
        if kingdom_name is not None:
            components.append(f"in {kingdom_name}")

        return " ".join(components)

    def copy(self) -> Self:
        return copy.deepcopy(self)

    def remaining_time(self, value: int) -> Self:
        self._remaining_time = value
        return self

    def kid(self, value: int) -> Self:
        self._kid = value
        return self

    def target_x(self, value: int) -> Self:
        self._target_x = value
        return self

    def target_y(self, value: int) -> Self:
        self._target_y = value
        return self

    def target_name(self, value: str) -> Self:
        self._target_name = value
        return self

    def target_player_name(self, value: str) -> Self:
        self._target_player_name = value
        return self

    def attacker_x(self, value: int) -> Self:
        self._attacker_x = value
        return self

    def attacker_y(self, value: int) -> Self:
        self._attacker_y = value
        return self

    def attacker_name(self, value: str) -> Self:
        self._attacker_name = value
        return self

    def attacker_player_name(self, value: str) -> Self:
        self._attacker_player_name = value
        return self

    def est_count(self, value: int) -> Self:
        self._est_count = value
        return self

    def mention_role_id(self, value: int) -> Self:
        self._mention_role_ids.append(value)
        return self


class AttackListener:
    @classmethod
    def create_builder(
        cls, deserialized: UnpackedAttackDataType
    ) -> AttackWarningBuilder:
        return (
            AttackWarningBuilder()
            .remaining_time(deserialized["remaining_time"])
            .kid(deserialized["kid"])
            .target_x(deserialized["target_x"])
            .target_y(deserialized["target_y"])
            .target_name(deserialized["target_name"])
            .target_player_name(deserialized["target_player_name"])
            .attacker_x(deserialized["attacker_x"])
            .attacker_y(deserialized["attacker_y"])
            .attacker_name(deserialized["attacker_name"])
            .attacker_player_name(deserialized["attacker_player_name"])
            .est_count(deserialized["est_count"])
        )

    @classmethod
    def deserialize(
        cls,
        message: str,
    ) -> list[UnpackedAttackDataType] | None:
        try:
            return cls._deserialize(message)
        except:
            logger.debug(
                "Failed to deserialize message from attack listener.",
                exc_info=True,
            )
            return

    @classmethod
    def _deserialize(
        cls,
        message: str
    ) -> list[UnpackedAttackDataType]:
        parts = message.split(r"%")
        data = json.loads(parts[5])

        deserialized_atks: list[UnpackedAttackDataType] = []
        players: dict[str, dict[str, Any]] = {
            str(player_data["OID"]): player_data
            for player_data in data["O"]
        }
        for atk_data in data["M"]:
            try:
                unpacked = cls._unpack_atk_data(atk_data, players)
                if unpacked is not None:
                    deserialized_atks.append(unpacked)
            except:
                continue

        return deserialized_atks

    @classmethod
    def _unpack_atk_data(
        cls,
        atk_data: dict[str, Any],
        players: dict[str, Any],
    ) -> UnpackedAttackDataType | None:
        if not ("GS" in atk_data or "GA" in atk_data):
            # Not an attack threat
            return

        atk_id: int = atk_data["M"]["MID"]
        remaining_time: int = atk_data["M"]["TT"] - atk_data["M"]["PT"]
        kid: int = atk_data["M"]["KID"]

        target_id: int = atk_data["M"]["TID"]
        attacker_id: int = atk_data["M"]["OID"]

        target_x: int = atk_data["M"]["TA"][1]
        target_y: int = atk_data["M"]["TA"][2]
        target_name: str = atk_data["M"]["TA"][10]
        target_player_name: str = players[str(target_id)]["N"]

        attacker_x: int = atk_data["M"]["SA"][1]
        attacker_y: int = atk_data["M"]["SA"][2]
        attacker_name: str = atk_data["M"]["SA"][10]
        attacker_player_name: str = players[str(attacker_id)]["N"]

        est_count: int = atk_data.get("GS", -1)

        return {
            "atk_id": atk_id,
            "remaining_time": remaining_time,
            "kid": kid,
            "target_x": target_x,
            "target_y": target_y,
            "target_name": target_name,
            "target_player_name": target_player_name,
            "attacker_x": attacker_x,
            "attacker_y": attacker_y,
            "attacker_name": attacker_name,
            "attacker_player_name": attacker_player_name,
            "est_count": est_count,
        }


class StatusMonitor:
    @classmethod
    def encode(
        cls,
        status: PuppetStatusType
    ) -> PuppetStatusOutputType:
        username = status["username"]
        server = status["server"]
        connected = status["connected"]
        attack_warnings = status["attack_warnings"]

        if connected is True:
            active_status = "enabled"
        elif connected is False:
            active_status = "disabled"
        else:
            active_status = "unknown"

        if attack_warnings:
            attack_warning_active = "enabled"
        else:
            attack_warning_active = "disabled"

        output_obj: PuppetStatusOutputType = {
            "username": username,
            "server": server,
            "status": active_status,
            "attack_warnings": attack_warning_active,
        }
        return output_obj
