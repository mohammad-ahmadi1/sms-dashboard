
# Gammu SMS Web Manager

A modern Flask web application for managing SMS messages stored by [Gammu](https://wammu.eu/gammu/) in a MySQL database. Features a real-time, responsive dashboard and optional Telegram notifications.

---

## Features

- **Modern UI:** Responsive interface built with Tailwind CSS.
- **Real-Time Notifications:** Instant browser notifications for new SMS.
- **Live UI Updates:** Message list updates automatically.
- **Bulk Actions:** Mark as read or delete multiple messages at once.
- **Easy Setup:** Minimal dependencies, single-file application.
- **Custom Modals:** Polished dialogs for confirmations.

---

## Prerequisites

- Python 3.13.1+
- GSM modem or compatible mobile device (e.g., [SIM800 Module](https://de.aliexpress.com/item/4000890352364.html?spm=a2g0o.order_list.order_list_main.5.53971802mb0CD6&gatewayAdapt=glo2deu))
- MySQL server
- Poetry (dependency management)
- [asdf](https://asdf-vm.com/) (optional)

---

## 1. Gammu Installation & Configuration

### Install Gammu & SMSD

```bash
sudo apt-get update
sudo apt-get install gammu gammu-smsd
```

### Configure Gammu

Connect your modem (e.g., `/dev/ttyUSB0`). Create `/etc/gammu-smsdrc`:

```ini
[gammu]
device = /dev/ttyUSB0
connection = at115200

[smsd]
service = sql
driver = native_mysql
host = localhost
user = gammu_user
password = <password>
database = gammu_db
logfile = syslog
loglevel = debug
```

Start and enable the service:

```bash
sudo systemctl start gammu-smsd
sudo systemctl enable gammu-smsd
sudo systemctl status gammu-smsd
```

### Set Up MySQL Database

```sql
CREATE DATABASE gammu_db;
CREATE USER 'gammu_user'@'localhost' IDENTIFIED BY 'your_secret_password';
GRANT ALL PRIVILEGES ON gammu_db.* TO 'gammu_user'@'localhost';
FLUSH PRIVILEGES;
```

Import Gammu's SQL schema (path may vary):

```bash
mysql -u gammu_user -p gammu_db < /usr/share/doc/gammu/examples/sql/mysql.sql
```

---

## 2. Web App Setup

### Clone & Install

```bash
git clone <your-repository-url>
cd <your-repository-directory>
poetry install
```

### Configure Environment

Create a `.env` file (see example below):

```env
DB_HOST=localhost
DB_USER=gammu_user
DB_PASSWORD=your_secret_password
DB_NAME=gammu_db
SECRET_KEY=<random_string>
FLASK_ENV=development

# Telegram (optional)
TELEGRAM_BOT_TOKEN=123456:ABC-YourBotToken
TELEGRAM_CHAT_ID=123456789
APP_PUBLIC_URL=http://127.0.0.1:5000
SERVER_IP=192.168.1.100
```

Generate a secure `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 3. Telegram Notifications (Optional)

- Create a bot via [BotFather](https://t.me/botfather).
- Add `TELEGRAM_BOT_TOKEN` to `.env`.
- Get your chat ID by messaging your bot and visiting:
  ```
  https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
  ```
- Add `TELEGRAM_CHAT_ID` to `.env`.

---

## 4. Running the Application


### Development

Run the dashboard and bot separately:

```bash
poetry run python -m sms-dashboard.app
poetry run python -m sms-dashboard.bot
```

Or run both with one command (process manager):

```bash
poetry run sms-dev
```

Open your browser at [http://127.0.0.1:5000](http://127.0.0.1:5000).

### Production (Gunicorn)

**Important:** Gunicorn should be pointed directly at the Flask app instance, not at the process manager script.

Run with Gunicorn:

```bash
poetry run sms-prod
```

If your Flask app uses a different entrypoint, adjust `sms-dashboard.app:app` accordingly.

#### systemd Service Example

Create `/etc/systemd/system/gammu-sms-web.service`:

```ini
[Unit]
Description=Gammu SMS Web Manager (Gunicorn)
After=network.target

[Service]
User=<your-user>
Group=www-data
WorkingDirectory=/home/<your-user>/<your-repository-directory>
Restart=on-failure
Environment=POETRY_VIRTUALENVS_IN_PROJECT=true
ExecStart=/usr/bin/poetry run sms-prod

[Install]
WantedBy=multi-user.target
```

Reload and start:

```bash
sudo systemctl daemon-reload
sudo systemctl start gammu-sms-web
sudo systemctl enable gammu-sms-web
sudo systemctl status gammu-sms-web
```

---

## License

MIT License. See [LICENSE](LICENSE).

---

## Notes

- Control the IP shown in Telegram welcome via `SERVER_IP` in `.env`.
- If unset, falls back to `APP_PUBLIC_URL` or active interface IP.

<!-- ---

## TODOs

- [x] Clean up the README
- [x] Clean up the code
- [ ] Long-term test
- [x] Telegram bot

--- -->

