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
    print("Starting Flask app and Telegram bot...")
    py = sys.executable

    procs: list[subprocess.Popen] = []
    try:
        app_cmd = [py, "-m", "sms-dashboard.app"]
        bot_cmd = [py, "-m", "sms-dashboard.bot"]

        app_proc = _spawn(app_cmd)
        procs.append(app_proc)
        # Stagger start slightly so logs aren't interleaved at once
        time.sleep(0.5)
        bot_proc = _spawn(bot_cmd)
        procs.append(bot_proc)

        print(f"App PID: {app_proc.pid} | Bot PID: {bot_proc.pid}")
        print("Press Ctrl+C to stop both.")

        # Wait until one of them exits
        while True:
            if app_proc.poll() is not None:
                print(f"Flask app exited with code {app_proc.returncode}")
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
        # Give them a moment to exit gracefully
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
