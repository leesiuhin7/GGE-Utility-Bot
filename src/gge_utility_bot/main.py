import asyncio
import logging
import os
import signal

import discord
import quart
from discord.ext import commands

from gge_utility_bot import config
from gge_utility_bot.auth import init as auth_init
from gge_utility_bot.bot_manager import BotManager
from gge_utility_bot.bot_manager import init as bot_init
from gge_utility_bot.bot_services import (
    AttackListener,
    ConfigManager,
    StatusMonitor,
)
from gge_utility_bot.bot_services import init as bot_services_init
from gge_utility_bot.db_comm import DBConnection
from gge_utility_bot.server_comm import ServerComm
from gge_utility_bot.server_comm import init as server_comm_init

app = quart.Quart(__name__)


@app.route("/ping")
async def keep_alive() -> quart.Response:
    return quart.Response(status=200)


async def terminate() -> None:
    await app.shutdown()


async def main() -> None:
    CONFIG_PATH = os.environ.get("CONFIG_PATH")
    CONTROL_PRIVATE_KEY = os.environ.get("CONTROL_PRIVATE_KEY")
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    DB_URI = os.environ.get("DB_URI")
    PORT = int(os.environ.get("PORT", 10000))

    if (
        CONFIG_PATH is None
        or CONTROL_PRIVATE_KEY is None
        or BOT_TOKEN is None
        or DB_URI is None
    ):
        logging.critical(
            "Mandatory environment variables are missing. Exiting.",
        )
        return

    # Initialize modules
    config.init(CONFIG_PATH)
    auth_init(CONTROL_PRIVATE_KEY)
    server_comm_init()
    bot_init()
    bot_services_init()

    # Logging config
    logging.basicConfig()
    logging_configs = config.cfg["logging"]["level_configs"]
    for logging_config in logging_configs:
        logging.getLogger(
            logging_config["name"],
        ).setLevel(logging_config["level"])

    # Signal handler
    try:
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(
            signal.SIGTERM,
            lambda: asyncio.create_task(terminate()),
        )
    except NotImplementedError:
        logging.warning("Signal handler is not implemented.")

    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(
        command_prefix="!",
        intents=intents,
    )

    server_comm = ServerComm()
    db_client = await DBConnection.connect(DB_URI)

    attack_listener = AttackListener(server_comm)
    status_monitor = StatusMonitor(server_comm)
    config_manager = ConfigManager(db_client)

    bot_manager = BotManager(
        bot=bot,
        attack_listener=attack_listener,
        status_monitor=status_monitor,
        config_manager=config_manager,
    )

    await server_comm.start()

    bot_task = asyncio.create_task(bot_manager.start(BOT_TOKEN))
    server_task = asyncio.create_task(
        app.run_task(host="0.0.0.0", port=PORT),
    )

    await asyncio.wait(
        [bot_task, server_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Cancel tasks
    bot_task.cancel()
    server_task.cancel()
    await asyncio.gather(
        bot_task,
        server_task,
        return_exceptions=True,
    )

    logging.info("Server process terminated.")


if __name__ == "__main__":
    asyncio.run(main())
