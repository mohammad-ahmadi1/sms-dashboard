import os
import socket
import ipaddress
from urllib.parse import urlparse
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from .multipart import assemble_inbox_rows
MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📥 Last 10 Messages"), KeyboardButton("📥 Last 20 Messages")],
        [KeyboardButton("📊 Dashboard"), KeyboardButton("❓ Help")]
    ],
    resize_keyboard=True
)

async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Please choose an option:", reply_markup=MENU_KEYBOARD
    )

async def handle_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text
    if text == "📥 Last 10 Messages":
        await cmd_last10(update, context)
    elif text == "📥 Last 20 Messages":
        await cmd_last20(update, context)
    elif text == "📊 Dashboard":
        app_url = os.environ.get("APP_PUBLIC_URL", "http://127.0.0.1:5000")
        await update.effective_message.reply_text(f"Dashboard: {app_url}")
    elif text == "❓ Help":
        await update.effective_message.reply_text(
            "Available commands:\n/menu - Show menu\n/last10 - Last 10 messages\n/last20 - Last 20 messages\n/start - Bot info"
        )
    else:
        await update.effective_message.reply_text("Unknown option. Use /menu to see available actions.")
async def cmd_last20(update: Update, context: ContextTypes.DEFAULT_TYPE):
    messages = fetch_last_messages(20)
    if not messages:
        await update.effective_message.reply_text("No recent messages found.")
        return
    reply = "\n\n".join([
        f"From: {m['SenderNumber']}\n{m['TextDecoded']}\nReceived: {m['ReceivingDateTime']}" for m in messages
    ])
    await update.effective_message.reply_text(reply)
import mysql.connector

# Load .env
load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# App context info (for verification)
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def get_db_connection():
    """Establishes a connection to the MySQL database."""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None

def fetch_last_messages(limit=5):
    """Fetch the last N messages from the inbox table, skipping empty messages."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT ID, SenderNumber, TextDecoded, ReceivingDateTime, Processed,
                   UDH
            FROM inbox
            ORDER BY ReceivingDateTime DESC
            LIMIT %s
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        # Assemble multipart messages and drop empty/blank rows
        messages = assemble_inbox_rows(rows)
    except mysql.connector.Error as err:
        print(f"Failed to fetch messages: {err}")
        messages = []
    finally:
        cursor.close()
        conn.close()
    return messages
async def cmd_last5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    messages = fetch_last_messages(5)
    if not messages:
        await update.effective_message.reply_text("No recent messages found.")
        return
    reply = "\n\n".join([
        f"From: {m['SenderNumber']}\n{m['TextDecoded']}\nReceived: {m['ReceivingDateTime']}" for m in messages
    ])
    await update.effective_message.reply_text(reply)

async def cmd_last10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    messages = fetch_last_messages(10)
    if not messages:
        await update.effective_message.reply_text("No recent messages found.")
        return
    reply = "\n\n".join([
        f"From: {m['SenderNumber']}\n{m['TextDecoded']}\nReceived: {m['ReceivingDateTime']}" for m in messages
    ])
    await update.effective_message.reply_text(reply)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    me = await bot.get_me()
    host = socket.gethostname()

    def get_server_ip() -> str:
        env_ip = os.environ.get('SERVER_IP')
        if env_ip:
            return env_ip
        app_url_env = os.environ.get('APP_PUBLIC_URL')
        if app_url_env:
            try:
                netloc = urlparse(app_url_env).hostname
                if netloc:
                    try:
                        return str(ipaddress.ip_address(netloc))
                    except ValueError:
                        pass
            except Exception:
                pass
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("1.1.1.1", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "unknown"

    ip = get_server_ip()
    env = os.environ.get("FLASK_ENV", "production")
    app_url = os.environ.get("APP_PUBLIC_URL", "http://127.0.0.1:5000")
    chat = update.effective_chat

    lines = [
        "✅ Welcome! You're connected to:",
        "",
        f"Bot: @{me.username} (id: {me.id})",
        f"Server: {host} ({ip})",
        f"Environment: {env}",
        f"Database: {DB_NAME or 'unknown'} @ {DB_HOST}",
        f"Dashboard: {app_url}",
        "",
        f"This chat id: {chat.id}",
        f"For menu, type /menu",
    ]
    if TELEGRAM_CHAT_ID:
        try:
            configured = int(TELEGRAM_CHAT_ID)
            status = "MATCH" if configured == chat.id else "DIFFERENT"
            lines.append(f"Configured TELEGRAM_CHAT_ID: {configured} ({status})")
        except Exception:
            lines.append(f"Configured TELEGRAM_CHAT_ID: {TELEGRAM_CHAT_ID}")

    await update.effective_message.reply_text("\n".join(lines))



def main():
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("last10", cmd_last10))
    app.add_handler(CommandHandler("last20", cmd_last20))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_choice))

    print("Starting Telegram bot (run_polling in main thread)...")
    app.run_polling(allowed_updates=["message", "chat_member", "my_chat_member"])


if __name__ == "__main__":
    main()
