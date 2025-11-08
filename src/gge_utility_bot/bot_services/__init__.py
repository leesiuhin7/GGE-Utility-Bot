from .attack_listener import AttackListener, RoutingInfo
from .battle_report import summarize as summarize_battle_report
from .config_manager import ConfigManager
from .status_monitor import StatusMonitor

__all__ = [
    "init",
    "AttackListener",
    "ConfigManager",
    "RoutingInfo",
    "StatusMonitor",
    "summarize_battle_report",
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
