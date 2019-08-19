#!/usr/bin/env python

# Dependencies: aiohttp, dbussy

# Actions
# start/stop or blocking: systemd-inhibit
# loop: org.freedesktop.ScreenSaver.SimulateUserActivity
# start/stop or blocking: org.freedesktop.Notifications.Inhibit
# start/stop: slack do not disturb
# brightness 100%

import asyncio
import logging
import sys

import dbussy
from dbussy import DBUS

logger = logging.getLogger(__name__)


async def wait_forever():
    while True:
        await asyncio.sleep(3600)


async def inhibit_notifications():
    conn = await dbussy.Connection.bus_get_async(DBUS.BUS_SESSION, private=False)
    msg = dbussy.Message.new_method_call(
        destination="org.freedesktop.Notifications",
        path="/org/freedesktop/Notifications",
        iface="org.freedesktop.Notifications",
        method="Inhibit",
    ).append_objects("ssa{sv}", __file__, "Presentation mode", {})
    reply = await conn.send_await_reply(msg)
    await wait_forever()


async def keep_screen_active():
    conn = await dbussy.Connection.bus_get_async(DBUS.BUS_SESSION, private=False)
    msg = dbussy.Message.new_method_call(
        destination="org.freedesktop.ScreenSaver",
        path="/org/freedesktop/ScreenSaver",
        iface="org.freedesktop.ScreenSaver",
        method="Inhibit",
    ).append_objects("ss", __file__, "Presentation mode")
    reply = await conn.send_await_reply(msg)
    await wait_forever()


async def enable_slack_dnd():
    logger = logging.getLogger('enable_slack_dnd')
    try:
        await wait_forever()
    finally:
        logger.debug("finally")
        # await asyncio.sleep(1)
        # logger.info("after sleep")


async def main():
    loop = asyncio.get_running_loop()
    tasks = [inhibit_notifications(), keep_screen_active(), enable_slack_dnd()]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("Cancelled")


if __name__ == "__main__":
    logging.basicConfig(
        format="%(name)s: %(message)s",
        level=logging.DEBUG if sys.flags.dev_mode else logging.INFO,
    )
    # formatter = logging.Formatter("{funcName}: {message}", style="{")
    # handler = logging.StreamHandler()
    # handler.setFormatter(formatter)
    # handler.setLevel(logging.DEBUG if sys.flags.dev_mode else logging.INFO)
    # logger.addHandler(handler)
    # logger.propagate = False
    asyncio.run(main())
