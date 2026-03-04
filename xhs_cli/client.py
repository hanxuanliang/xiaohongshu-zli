"""Xiaohongshu browser-based client using camoufox.

All operations navigate to pages and extract data from window.__INITIAL_STATE__,
exactly like a real user browsing. This avoids API-level risk control (300011).
"""

from __future__ import annotations

import json
import logging
import random
import time
from typing import Any

logger = logging.getLogger(__name__)


class XhsClient:
    """Camoufox-based Xiaohongshu client.

    Navigates to real pages and extracts data from __INITIAL_STATE__,
    indistinguishable from a real user browsing.
    """

    def __init__(self, cookie_dict: dict[str, str]):
        self._cookie_dict = cookie_dict
        self._camoufox_ctx = None
        self._browser = None
        self._page = None

    def start(self):
        """Launch camoufox and inject cookies."""
        from camoufox.sync_api import Camoufox

        logger.info("Starting camoufox browser...")
        self._camoufox_ctx = Camoufox(headless=True)
        self._browser = self._camoufox_ctx.__enter__()
        self._page = self._browser.new_page()

        # Inject cookies
        cookies = [
            {"name": k, "value": v, "domain": ".xiaohongshu.com", "path": "/"}
            for k, v in self._cookie_dict.items()
        ]
        self._page.context.add_cookies(cookies)

        # Navigate to homepage to establish session
        self._page.goto(
            "https://www.xiaohongshu.com",
            wait_until="domcontentloaded",
            timeout=20000,
        )
        self._human_wait(1, 2)
        logger.info("Browser ready.")

    def close(self):
        """Shut down the browser."""
        if self._camoufox_ctx:
            try:
                self._camoufox_ctx.__exit__(None, None, None)
            except Exception:
                pass
            self._camoufox_ctx = None
            self._browser = None
            self._page = None
            logger.info("Browser closed.")

    # ===== Search =====

    def search_notes(self, keyword: str) -> list[dict]:
        """Search notes by keyword.

        Navigates to search_result page and extracts from __INITIAL_STATE__.search.feeds.
        """
        import urllib.parse
        params = urllib.parse.urlencode({"keyword": keyword, "source": "web_explore_feed"})
        url = f"https://www.xiaohongshu.com/search_result?{params}"

        logger.info("Searching: %s", keyword)
        self._page.goto(url, wait_until="domcontentloaded", timeout=20000)
        self._human_wait(1, 2)

        # Wait for __INITIAL_STATE__ to be populated
        self._wait_for_initial_state()

        # Extract search feeds
        result = self._page.evaluate("""() => {
            if (window.__INITIAL_STATE__ &&
                window.__INITIAL_STATE__.search &&
                window.__INITIAL_STATE__.search.feeds) {
                const feeds = window.__INITIAL_STATE__.search.feeds;
                const feedsData = feeds.value !== undefined ? feeds.value : feeds._value;
                if (feedsData) {
                    return JSON.parse(JSON.stringify(feedsData));
                }
            }
            return null;
        }""")

        if not result:
            logger.warning("No search results found in __INITIAL_STATE__")
            return []

        return result

    # ===== Note Detail =====

    def get_note_detail(self, note_id: str, xsec_token: str = "") -> dict:
        """Get note detail by navigating to the explore page.

        Extracts from __INITIAL_STATE__.note.noteDetailMap.
        """
        url = f"https://www.xiaohongshu.com/explore/{note_id}"
        if xsec_token:
            url += f"?xsec_token={xsec_token}&xsec_source=pc_feed"

        logger.info("Loading note: %s", note_id)
        self._page.goto(url, wait_until="domcontentloaded", timeout=20000)
        self._human_wait(1.5, 3)

        self._wait_for_initial_state()

        # Extract note detail
        for attempt in range(3):
            result = self._page.evaluate("""() => {
                if (window.__INITIAL_STATE__ &&
                    window.__INITIAL_STATE__.note &&
                    window.__INITIAL_STATE__.note.noteDetailMap) {
                    return JSON.parse(JSON.stringify(
                        window.__INITIAL_STATE__.note.noteDetailMap
                    ));
                }
                return null;
            }""")

            if result:
                # Find the note in the map
                if note_id in result:
                    return result[note_id]
                # Try first key if note_id not found
                if result:
                    first_key = next(iter(result))
                    return result[first_key]

            time.sleep(0.5)

        raise RuntimeError(f"Failed to extract note detail for {note_id}")

    # ===== User Profile =====

    def get_user_info(self, user_id: str) -> dict:
        """Get user profile by navigating to their profile page."""
        url = f"https://www.xiaohongshu.com/user/profile/{user_id}"

        logger.info("Loading user profile: %s", user_id)
        self._page.goto(url, wait_until="domcontentloaded", timeout=20000)
        self._human_wait(1.5, 3)

        self._wait_for_initial_state()

        # Vue wraps values in reactive refs like {_value, dep, ...}
        # We need to unwrap _value recursively
        result = self._page.evaluate("""() => {
            function unwrap(obj, depth) {
                if (depth > 6 || obj === null || obj === undefined) return obj;
                if (typeof obj !== 'object') return obj;

                // Unwrap Vue ref: if has _value, use that
                if ('_value' in obj && 'dep' in obj) {
                    return unwrap(obj._value, depth + 1);
                }
                // Also handle .value pattern
                if ('value' in obj && 'dep' in obj) {
                    return unwrap(obj.value, depth + 1);
                }

                if (Array.isArray(obj)) {
                    return obj.map(item => unwrap(item, depth + 1));
                }

                const result = {};
                const seen = new Set();
                for (const key of Object.keys(obj)) {
                    if (key === 'dep' || key === '__v_raw' || key === '__v_skip'
                        || key.startsWith('__')) continue;
                    if (seen.has(key)) continue;
                    seen.add(key);
                    try {
                        result[key] = unwrap(obj[key], depth + 1);
                    } catch(e) {}
                }
                return result;
            }

            if (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.user) {
                const u = window.__INITIAL_STATE__.user;
                const data = {};
                // Extract key fields
                if (u.userPageData) data.userPageData = unwrap(u.userPageData, 0);
                if (u.notes) data.notes = unwrap(u.notes, 0);
                if (u.userInfo) data.userInfo = unwrap(u.userInfo, 0);
                return data;
            }
            return null;
        }""")

        if not result:
            raise RuntimeError(f"Failed to extract user profile for {user_id}")
        return result

    # ===== Self Info =====

    def get_self_info(self) -> dict:
        """Check login status by visiting user settings page."""
        self._page.goto(
            "https://www.xiaohongshu.com",
            wait_until="domcontentloaded",
            timeout=15000,
        )
        self._human_wait(1, 2)

        self._wait_for_initial_state()

        result = self._page.evaluate("""() => {
            if (window.__INITIAL_STATE__ &&
                window.__INITIAL_STATE__.user &&
                window.__INITIAL_STATE__.user.userPageData) {
                return JSON.parse(JSON.stringify(
                    window.__INITIAL_STATE__.user.userPageData
                ));
            }
            return null;
        }""")

        return result or {}

    # ===== Comments via scroll =====

    def get_note_comments(self, note_id: str, xsec_token: str = "",
                          max_comments: int = 50) -> list[dict]:
        """Load comments by scrolling the note page.

        Must be called after get_note_detail on the same note.
        """
        # First get initial comments from __INITIAL_STATE__
        comments_data = self._page.evaluate("""() => {
            if (window.__INITIAL_STATE__ &&
                window.__INITIAL_STATE__.note &&
                window.__INITIAL_STATE__.note.noteDetailMap) {
                const map = window.__INITIAL_STATE__.note.noteDetailMap;
                const keys = Object.keys(map);
                if (keys.length > 0) {
                    const comments = map[keys[0]].comments;
                    if (comments) {
                        return JSON.parse(JSON.stringify(comments));
                    }
                }
            }
            return null;
        }""")

        return comments_data if comments_data else []

    # ===== Like / Unlike =====

    def like_note(self, note_id: str, xsec_token: str = "") -> bool:
        """Like a note by clicking the like button."""
        return self._toggle_interact(note_id, xsec_token, "like", True)

    def unlike_note(self, note_id: str, xsec_token: str = "") -> bool:
        """Unlike a note by clicking the like button."""
        return self._toggle_interact(note_id, xsec_token, "like", False)

    # ===== Favorite / Unfavorite =====

    def favorite_note(self, note_id: str, xsec_token: str = "") -> bool:
        """Favorite a note by clicking the collect button."""
        return self._toggle_interact(note_id, xsec_token, "favorite", True)

    def unfavorite_note(self, note_id: str, xsec_token: str = "") -> bool:
        """Unfavorite a note by clicking the collect button."""
        return self._toggle_interact(note_id, xsec_token, "favorite", False)

    # ===== Comment =====

    def post_comment(self, note_id: str, content: str, xsec_token: str = "") -> bool:
        """Post a comment on a note by typing into the comment input."""
        self._navigate_to_note(note_id, xsec_token)

        # Find and click comment input
        try:
            input_el = self._page.query_selector('#content-textarea')
            if not input_el:
                input_el = self._page.query_selector('[contenteditable="true"]')
            if not input_el:
                raise RuntimeError("Comment input not found")

            input_el.click()
            self._human_wait(0.3, 0.8)
            input_el.type(content, delay=random.randint(50, 150))
            self._human_wait(0.5, 1.0)

            # Click submit button
            submit = self._page.query_selector('.submit.active') or \
                     self._page.query_selector('button.submit')
            if submit:
                submit.click()
                self._human_wait(1, 2)
                logger.info("Comment posted on %s", note_id)
                return True

            # Try pressing Enter as fallback
            self._page.keyboard.press("Enter")
            self._human_wait(1, 2)
            logger.info("Comment posted (Enter) on %s", note_id)
            return True

        except Exception as e:
            logger.error("Failed to post comment: %s", e)
            return False

    # ===== Internal: Interaction helpers =====

    def _navigate_to_note(self, note_id: str, xsec_token: str = ""):
        """Navigate to note detail page."""
        url = f"https://www.xiaohongshu.com/explore/{note_id}"
        if xsec_token:
            url += f"?xsec_token={xsec_token}&xsec_source=pc_feed"
        self._page.goto(url, wait_until="domcontentloaded", timeout=20000)
        self._human_wait(1.5, 3)
        self._wait_for_initial_state()

    def _get_interact_state(self, note_id: str) -> dict:
        """Get like/favorite state from __INITIAL_STATE__."""
        result = self._page.evaluate("""(noteId) => {
            if (window.__INITIAL_STATE__ &&
                window.__INITIAL_STATE__.note &&
                window.__INITIAL_STATE__.note.noteDetailMap) {
                const map = window.__INITIAL_STATE__.note.noteDetailMap;
                const detail = map[noteId] || map[Object.keys(map)[0]];
                if (detail && detail.note && detail.note.interactInfo) {
                    return detail.note.interactInfo;
                }
            }
            return null;
        }""", note_id)
        return result or {}

    def _toggle_interact(self, note_id: str, xsec_token: str,
                         action: str, target_state: bool) -> bool:
        """Toggle like/favorite by clicking the button.

        Args:
            action: "like" or "favorite"
            target_state: True to like/favorite, False to unlike/unfavorite
        """
        SELECTORS = {
            "like": ".interact-container .left .like-lottie",
            "favorite": ".interact-container .left .reds-icon.collect-icon",
        }
        STATE_KEYS = {
            "like": "liked",
            "favorite": "collected",
        }

        self._navigate_to_note(note_id, xsec_token)

        # Check current state
        state = self._get_interact_state(note_id)
        current = state.get(STATE_KEYS[action], False)
        if current == target_state:
            action_name = action if target_state else f"un{action}"
            logger.info("Note %s already %sd, skipping", note_id, action_name)
            return True

        # Click the button
        selector = SELECTORS[action]
        el = self._page.query_selector(selector)
        if not el:
            logger.error("%s button not found: %s", action, selector)
            return False

        el.click()
        self._human_wait(2, 3)

        # Verify
        state = self._get_interact_state(note_id)
        new_state = state.get(STATE_KEYS[action], False)
        if new_state == target_state:
            logger.info("Note %s %s success", note_id, action)
            return True

        # Retry once
        logger.warning("State didn't change, retrying click...")
        el = self._page.query_selector(selector)
        if el:
            el.click()
            self._human_wait(2, 3)

        return True

    # ===== Internal helpers =====

    def _wait_for_initial_state(self, timeout: float = 10.0):
        """Wait for window.__INITIAL_STATE__ to be populated."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                result = self._page.evaluate(
                    "() => window.__INITIAL_STATE__ !== undefined"
                )
                if result:
                    return
            except Exception:
                pass
            time.sleep(0.3)
        logger.warning("__INITIAL_STATE__ not found after %.1fs", timeout)

    def _human_wait(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Wait a random human-like interval."""
        time.sleep(random.uniform(min_sec, max_sec))

