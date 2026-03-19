"""
Playwright-based Slack scraper.
Reads messages from channels, DMs, and group chats.
"""
import re
from playwright.sync_api import sync_playwright, Page, BrowserContext
from config import AUTH_STATE_PATH, SLACK_WORKSPACE_URL, CHANNELS
from utils import resolve_date


def _create_context(playwright) -> BrowserContext:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(storage_state=str(AUTH_STATE_PATH))
    return context


def _wait_for_slack(page: Page):
    """Wait for Slack to fully load."""
    page.wait_for_selector('.p-channel_sidebar', timeout=30000)
    page.wait_for_timeout(3000)


def _extract_messages(page: Page) -> list[dict]:
    """Extract visible messages from the current conversation."""
    messages = []
    current_date = ""

    # Messages are in role="listitem" elements
    message_elements = page.query_selector_all('[role="listitem"]')

    for el in message_elements:
        try:
            # Check for day divider (gives us the date)
            divider = el.query_selector('[data-qa="day-divider-label"]')
            if divider:
                current_date = divider.inner_text().strip()
                # Remove dropdown arrow text if present
                current_date = current_date.split("\n")[0].strip()
                continue

            # Get author
            author_el = el.query_selector('[data-qa="message_sender_name"]')
            author = author_el.inner_text().strip() if author_el else None

            # Get timestamp from .c-timestamp element
            time_el = el.query_selector('.c-timestamp')
            time_str = ""
            date_str = current_date
            if time_el:
                aria_label = time_el.get_attribute("aria-label") or ""
                # aria-label is like "Mar 15th at 2:20:36 PM" or "Yesterday at 4:17:36 PM"
                if aria_label:
                    # Extract date part (everything before " at ")
                    if " at " in aria_label:
                        parts = aria_label.split(" at ")
                        date_str = parts[0].strip() or current_date
                        time_str = parts[1].strip()
                    else:
                        time_str = aria_label
                else:
                    time_str = time_el.inner_text().strip()

            # Resolve relative dates to YYYY-MM-DD
            date_str = resolve_date(date_str)

            # Convert 12h time to 24h HH:MM:SS format
            time_clean = time_str
            time_24h_match = re.match(r'(\d+):(\d+):?(\d+)?\s*([AP]M)', time_str, re.IGNORECASE)
            if time_24h_match:
                h = int(time_24h_match.group(1))
                m = int(time_24h_match.group(2))
                s = int(time_24h_match.group(3) or 0)
                ampm = time_24h_match.group(4).upper()
                if ampm == "PM" and h != 12:
                    h += 12
                elif ampm == "AM" and h == 12:
                    h = 0
                time_clean = f"{h:02d}:{m:02d}:{s:02d}"

            # Get message text
            text_el = el.query_selector('[data-qa="message-text"]')
            if not text_el:
                text_el = el.query_selector('.c-message__body, .p-rich_text_block')
            text = text_el.inner_text().strip() if text_el else ""

            if not text:
                continue

            messages.append({
                "author": author or "Unknown",
                "date": date_str or "Unknown date",
                "time": time_clean or time_str,
                "text": text,
            })
        except Exception:
            continue

    return messages


def _scroll_to_load_history(page: Page, max_scrolls: int = 50):
    """Scroll up to load historical messages."""
    msg_list = page.query_selector('[role="list"]')
    if not msg_list:
        return

    for _ in range(max_scrolls):
        page.evaluate("""
            const list = document.querySelector('[role="list"]');
            if (list) list.scrollTop = 0;
        """)
        page.wait_for_timeout(1500)

        # Check if we've reached the beginning
        body_text = page.inner_text("body")
        if "This is the very beginning" in body_text or "was created" in body_text:
            break


def scrape_conversation(page: Page, load_history: bool = False) -> list[dict]:
    """Scrape messages from the currently open conversation."""
    page.wait_for_timeout(3000)

    if load_history:
        _scroll_to_load_history(page)
        page.wait_for_timeout(2000)

    return _extract_messages(page)


def _click_sidebar_item(page: Page, name: str) -> bool:
    """Click a channel or DM in the sidebar by name."""
    sidebar = page.query_selector('.p-channel_sidebar')
    if not sidebar:
        return False

    # Find items in the sidebar virtual list
    items = sidebar.query_selector_all('[data-qa="virtual-list-item"]')
    for item in items:
        item_text = item.inner_text().strip()
        if name.lower() in item_text.lower():
            item.click()
            page.wait_for_timeout(3000)
            return True
    return False


def _get_sidebar_dm_names(page: Page) -> list[str]:
    """Get DM conversation names from sidebar."""
    names = []
    sidebar = page.query_selector('.p-channel_sidebar')
    if not sidebar:
        return names

    # Click "Direct messages" section to make sure it's expanded
    dm_label = page.query_selector('[aria-label="Direct messages"], button:has-text("Direct messages")')
    if dm_label:
        dm_label.click()
        page.wait_for_timeout(1000)

    items = sidebar.query_selector_all('[data-qa="virtual-list-item"]')
    in_dm_section = False
    for item in items:
        text = item.inner_text().strip()
        if "Direct messages" in text:
            in_dm_section = True
            continue
        if in_dm_section and text:
            # Skip section headers and non-DM items
            if text in ("Channels", "Apps", "Starred", "Browse all channels"):
                break
            names.append(text)

    return names


def scrape_channels(page: Page, channel_names: list[str], load_history: bool = False) -> dict:
    """Scrape specified channels. Returns {channel_name: [messages]}."""
    results = {}
    for name in channel_names:
        print(f"  Opening channel #{name}...")
        if _click_sidebar_item(page, name):
            messages = scrape_conversation(page, load_history=load_history)
            results[name] = messages
            print(f"  Found {len(messages)} messages in #{name}")
        else:
            print(f"  Could not find channel #{name} in sidebar")
    return results


def scrape_dms(page: Page, load_history: bool = False) -> dict:
    """Scrape all visible DMs. Returns {person_name: [messages]}."""
    results = {}
    dm_names = _get_sidebar_dm_names(page)
    print(f"  Found {len(dm_names)} DM conversations: {dm_names}")

    for name in dm_names:
        # Clean up name (remove status emojis, "guest" suffix, "you" suffix)
        clean_name = re.sub(r'(guest|you)$', '', name).strip()
        print(f"  Opening DM with {clean_name}...")
        if _click_sidebar_item(page, name):
            messages = scrape_conversation(page, load_history=load_history)
            if messages:
                results[clean_name] = messages
                print(f"  Found {len(messages)} messages with {clean_name}")

    return results


def scrape_all(load_history: bool = False) -> dict:
    """
    Scrape everything: channels, DMs, group chats.
    Returns {"channels": {...}, "dms": {...}, "groups": {...}}
    """
    with sync_playwright() as p:
        context = _create_context(p)
        page = context.new_page()

        print("  Loading Slack...")
        page.goto(SLACK_WORKSPACE_URL, wait_until="domcontentloaded", timeout=60000)
        _wait_for_slack(page)
        print("  Slack loaded!")

        # Scrape channels
        print("\n  --- Channels ---")
        channels = scrape_channels(page, CHANNELS, load_history=load_history)

        # Scrape DMs
        print("\n  --- Direct Messages ---")
        dms = scrape_dms(page, load_history=load_history)

        # Separate group DMs from individual DMs
        individual_dms = {}
        group_dms = {}
        for name, messages in dms.items():
            if "," in name:
                group_dms[name] = messages
            else:
                individual_dms[name] = messages

        context.close()

        return {
            "channels": channels,
            "dms": individual_dms,
            "groups": group_dms,
        }
