#!/usr/bin/env python


import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

import dbussy
import slack
from dbussy import DBUS
from decouple import Config, RepositoryEnv

logger = logging.getLogger(__name__)

CLEANUP_SECONDS = 5


def config_file_path():
    config_home = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    return Path(config_home) / "presentation_mode.cfg"


def load_config():
    fpath = config_file_path()
    if fpath.exists():
        return Config(RepositoryEnv(fpath))
    else:
        return Config(os.environ)


async def wait_forever():
    while True:
        await asyncio.sleep(3600)


async def inhibit_notifications():
    conn = await dbussy.Connection.bus_get_async(DBUS.BUS_SESSION, private=False)
    try:
        msg = dbussy.Message.new_method_call(
            destination="org.freedesktop.Notifications",
            path="/org/freedesktop/Notifications",
            iface="org.freedesktop.Notifications",
            method="Inhibit",
        ).append_objects("ssa{sv}", os.path.basename(__file__), "Presentation mode", {})
        reply = await conn.send_await_reply(msg)
        await wait_forever()
    finally:
        conn.close()


async def keep_screen_active():
    conn = await dbussy.Connection.bus_get_async(DBUS.BUS_SESSION, private=False)
    try:
        msg = dbussy.Message.new_method_call(
            destination="org.freedesktop.ScreenSaver",
            path="/org/freedesktop/ScreenSaver",
            iface="org.freedesktop.ScreenSaver",
            method="Inhibit",
        ).append_objects("ss", os.path.basename(__file__), "Presentation mode")
        reply = await conn.send_await_reply(msg)
        await wait_forever()
    finally:
        conn.close()


async def slack_dnd(token):
    client = slack.WebClient(token=token, run_async=True)
    await client.dnd_setSnooze(num_minutes=15)
    try:
        while True:
            await asyncio.sleep(10 * 60)
            await client.dnd_setSnooze(num_minutes=15)
    finally:
        logger.debug('Disabling "Do Not Disturb"')
        await client.dnd_endSnooze()


async def run_tasks():
    conf = load_config()
    tasks = [inhibit_notifications(), keep_screen_active()]

    slack_token = conf.get("SLACK_API_TOKEN", default=None)
    if slack_token:
        tasks.append(slack_dnd(token=slack_token))
    else:
        logging.info(
            f"Set SLACK_API_TOKEN=<your-token> in environment or in {config_file_path()}"
            ' to enable Slack "Do not disturb".'
        )

    async def catch_all_errors(awaitable):
        try:
            await awaitable
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(e)

    await asyncio.gather(*(catch_all_errors(coro) for coro in tasks))


async def main_coro():
    loop = asyncio.get_running_loop()

    main_task = asyncio.create_task(run_tasks())
    current_task = asyncio.current_task()

    def cancel_tasks():
        logger.debug("Cancelling tasks...")
        current_task.cancel()

    def force_quit():
        logger.debug("Stopping the loop by force...")
        loop.stop()

    signals = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
    for sig in signals:
        loop.add_signal_handler(sig, cancel_tasks)

    try:
        await wait_forever()
    except asyncio.CancelledError:
        pass
    finally:
        for sig in signals:
            loop.remove_signal_handler(sig)
        # `asyncio.run` will cancel and wait for all running tasks
        # (including `main_task`) when leaving `main_coro()`
        logger.info("Waiting for tasks to clean up... (press CTRL+C to force quit)")
        loop.call_later(CLEANUP_SECONDS, force_quit)


def main():
    if sys.flags.dev_mode:
        logging.basicConfig(format="%(name)s:%(funcName)s: %(message)s", level=logging.DEBUG)
    else:
        logging.basicConfig(format="%(message)s", level=logging.INFO)
    asyncio.run(main_coro())


if __name__ == "__main__":
    main()
