import json
import logging
from typing import Any, TypedDict

import utils


logger = logging.getLogger(__name__)


class UnpackedAttackDataType(TypedDict):
    atk_id: int
    remaining_time: int
    target_x: int
    target_y: int
    target_name: str
    target_player_name: str
    attacker_x: int
    attacker_y: int
    attacker_name: str
    attacker_player_name: str
    est_count: int


class AttackListener:
    @classmethod
    def serialize(cls, deserialized: UnpackedAttackDataType) -> str:
        remaining_time = deserialized["remaining_time"]
        target_x = deserialized["target_x"]
        target_y = deserialized["target_y"]
        target_name = deserialized["target_name"]
        target_player_name = deserialized["target_player_name"]
        attacker_x = deserialized["attacker_x"]
        attacker_y = deserialized["attacker_y"]
        attacker_name = deserialized["attacker_name"]
        attacker_player_name = deserialized["attacker_player_name"]
        est_count = deserialized["est_count"]

        # Convert seconds into time string
        compound_time = utils.as_compound_time(remaining_time)

        components = [
            f"Incoming attack in approx. {compound_time}",
            f"at \"{target_name}\" of \"{target_player_name}\"",
            f"({target_x}:{target_y})",
            f"from \"{attacker_name}\" of \"{attacker_player_name}\"",
            f"({attacker_x}:{attacker_y})",
        ]
        if est_count != -1:
            components.append(f"with approx. {est_count} troop(s)")

        return " ".join(components)

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
