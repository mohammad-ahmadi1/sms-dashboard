import os
import socket
import ipaddress
from urllib.parse import urlparse
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from . import app
import mysql.connector

from .multipart import assemble_inbox_rows


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


def mark_message_as_read(message_id: int) -> bool:
    """Mark a specific message ID as read in the database."""
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        # Note: The column name is `Processed`, not `proceed`
        cursor.execute("UPDATE inbox SET Processed = 'true' WHERE ID = %s AND Processed = 'false'", (message_id,))
        conn.commit()
        return cursor.rowcount > 0
    except mysql.connector.Error as err:
        print(f"Error updating message: {err}")
        return False
    finally:
        cursor.close()
        conn.close()


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button clicks."""
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    action, _, message_id_str = query.data.partition('_')

    if action == 'read':
        try:
            message_id = int(message_id_str)
            if mark_message_as_read(message_id):
                # Edit the original message to remove the button
                await query.edit_message_text(
                    text=query.message.text + "\n\n---\n✅ Marked as Read",
                    reply_markup=None  # Remove keyboard
                )
                print(f"Marked message ID {message_id} as read.")
                app.remove_sent_ids([message_id])
            else:
                await query.edit_message_text(
                    text=query.message.text + "\n\n---\n⚠️ Already marked as read or error.",
                    reply_markup=None
                )
        except (ValueError, IndexError):
            await query.edit_message_text(
                text=query.message.text + "\n\n---\n❌ Error processing command.",
                reply_markup=None
            )


MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📥 Last 5 Messages"), KeyboardButton("📥 Last 10 Messages")],
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
    if text == "📥 Last 5 Messages":
        await cmd_last5(update, context)
    elif text == "📥 Last 10 Messages":
        await cmd_last10(update, context)
    elif text == "📊 Dashboard":
        app_url = os.environ.get("APP_PUBLIC_URL", "http://127.0.0.1:5000")
        await update.effective_message.reply_text(f"Dashboard: {app_url}")
    elif text == "❓ Help":
        await update.effective_message.reply_text(
            "Available commands:\n/menu - Show menu\n/last5 - Last 5 messages\n/last10 - Last 10 messages\n/start - Bot info"
        )
    else:
        await update.effective_message.reply_text("Unknown option. Use /menu to see available actions.")


def fetch_last_messages(limit=5):
    """Fetch the last N messages from the inbox table, skipping empty messages."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch unread messages first, then read ones, up to the limit
        cursor.execute(
            """
            (SELECT ID, SenderNumber, TextDecoded, ReceivingDateTime, Processed, UDH
            FROM inbox
            WHERE TextDecoded IS NOT NULL AND TextDecoded != ''
            ORDER BY ReceivingDateTime DESC)
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


async def send_messages_with_button(update: Update, context: ContextTypes.DEFAULT_TYPE, limit: int):
    """Helper to fetch and send messages with a 'Mark as Read' button."""
    messages = fetch_last_messages(limit)
    if not messages:
        await update.effective_message.reply_text("No recent messages found.")
        return

    for m in reversed(messages):
        status = "✅" if m['Processed'] == 'true' else "🆕"
        text = f"{status} From: {m['SenderNumber']}\n{m['TextDecoded']}\nReceived: {m['ReceivingDateTime']}"

        keyboard = None
        if m['Processed'] == 'false':
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Mark as Read", callback_data=f"read_{m['ID']}")]
            ])

        await update.effective_message.reply_text(text, reply_markup=keyboard)


async def cmd_last10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_messages_with_button(update, context, 10)


async def cmd_last5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_messages_with_button(update, context, 5)


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
    app.add_handler(CommandHandler("last5", cmd_last5))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_choice))

    print("Starting Telegram bot (run_polling in main thread)...")
    app.run_polling(allowed_updates=["message", "callback_query", "chat_member", "my_chat_member"])


if __name__ == "__main__":
    main()
