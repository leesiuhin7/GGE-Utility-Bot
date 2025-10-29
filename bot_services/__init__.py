from .attack_listener import AttackListener, RoutingInfo
from .battle_report import summarize as summarize_battle_report
from .status_monitor import StatusMonitor
from .config_manager import ConfigManager


__all__ = [
    "init",
    "AttackListener",
    "RoutingInfo",
    "summarize_battle_report",
    "StatusMonitor",
    "ConfigManager",
]


def init() -> None:
    from config import cfg
    AttackListener.REQUEST_COOLDOWN = (
        cfg["attack_listener"]["request_cooldown"]
    )
    AttackListener.REQUEST_TIMEOUT = (
        cfg["attack_listener"]["request_timeout"]
    )
    AttackListener.PLAYER_CONFIGS = cfg["players"]
    StatusMonitor.PLAYER_CONFIGS = cfg["players"]
