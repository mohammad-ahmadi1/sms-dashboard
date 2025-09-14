import os
import time
import threading
import socket
import ipaddress
from urllib.parse import urlparse
import json
import urllib.request
import urllib.parse
from dotenv import load_dotenv
import mysql.connector
from flask import Flask, render_template_string, redirect, url_for, flash, request
from .multipart import assemble_inbox_rows
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# Securely load credentials from environment variables
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASSWORD'),
    'database': os.environ.get('DB_NAME'),
}

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# --- Flask Application ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-default') # Used for flashing messages

# Securely set SECRET_KEY: require in production, allow default in development
secret_key = os.environ.get('SECRET_KEY')
flask_env = os.environ.get('FLASK_ENV', 'production').lower()
if not secret_key:
    if flask_env == 'development':
        secret_key = 'dev-default'
        print("WARNING: Using default SECRET_KEY in development mode. Do not use in production!", flush=True)
    else:
        raise RuntimeError("SECRET_KEY environment variable must be set in production.")
app.config['SECRET_KEY'] = secret_key  # Used for flashing messages
# --- Database Connection ---
def get_db_connection():
    """Establishes a connection to the MySQL database."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None

# --- HTML Template ---
# This template uses Tailwind CSS and JavaScript for a modern, interactive UI.
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gammu SMS Manager</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.0/css/all.min.css" rel="stylesheet">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .message-card {
            animation: fadeIn 0.5s ease-out forwards;
        }
        .modal-overlay {
            transition: opacity 0.3s ease;
        }
        .modal-panel {
            transition: transform 0.3s ease, opacity 0.3s ease;
        }
    </style>
</head>
<body class="bg-gray-50 text-gray-800">

    <div class="container mx-auto p-4 sm:p-6 lg:p-8">
        <header class="mb-8 text-center">
            <h1 class="text-4xl md:text-5xl font-bold text-gray-900">SMS Inbox</h1>
            <p class="text-lg text-gray-500 mt-2">Manage messages from your Gammu database</p>
        </header>

        <!-- Flash Messages -->
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="mb-4 p-4 rounded-lg shadow-md {{ 'bg-green-100 text-green-800' if category == 'success' else 'bg-red-100 text-red-800' }}" role="alert">
                <i class="fas {{ 'fa-check-circle' if category == 'success' else 'fa-exclamation-triangle' }} mr-2"></i>{{ message }}
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        <form id="bulk-action-form" action="{{ url_for('bulk_action') }}" method="POST">
            <!-- Main Actions Header -->
            <div class="flex items-center justify-between bg-white p-4 rounded-lg shadow-sm mb-6 sticky top-4 z-10">
                <div class="flex items-center space-x-3">
                    <input type="checkbox" id="select-all" class="h-5 w-5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500">
                    <label for="select-all" class="text-gray-700 font-medium">Select All</label>
                </div>
                <a href="{{ url_for('index') }}" class="text-gray-500 hover:text-indigo-600 transition-colors duration-200" title="Refresh Messages">
                    <i class="fas fa-sync-alt fa-lg"></i>
                </a>
            </div>

            <!-- Messages Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pb-24">
                {% if messages %}
                    {% for message in messages %}
                    <div class="message-card bg-white rounded-xl shadow-lg p-6 flex flex-col justify-between border-l-4 {{ 'border-indigo-500' if message.Processed == 'false' else 'border-gray-200' }} hover:shadow-xl transition-shadow duration-300">
                        <div>
                            <div class="flex justify-between items-start mb-4">
                                <span class="font-bold text-xl text-gray-800">{{ message.SenderNumber }}</span>
                                <input type="checkbox" name="message_ids" value="{{ message.ID }}" class="message-checkbox h-5 w-5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500">
                            </div>
                            <p class="text-gray-600 mb-5 break-words">{{ message.TextDecoded }}</p>
                        </div>
                        <div class="border-t border-gray-100 pt-4">
                            <p class="text-xs text-gray-400 mb-4 text-left">{{ message.ReceivingDateTime.strftime('%B %d, %Y at %I:%M %p') }}</p>
                             <div class="flex justify-between items-center">
                                {% if message.Processed == 'false' %}
                                    <span class="text-xs bg-indigo-100 text-indigo-800 font-semibold py-1 px-3 rounded-full">Unread</span>
                                {% else %}
                                     <span class="text-xs bg-gray-100 text-gray-600 font-semibold py-1 px-3 rounded-full">Read</span>
                                {% endif %}
                                <div class="flex items-center space-x-3">
                                    <a href="{{ url_for('mark_as_read', message_id=message.ID) }}" class="text-gray-400 hover:text-green-500 transition-colors" title="Mark as Read">
                                        <i class="fas fa-check-circle fa-lg"></i>
                                    </a>
                                    <button type="button" onclick="showDeleteModal('{{ url_for('delete_message', message_id=message.ID) }}')" class="text-gray-400 hover:text-red-500 transition-colors" title="Delete Message">
                                        <i class="fas fa-trash-alt fa-lg"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="col-span-full text-center py-16 bg-white rounded-lg shadow-sm">
                         <i class="fas fa-inbox fa-4x text-gray-300 mb-4"></i>
                         <h2 class="text-2xl font-semibold text-gray-700">Inbox is Empty</h2>
                         <p class="text-gray-500 mt-1">New messages will appear here.</p>
                    </div>
                {% endif %}
            </div>

            <!-- Floating Action Bar -->
            <div id="floating-bar" class="hidden fixed bottom-0 left-0 right-0 bg-white/80 backdrop-blur-sm border-t border-gray-200 shadow-lg p-4 z-50 transition-transform duration-300 translate-y-full">
                <div class="container mx-auto flex justify-between items-center">
                    <span id="selection-count" class="font-semibold text-gray-700">0 items selected</span>
                    <div class="space-x-3">
                        <button type="submit" name="action" value="read" class="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-5 rounded-lg transition-colors shadow-sm hover:shadow-md">
                            <i class="fas fa-check-circle mr-2"></i>Mark as Read
                        </button>
                        <button type="button" onclick="showBulkDeleteModal()" class="bg-red-500 hover:bg-red-600 text-white font-bold py-2 px-5 rounded-lg transition-colors shadow-sm hover:shadow-md">
                            <i class="fas fa-trash-alt mr-2"></i>Delete
                        </button>
                    </div>
                </div>
            </div>
        </form>
    </div>

    <!-- Delete Confirmation Modal -->
    <div id="delete-modal" class="fixed inset-0 z-50 hidden items-center justify-center p-4">
        <div class="modal-overlay fixed inset-0 bg-black/50" onclick="hideDeleteModal()"></div>
        <div class="modal-panel bg-white rounded-lg shadow-xl p-6 w-full max-w-md transform scale-95 opacity-0">
            <div class="text-center">
                <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100">
                    <i class="fas fa-exclamation-triangle fa-xl text-red-600"></i>
                </div>
                <h3 class="text-lg leading-6 font-medium text-gray-900 mt-4">Delete Message(s)</h3>
                <div class="mt-2">
                    <p class="text-sm text-gray-500">Are you sure you want to delete the selected message(s)? This action cannot be undone.</p>
                </div>
            </div>
            <div class="mt-5 sm:mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3">
                <form id="delete-confirm-form" method="POST" action="">
                    <button type="submit" class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-600 text-base font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500">
                        Confirm Delete
                    </button>
                </form>
                <button type="button" onclick="hideDeleteModal()" class="w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
                    Cancel
                </button>
            </div>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function () {
            const selectAllCheckbox = document.getElementById('select-all');
            const messageCheckboxes = document.querySelectorAll('.message-checkbox');
            const floatingBar = document.getElementById('floating-bar');
            const selectionCount = document.getElementById('selection-count');
            const bulkActionForm = document.getElementById('bulk-action-form');
            const deleteModal = document.getElementById('delete-modal');
            const modalOverlay = deleteModal.querySelector('.modal-overlay');
            const modalPanel = deleteModal.querySelector('.modal-panel');
            const deleteConfirmForm = document.getElementById('delete-confirm-form');

            function updateFloatingBar() {
                const selectedCount = document.querySelectorAll('.message-checkbox:checked').length;
                if (selectedCount > 0) {
                    floatingBar.classList.remove('hidden');
                    floatingBar.classList.remove('translate-y-full');
                    selectionCount.textContent = `${selectedCount} item${selectedCount > 1 ? 's' : ''} selected`;
                } else {
                    floatingBar.classList.add('translate-y-full');
                }
            }

            selectAllCheckbox.addEventListener('change', function () {
                messageCheckboxes.forEach(checkbox => {
                    checkbox.checked = selectAllCheckbox.checked;
                });
                updateFloatingBar();
            });

            messageCheckboxes.forEach(checkbox => {
                checkbox.addEventListener('change', function () {
                    selectAllCheckbox.checked = (document.querySelectorAll('.message-checkbox:checked').length === messageCheckboxes.length);
                    updateFloatingBar();
                });
            });

            window.showDeleteModal = function(deleteUrl) {
                deleteConfirmForm.action = deleteUrl;
                deleteModal.classList.remove('hidden');
                deleteModal.classList.add('flex');
                setTimeout(() => {
                    modalOverlay.classList.remove('opacity-0');
                    modalPanel.classList.remove('opacity-0', 'scale-95');
                }, 10);
            }

            window.hideDeleteModal = function() {
                modalOverlay.classList.add('opacity-0');
                modalPanel.classList.add('opacity-0', 'scale-95');
                setTimeout(() => {
                    deleteModal.classList.add('hidden');
                    deleteModal.classList.remove('flex');
                }, 300);
            }
            
            window.showBulkDeleteModal = function() {
                // Set form to submit with 'delete' action, then show modal
                const hiddenInputAction = document.createElement('input');
                hiddenInputAction.type = 'hidden';
                hiddenInputAction.name = 'action';
                hiddenInputAction.value = 'delete';
                
                // Remove any existing hidden action input to avoid duplicates
                const existingInput = bulkActionForm.querySelector('input[name="action"]');
                if(existingInput) existingInput.remove();

                bulkActionForm.appendChild(hiddenInputAction);
                
                // The modal's confirm button will now submit the main form
                deleteConfirmForm.action = 'javascript:document.getElementById("bulk-action-form").submit()';
                
                deleteModal.classList.remove('hidden');
                deleteModal.classList.add('flex');
                 setTimeout(() => {
                    modalOverlay.classList.remove('opacity-0');
                    modalPanel.classList.remove('opacity-0', 'scale-95');
                }, 10);
            }

            updateFloatingBar();
        });
    </script>
</body>
</html>
"""

# --- App Routes ---

@app.route('/')
def index():
    """Main page, displays all messages from the inbox."""
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed. Check console for errors.", "error")
        return render_template_string(HTML_TEMPLATE, messages=[])

    cursor = conn.cursor(dictionary=True)
    try:
        # Include UDH and SequencePosition to support multipart assembly when available
        cursor.execute("""
            SELECT ID, SenderNumber, TextDecoded, ReceivingDateTime, Processed,
                   UDH
            FROM inbox
            ORDER BY ReceivingDateTime DESC
        """)
        raw_messages = cursor.fetchall()
        # Assemble multipart messages and drop empty/blank rows
        messages = assemble_inbox_rows(raw_messages)
    except mysql.connector.Error as err:
        flash(f"Failed to fetch messages: {err}", "error")
        messages = []
    finally:
        cursor.close()
        conn.close()

    return render_template_string(HTML_TEMPLATE, messages=messages)

@app.route('/read/<int:message_id>')
def mark_as_read(message_id):
    """Marks a single message as read."""
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "error")
        return redirect(url_for('index'))

    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE inbox SET Processed = 'true' WHERE ID = %s", (message_id,))
        conn.commit()
        flash("Message marked as read.", "success")
    except mysql.connector.Error as err:
        flash(f"Error updating message: {err}", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('index'))

@app.route('/delete/<int:message_id>', methods=['POST'])
def delete_message(message_id):
    """Deletes a single message."""
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "error")
        return redirect(url_for('index'))

    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM inbox WHERE ID = %s", (message_id,))
        conn.commit()
        flash("Message deleted successfully.", "success")
    except mysql.connector.Error as err:
        flash(f"Error deleting message: {err}", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('index'))

@app.route('/bulk_action', methods=['POST'])
def bulk_action():
    """Handles bulk actions (delete, mark as read) on selected messages."""
    action = request.form.get('action')
    message_ids = request.form.getlist('message_ids')

    if not action or not message_ids:
        flash("No action or no messages selected.", "error")
        return redirect(url_for('index'))

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "error")
        return redirect(url_for('index'))

    cursor = conn.cursor()
    try:
        placeholders = ', '.join(['%s'] * len(message_ids))
        
        if action == 'read':
            query = f"UPDATE inbox SET Processed = 'true' WHERE ID IN ({placeholders})"
            cursor.execute(query, tuple(message_ids))
            flash(f"{cursor.rowcount} message(s) marked as read.", "success")
        elif action == 'delete':
            query = f"DELETE FROM inbox WHERE ID IN ({placeholders})"
            cursor.execute(query, tuple(message_ids))
            flash(f"{cursor.rowcount} message(s) deleted.", "success")
        
        conn.commit()

    except mysql.connector.Error as err:
        flash(f"An error occurred: {err}", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('index'))


# --- Telegram Bot ---
def _http_send_telegram_message(token: str, chat_id: str, text: str, parse_mode: str | None = None, reply_markup: dict | None = None):
    """Send a message via Telegram Bot API using standard library (no extra deps)."""
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(api_url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                print(f"Telegram API non-200: {resp.status}")
    except Exception as e:
        print(f"Telegram sendMessage error: {e}")

def send_message_to_telegram(message):
    """Sends a formatted message to a Telegram chat for new SMS notifications."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return  # Silently fail if not configured

    try:
        text = (
            f"New SMS from: {message['SenderNumber']}\n\n"
            f"{message['TextDecoded']}\n\n"
            f"Received: {message['ReceivingDateTime'].strftime('%B %d, %Y at %I:%M %p')}"
        )
        
        # Create an inline keyboard with a "Mark as Read" button
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "Mark as Read", "callback_data": f"read_{message['ID']}"}
                ]
            ]
        }

        _http_send_telegram_message(
            TELEGRAM_BOT_TOKEN,
            TELEGRAM_CHAT_ID,
            text,
            reply_markup=keyboard
        )
        print(f"Sent message to Telegram for SMS ID {message['ID']}")
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")


async def _start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with a helpful welcome & verification info."""
    try:
        bot = context.bot
        me = await bot.get_me()
        host = socket.gethostname()
        
        def get_server_ip() -> str:
            # 1) Explicit env override
            env_ip = os.environ.get('SERVER_IP')
            if env_ip:
                return env_ip
            # 2) APP_PUBLIC_URL netloc if it's an IP
            app_url = os.environ.get('APP_PUBLIC_URL')
            if app_url:
                try:
                    netloc = urlparse(app_url).hostname
                    if netloc:
                        try:
                            return str(ipaddress.ip_address(netloc))
                        except ValueError:
                            pass
                except Exception:
                    pass
            # 3) UDP socket trick to infer outbound interface IP (LAN)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("1.1.1.1", 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except Exception:
                return "unknown"

        ip = get_server_ip()
        env = os.environ.get('FLASK_ENV', 'production')
        db_host = DB_CONFIG.get('host') or 'unknown'
        db_name = DB_CONFIG.get('database') or 'unknown'
        app_url = os.environ.get('APP_PUBLIC_URL', 'http://127.0.0.1:5000')
        chat = update.effective_chat

        lines = [
            "✅ Bot is alive and ready!",
            "",
            f"Bot: @{me.username} (id: {me.id})",
            f"Server: {host} ({ip})",
            f"Environment: {env}",
            f"Database: {db_name} @ {db_host}",
            f"Dashboard: {app_url}",
            "",
            f"Current chat id: {chat.id}",
        ]
        # If a specific chat id is configured, hint whether we match it
        if TELEGRAM_CHAT_ID:
            try:
                configured = int(TELEGRAM_CHAT_ID)
                status = "MATCH" if configured == chat.id else "DIFFERENT"
                lines.append(f"Configured TELEGRAM_CHAT_ID: {configured} ({status})")
            except Exception:
                lines.append(f"Configured TELEGRAM_CHAT_ID: {TELEGRAM_CHAT_ID}")

        await update.effective_message.reply_text("\n".join(lines))
    except Exception as e:
        # Avoid crashing the handler
        print(f"/start handler error: {e}")

def _start_telegram_bot_background():
    """Run python-telegram-bot Application in a background thread with /start."""
    if not TELEGRAM_BOT_TOKEN:
        return

    def _runner():
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", _start_command))

        # Send a startup ping via HTTP helper (works outside event loop)
        if TELEGRAM_CHAT_ID:
            try:
                host = socket.gethostname()
                try:
                    ip = socket.gethostbyname(host)
                except Exception:
                    ip = "unknown"
                env = os.environ.get('FLASK_ENV', 'production')
                app_url = os.environ.get('APP_PUBLIC_URL', 'http://127.0.0.1:5000')
                text = (
                    "🚀 Bot started successfully\n\n"
                    f"Server: {host} ({ip})\n"
                    f"Environment: {env}\n"
                    f"Dashboard: {app_url}"
                )
                _http_send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, text)
            except Exception as e:
                print(f"Startup ping failed: {e}")

        print("Starting Telegram bot polling...")
        # Disable signal handlers since we're not in main thread
        try:
            app.run_polling(
                allowed_updates=["message", "chat_member", "my_chat_member"],
                stop_signals=()
            )
        except TypeError:
            # Older PTB: use close_loop=False to reduce signal handling
            app.run_polling(allowed_updates=["message", "chat_member", "my_chat_member"], close_loop=False)

    th = threading.Thread(target=_runner, daemon=True, name="telegram-bot")
    th.start()

def remove_sent_ids(ids_to_remove):
    """Removes specified IDs from the sent IDs cache file."""
    SENT_IDS_FILE = os.path.join(os.path.dirname(__file__), "message_ids.txt")
    try:
        if os.path.exists(SENT_IDS_FILE):
            with open(SENT_IDS_FILE, "r") as f:
                all_ids = [line.strip() for line in f if line.strip().isdigit()]
            # Convert both lists to integers for comparison
            ids_to_remove_set = set(int(i) for i in ids_to_remove)
            remaining_ids = [msg_id for msg_id in all_ids if int(msg_id) not in ids_to_remove_set]
            with open(SENT_IDS_FILE, "w") as f:
                for msg_id in remaining_ids:
                    f.write(f"{msg_id}\n")
    except Exception as e:
        print(f"Error removing IDs from sent_message_ids.txt: {e}")

def pull_new_messages():
    """Pulls the database for new messages and sends them to Telegram, caching last sent ID."""
    print("Starting background thread to pull for new messages...")
    SENT_IDS_FILE = os.path.join(os.path.dirname(__file__), "message_ids.txt")

    def load_sent_ids():
        if not os.path.exists(SENT_IDS_FILE):
            return set()
        try:
            with open(SENT_IDS_FILE, "r") as f:
                return set(int(line.strip()) for line in f if line.strip().isdigit())
        except Exception as e:
            print(f"Error loading sent IDs file: {e}")
            return set()

    def save_sent_ids(sent_ids):
        try:
            with open(SENT_IDS_FILE, "w") as f:
                for msg_id in sorted(sent_ids):
                    f.write(f"{msg_id}\n")
        except Exception as e:
            print(f"Error saving sent IDs file: {e}")
    

    sent_ids = load_sent_ids()

    while True:
        conn = get_db_connection()
        if not conn:
            print("Pulling thread: Database connection failed. Retrying in 60s.")
            time.sleep(60)
            continue

        cursor = conn.cursor(dictionary=True)
        try:
            # Clean up empty/blank messages first
            cursor.execute("DELETE FROM inbox WHERE TextDecoded IS NULL OR TRIM(TextDecoded) = ''")
            deleted = cursor.rowcount
            if deleted > 0:
                conn.commit()
                print(f"Pulling thread: Removed {deleted} empty/blank messages.")

            # Fetch unread messages that haven't been processed by the bot yet
            cursor.execute("""
                SELECT ID, SenderNumber, TextDecoded, ReceivingDateTime, Processed,
                       UDH
                FROM inbox
                WHERE Processed = 'false'
                ORDER BY ReceivingDateTime ASC
            """)
            raw_messages = cursor.fetchall()

            new_sent = False
            for message in raw_messages:
                msg_id = message.get('ID')
                if msg_id is not None and int(msg_id) not in sent_ids:
                    send_message_to_telegram(message)
                    sent_ids.add(int(msg_id))
                    new_sent = True
                    time.sleep(1)  # Add delay to avoid Telegram rate limits

            if new_sent:
                save_sent_ids(sent_ids)

        except mysql.connector.Error as err:
            print(f"Pulling thread error: {err}")
        finally:
            cursor.close()
            conn.close()

        time.sleep(10) # Pulls every 10 seconds


# --- Main Execution ---
if __name__ == '__main__':
    # Start the background thread only if Telegram is configured
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        polling_thread = threading.Thread(target=pull_new_messages, daemon=True)
        polling_thread.start()

    # Telegram command bot runs as a separate process via `python -m sms-dashboard.bot`.
    # We don't start it here to avoid polling conflicts.

    print("Starting Flask server...")
    print("Access the app at http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
