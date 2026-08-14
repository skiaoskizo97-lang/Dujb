import asyncio
import html as html_mod
import os
import json
import re
import time
import urllib.parse
import hashlib
import zipfile
import io
from datetime import datetime
from pathlib import Path
import requests
from urllib3.exceptions import InsecureRequestWarning
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)

# ==================== CONFIGURATION ====================
OWNER_ID = 1249057893
CHANNEL_USERNAME = "@cookiesnetflix1"
CHANNEL_ID = None

from netflix_account import fetch_account_info_sync

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

BOT_DISPLAY_NAME = "Flexible X"
WAITING_FOR_FILE = 1
DEFAULT_LANG = "en"

# Referral System Config
REFERRAL_BONUS_PER_USER = 3
REFERRAL_MAX_DAILY_LIMIT = 50
BASE_DAILY_LIMIT = 24

# === RAILWAY VOLUME PATHS ===
VOLUME_ROOT = Path("/mnt/data")
ARCHIVE_ROOT = VOLUME_ROOT / "archive"
USERS_FILE = VOLUME_ROOT / "users.txt"
REFERRALS_FILE = VOLUME_ROOT / "referrals.json"
RATE_LIMITS_FILE = VOLUME_ROOT / "rate_limits.json"

# Netflix iOS API params
API_URL = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
QUERY_PARAMS = {
    "appVersion": "15.48.1",
    "config": '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false[...]