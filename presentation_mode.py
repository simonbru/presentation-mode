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


async def wait_shielded():
    logger = logging.getLogger("wait_shielded")
    while True:
        try:
            await wait_forever()
        except asyncio.CancelledError:
            logger.debug("Catch CancelledError")
            pass


async def throw_cancelled():
    await asyncio.sleep(1)
    raise asyncio.CancelledError


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


async def slack_dnd():
    logger = logging.getLogger("slack_dnd")
    slack_token = config("SLACK_API_TOKEN")
    if not slack_token:
        logger.warning("SLACK_API_TOKEN is empty, skip Slack DnD")
        return
    client = slack.WebClient(token=slack_token, run_async=True)
    # while True:
    # try:
    # await asyncio.sleep(10)
    # except asyncio.CancelledError:
    # logger.debug("Catching CancelledError")
    # pass
    try:
        while True:
            # await client.dnd_setSnooze(num_minutes=15)
            await asyncio.sleep(10)
    # except asyncio.CancelledError:
    finally:
        logger.info('Disabling "Do Not Disturb"')
        await asyncio.sleep(1)
        logger.info("after sleep")
        # await asyncio.wait_for(client.dnd_endSnooze(), 5)
        # await asyncio.wait_for(asyncio.sleep(10), 5)


async def main_routine():
    loop = asyncio.get_running_loop()
    tasks = [
        inhibit_notifications(),
        keep_screen_active(),
        slack_dnd(),
        # wait_shielded(),
    ]
    tasks = [asyncio.create_task(coro) for coro in tasks]
    # gathering_task = asyncio.gather(*tasks, return_exceptions=True)
    current_task = asyncio.current_task()

    # def cancel_tasks():
        # logger.debug("Cancelling tasks...")

        # current_task.cancel()
        # gathering_task.cancel()
        # for task in tasks:
        # task.cancel()

    # loop.add_signal_handler(signal.SIGTERM, cancel_tasks)
    # loop.add_signal_handler(signal.SIGINT, cancel_tasks)

    # asyncio.gather(*tasks)
    try:
        await asyncio.gather(*tasks, return_exceptions=False)
        # await gathering_task
        # pass
    # except asyncio.CancelledError:
    finally:
        # logger.info("Waiting for tasks to clean up... (press CTRL+C to force quit)")
        # await gathering_task
        # await asyncio.wait_for(
            # asyncio.gather(*tasks, return_exceptions=True), timeout=CLEANUP_SECONDS
        # )
        loop.close()
        # loop.remove_signal_handler(signal.SIGTERM)
        # loop.remove_signal_handler(signal.SIGINT)
    logger.debug("End of main_routine")


async def main2():
    logger = logging.getLogger('main2')
    loop = asyncio.get_running_loop()

    task = asyncio.create_task(main_routine())
    current_task = asyncio.current_task()
    
    def cancel_tasks():
        logger.debug("Cancelling tasks...")
        # logger.debug((current_task, asyncio.current_task()))
        current_task.cancel()
        # task.cancel()

    def coucou(word=''):
        logger.debug(f"COUCOU {word}")
    
    signals = (signal.SIGTERM, signal.SIGINT)
    # signals = ()
    for sig in signals:
        loop.add_signal_handler(sig, cancel_tasks)
    
    # loop.add_signal_handler(signal.SIGINT, cancel_tasks)
    # loop.add_signal_handler(signal.SIGINT, coucou)
    # loop.add_signal_handler(signal.SIGINT, coucou, '2')
    # loop.add_signal_handler(signal.SIGINT, coucou, '3')

    try:
        await wait_forever()
    finally:
        for sig in signals:
            loop.remove_signal_handler(sig)
        logger.info("Waiting for tasks to clean up... (press CTRL+C to force quit)")
        loop.call_later(CLEANUP_SECONDS, lambda *args: loop.stop())

    # await asyncio.sleep(10)

    # await throw_cancelled()
    # await asyncio.sleep(1)

    # task = asyncio.create_task(wait_shielded())
    # task.cancel()
    # print(task.cancelled())
    # await asyncio.sleep(1)
    # task.cancel()
    # await asyncio.sleep(1)
    # await task
    # logger.info("Waiting for tasks to clean up... (press CTRL+C to force quit)")
    # loop.call_later(CLEANUP_SECONDS, lambda *args: loop.stop())


def main():
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
    asyncio.run(main2())
    print("After loop")


if __name__ == "__main__":
    main()
