import asyncio
import contextvars
import json
import os
import shutil
import requests
from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile, InlineQuery, InlineQueryResultArticle,
    InputTextMessageContent, LabeledPrice, PreCheckoutQuery,
    ChosenInlineResult, InputMediaAudio, Update,
)
from aiogram.filters import CommandStart, Command, CommandObject
import yt_dlp
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1
from urllib.parse import quote

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise SystemExit("Не задана переменная окружения BOT_TOKEN")
DEEZER_API = "https://api.deezer.com"
DONATE_CONTACT = "@neslle"

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

PAGE_SIZE = 8
cache = {}
donate_cache = {}
track_info = {}   # track_id -> (artist, title)
pending = {}      # (user_id, payload) -> inline_message_id
FFMPEG_PATH = shutil.which("ffmpeg") or "/data/data/com.termux/files/usr/bin/ffmpeg"
BOT_USERNAME = None  # заполним при старте

# ============ ПРЕМИУМ-ЭМОДЗИ ============
E_START    = '<tg-emoji emoji-id="5422780559233428036">🎵</tg-emoji>'
E_SEARCH   = '<tg-emoji emoji-id="5422665131987345081">🔍</tg-emoji>'
E_TRACKS   = '<tg-emoji emoji-id="5422560021252712616">🎶</tg-emoji>'
E_ARTIST   = '<tg-emoji emoji-id="5422806294677462598">🎤</tg-emoji>'
E_LOADING  = '<tg-emoji emoji-id="5424850415642518088">⏳</tg-emoji>'
E_SEND     = '<tg-emoji emoji-id="5355063643828406581">📤</tg-emoji>'
E_OK       = '<tg-emoji emoji-id="5355063643828406581">✅</tg-emoji>'
E_ERROR    = '<tg-emoji emoji-id="5269672809151354257">❌</tg-emoji>'
E_EMPTY    = '<tg-emoji emoji-id="5294527084813626369">🗑</tg-emoji>'
E_MP3      = '<tg-emoji emoji-id="5426986775325191607">🎧</tg-emoji>'
E_NOTE     = '<tg-emoji emoji-id="5353000169740717543">📝</tg-emoji>'
E_STAR     = '<tg-emoji emoji-id="5422780559233428036">⭐</tg-emoji>'

# ============ ЛАТИНИЦА ============
LAT1_LOWER = "𝔞𝔟𝔠𝔡𝔢𝔣𝔤𝔥𝔦𝔧𝔨𝔩𝔪𝔫𝔬𝔭𝔮𝔯𝔰𝔱𝔲𝔳𝔴𝔵𝔶𝔷"
LAT2_LOWER = "𝙖𝙗𝙘𝙙𝙚𝙛𝙜𝙝𝙞𝙟𝙠𝙡𝙢𝙣𝙤𝙥𝙦𝙧𝙨𝙩𝙪𝙫𝙬𝙭𝙮𝙯"
LAT3_LOWER = "𝒂𝒃𝒄𝒅𝒆𝒇𝒈𝒉𝒊𝒋𝒌𝒍𝒎𝒏𝒐𝒑𝒒𝒓𝒔𝒕𝒖𝒗𝒘𝒙𝒚𝒛"
LAT4_LOWER = "𝖆𝖇𝖈𝖉𝖊𝖋𝖌𝖍𝖎𝖏𝖐𝖑𝖒𝖓𝖔𝖕𝖖𝖗𝖘𝖙𝖚𝖛𝖜𝖝𝖞𝖟"
LAT1_UPPER = "𝔄𝔅ℭ𝔇𝔈𝔉𝔊ℌℑ𝔍𝔎𝔏𝔐𝔑𝔒𝔓𝔔ℜ𝔖𝔗𝔘𝔙𝔚𝔛𝔜ℨ"
LAT2_UPPER = "𝘼𝘽𝘾𝘿𝙀𝙁𝙂𝙃𝙄𝙅𝙆𝙇𝙈𝙉𝙊𝙋𝙌𝙍𝙎𝙏𝙐𝙑𝙒𝙓𝙔𝙕"
LAT3_UPPER = "𝑨𝑩𝑪𝑫𝑬𝑭𝑮𝑯𝑰𝑱𝑲𝑳𝑴𝑵𝑶𝑷𝑸𝑹𝑺𝑻𝑼𝑽𝑾𝑿𝒀𝒁"
LAT4_UPPER = "𝕬𝕭𝕮𝕯𝕰𝕱𝕲𝕳𝕴𝕵𝕶𝕷𝕸𝕹𝕺𝕻𝕼𝕽𝕾𝕿𝖀𝖁𝖂𝖃𝖄𝖅"

# ============ РУССКИЙ ============
RUS_LOWER = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
RUS_UPPER = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
ENG_LOWER = "abcdefghijklmnopqrstuvwxyz"
ENG_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

RU1_LOWER = "ᴀбʙᴦдᴇежзийᴋᴧʍноᴨᴩᴄᴛуɸхцчɯщъыь϶юя"
RU1_UPPER = "ᴀБВГДЕЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
RU2_LOWER = "α6βгдεεж3ийκлʍhøпρc†ψфχцчшщъыьэюя"
RU2_UPPER = "Α6ΒΓΔΕΕЖ3ИЙΚΛʍHØПΡC†ΨΦΧЦЧШЩЪЫЬЭЮЯ"
RU3_LOWER = "α6Bгдεεж3ийκлmH⊕пpςTψфxцчшщъыьэюя"
RU3_UPPER = "Α6ΒΓΔΕΕЖ3ИЙΚΛMH⊕ПPΣTΨΦXЦЧШЩЪЫЬЭЮЯ"
RU4_LOWER = "a6Bгдeeж3ийκлḿHőпṕćTӳфxцччшщъыьэюя"
RU4_UPPER = "A6BГДEEЖ3ИЙΚΛḾHŐПṔĆTӲФXЦЧЧШЩЪЫЬЭЮЯ"

def build_map(ru_lower, ru_upper, lat_lower, lat_upper):
    m = {}
    for i, k in enumerate(RUS_LOWER):
        if i < len(ru_lower):
            m[k] = ru_lower[i]
    for i, k in enumerate(RUS_UPPER):
        if i < len(ru_upper):
            m[k] = ru_upper[i]
    for i, k in enumerate(ENG_LOWER):
        if i < len(lat_lower):
            m[k] = lat_lower[i]
    for i, k in enumerate(ENG_UPPER):
        if i < len(lat_upper):
            m[k] = lat_upper[i]
    return m

STYLE_START  = build_map(RU1_LOWER, RU1_UPPER, LAT1_LOWER, LAT1_UPPER)
STYLE_TRACKS = build_map(RU2_LOWER, RU2_UPPER, LAT2_LOWER, LAT2_UPPER)
STYLE_STATUS = build_map(RU3_LOWER, RU3_UPPER, LAT3_LOWER, LAT3_UPPER)
STYLE_ERROR  = build_map(RU4_LOWER, RU4_UPPER, LAT4_LOWER, LAT4_UPPER)

# ============ ЯЗЫК ============
LANGS = ("ru", "en", "ar")
LANG_FILE = "langs.json"
current_lang = contextvars.ContextVar("current_lang", default="ru")
user_lang = {}          # user_id -> "ru" | "en" | "ar"
lang_pending_dl = {}    # user_id -> payload, если человек пришёл по ссылке до выбора языка

def _style(m, t):
    # арабский — без стилизации
    if current_lang.get() == "ar":
        return t
    return "".join(m.get(c, c) for c in t)

def s_start(t):  return _style(STYLE_START, t)
def s_tracks(t): return _style(STYLE_TRACKS, t)
def s_status(t): return _style(STYLE_STATUS, t)
def s_error(t):  return _style(STYLE_ERROR, t)

STRINGS = {
    "ru": {
        "start": "Пришли название песни или артиста",
        "support": "Поддержка бота: /donat",
        "lang_hint": "Сменить язык: /language",
        "donate_choose": "Выбери способ поддержки:",
        "donate_stars_btn": "Задонатить звёздами",
        "donate_other_btn": "Другая оплата",
        "donate_enter": "Введи сумму звёзд (целое число, например 50):",
        "donate_other_text": "Для других видов оплаты обратись к {c}",
        "min_star": "Минимум 1 звезда.",
        "invoice_label": "Поддержка бота",
        "invoice_title": "Поддержка бота ⭐",
        "invoice_desc": "Донат {n} звёзд",
        "thanks": "Спасибо! Ты задонатил {n} ⭐",
        "inline_hint": "Введи название песни или артиста",
        "inline_dl_line": "Скачать MP3 — напиши боту:",
        "inline_open": "Открыть бота →",
        "btn_download": "Скачать MP3",
        "downloading": "Скачиваю: {name}",
        "downloading_pct": "Скачиваю: {name} — {pct}%",
        "attempt": "Попытка {n}/{m}: {name}",
        "error": "Ошибка: {e}",
        "track_not_found": "Трек не найден",
        "sent_to_dm": "Трек отправлен в личку с ботом",
        "failed_retry": "Не удалось скачать, попробуй ещё раз",
        "too_short": "Слишком короткий запрос",
        "searching_dl": "Ищу и качаю трек",
        "sent_title": "Отправлено: {name}",
        "found_tracks": "Найденные треки",
        "found_artists": "Найденные артисты",
        "nothing": "Ничего не найдено",
        "session_expired": "Сессия устарела",
        "loading_short": "Качаю...",
        "loading_title": "Загружаю: {name}",
        "loading_tracks": "Загружаю треки...",
        "artist_no_tracks": "У артиста нет треков",
        "artist_tracks": "Треки: {name}",
        "track_word": "трек",
        "yt_nothing": "Ничего не найдено на YouTube",
    },
    "en": {
        "start": "Send a song or artist name",
        "support": "Support the bot: /donat",
        "lang_hint": "Change language: /language",
        "donate_choose": "Choose a way to support:",
        "donate_stars_btn": "Donate with Stars",
        "donate_other_btn": "Other payment",
        "donate_enter": "Enter the number of stars (whole number, e.g. 50):",
        "donate_other_text": "For other payment methods contact {c}",
        "min_star": "Minimum 1 star.",
        "invoice_label": "Bot support",
        "invoice_title": "Bot support ⭐",
        "invoice_desc": "Donation of {n} stars",
        "thanks": "Thank you! You donated {n} ⭐",
        "inline_hint": "Enter a song or artist name",
        "inline_dl_line": "Download MP3 — message the bot:",
        "inline_open": "Open the bot →",
        "btn_download": "Download MP3",
        "downloading": "Downloading: {name}",
        "downloading_pct": "Downloading: {name} — {pct}%",
        "attempt": "Attempt {n}/{m}: {name}",
        "error": "Error: {e}",
        "track_not_found": "Track not found",
        "sent_to_dm": "Track sent to your private chat with the bot",
        "failed_retry": "Download failed, please try again",
        "too_short": "Query is too short",
        "searching_dl": "Searching and downloading",
        "sent_title": "Sent: {name}",
        "found_tracks": "Tracks found",
        "found_artists": "Artists found",
        "nothing": "Nothing found",
        "session_expired": "Session expired",
        "loading_short": "Downloading...",
        "loading_title": "Loading: {name}",
        "loading_tracks": "Loading tracks...",
        "artist_no_tracks": "This artist has no tracks",
        "artist_tracks": "Tracks: {name}",
        "track_word": "track",
        "yt_nothing": "Nothing found on YouTube",
    },
    "ar": {
        "start": "أرسل اسم أغنية أو فنان",
        "support": "دعم البوت: /donat",
        "lang_hint": "تغيير اللغة: /language",
        "donate_choose": "اختر طريقة الدعم:",
        "donate_stars_btn": "تبرّع بالنجوم",
        "donate_other_btn": "طريقة دفع أخرى",
        "donate_enter": "أدخل عدد النجوم (عدد صحيح، مثلاً 50):",
        "donate_other_text": "لطرق الدفع الأخرى تواصل مع {c}",
        "min_star": "الحد الأدنى نجمة واحدة.",
        "invoice_label": "دعم البوت",
        "invoice_title": "دعم البوت ⭐",
        "invoice_desc": "تبرّع بـ {n} نجمة",
        "thanks": "شكرًا! لقد تبرّعت بـ {n} ⭐",
        "inline_hint": "أدخل اسم أغنية أو فنان",
        "inline_dl_line": "تنزيل MP3 — راسل البوت:",
        "inline_open": "افتح البوت ←",
        "btn_download": "تنزيل MP3",
        "downloading": "جارٍ التنزيل: {name}",
        "downloading_pct": "جارٍ التنزيل: {name} — {pct}%",
        "attempt": "المحاولة {n}/{m}: {name}",
        "error": "خطأ: {e}",
        "track_not_found": "المقطع غير موجود",
        "sent_to_dm": "تم إرسال المقطع في المحادثة الخاصة مع البوت",
        "failed_retry": "تعذّر التنزيل، حاول مرة أخرى",
        "too_short": "الطلب قصير جدًا",
        "searching_dl": "جارٍ البحث والتنزيل",
        "sent_title": "تم الإرسال: {name}",
        "found_tracks": "المقاطع التي تم العثور عليها",
        "found_artists": "الفنانون الذين تم العثور عليهم",
        "nothing": "لم يتم العثور على شيء",
        "session_expired": "انتهت الجلسة",
        "loading_short": "جارٍ التنزيل...",
        "loading_title": "جارٍ التحميل: {name}",
        "loading_tracks": "جارٍ تحميل المقاطع...",
        "artist_no_tracks": "لا توجد مقاطع لهذا الفنان",
        "artist_tracks": "مقاطع: {name}",
        "track_word": "المقطع",
        "yt_nothing": "لم يتم العثور على شيء على YouTube",
    },
}

LANG_PROMPT = "🌐 Выбери язык / Choose your language / اختر لغتك"

def tr(key, **kw):
    lang = current_lang.get()
    text = STRINGS.get(lang, STRINGS["ru"]).get(key) or STRINGS["ru"][key]
    return text.format(**kw) if kw else text

def load_langs():
    try:
        with open(LANG_FILE, encoding="utf-8") as f:
            for k, v in json.load(f).items():
                if v in LANGS:
                    user_lang[int(k)] = v
    except Exception:
        pass

def set_user_lang(uid, code):
    user_lang[uid] = code
    try:
        with open(LANG_FILE, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in user_lang.items()}, f)
    except Exception as e:
        print(f"Не удалось сохранить язык: {e}")

def default_lang(user):
    code = (getattr(user, "language_code", None) or "").lower()
    if code.startswith("ar"):
        return "ar"
    if code.startswith("en"):
        return "en"
    return "ru"

def _event_user(update):
    for attr in ("message", "edited_message", "callback_query", "inline_query",
                 "chosen_inline_result", "pre_checkout_query"):
        ev = getattr(update, attr, None)
        if ev is not None and getattr(ev, "from_user", None):
            return ev.from_user
    return None

class LangMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data):
        user = _event_user(event)
        lang = "ru"
        if user:
            lang = user_lang.get(user.id) or default_lang(user)
        token = current_lang.set(lang)
        try:
            return await handler(event, data)
        finally:
            current_lang.reset(token)

dp.update.outer_middleware(LangMiddleware())

def lang_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang|ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang|en")],
        [InlineKeyboardButton(text="🇸🇦 العربية", callback_data="lang|ar")],
    ])

# ============ DEEZER ============
def deezer_search_track(query):
    r = requests.get(f"{DEEZER_API}/search", params={"q": query}, timeout=15).json()
    return r.get("data", [])

def deezer_search_artist(query):
    r = requests.get(f"{DEEZER_API}/search/artist", params={"q": query}, timeout=15).json()
    return r.get("data", [])

def deezer_get_track(track_id):
    r = requests.get(f"{DEEZER_API}/track/{track_id}", timeout=15).json()
    if "error" in r:
        raise ValueError("track not found")
    return r

def deezer_artist_top(artist_id):
    r = requests.get(f"{DEEZER_API}/artist/{artist_id}/top", params={"limit": 50}, timeout=15).json()
    return r.get("data", [])

def build_kb(items, page, kind):
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    chunk = items[start:end]
    kb = []
    for i, item in enumerate(chunk):
        title = item["title"] if kind == "track" else item["name"]
        artist = item["artist"]["name"] if kind == "track" else ""
        label = f"{title} — {artist}" if artist else title
        kb.append([InlineKeyboardButton(text=s_tracks(label[:60]), callback_data=f"{kind}|{start+i}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"page|{page-1}"))
    if end < len(items):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"page|{page+1}"))
    if nav:
        kb.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ============ MP3 ============
def clean_mp3_tags(path, title, artist):
    try:
        audio = MP3(path, ID3=ID3)
        if audio.tags is not None:
            audio.delete()
        audio = MP3(path, ID3=ID3)
        if audio.tags is None:
            audio.add_tags()
        audio.tags.add(TIT2(encoding=3, text=s_tracks(title)))
        audio.tags.add(TPE1(encoding=3, text=s_tracks(artist)))
        audio.save()
    except Exception as e:
        print(f"Ошибка очистки тегов: {e}")

def safe_remove(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

def cleanup_user_files(uid):
    prefix = f"song_{uid}"
    for f in os.listdir("."):
        if f.startswith(prefix):
            safe_remove(f)

def download_mp3_sync(query, uid, title_hint=None, artist_hint=None, progress_hook=None):
    out_file = f"song_{uid}"

    def cleanup():
        for f in os.listdir("."):
            if f.startswith(out_file):
                try:
                    os.remove(f)
                except Exception:
                    pass

    cleanup()

    base_opts = {
        "quiet": True,
        "noplaylist": True,
        "source_address": "0.0.0.0",  # только IPv4 (лечит No route to host)
        "socket_timeout": 20,
        "retries": 5,
        "fragment_retries": 5,
    }
    # JS-рантайм для YouTube (если установлен node или deno)
    for rt in ("deno", "node"):
        if shutil.which(rt):
            base_opts["js_runtimes"] = {rt: {}}
            break

    # ищем несколько вариантов, чтобы при 403 попробовать следующий
    with yt_dlp.YoutubeDL({**base_opts, "extract_flat": True}) as ydl:
        res = ydl.extract_info(f"ytsearch5:{query}", download=False)
    entries = [e for e in (res.get("entries") or []) if e and e.get("url")]
    if not entries:
        raise RuntimeError(tr("yt_nothing"))

    ydl_opts = {
        **base_opts,
        "format": "bestaudio/best",
        "outtmpl": f"{out_file}.%(ext)s",
        "ffmpeg_location": FFMPEG_PATH,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "progress_hooks": [progress_hook] if progress_hook else [],
    }

    info = None
    last_err = None
    for e in entries[:4]:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(e["url"], download=True)
            break
        except Exception as err:
            last_err = err
            cleanup()
    if info is None:
        raise last_err

    final_title = title_hint or info.get("title", query)
    final_artist = artist_hint or info.get("uploader", "Unknown")
    path = f"{out_file}.mp3"
    clean_mp3_tags(path, final_title, final_artist)
    return path, s_tracks(final_title), s_tracks(final_artist)

async def safe_edit(msg, text):
    try:
        await msg.edit_text(text)
    except Exception:
        pass

def dl_markup(payload):
    url = f"https://t.me/{BOT_USERNAME}?start={quote(payload)}"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=tr("btn_download"),
            url=url,
            icon_custom_emoji_id="5426986775325191607"
        )
    ]])

async def safe_edit_inline(inline_id, text, markup=None):
    try:
        await bot.edit_message_text(
            text=text, inline_message_id=inline_id, reply_markup=markup
        )
    except Exception:
        pass

async def download_with_progress(query, uid, status_msg, title_hint=None, artist_hint=None,
                                 inline_id=None, inline_markup=None):
    loop = asyncio.get_event_loop()
    last_pct = {"v": -1}

    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            got = d.get("downloaded_bytes", 0)
            if total > 0:
                pct = int(got * 100 / total)
                if pct != last_pct["v"] and pct % 5 == 0:
                    last_pct["v"] = pct
                    name = title_hint or tr("track_word")
                    text = f"{E_LOADING} " + s_status(tr("downloading_pct", name=name, pct=pct))
                    asyncio.run_coroutine_threadsafe(safe_edit(status_msg, text), loop)
                    if inline_id:
                        asyncio.run_coroutine_threadsafe(
                            safe_edit_inline(inline_id, text, inline_markup), loop
                        )

    attempts = 3
    for attempt in range(1, attempts + 1):
        last_pct["v"] = -1
        try:
            path, name, artist_name = await asyncio.to_thread(
                download_mp3_sync, query, uid, title_hint, artist_hint, hook
            )
            return path, name, artist_name
        except Exception:
            cleanup_user_files(uid)
            if attempt == attempts:
                raise
            text = f"{E_LOADING} " + s_status(
                tr("attempt", n=attempt + 1, m=attempts,
                   name=title_hint or tr("track_word"))
            )
            await safe_edit(status_msg, text)
            if inline_id:
                await safe_edit_inline(inline_id, text, inline_markup)
            await asyncio.sleep(2)

# ============ /start ============
def start_text():
    return (
        f"{E_START} " + s_start(tr("start")) +
        "\n\n" + tr("support") + "\n" + tr("lang_hint")
    )

async def ask_language(msg: Message):
    await msg.answer(LANG_PROMPT, reply_markup=lang_kb())

async def handle_dl(msg: Message, uid: int, payload: str):
    """Обработка deep-link: /start dl_<id трека>"""
    if payload.startswith("dl_"):
        rest = payload[3:]
        if rest.isdigit():
            try:
                t = await asyncio.to_thread(deezer_get_track, rest)
                artist, title = t["artist"]["name"], t["title"]
            except Exception:
                await msg.answer(f"{E_ERROR} " + s_error(tr("track_not_found")))
                return
            query = f"{artist} {title}"
            wait = await msg.answer(f"{E_LOADING} " + s_status(tr("downloading", name=title)))
            imid = pending.get((uid, payload))
            markup = dl_markup(payload)
            if imid:
                await safe_edit_inline(
                    imid, f"{E_LOADING} " + s_status(tr("downloading", name=title)), markup
                )
            try:
                path, name, artist_name = await download_with_progress(
                    query, uid, wait, title, artist,
                    inline_id=imid, inline_markup=markup
                )
                try:
                    sent = await msg.answer_audio(FSInputFile(path), title=name, performer=artist_name)
                finally:
                    safe_remove(path)
                await safe_edit(
                    wait,
                    f"{E_OK} " + s_tracks(f"{title} — {artist}")
                )

                # заменяем сообщение в публичном чате на аудио
                pending.pop((uid, payload), None)
                if not imid:
                    print(f"Нет inline_message_id для {payload} (chosen_inline_result не пришёл?)")
                if imid:
                    try:
                        await bot.edit_message_media(
                            inline_message_id=imid,
                            media=InputMediaAudio(
                                media=sent.audio.file_id,
                                title=name,
                                performer=artist_name,
                            ),
                        )
                    except Exception as e:
                        print(f"Не удалось заменить inline-сообщение: {e}")
                        await safe_edit_inline(
                            imid, f"{E_OK} " + s_status(tr("sent_to_dm")), markup
                        )
            except Exception as e:
                await safe_edit(wait, f"{E_ERROR} " + s_error(tr("error", e=e)))
                if imid:
                    await safe_edit_inline(
                        imid, f"{E_ERROR} " + s_error(tr("failed_retry")), markup
                    )
            return

    await msg.answer(start_text())

@dp.message(CommandStart(deep_link=True))
async def start_deeplink(msg: Message, command: CommandObject):
    uid = msg.from_user.id
    payload = command.args or ""
    if uid not in user_lang:
        # самый первый запуск — сначала выбор языка
        if payload.startswith("dl_"):
            lang_pending_dl[uid] = payload
        await ask_language(msg)
        return
    await handle_dl(msg, uid, payload)

@dp.message(CommandStart())
async def start(msg: Message):
    if msg.from_user.id not in user_lang:
        await ask_language(msg)
        return
    await msg.answer(start_text())

@dp.message(Command("language"))
async def language_cmd(msg: Message):
    await ask_language(msg)

@dp.callback_query(F.data.startswith("lang|"))
async def set_language(cb: CallbackQuery):
    code = cb.data.split("|")[1]
    if code not in LANGS:
        await cb.answer()
        return
    uid = cb.from_user.id
    set_user_lang(uid, code)
    current_lang.set(code)
    await cb.message.edit_text(start_text())
    await cb.answer()
    payload = lang_pending_dl.pop(uid, None)
    if payload:
        await handle_dl(cb.message, uid, payload)

# ============ /donat ============
@dp.message(Command("donat"))
async def donat_cmd(msg: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=tr("donate_stars_btn"),
            callback_data="donate_stars",
            icon_custom_emoji_id="5422780559233428036"
        )],
        [InlineKeyboardButton(
            text=tr("donate_other_btn"),
            callback_data="donate_other",
            icon_custom_emoji_id="5353000169740717543"
        )],
    ])
    await msg.answer(tr("donate_choose"), reply_markup=kb)

@dp.callback_query(F.data == "donate_stars")
async def donate_stars(cb: CallbackQuery):
    uid = cb.from_user.id
    donate_cache[uid] = "await_sum"
    await cb.message.edit_text(
        f"{E_STAR} " + s_start(tr("donate_enter"))
    )
    await cb.answer()

@dp.callback_query(F.data == "donate_other")
async def donate_other(cb: CallbackQuery):
    await cb.message.edit_text(tr("donate_other_text", c=DONATE_CONTACT))
    await cb.answer()

@dp.message(F.text.regexp(r"^\d+$"))
async def handle_donate_sum(msg: Message):
    uid = msg.from_user.id
    if donate_cache.get(uid) != "await_sum":
        return
    amount = int(msg.text.strip())
    donate_cache.pop(uid, None)
    if amount < 1:
        await msg.answer(f"{E_ERROR} " + s_error(tr("min_star")))
        return
    prices = [LabeledPrice(label=tr("invoice_label"), amount=amount)]
    await bot.send_invoice(
        chat_id=msg.chat.id,
        title=tr("invoice_title"),
        description=tr("invoice_desc", n=amount),
        payload=f"donate_{uid}_{amount}",
        provider_token="",
        currency="XTR",
        prices=prices,
    )

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)

@dp.message(F.successful_payment)
async def on_paid(msg: Message):
    amount = msg.successful_payment.total_amount
    await msg.answer(f"{E_OK} " + s_start(tr("thanks", n=amount)))

# ============ INLINE MODE ============
@dp.inline_query()
async def inline_search(inline_query: InlineQuery):
    query = inline_query.query.strip()

    if not query:
        await inline_query.answer(
            results=[],
            cache_time=1,
            switch_pm_text=tr("inline_hint"),
            switch_pm_parameter="start",
        )
        return

    tracks = await asyncio.to_thread(deezer_search_track, query)
    results = []

    for t in tracks[:30]:
        title = t["title"]
        artist = t["artist"]["name"]
        label = s_tracks(f"{title} — {artist}")
        # deep-link с id трека
        dl_payload = f"dl_{t['id']}"
        dl_url = f"https://t.me/{BOT_USERNAME}?start={quote(dl_payload)}"

        msg_text = (
            f"{E_MP3} " + s_tracks(f"{title} — {artist}") + "\n\n"
            + s_tracks(tr("inline_dl_line")) + "\n"
            + s_tracks(tr("inline_open"))
        )

        results.append(
            InlineQueryResultArticle(
                id=str(t["id"]),
                title=label,
                description=f"{artist} • Deezer",
                input_message_content=InputTextMessageContent(
                    message_text=msg_text,
                    parse_mode="HTML",
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text=tr("btn_download"),
                        url=dl_url,
                        icon_custom_emoji_id="5426986775325191607"
                    )
                ]]),
            )
        )

    await inline_query.answer(
        results=results,
        cache_time=5,
        is_personal=True,
    )

@dp.chosen_inline_result()
async def on_chosen(res: ChosenInlineResult):
    print(f"chosen_inline_result: id={res.result_id}, inline_message_id={res.inline_message_id}")
    if not res.inline_message_id:
        return
    if len(pending) > 500:
        pending.pop(next(iter(pending)))
    pending[(res.from_user.id, f"dl_{res.result_id}")] = res.inline_message_id

# ============ ТЕКСТ ============
@dp.message(F.text)
async def handle_text(msg: Message):
    query = msg.text.strip()
    uid = msg.from_user.id

    if len(query) < 2:
        await msg.answer(f"{E_ERROR} " + s_error(tr("too_short")))
        return

    for sep in [" - ", " – ", " — "]:
        if sep in query:
            artist, title = query.split(sep, 1)
            wait = await msg.answer(f"{E_LOADING} " + s_status(tr("searching_dl")))
            try:
                path, name, artist_name = await download_with_progress(
                    f"{artist.strip()} {title.strip()}", uid, wait,
                    title.strip(), artist.strip()
                )
                try:
                    await msg.answer_audio(FSInputFile(path), title=name, performer=artist_name)
                finally:
                    safe_remove(path)
                await safe_edit(wait, f"{E_OK} " + s_status(tr("sent_title", name=title.strip())))
            except Exception as e:
                await safe_edit(wait, f"{E_ERROR} " + s_error(tr("error", e=e)))
            return

    tracks = await asyncio.to_thread(deezer_search_track, query)
    if tracks:
        cache[uid] = {"type": "track", "data": tracks, "page": 0}
        kb = build_kb(tracks, 0, "track")
        await msg.answer(f"{E_SEARCH} " + s_tracks(tr("found_tracks")), reply_markup=kb)
        return

    artists = await asyncio.to_thread(deezer_search_artist, query)
    if artists:
        cache[uid] = {"type": "artist", "data": artists, "page": 0}
        kb = build_kb(artists, 0, "artist")
        await msg.answer(f"{E_ARTIST} " + s_tracks(tr("found_artists")), reply_markup=kb)
        return

    await msg.answer(f"{E_EMPTY} " + s_error(tr("nothing")))

@dp.callback_query(F.data.startswith("page|"))
async def paginate(cb: CallbackQuery):
    uid = cb.from_user.id
    page = int(cb.data.split("|")[1])
    if uid not in cache:
        await cb.answer(s_error(tr("session_expired")))
        return
    cache[uid]["page"] = page
    items = cache[uid]["data"]
    kind = cache[uid]["type"]
    kb = build_kb(items, page, kind)
    await cb.message.edit_reply_markup(reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data.startswith("track|"))
async def pick_track(cb: CallbackQuery):
    uid = cb.from_user.id
    idx = int(cb.data.split("|")[1])
    if uid not in cache:
        await cb.answer(s_error(tr("session_expired")))
        return
    track = cache[uid]["data"][idx]
    query = f"{track['artist']['name']} {track['title']}"
    await cb.answer(s_status(tr("loading_short")))
    await cb.message.edit_text(f"{E_LOADING} " + s_status(tr("loading_title", name=track['title'])))
    try:
        path, name, artist_name = await download_with_progress(
            query, uid, cb.message,
            track["title"], track["artist"]["name"]
        )
        try:
            await cb.message.answer_audio(FSInputFile(path), title=name, performer=artist_name)
        finally:
            safe_remove(path)
        await safe_edit(cb.message, f"{E_OK} " + s_status(tr("sent_title", name=track['title'])))
    except Exception as e:
        await safe_edit(cb.message, f"{E_ERROR} " + s_error(tr("error", e=e)))

@dp.callback_query(F.data.startswith("artist|"))
async def pick_artist(cb: CallbackQuery):
    uid = cb.from_user.id
    idx = int(cb.data.split("|")[1])
    if uid not in cache:
        await cb.answer(s_error(tr("session_expired")))
        return
    artist = cache[uid]["data"][idx]
    await cb.answer(s_status(tr("loading_tracks")))
    top = await asyncio.to_thread(deezer_artist_top, artist["id"])
    if not top:
        await cb.message.edit_text(f"{E_EMPTY} " + s_error(tr("artist_no_tracks")))
        return
    cache[uid] = {"type": "track", "data": top, "page": 0}
    kb = build_kb(top, 0, "track")
    await cb.message.edit_text(f"{E_MP3} " + s_tracks(tr("artist_tracks", name=artist['name'])), reply_markup=kb)

async def main():
    global BOT_USERNAME
    load_langs()
    me = await bot.get_me()
    BOT_USERNAME = me.username
    print(f"Bot started: @{BOT_USERNAME}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
