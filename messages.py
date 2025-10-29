from typing import TypedDict, Literal


class ConfigType(TypedDict):
    reload: dict[
        Literal[
            "not_channel",
            "not_registered",
            "failed",
            "success",
        ],
        str,
    ]
    dump: dict[
        Literal[
            "not_channel",
            "not_registered",
            "success",
        ],
        str,
    ]


class PuppetType(TypedDict):
    status: dict[Literal["success"], str]


class BattleReportType(TypedDict):
    summary: str


class MessageType(TypedDict):
    config: ConfigType
    puppet: PuppetType
    battle_report: BattleReportType


MESSAGES: MessageType = {
    "config": {
        "reload": {
            "not_channel": "This channel cannot be used to reload configuration.",
            "not_registered": "This channel has not been registered for configuration.",
            "failed": "Reload configuration failed.",
            "success": "Reload configuration succeeded.",
        },
        "dump": {
            "not_channel": "This channel cannot be used to reload configuration.",
            "not_registered": "This channel has not been registered for configuration.",
            "success": "Configuration dump succeeded.",
        }
    },
    "puppet": {
        "status": {
            "success": "Puppet status loaded successfully.",
        }
    },
    "battle_report": {
        "summary": "Battle report summary.",
    },
}
