import os
import signal
import subprocess
import sys
import time
from typing import List
from dotenv import load_dotenv


# Load .env to check for Telegram config
load_dotenv()


def _spawn(cmd: List[str]) -> subprocess.Popen:
    env = os.environ.copy()
    # Use unbuffered output for logging
    env["PYTHONUNBUFFERED"] = "1"
    return subprocess.Popen(cmd, env=env)


def main() -> int:
    print("Starting production server...")
    py = sys.executable
    procs: list[subprocess.Popen] = []

    try:
        # Gunicorn command for Flask app.
        # We change directory to `src` to ensure Python can find the package.
        gunicorn_cmd = [
            "gunicorn",
            "--chdir", "src",
            "-w", "4",
            "-b", "0.0.0.0:5000",
            "sms-dashboard.app:app"
        ]
        gunicorn_proc = _spawn(gunicorn_cmd)
        procs.append(gunicorn_proc)
        print(f"Started Gunicorn server (PID: {gunicorn_proc.pid})")

        # Conditionally start Telegram bot
        if os.environ.get("TELEGRAM_BOT_TOKEN"):
            bot_cmd = [py, "-m", "sms-dashboard.bot"]
            bot_proc = _spawn(bot_cmd)
            procs.append(bot_proc)
            print(f"Started Telegram bot (PID: {bot_proc.pid})")
        else:
            print("TELEGRAM_BOT_TOKEN not found, skipping bot.")

        print("Press Ctrl+C to stop all services.")

        # Wait for any process to exit
        while True:
            for p in procs:
                if p.poll() is not None:
                    print(f"Process {p.pid} exited with code {p.returncode}. Stopping all services.")
                    # If one process fails, stop them all
                    return 1
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nStopping all services...")
        return 0
    finally:
        # Terminate all children gracefully
        for p in reversed(procs):
            if p.poll() is None:
                try:
                    p.send_signal(signal.SIGINT)
                except Exception:
                    pass
        
        # Wait a moment for graceful shutdown
        time.sleep(3)

        # Force kill any that are still running
        for p in reversed(procs):
            if p.poll() is None:
                try:
                    p.terminate()
                    time.sleep(1)
                    if p.poll() is None:
                        p.kill()
                except Exception:
                    pass
        print("All services stopped.")


if __name__ == "__main__":
    raise SystemExit(main())
