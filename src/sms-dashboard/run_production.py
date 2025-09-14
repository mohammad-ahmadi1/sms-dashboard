import os
import signal
import subprocess
import sys
import time
from typing import List


def _spawn(cmd: List[str]) -> subprocess.Popen:
    env = os.environ.copy()
    return subprocess.Popen(cmd, env=env)


def main() -> int:
    print("Starting Gunicorn (Flask app) and Telegram bot...")
    py = sys.executable

    procs: list[subprocess.Popen] = []
    try:
        # Gunicorn command for Flask app
        gunicorn_cmd = [
            "gunicorn",
            "--chdir", "src/sms-dashboard",
            "-w", "2",
            "-b", "0.0.0.0:5000",
            "sms-dashboard.app:app"
        ]
        bot_cmd = [py, "-m", "sms-dashboard.bot"]

        gunicorn_proc = _spawn(gunicorn_cmd)
        procs.append(gunicorn_proc)
        time.sleep(0.5)
        bot_proc = _spawn(bot_cmd)
        procs.append(bot_proc)

        print(f"Gunicorn PID: {gunicorn_proc.pid} | Bot PID: {bot_proc.pid}")
        print("Press Ctrl+C to stop both.")

        # Wait until one of them exits
        while True:
            if gunicorn_proc.poll() is not None:
                print(f"Gunicorn exited with code {gunicorn_proc.returncode}")
                break
            if bot_proc.poll() is not None:
                print(f"Telegram bot exited with code {bot_proc.returncode}")
                break
            time.sleep(0.5)

        return 0
    except KeyboardInterrupt:
        print("\nStopping services...")
        return 0
    finally:
        # Terminate all children
        for p in procs:
            if p.poll() is None:
                try:
                    p.send_signal(signal.SIGINT)
                except Exception:
                    pass
        t0 = time.time()
        for p in procs:
            while p.poll() is None and (time.time() - t0) < 5:
                time.sleep(0.1)
        for p in procs:
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
        for p in procs:
            if p.poll() is None:
                try:
                    p.kill()
                except Exception:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
