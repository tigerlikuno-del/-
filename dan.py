
import os
import logging
import asyncio
import aiohttp

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BufferedInputFile
)
from dotenv import load_dotenv

load_dotenv()

# Настройки
BOT_TOKEN = os.getenv("9078191852:AAEPnx4WthU4nr5RcUfuzB6BBcf-gg_DsEU")

if not BOT_TOKEN:
    raise RuntimeError("Не указан BOT_TOKEN!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# Хранилище
track_cache = {}
favorites = {}

logging.basicConfig(level=logging.INFO)


# Главное меню
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔎 Поиск музыки")],
            [KeyboardButton(text="⭐ Избранное"),
             KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True
    )


# Поиск музыки
async def search_music(query):
    url = "https://itunes.apple.com/search"

    params = {
        "term": query,
        "entity": "song",
        "limit": 8,
        "country": "US"
    }

    timeout = aiohttp.ClientTimeout(total=20)

    async with aiohttp.ClientSession(
        timeout=timeout
    ) as session:

        async with session.get(
            url, params=params
        ) as response:

            response.raise_for_status()
            data = await response.json()

            return data.get("results", [])


# Клавиатура трека
def track_keyboard(track_id, has_preview):
    buttons = []

    if has_preview:
        buttons.append([
            InlineKeyboardButton(
                text="🎧 Слушать фрагмент",
                callback_data=f"play:{track_id}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="⭐ В избранное",
            callback_data=f"fav:{track_id}"
        )
    ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


# Отправка результатов
async def show_results(message, query):
    status = await message.answer("🔎 Ищу музыку...")

    try:
        results = await search_music(query)

        await status.delete()

        if not results:
            await message.answer(
                "😕 Ничего не найдено. Попробуй другое название."
            )
            return

        await message.answer(
            f"🎵 Найдено треков: {len(results)}"
        )

        for track in results:
            track_id = str(track["trackId"])
            track_cache[track_id] = track

            title = track.get("trackName", "Без названия")
            artist = track.get("artistName", "Неизвестный исполнитель")
            album = track.get("collectionName", "Неизвестный альбом")
            preview = track.get("previewUrl")

            text = (
                f"🎵 {title}\n"
                f"👤 Исполнитель: {artist}\n"
                f"💿 Альбом: {album}\n"
            )

            if track.get("trackViewUrl"):
                text += f"\n🔗 {track['trackViewUrl']}"

            await message.answer(
                text,
                reply_markup=track_keyboard(
                    track_id,
                    bool(preview)
                )
            )

    except Exception:
        logging.exception("Ошибка поиска")

        try:
            await status.edit_text(
                "⚠️ Ошибка поиска. Попробуй позже."
            )
        except Exception:
            await message.answer("⚠️ Ошибка поиска.")


# Старт
@router.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🎵 Добро пожаловать в Music Bot!\n\n"
        "Здесь ты можешь искать музыку "
        "и слушать ознакомительные фрагменты.\n\n"
        "Выбирай действие в меню 👇",
        reply_markup=main_menu()
    )


# Помощь
@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def help_command(message: Message):
    await message.answer(
        "🎵 MUSIC BOT\n\n"
        "🔎 Поиск — найти песню\n"
        "🎧 Слушать — получить аудиофрагмент\n"
        "⭐ Избранное — сохранить любимые треки\n\n"
        "Команды:\n"
        "/start — главное меню\n"
        "/search название — поиск\n"
        "/favorites — избранное",
        reply_markup=main_menu()
    )


# Команда поиска
@router.message(Command("search"))
async def search_command(message: Message):
    query = message.text.partition(" ")[2].strip()

    if not query:
        await message.answer(
            "Напиши название песни:\n/search Believer"
        )
        return

    await show_results(message, query)


# Кнопка поиска
@router.message(F.text == "🔎 Поиск музыки")
async def search_button(message: Message):
    await message.answer(
        "🔎 Напиши название песни или исполнителя."
    )


# Поиск обычным текстом
@router.message(F.text)
async def text_search(message: Message):
    query = message.text.strip()

    if query in ["⭐ Избранное", "🔎 Поиск музыки", "ℹ️ Помощь"]:
        return

    await show_results(message, query)


# Прослушивание фрагмента
@router.callback_query(F.data.startswith("play:"))
async def play_track(callback: CallbackQuery):
    track_id = callback.data.split(":")[1]
    track = track_cache.get(track_id)

    if not track:
        await callback.answer("Трек не найден.", show_alert=True)
        return

    preview_url = track.get("previewUrl")

    if not preview_url:
        await callback.answer(
            "Фрагмент недоступен.",
            show_alert=True
        )
        return

    await callback.answer("Загружаю музыку...")

    try:
        timeout = aiohttp.ClientTimeout(total=40)

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.get(preview_url) as response:
                response.raise_for_status()

                audio_data = await response.read()

        if len(audio_data) > 10 * 1024 * 1024:
            await callback.message.answer(
                "Файл слишком большой."
            )
            return

        audio = BufferedInputFile(
            audio_data,
            filename="music_preview.m4a"
        )

        await callback.message.answer_audio(
            audio=audio,
            title=track.get("trackName", "Music"),
            performer=track.get("artistName", "Unknown")
        )

    except Exception:
        logging.exception("Ошибка загрузки аудио")

        await callback.message.answer(
            "⚠️ Не удалось загрузить фрагмент."
        )


# Добавление в избранное
@router.callback_query(F.data.startswith("fav:"))
async def add_favorite(callback: CallbackQuery):
    track_id = callback.data.split(":")[1]
    track = track_cache.get(track_id)

    if not track:
        await callback.answer("Трек не найден.")
        return

    user_id = callback.from_user.id

    user_favorites = favorites.setdefault(
        user_id, {}
    )

    if track_id in user_favorites:
        del user_favorites[track_id]
        await callback.answer("Удалено из избранного.")
    else:
        user_favorites[track_id] = track
        await callback.answer("⭐ Добавлено в избранное!")


# Избранное
@router.message(Command("favorites"))
@router.message(F.text == "⭐ Избранное")
async def show_favorites(message: Message):
    user_favorites = favorites.get(
        message.from_user.id, {}
    )

    if not user_favorites:
        await message.answer(
            "⭐ У тебя пока нет избранных треков."
        )
        return

    await message.answer("⭐ Твоё избранное:")

    for track_id, track in user_favorites.items():
        title = track.get("trackName", "Unknown")
        artist = track.get("artistName", "Unknown")

        await message.answer(
            f"🎵 {title}\n"
            f"👤 {artist}",
            reply_markup=track_keyboard(
                track_id,
                bool(track.get("previewUrl"))
            )
        )


# Запуск
async def main():
    dp.include_router(router)

    print("🎵 MUSIC BOT STARTED!")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
