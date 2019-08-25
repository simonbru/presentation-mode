#!/usr/bin/env python


import asyncio
import logging
import os
import signal
import sys

import dbussy
import slack
from dbussy import DBUS
from decouple import config

logger = logging.getLogger(__name__)

CLEANUP_SECONDS = 5


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


async def slack_dnd():
    logger = logging.getLogger("slack_dnd")
    slack_token = config("SLACK_API_TOKEN")
    if not slack_token:
        logger.warning("SLACK_API_TOKEN is empty, skip Slack DnD")
        return
    client = slack.WebClient(token=slack_token, run_async=True)
    await client.dnd_setSnooze(num_minutes=15)
    try:
        while True:
            await asyncio.sleep(10 * 60)
            await client.dnd_setSnooze(num_minutes=15)
    finally:
        logger.info('Disabling "Do Not Disturb"')
        await client.dnd_endSnooze()


async def run_tasks():
    tasks = [inhibit_notifications(), keep_screen_active(), slack_dnd()]
    await asyncio.gather(*tasks, return_exceptions=False)


async def main_coro():
    logger = logging.getLogger("main")
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
    logging.basicConfig(
        format="%(name)s: %(message)s",
        level=logging.DEBUG if sys.flags.dev_mode else logging.INFO,
    )
    asyncio.run(main_coro())


if __name__ == "__main__":
    main()
