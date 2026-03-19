"""
Playwright-based Microsoft Teams scraper.
Reads messages from channels, 1:1 chats, and group chats.

NOTE: Teams DOM selectors may need adjustment as Microsoft updates
the Teams web client. Test against a live Teams instance.
"""
import re
from playwright.sync_api import sync_playwright, Page, BrowserContext
from config import AUTH_STATE_PATH, SOURCE_URL, CHANNELS
from utils import resolve_date


def _create_context(playwright) -> BrowserContext:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(storage_state=str(AUTH_STATE_PATH))
    return context


def _wait_for_teams(page: Page):
    """Wait for Teams to fully load."""
    page.wait_for_selector('[data-tid="app-layout"]', timeout=60000)
    page.wait_for_timeout(5000)


def _extract_messages(page: Page) -> list[dict]:
    """Extract visible messages from the current Teams conversation."""
    messages = []
    current_date = ""

    message_elements = page.query_selector_all('[data-tid="chat-pane-message"]')
    if not message_elements:
        message_elements = page.query_selector_all('[role="listitem"]')

    for el in message_elements:
        try:
            divider = el.query_selector('[data-tid="message-group-date-header"]')
            if not divider:
                divider = el.query_selector('.ui-chat__message__dateDivider')
            if divider:
                current_date = divider.inner_text().strip()
                continue

            author_el = el.query_selector('[data-tid="message-author-name"]')
            if not author_el:
                author_el = el.query_selector('.ui-chat__message__author')
            author = author_el.inner_text().strip() if author_el else None

            time_el = el.query_selector('[data-tid="message-timestamp"]')
            if not time_el:
                time_el = el.query_selector('time')
            time_str = ""
            date_str = current_date
            if time_el:
                raw_time = time_el.get_attribute("aria-label") or time_el.inner_text().strip()
                if raw_time:
                    time_match = re.search(r'(\d+:\d+(?::\d+)?\s*[AP]M)', raw_time, re.IGNORECASE)
                    if time_match:
                        time_str = time_match.group(1)
                        date_part = raw_time[:time_match.start()].strip()
                        if date_part:
                            date_str = date_part

            date_str = resolve_date(date_str)

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

            text_el = el.query_selector('[data-tid="message-body"]')
            if not text_el:
                text_el = el.query_selector('.ui-chat__message__content')
            if not text_el:
                text_el = el.query_selector('[role="document"]')
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
    """Scroll up to load historical messages in Teams."""
    for _ in range(max_scrolls):
        page.evaluate("""
            const container = document.querySelector('[data-tid="message-pane-list-container"]')
                || document.querySelector('[role="main"] [role="list"]');
            if (container) container.scrollTop = 0;
        """)
        page.wait_for_timeout(1500)

        body_text = page.inner_text("body")
        if "This is the beginning" in body_text or "started this conversation" in body_text:
            break


def scrape_conversation(page: Page, load_history: bool = False) -> list[dict]:
    """Scrape messages from the currently open Teams conversation."""
    page.wait_for_timeout(3000)

    if load_history:
        _scroll_to_load_history(page)
        page.wait_for_timeout(2000)

    return _extract_messages(page)


def _click_sidebar_item(page: Page, name: str) -> bool:
    """Click a channel or chat in the Teams sidebar by name."""
    items = page.query_selector_all('[data-tid="team-channel-item"], [role="treeitem"]')
    for item in items:
        try:
            item_text = item.inner_text().strip()
            if name.lower() in item_text.lower():
                item.click()
                page.wait_for_timeout(3000)
                return True
        except Exception:
            continue
    return False


def _navigate_to_teams_section(page: Page):
    """Click the Teams icon in the left rail to show team channels."""
    teams_btn = page.query_selector('[data-tid="app-bar-Teams"]')
    if not teams_btn:
        teams_btn = page.query_selector('[aria-label="Teams"]')
    if teams_btn:
        teams_btn.click()
        page.wait_for_timeout(2000)


def _navigate_to_chat_section(page: Page):
    """Click the Chat icon in the left rail to show chats."""
    chat_btn = page.query_selector('[data-tid="app-bar-Chat"]')
    if not chat_btn:
        chat_btn = page.query_selector('[aria-label="Chat"]')
    if chat_btn:
        chat_btn.click()
        page.wait_for_timeout(2000)


def _get_chat_names(page: Page) -> list[dict]:
    """Get chat conversation names and types from the Chat section.
    Returns list of {"name": str, "is_group": bool}."""
    chats = []
    chat_items = page.query_selector_all('[data-tid="chat-list-item"]')
    if not chat_items:
        chat_items = page.query_selector_all('[role="listitem"]')

    for item in chat_items:
        try:
            name = item.inner_text().strip().split("\n")[0]
            if not name:
                continue
            is_group = "," in name or "and" in name.lower()
            chats.append({"name": name, "is_group": is_group})
        except Exception:
            continue

    return chats


def scrape_channels(page: Page, channel_names: list[str], load_history: bool = False) -> dict:
    """Scrape specified Teams channels. Returns {channel_name: [messages]}."""
    results = {}
    _navigate_to_teams_section(page)

    for name in channel_names:
        print(f"  Opening Teams channel {name}...")
        if _click_sidebar_item(page, name):
            messages = scrape_conversation(page, load_history=load_history)
            results[name] = messages
            print(f"  Found {len(messages)} messages in {name}")
        else:
            print(f"  Could not find Teams channel {name}")

    return results


def scrape_all(load_history: bool = False) -> dict:
    """
    Scrape everything from Teams: channels, 1:1 chats, group chats.
    Returns {"channels": {...}, "dms": {...}, "groups": {...}}
    """
    with sync_playwright() as p:
        context = _create_context(p)
        page = context.new_page()

        print("  Loading Teams...")
        page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=60000)
        _wait_for_teams(page)
        print("  Teams loaded!")

        # Scrape channels
        print("\n  --- Teams Channels ---")
        channels = scrape_channels(page, CHANNELS, load_history=load_history)

        # Scrape chats
        print("\n  --- Teams Chats ---")
        _navigate_to_chat_section(page)
        all_chats = _get_chat_names(page)

        individual_chats = {}
        group_chats = {}

        for chat in all_chats:
            name = chat["name"]
            print(f"  Opening chat with {name}...")
            if _click_sidebar_item(page, name):
                messages = scrape_conversation(page, load_history=load_history)
                if messages:
                    if chat["is_group"]:
                        group_chats[name] = messages
                    else:
                        individual_chats[name] = messages
                    print(f"  Found {len(messages)} messages with {name}")

        context.close()

        return {
            "channels": channels,
            "dms": individual_chats,
            "groups": group_chats,
        }
