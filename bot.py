import plugins.monkey_patch
import sys
import glob
import importlib
from pathlib import Path
from pyrogram import Client, idle, __version__
from pyrogram.raw.all import layer
import time
from pyrogram.errors import FloodWait
import asyncio
from datetime import date, datetime
import pytz

# ===================================================================
# NEW CODE: SCHEDULER IMPORTS
# ===================================================================
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
# ===================================================================

from aiohttp import web
from database.ia_filterdb import Media, Media2
from database.users_chats_db import db
from info import *
from utils import temp
from Script import script
from plugins import web_server, check_expired_premium, keep_alive
from dreamxbotz.Bot import dreamxbotz
from dreamxbotz.util.keepalive import ping_server
from dreamxbotz.Bot.clients import initialize_clients
from PIL import Image
Image.MAX_IMAGE_PIXELS = 500_000_000

import logging
import logging.config

logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("imdbpy").setLevel(logging.ERROR)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("aiohttp.web").setLevel(logging.ERROR)
logging.getLogger("pymongo").setLevel(logging.WARNING)

# ===================================================================
# NEW CODE: SCHEDULER INITIALIZATION AND FUNCTIONS
# ===================================================================

# Initialize the Scheduler instance
scheduler = AsyncIOScheduler()

async def index_messages(client):
    """The core function to re-index all channels."""
    print("🤖 Starting daily auto-index task...")
    try:
        # Assuming your main index function is here
        from plugins.index_files import full_index_channels
        await full_index_channels(client) # Pass the Pyrogram client instance
        print("✅ Daily auto-index completed.")
    except ImportError:
         print("❌ Error: Could not find 'full_index_channels'. Ensure it's correctly defined.")
    except Exception as e:
        print(f"❌ Error during daily index: {e}")

def schedule_daily_index(client, hour: int, minute: int):
    """Schedules the index_messages task for a specific time."""
    # Remove any existing jobs named 'Daily Indexer'
    if scheduler.get_job('Daily Indexer'):
        scheduler.remove_job('Daily Indexer')

    # Add the new daily job
    # Note: APScheduler CronTrigger uses UTC time by default.
    scheduler.add_job(
        index_messages,
        CronTrigger(hour=hour, minute=minute),
        args=[client],
        name='Daily Indexer',
        misfire_grace_time=600 # Wait up to 10 minutes if job is missed
    )
    print(f"⏰ Daily Indexing scheduled for {hour:02d}:{minute:02d} UTC everyday.")

# ===================================================================
# END OF SCHEDULER CODE
# ===================================================================

botStartTime = time.time()
ppath = "plugins/*.py"
files = glob.glob(ppath)

async def dreamxbotz_start():
    print('\n\nInitalizing DreamxBotz')
    await dreamxbotz.start()
    
    # ===============================================================
    # NEW CODE: START SCHEDULER AND SET DEFAULT INDEX TIME
    # ===============================================================
    #scheduler.start()
    # Schedule a default time for the daily index (e.g., 03:00 AM UTC)
    #schedule_daily_index(dreamxbotz, hour=3, minute=0)
    # ===============================================================
    
    bot_info = await dreamxbotz.get_me()
    dreamxbotz.username = bot_info.username
    await initialize_clients()
    for name in files:
        with open(name) as a:
            patt = Path(a.name)
            plugin_name = patt.stem.replace(".py", "")
            plugins_dir = Path(f"plugins/{plugin_name}.py")
            import_path = "plugins.{}".format(plugin_name)
            spec = importlib.util.spec_from_file_location(import_path, plugins_dir)
            load = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(load)
            sys.modules["plugins." + plugin_name] = load
            print("DreamxBotz Imported => " + plugin_name)
    if ON_HEROKU:
        asyncio.create_task(ping_server())  
    b_users, b_chats = await db.get_banned()
    temp.BANNED_USERS = b_users
    temp.BANNED_CHATS = b_chats
    await Media.ensure_indexes()
    if MULTIPLE_DB:
        await Media2.ensure_indexes()
        print("Multiple Database Mode On. Now Files Will Be Save In Second DB If First DB Is Full")
    else:
        print("Single DB Mode On ! Files Will Be Save In First Database")
    me = await dreamxbotz.get_me()
    temp.ME = me.id
    temp.U_NAME = me.username
    temp.B_NAME = me.first_name
    temp.B_LINK = me.mention
    dreamxbotz.username = '@' + me.username
    dreamxbotz.loop.create_task(check_expired_premium(dreamxbotz))
    logging.info(f"{me.first_name} with Pyrogram v{__version__} (Layer {layer}) started on {me.username}.")
    logging.info(LOG_STR)
    logging.info(script.LOGO)
    tz = pytz.timezone('Asia/Kolkata')
    today = date.today()
    now = datetime.now(tz)
    time = now.strftime("%H:%M:%S %p")
    await dreamxbotz.send_message(chat_id=LOG_CHANNEL, text=script.RESTART_TXT.format(temp.B_LINK, today, time))
    app = web.AppRunner(await web_server())
    await app.setup()
    bind_address = "0.0.0.0"
    await web.TCPSite(app, bind_address, PORT).start()
    dreamxbotz.loop.create_task(keep_alive())
    await idle()
    
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    while True:
        try:
            loop.run_until_complete(dreamxbotz_start())
            break 
        except FloodWait as e:
            print(f"FloodWait! Sleeping for {e.value} seconds.")
            time.sleep(e.value) 
        except KeyboardInterrupt:
            logging.info('Service Stopped Bye 👋')
            break
