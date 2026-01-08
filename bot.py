import os
import asyncio
from openai import OpenAI

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TELEGRAM_LIMIT = 4096  # лимит символов в одном сообщении Telegram


def load_system_prompt(path: str = "system_prompt.txt") -> str:
    """Читаем твой большой системный промпт из файла."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def split_telegram(text: str, limit: int = TELEGRAM_LIMIT):
    """Режем длинный текст на куски, чтобы влезать в ограничение Telegram."""
    text = text.strip()
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        chunk = text[:limit]
        cut = chunk.rfind("\n")
        if cut > limit * 0.6:
            chunk = chunk[:cut]
        chunks.append(chunk)
        text = text[len(chunk):].lstrip()
    return chunks


# Клиент OpenAI (ключ берётся из переменной окружения OPENAI_API_KEY)
client = OpenAI()
SYSTEM_PROMPT = load_system_prompt()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    await update.message.reply_text(
        "Hi! My name is Dicky. I'm your English assistant and cat (obviously).\n"
        "Send me a new word or a phrase and I will translate it for you.\n"
        "I was created by @senatorous, send him my best regards by the way.\n"
    )


def build_user_input(word: str) -> str:
    """Как мы формируем вход для модели по твоему слову."""
    return f"Слово/фраза: {word}"


def call_openai(word: str) -> str:
    """Синхронный вызов OpenAI API — будем запускать его в отдельном потоке."""
    # если OPENAI_MODEL не задан, берём gpt-4.1-mini
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,  # твой большой системный промпт из файла
        input=build_user_input(word),
        max_output_tokens=600,
    )

    # Берём готовый текстовый ответ
    return (response.output_text or "").strip()


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатываем любое текстовое сообщение (кроме команд)."""
    user_text = (update.message.text or "").strip()
    print("Пришло сообщение в Telegram:", user_text)

    if not user_text:
        return

    if len(user_text) > 80:
        await update.message.reply_text(
            "Too long, lad! I'm just a cat. Send me a word or phrase less than 80 characters."
        )
        return

    # Показываем "печатает..."
    await update.message.chat.send_action(action="typing")

    try:
        # Вызов OpenAI запускаем в отдельном потоке, чтобы не блокировать бота
        answer = await asyncio.to_thread(call_openai, user_text)

        if not answer:
            answer = "Got an empty answer from model. Sad. Try another word."

        # Режем ответ по кускам, если он длинный
        for chunk in split_telegram(answer):
            await update.message.reply_text(chunk)

    except Exception as e:
        # Логируем ошибку в консоль и отправляем пользователю
        print("Ошибка при вызове OpenAI:", repr(e))
        await update.message.reply_text(
            f"Oops, an error: {type(e).__name__}: {e}"
        )


def main():
    # Читаем токен Telegram из переменной окружения
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not tg_token:
        raise RuntimeError(
            "Не найден TELEGRAM_BOT_TOKEN. "
            "Задай его командой: export TELEGRAM_BOT_TOKEN='твой_токен'"
        )

    app = ApplicationBuilder().token(tg_token).build()

    # Обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Бот запущен. Жду сообщения в Telegram...")
    app.run_polling()


if __name__ == "__main__":
    main()
