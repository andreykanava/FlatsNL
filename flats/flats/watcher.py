import subprocess
import time

INTERVAL_SECONDS = 10 * 60


def run_cycle():
    result = subprocess.run(["python", "flats/run_all.py"])
    return result.returncode


if __name__ == "__main__":
    while True:
        print("=== Starting scrape cycle ===")
        code = run_cycle()
        print(f"=== Cycle finished with code {code} ===")
        print(f"=== Sleeping {INTERVAL_SECONDS} seconds ===")
        time.sleep(INTERVAL_SECONDS)
