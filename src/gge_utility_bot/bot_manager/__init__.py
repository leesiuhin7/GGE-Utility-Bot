from .bot_manager import BotManager

__all__ = ["BotManager"]


def init() -> None:
    from gge_utility_bot.config import cfg

    from .utils import BotUtils

    BotManager.GUILD_INFOS = cfg["discord"]["guilds"]
    BotUtils.GUILD_INFOS = cfg["discord"]["guilds"]
