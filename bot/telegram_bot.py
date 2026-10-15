"""Telegram-бот «Адал Кеңесші».

Бот — тонкий клиент: вопросы отправляет в наш HTTP API (/api/chat), как и сайт.
Ответ печатается «вживую» (сообщение редактируется по мере генерации).

Запуск (API должен быть запущен):  python -m bot.telegram_bot
"""
import asyncio
import html
import json
import logging
import random
import re
import time
from collections import defaultdict, deque

import httpx
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("tg")

router = Router()
QUIZ = json.loads((config.DATA_DIR / "quiz.json").read_text(encoding="utf-8"))
CONCEPTS = json.loads((config.DATA_DIR / "concepts.json").read_text(encoding="utf-8"))

user_lang: dict[int, str] = {}
history: dict[int, deque] = defaultdict(lambda: deque(maxlen=6))
busy: set[int] = set()
next_mode: dict[int, str] = {}   # режим для следующего сообщения: situation | factcheck
last_questions: dict[int, str] = {}

TEXT = {
    "ru": {
        "start": ("<b>Сәлеметсіз бе! Я — Адал Кеңесші 🇰🇿</b>\n\n"
                  "AI-навигатор по внутренней политике Казахстана. Отвечаю на вопросы о "
                  "<b>Конституции 2026 года</b>, Посланиях и выступлениях Главы государства, ценностях "
                  "«Адал азамат», «Закон и Порядок», «Таза Қазақстан» и др.\n\n"
                  "✅ Только по официальным документам\n🔗 Со ссылками на первоисточник\n"
                  "🛡 Если ответа нет в документах — честно скажу об этом\n\n"
                  "Просто напишите вопрос. Команды:\n"
                  "/situation — 🧭 что делать в моей ситуации (например, просят взятку)\n"
                  "/check — 🔎 проверить факт или новость по документам\n"
                  "/values — ценности, /quiz — викторина, /lang — язык."),
        "ask_situation": "🧭 Опишите вашу ситуацию одним сообщением. Например: «Сотрудник госоргана намекает, что справку выдадут быстрее за деньги».",
        "ask_check": "🔎 Пришлите утверждение или новость, которую нужно проверить по официальным документам.",
        "verdict": {"TRUE": "✅ Подтверждается документами", "FALSE": "❌ Не соответствует документам",
                    "PARTIAL": "⚠️ Частично верно или неточно", "UNKNOWN": "❓ Нет данных для проверки"},
        "thinking": "🔎 Ищу в официальных документах…",
        "sources": "Источники",
        "values": "Принципы и ценности внутренней политики (Указ № 1081). Выберите, чтобы узнать подробнее:",
        "quiz": "Вопрос викторины «Адал азамат» 👇 Ещё вопрос — /quiz",
        "voice": "🎙 Голосовые сообщения пока не поддерживаются в Telegram. Напишите вопрос текстом или используйте голосовой ввод на сайте.",
        "busy": "⏳ Подождите, я ещё отвечаю на предыдущий вопрос.",
        "lang": "Выберите язык / Тілді таңдаңыз:",
        "lang_set": "Язык: русский 🇷🇺",
        "thanks": "Спасибо за оценку!",
        "error": "⚠️ Сервис временно недоступен. Попробуйте позже.",
        "const": "📜 Ответ опирается на Конституцию 2026",
    },
    "kk": {
        "start": ("<b>Сәлеметсіз бе! Мен — Адал Кеңесші 🇰🇿</b>\n\n"
                  "Қазақстанның ішкі саясаты бойынша AI-навигатормын. <b>2026 жылғы Конституция</b>, "
                  "Мемлекет басшысының Жолдаулары мен сөздері, «Адал азамат», «Заң мен Тәртіп», "
                  "«Таза Қазақстан» құндылықтары туралы сұрақтарға жауап беремін.\n\n"
                  "✅ Тек ресми құжаттар негізінде\n🔗 Бастапқы дереккөзге сілтемемен\n"
                  "🛡 Құжаттарда жауап болмаса — ашық айтамын\n\n"
                  "Сұрағыңызды жазыңыз. Командалар:\n"
                  "/situation — 🧭 менің жағдайымда не істеу керек (мысалы, пара сұрап отыр)\n"
                  "/check — 🔎 фактіні немесе жаңалықты құжаттар бойынша тексеру\n"
                  "/values — құндылықтар, /quiz — викторина, /lang — тіл."),
        "ask_situation": "🧭 Жағдайыңызды бір хабарламамен сипаттаңыз. Мысалы: «Мемлекеттік қызметші анықтаманы ақшаға тез беретінін меңзеп отыр».",
        "ask_check": "🔎 Ресми құжаттар бойынша тексеру керек тұжырымды немесе жаңалықты жіберіңіз.",
        "verdict": {"TRUE": "✅ Құжаттармен расталады", "FALSE": "❌ Құжаттарға сәйкес келмейді",
                    "PARTIAL": "⚠️ Ішінара дұрыс немесе нақты емес", "UNKNOWN": "❓ Тексеруге дерек жоқ"},
        "thinking": "🔎 Ресми құжаттардан іздеп жатырмын…",
        "sources": "Дереккөздер",
        "values": "Ішкі саясаттың қағидаттары мен құндылықтары (№ 1081 Жарлық). Толығырақ білу үшін таңдаңыз:",
        "quiz": "«Адал азамат» викторинасының сұрағы 👇 Тағы сұрақ — /quiz",
        "voice": "🎙 Telegram-да дауыстық хабарламалар әзірге қолдау таппайды. Сұрақты мәтінмен жазыңыз немесе сайттағы дауыспен енгізуді пайдаланыңыз.",
        "busy": "⏳ Күте тұрыңыз, алдыңғы сұраққа жауап беріп жатырмын.",
        "lang": "Тілді таңдаңыз / Выберите язык:",
        "lang_set": "Тіл: қазақша 🇰🇿",
        "thanks": "Бағаңызға рахмет!",
        "error": "⚠️ Сервис уақытша қолжетімсіз. Кейінірек қайталап көріңіз.",
        "const": "📜 Жауап 2026 Конституциясына сүйенеді",
    },
}


def lang_of(uid: int, text: str = "") -> str:
    if uid in user_lang:
        return user_lang[uid]
    return "kk" if any(ch in "әғқңөұүһі" for ch in text.lower()) else "ru"


def md_to_tg(text: str) -> str:
    """Markdown от LLM → безопасный HTML, который понимает Telegram."""
    s = html.escape(text, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s, flags=re.S)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)
    s = re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", s, flags=re.M)
    s = re.sub(r"^\s*[-*]\s+", "• ", s, flags=re.M)
    return s[:3900]


def api_headers(uid: int) -> dict:
    return {"X-Internal-Token": config.ADMIN_TOKEN, "X-User-Id": str(uid)}


async def safe_edit(msg: Message, text: str, **kw) -> None:
    try:
        await msg.edit_text(text, disable_web_page_preview=True, **kw)
    except TelegramBadRequest as e:  # «message is not modified» и т.п.
        if "not modified" not in str(e):
            log.warning("edit failed: %s", e)


@router.message(CommandStart())
async def start(message: Message):
    uid = message.from_user.id
    if uid not in user_lang and message.from_user.language_code == "kk":
        user_lang[uid] = "kk"
    await message.answer(TEXT[lang_of(uid)]["start"])


@router.message(Command("lang"))
async def choose_lang(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="🇰🇿 Қазақша", callback_data="lang:kk")
    kb.button(text="🇷🇺 Русский", callback_data="lang:ru")
    await message.answer(TEXT["ru"]["lang"], reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("lang:"))
async def set_lang(cb: CallbackQuery):
    lang = cb.data.split(":")[1]
    user_lang[cb.from_user.id] = lang
    await cb.answer(TEXT[lang]["lang_set"])
    await cb.message.answer(TEXT[lang]["start"])


@router.message(Command("values"))
async def values(message: Message):
    lang = lang_of(message.from_user.id)
    kb = InlineKeyboardBuilder()
    for c in CONCEPTS:
        kb.button(text=f"{c['icon']} {c[lang]['name'][:40]}", callback_data=f"cv:{c['id']}")
    kb.adjust(1)
    await message.answer(TEXT[lang]["values"], reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("cv:"))
async def concept_clicked(cb: CallbackQuery):
    c = next((x for x in CONCEPTS if x["id"] == cb.data[3:]), None)
    await cb.answer()
    if c:
        await answer_question(cb.message, cb.from_user.id, c[lang_of(cb.from_user.id)]["question"])


@router.message(Command("situation", "check"))
async def set_mode(message: Message):
    lang = lang_of(message.from_user.id)
    cmd, _, rest = message.text.partition(" ")
    mode = "situation" if cmd.lstrip("/").startswith("situation") else "factcheck"
    if rest.strip():  # «/check текст» — сразу проверяем
        await answer_question(message, message.from_user.id, rest.strip(), mode)
        return
    next_mode[message.from_user.id] = mode
    await message.answer(TEXT[lang]["ask_situation" if mode == "situation" else "ask_check"])


@router.message(Command("quiz"))
async def quiz(message: Message):
    lang = lang_of(message.from_user.id)
    q = random.choice(QUIZ)
    L = q[lang]
    await message.answer(TEXT[lang]["quiz"])
    await message.answer_poll(
        question=L["question"][:300],
        options=[o[:100] for o in L["options"]],
        type="quiz",
        correct_option_id=q["answer"],
        explanation=L["explanation"][:200],
        is_anonymous=False,
    )


@router.message(F.voice | F.audio)
async def voice(message: Message):
    await message.answer(TEXT[lang_of(message.from_user.id)]["voice"])


@router.callback_query(F.data.startswith("fb:"))
async def feedback(cb: CallbackQuery):
    _, qid, val = cb.data.split(":")
    async with httpx.AsyncClient(base_url=config.API_URL, timeout=10) as client:
        try:
            await client.post("/api/feedback", json={"query_id": int(qid), "value": int(val)})
        except httpx.HTTPError:
            pass
    await cb.answer(TEXT[lang_of(cb.from_user.id)]["thanks"])
    await cb.message.edit_reply_markup(reply_markup=None)


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message):
    uid = message.from_user.id
    await answer_question(message, uid, message.text, next_mode.pop(uid, "ask"))


async def answer_question(message: Message, uid: int, question: str, mode: str = "ask"):
    lang = lang_of(uid, question)
    if uid in busy:
        await message.answer(TEXT[lang]["busy"])
        return
    busy.add(uid)
    reply = await message.answer(TEXT[lang]["thinking"])
    text, sources, done, error, verdict = "", [], None, None, None
    last_edit = 0.0
    try:
        async with httpx.AsyncClient(base_url=config.API_URL, timeout=httpx.Timeout(90, connect=5)) as client:
            payload = {"question": question, "history": list(history[uid]), "lang": lang, "mode": mode}
            async with client.stream("POST", "/api/chat", json=payload, headers=api_headers(uid)) as resp:
                if resp.status_code == 429:
                    error = (await resp.aread()).decode()
                    error = json.loads(error).get("error", TEXT[lang]["error"])
                else:
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        ev = json.loads(line[5:])
                        if ev["type"] == "sources":
                            sources = ev["sources"]
                        elif ev["type"] == "delta":
                            text += ev["text"]
                            if time.monotonic() - last_edit > 1.2:  # не чаще ~1 раза в секунду (лимиты Telegram)
                                last_edit = time.monotonic()
                                head = f"<b>{TEXT[lang]['verdict'][verdict]}</b>\n\n" if verdict else ""
                                await safe_edit(reply, head + md_to_tg(text) + " ▌")
                        elif ev["type"] == "replace":
                            text = ev["text"]
                            if not ev.get("keep_sources"):
                                sources = []
                        elif ev["type"] == "verdict":
                            verdict = ev["value"]
                        elif ev["type"] == "done":
                            done = ev
                        elif ev["type"] == "error":
                            error = ev["message"]
    except httpx.HTTPError as e:
        log.warning("API error: %s", e)
        error = TEXT[lang]["error"]
    finally:
        busy.discard(uid)

    if error:
        await safe_edit(reply, html.escape(error))
        return

    body = md_to_tg(text)
    if verdict:
        body = f"<b>{TEXT[lang]['verdict'][verdict]}</b>\n\n{body}"
    kb = InlineKeyboardBuilder()
    n_src = 0
    if done and done.get("answered"):
        cited = [s for s in sources if s["n"] in done["cited"]] or sources[:3]
        for s in cited[:5]:
            n_src += 1
            label = s["title"] if not s["article"] else (
                f"Конституция, ст. {s['article']}" if lang == "ru" else f"Конституция, {s['article']}-бап")
            kb.button(text=f"[{s['n']}] {label}"[:60], url=s["link"])
        if done.get("constitution"):
            body += f"\n\n<i>{TEXT[lang]['const']}</i>"
        history[uid].extend([{"role": "user", "content": question}, {"role": "assistant", "content": text}])
    if done:
        kb.button(text="👍", callback_data=f"fb:{done['query_id']}:1")
        kb.button(text="👎", callback_data=f"fb:{done['query_id']}:-1")
    kb.adjust(*([1] * n_src), 2)  # источники — по одному в строке, 👍👎 — рядом
    await safe_edit(reply, body, reply_markup=kb.as_markup())


async def main():
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("Укажите TELEGRAM_BOT_TOKEN в .env")
    bot = Bot(config.TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    log.info("Telegram-бот запущен, API: %s", config.API_URL)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
