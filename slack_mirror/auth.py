"""
First-time login: opens a browser for manual Slack login, then saves the session.
Run this once: python auth.py

When run with --signal mode, it waits for a signal file instead of stdin input.
"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from config import AUTH_STATE_PATH, SOURCE_URL, SOURCE_DIR

# Signal file in workspace dir or fallback to root
SIGNAL_FILE = SOURCE_DIR / ".auth_done"
SIGNAL_FILE_ROOT = Path(__file__).parent / ".auth_done"


def login_and_save_session(signal_mode: bool = False):
    # Clean up any old signal files
    for sf in [SIGNAL_FILE, SIGNAL_FILE_ROOT]:
        if sf.exists():
            sf.unlink()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto(SOURCE_URL)

        print(f"\n=== Login ({SOURCE_URL}) ===")
        print("1. Log in to your Slack workspace in the browser that just opened")
        print("2. Make sure you can see your channels/messages")

        if signal_mode:
            print("3. Waiting for signal file...\n")
            # Wait up to 5 minutes for signal file
            for _ in range(300):
                if SIGNAL_FILE.exists():
                    SIGNAL_FILE.unlink()
                    break
                if SIGNAL_FILE_ROOT.exists():
                    SIGNAL_FILE_ROOT.unlink()
                    break
                time.sleep(1)
            else:
                print("Timed out waiting for login. Saving session anyway...")
        else:
            print("3. Come back here and press Enter\n")
            input("Press Enter after you've logged in...")

        context.storage_state(path=str(AUTH_STATE_PATH))
        print(f"Session saved to {AUTH_STATE_PATH}")
        print("You can now run the scraper without logging in again.")

        browser.close()


if __name__ == "__main__":
    signal_mode = "--signal" in sys.argv
    login_and_save_session(signal_mode=signal_mode)
