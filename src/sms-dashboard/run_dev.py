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
    # Use unbuffered output
    env["PYTHONUNBUFFERED"] = "1"
    return subprocess.Popen(cmd, env=env)


def main() -> int:
    print("Starting development server...")
    py = sys.executable
    procs: list[subprocess.Popen] = []

    try:
        # Start Flask app
        app_cmd = [py, "-m", "sms-dashboard.app"]
        app_proc = _spawn(app_cmd)
        procs.append(app_proc)
        print(f"Started Flask app (PID: {app_proc.pid})")

        # Conditionally start Telegram bot
        if os.environ.get("TELEGRAM_BOT_TOKEN"):
            bot_cmd = [py, "-m", "sms-dashboard.bot"]
            bot_proc = _spawn(bot_cmd)
            procs.append(bot_proc)
            print(f"Started Telegram bot (PID: {bot_proc.pid})")
        else:
            print("TELEGRAM_BOT_TOKEN not found, skipping bot.")

        print("Press Ctrl+C to stop.")

        # Wait for any process to exit
        while True:
            for p in procs:
                if p.poll() is not None:
                    print(f"Process {p.pid} exited with code {p.returncode}. Stopping all services.")
                    return 1  # Exit with an error code
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nStopping all services...")
        return 0
    finally:
        # Terminate all children
        for p in reversed(procs):
            if p.poll() is None:
                try:
                    # Send SIGINT first for graceful shutdown
                    p.send_signal(signal.SIGINT)
                except Exception:
                    pass
        
        # Wait for a moment
        time.sleep(2)

        # Force kill any remaining processes
        for p in reversed(procs):
            if p.poll() is None:
                try:
                    p.terminate()
                    time.sleep(0.5)
                    if p.poll() is None:
                        p.kill()
                except Exception:
                    pass
        print("All services stopped.")


if __name__ == "__main__":
    raise SystemExit(main())
