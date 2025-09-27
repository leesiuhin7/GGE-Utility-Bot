from typing import TypedDict, Literal


class ConfigType(TypedDict):
    reload: dict[
        Literal[
            "not_channel",
            "not_registered",
            "failed",
            "succeeded",
        ],
        str,
    ]


class MessageType(TypedDict):
    config: ConfigType


MESSAGES: MessageType = {
    "config": {
        "reload": {
            "not_channel": "This channel cannot be used to reload configuration.",
            "not_registered": "This channel has not been registered for configuration.",
            "failed": "Reload configuration failed.",
            "succeeded": "Reload configuration succeeded.",
        }
    }
}
