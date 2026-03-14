"""
Centralised Browserbase browser manager.

Handles session lifecycle, cookie persistence, search, and add-to-cart
for Amazon and Flipkart.

Usage:
    from shopping_agent.app.tools.browserbase import BrowserbaseManager

    mgr = BrowserbaseManager(api_key="...", project_id="...")

    # One-time: start session, log in manually, save cookies
    url = mgr.start_login_session()          # Amazon
    url = mgr.start_flipkart_login_session() # Flipkart
    # ... user logs in via the URL ...
    mgr.save_cookies()          # Amazon
    mgr.save_flipkart_cookies() # Flipkart

    # Reusable: search and add to cart
    results = mgr.search_amazon("wireless earbuds")
    results = mgr.search_flipkart("wireless earbuds")
    statuses = mgr.add_to_cart(["https://amazon.in/dp/B0FMDL81GS", ...])
    statuses = mgr.add_to_cart_flipkart(["https://www.flipkart.com/...", ...])
"""

import asyncio
import base64
import json
import os
from typing import Any

from browserbase import Browserbase
from playwright.async_api import async_playwright


COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".bb_cookies.json")
SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".bb_session")
FLIPKART_COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".bb_flipkart_cookies.json")
FLIPKART_SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".bb_flipkart_session")


class BrowserbaseManager:

    def __init__(
        self,
        api_key: str | None = None,
        project_id: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("BROWSERBASE_API_KEY", "")
        self.project_id = project_id or os.environ.get("BROWSERBASE_PROJECT_ID", "")
        if not self.api_key or not self.project_id:
            raise ValueError("BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID are required")
        self.client = Browserbase(api_key=self.api_key)

    # ------------------------------------------------------------------ #
    #  Session & cookie helpers
    # ------------------------------------------------------------------ #

    def _create_session(self, timeout: int = 300) -> Any:
        return self.client.sessions.create(
            project_id=self.project_id,
            timeout=timeout,
        )

    def _release_session(self, session_id: str) -> None:
        try:
            self.client.sessions.update(session_id, status="REQUEST_RELEASE")
        except Exception:
            pass

    def _load_cookies(self, cookie_file: str = COOKIES_FILE) -> dict | None:
        if not os.path.exists(cookie_file):
            return None
        with open(cookie_file) as f:
            return json.load(f)

    async def _inject_cookies(
        self, context, page, cookies_data: dict | None,
        domain_url: str = "https://www.amazon.in",
    ) -> None:
        if not cookies_data:
            return
        if cookies_data.get("cookies"):
            await context.add_cookies(cookies_data["cookies"])
        if cookies_data.get("local_storage"):
            await page.goto(domain_url, wait_until="domcontentloaded", timeout=30000)
            await page.evaluate("""
                (data) => {
                    for (const [key, value] of Object.entries(data)) {
                        localStorage.setItem(key, value);
                    }
                }
            """, cookies_data["local_storage"])

    # ------------------------------------------------------------------ #
    #  1. start_login_session  →  returns debug URL for manual login
    # ------------------------------------------------------------------ #

    def start_login_session(self, timeout: int = 900) -> dict:
        """
        Create a browser session for manual login.

        Returns dict with session_id, cdp_url, and debug_url.
        Open debug_url in your browser to log in.
        """
        session = self._create_session(timeout=timeout)
        debug_urls = self.client.sessions.debug(session.id)

        session_data = {
            "session_id": session.id,
            "cdp_url": session.connect_url,
            "debug_url": debug_urls.debugger_fullscreen_url,
        }
        with open(SESSION_FILE, "w") as f:
            json.dump(session_data, f, indent=2)

        return session_data

    # ------------------------------------------------------------------ #
    #  2. save_cookies  →  extract cookies from running session
    # ------------------------------------------------------------------ #

    def save_cookies(self) -> dict:
        """
        Connect to the running login session, extract cookies, save to disk.

        Returns summary: {amazon_cookies: int, local_storage_keys: int}
        """
        return asyncio.run(self._save_cookies_async())

    async def _save_cookies_async(self) -> dict:
        if not os.path.exists(SESSION_FILE):
            raise RuntimeError("No active session. Call start_login_session() first.")

        with open(SESSION_FILE) as f:
            data = json.load(f)

        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(data["cdp_url"])
            context = browser.contexts[0]
            cookies = await context.cookies()

            page = context.pages[0] if context.pages else await context.new_page()
            local_storage = {}
            if "amazon" in page.url:
                local_storage = await page.evaluate("""
                    () => {
                        const d = {};
                        for (let i = 0; i < localStorage.length; i++) {
                            const k = localStorage.key(i);
                            d[k] = localStorage.getItem(k);
                        }
                        return d;
                    }
                """)

        saved = {"cookies": cookies, "local_storage": local_storage}
        with open(COOKIES_FILE, "w") as f:
            json.dump(saved, f, indent=2)

        amazon_cookies = [c for c in cookies if "amazon" in c.get("domain", "")]
        return {
            "amazon_cookies": len(amazon_cookies),
            "total_cookies": len(cookies),
            "local_storage_keys": len(local_storage),
        }

    # ------------------------------------------------------------------ #
    #  3. search_amazon  →  top N non-sponsored results
    # ------------------------------------------------------------------ #

    def search_amazon(self, query: str, max_results: int = 8) -> list[dict]:
        """
        Search Amazon.in for a query. Returns top non-sponsored results.

        Each result: {title, price, rating, reviews, asin, url, image}
        """
        return asyncio.run(self._search_amazon_async(query, max_results))

    async def _search_amazon_async(self, query: str, max_results: int) -> list[dict]:
        cookies_data = self._load_cookies()
        session = self._create_session(timeout=300)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(session.connect_url)
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else await context.new_page()

                await self._inject_cookies(context, page, cookies_data)

                search_url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
                await page.goto(search_url, wait_until="load", timeout=45000)
                await page.wait_for_timeout(3000)

                try:
                    await page.wait_for_selector(
                        '[data-component-type="s-search-result"]', timeout=20000
                    )
                except Exception:
                    return []

                await page.wait_for_timeout(2000)

                return await page.evaluate(_EXTRACT_RESULTS_JS, max_results)
        finally:
            self._release_session(session.id)

    # ------------------------------------------------------------------ #
    #  4. add_to_cart  →  visit each URL, click Add to Cart
    # ------------------------------------------------------------------ #

    def add_to_cart(self, urls: list[str]) -> dict:
        """
        Add a list of Amazon product URLs/ASINs to cart.

        Returns {items: [...], cart_screenshot: "base64png"}
        """
        urls = [_normalize_url(u) for u in urls if u.strip()]
        return asyncio.run(self._add_to_cart_async(urls))

    async def _add_to_cart_async(self, urls: list[str]) -> dict:
        cookies_data = self._load_cookies()
        session = self._create_session(timeout=300)
        results = []
        cart_screenshot_b64 = ""

        try:
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(session.connect_url)
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else await context.new_page()

                await self._inject_cookies(context, page, cookies_data)

                for url in urls:
                    status = {"url": url, "title": "", "image": "", "success": False, "message": ""}
                    try:
                        await page.goto(url, wait_until="load", timeout=30000)
                        await page.wait_for_timeout(2000)

                        # Extract title + product image
                        product_info = await page.evaluate("""
                            () => {
                                const titleEl = document.getElementById('productTitle');
                                const title = titleEl ? titleEl.innerText.trim().substring(0, 100) : '';
                                const imgEl = document.getElementById('landingImage')
                                    || document.getElementById('imgBlkFront')
                                    || document.querySelector('#imageBlock img')
                                    || document.querySelector('#main-image-container img');
                                const image = imgEl ? imgEl.getAttribute('src') || '' : '';
                                return { title, image };
                            }
                        """)
                        status["title"] = product_info["title"]
                        status["image"] = product_info["image"]

                        add_btn = (
                            await page.query_selector("#add-to-cart-button")
                            or await page.query_selector("#submit\\.add-to-cart")
                            or await page.query_selector("input[name='submit.add-to-cart']")
                        )

                        if not add_btn:
                            status["message"] = "Add to Cart button not found"
                            results.append(status)
                            continue

                        await add_btn.click()
                        await page.wait_for_timeout(3000)

                        added = await page.evaluate("""
                            () => {
                                const ok = document.getElementById('sw-atc-confirmation')
                                    || document.getElementById('huc-v2-order-row-confirm-text')
                                    || document.body.innerText.includes('Added to Cart');
                                const cnt = document.getElementById('nav-cart-count');
                                return { confirmed: !!ok, cartCount: cnt ? cnt.innerText.trim() : '?' };
                            }
                        """)

                        status["success"] = True
                        status["message"] = f"Added (cart: {added['cartCount']})"

                    except Exception as e:
                        status["message"] = str(e)[:100]

                    results.append(status)

                # Navigate to cart page and take a full-page screenshot
                try:
                    await page.goto("https://www.amazon.in/gp/cart/view.html", wait_until="load", timeout=30000)
                    await page.wait_for_timeout(3000)
                    screenshot_bytes = await page.screenshot(full_page=True)
                    cart_screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
                except Exception:
                    cart_screenshot_b64 = ""

        finally:
            self._release_session(session.id)

        return {"items": results, "cart_screenshot": cart_screenshot_b64}

    # ================================================================== #
    #  FLIPKART
    # ================================================================== #

    # ------------------------------------------------------------------ #
    #  5. start_flipkart_login_session
    # ------------------------------------------------------------------ #

    def start_flipkart_login_session(self, timeout: int = 900) -> dict:
        """Create a browser session for manual Flipkart login."""
        session = self._create_session(timeout=timeout)
        debug_urls = self.client.sessions.debug(session.id)

        session_data = {
            "session_id": session.id,
            "cdp_url": session.connect_url,
            "debug_url": debug_urls.debugger_fullscreen_url,
        }
        with open(FLIPKART_SESSION_FILE, "w") as f:
            json.dump(session_data, f, indent=2)

        return session_data

    # ------------------------------------------------------------------ #
    #  6. save_flipkart_cookies
    # ------------------------------------------------------------------ #

    def save_flipkart_cookies(self) -> dict:
        """Extract cookies from the running Flipkart login session and save to disk."""
        return asyncio.run(self._save_flipkart_cookies_async())

    async def _save_flipkart_cookies_async(self) -> dict:
        if not os.path.exists(FLIPKART_SESSION_FILE):
            raise RuntimeError("No active Flipkart session. Call start_flipkart_login_session() first.")

        with open(FLIPKART_SESSION_FILE) as f:
            data = json.load(f)

        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(data["cdp_url"])
            context = browser.contexts[0]
            cookies = await context.cookies()

            page = context.pages[0] if context.pages else await context.new_page()
            local_storage = {}
            if "flipkart" in page.url:
                local_storage = await page.evaluate("""
                    () => {
                        const d = {};
                        for (let i = 0; i < localStorage.length; i++) {
                            const k = localStorage.key(i);
                            d[k] = localStorage.getItem(k);
                        }
                        return d;
                    }
                """)

        saved = {"cookies": cookies, "local_storage": local_storage}
        with open(FLIPKART_COOKIES_FILE, "w") as f:
            json.dump(saved, f, indent=2)

        flipkart_cookies = [c for c in cookies if "flipkart" in c.get("domain", "")]
        return {
            "flipkart_cookies": len(flipkart_cookies),
            "total_cookies": len(cookies),
            "local_storage_keys": len(local_storage),
        }

    # ------------------------------------------------------------------ #
    #  7. search_flipkart  →  top N non-sponsored results
    # ------------------------------------------------------------------ #

    def search_flipkart(self, query: str, max_results: int = 8) -> list[dict]:
        """
        Search Flipkart for a query. Returns top non-sponsored results.

        Each result: {title, price, rating, reviews, pid, url, image}
        """
        return asyncio.run(self._search_flipkart_async(query, max_results))

    async def _search_flipkart_async(self, query: str, max_results: int) -> list[dict]:
        cookies_data = self._load_cookies(FLIPKART_COOKIES_FILE)
        session = self._create_session(timeout=300)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(session.connect_url)
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else await context.new_page()

                await self._inject_cookies(
                    context, page, cookies_data, "https://www.flipkart.com"
                )

                search_url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
                await page.goto(search_url, wait_until="load", timeout=45000)
                await page.wait_for_timeout(3000)

                try:
                    await page.wait_for_selector("div[data-id]", timeout=20000)
                except Exception:
                    return []

                await page.wait_for_timeout(2000)

                return await page.evaluate(_EXTRACT_FLIPKART_RESULTS_JS, max_results)
        finally:
            self._release_session(session.id)

    # ------------------------------------------------------------------ #
    #  8. add_to_cart_flipkart  →  visit each URL, click Add to Cart
    # ------------------------------------------------------------------ #

    def add_to_cart_flipkart(self, urls: list[str]) -> dict:
        """
        Add a list of Flipkart product URLs to cart.

        Returns {items: [...], cart_screenshot: "base64png"}
        """
        urls = [_normalize_flipkart_url(u) for u in urls if u.strip()]
        return asyncio.run(self._add_to_cart_flipkart_async(urls))

    async def _add_to_cart_flipkart_async(self, urls: list[str]) -> dict:
        cookies_data = self._load_cookies(FLIPKART_COOKIES_FILE)
        session = self._create_session(timeout=300)
        results = []
        cart_screenshot_b64 = ""

        try:
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(session.connect_url)
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else await context.new_page()

                await self._inject_cookies(
                    context, page, cookies_data, "https://www.flipkart.com"
                )

                for url in urls:
                    status = {"url": url, "title": "", "image": "", "success": False, "message": ""}
                    try:
                        await page.goto(url, wait_until="load", timeout=30000)
                        await page.wait_for_timeout(2000)

                        # Extract title from page title
                        title = await page.evaluate("""
                            () => {
                                const t = document.title;
                                const parts = t.split(' Price in India');
                                return (parts[0] || t.split(' - Buy ')[0] || t).substring(0, 100);
                            }
                        """)
                        status["title"] = title

                        # Extract product image
                        image = await page.evaluate("""
                            () => {
                                const imgs = Array.from(document.querySelectorAll('img'));
                                const pi = imgs.find(i => {
                                    const s = i.getAttribute('src') || '';
                                    return s.includes('rukminim') && s.includes('/image/') && !s.includes('promos');
                                });
                                return pi ? pi.getAttribute('src') : '';
                            }
                        """)
                        status["image"] = image

                        # Check if out of stock
                        is_oos = await page.evaluate("""
                            () => {
                                const t = document.body.innerText;
                                return t.includes('Out of stock') || t.includes('Currently unavailable');
                            }
                        """)
                        if is_oos:
                            status["message"] = "Out of stock"
                            results.append(status)
                            continue

                        # Flipkart uses React Native Web — "Add to cart" is a div, not a button
                        try:
                            await page.click(
                                'div[dir="auto"]:text-is("Add to cart")', timeout=5000
                            )
                        except Exception:
                            try:
                                await page.click(
                                    'button:has-text("Add to cart")', timeout=3000
                                )
                            except Exception:
                                status["message"] = "Add to Cart button not found"
                                results.append(status)
                                continue

                        await page.wait_for_timeout(3000)

                        # Check cart count from header
                        cart_count = await page.evaluate("""
                            () => {
                                const el = document.querySelector('a[href*="viewcart"] span');
                                return el ? el.innerText.trim() : '?';
                            }
                        """)

                        status["success"] = True
                        status["message"] = f"Added (cart: {cart_count})"

                    except Exception as e:
                        status["message"] = str(e)[:100]

                    results.append(status)

                # Navigate to cart page and take a full-page screenshot
                try:
                    await page.goto(
                        "https://www.flipkart.com/viewcart?marketplace=FLIPKART",
                        wait_until="load", timeout=30000,
                    )
                    await page.wait_for_timeout(3000)
                    screenshot_bytes = await page.screenshot(full_page=True)
                    cart_screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
                except Exception:
                    cart_screenshot_b64 = ""

        finally:
            self._release_session(session.id)

        return {"items": results, "cart_screenshot": cart_screenshot_b64}


# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

def _normalize_url(url_or_asin: str) -> str:
    url_or_asin = url_or_asin.strip()
    if len(url_or_asin) == 10 and url_or_asin.isalnum():
        return f"https://www.amazon.in/dp/{url_or_asin}"
    if url_or_asin.startswith("http"):
        return url_or_asin
    return f"https://www.amazon.in{url_or_asin}"


_EXTRACT_RESULTS_JS = """
(maxResults) => {
    const items = document.querySelectorAll('[data-component-type="s-search-result"]');
    const products = [];
    for (const item of items) {
        if (products.length >= maxResults) break;
        const isSponsored =
            item.querySelector('.puis-sponsored-label-text') !== null ||
            item.querySelector('[data-component-type="sp-sponsored-result"]') !== null ||
            item.innerText.includes('Sponsored');
        if (isSponsored) continue;
        const asin = item.getAttribute('data-asin') || '';
        if (!asin) continue;
        const h2 = item.querySelector('h2');
        const title = h2 ? h2.innerText.trim() : '';
        const priceEl = item.querySelector('.a-price .a-offscreen');
        const price = priceEl ? priceEl.innerText.trim() : '';
        const ratingEl = item.querySelector('.a-icon-alt');
        const rating = ratingEl ? ratingEl.innerText.trim() : '';
        const reviewEl = item.querySelector(
            'span.a-size-base.s-underline-text, a[href*="#customerReviews"] span'
        );
        const reviews = reviewEl ? reviewEl.innerText.trim() : '';
        const linkEl =
            item.querySelector('h2 a') ||
            item.querySelector('a.a-link-normal[href*="/dp/"]') ||
            item.querySelector('a[href*="/dp/"]');
        let href = linkEl ? linkEl.getAttribute('href') : '';
        if (href && !href.startsWith('http')) href = 'https://www.amazon.in' + href;
        const imgEl = item.querySelector('img.s-image');
        const image = imgEl ? imgEl.getAttribute('src') : '';
        products.push({ title, price, rating, reviews, asin, url: href, image });
    }
    return products;
}
"""


def _normalize_flipkart_url(url_or_path: str) -> str:
    url_or_path = url_or_path.strip()
    if url_or_path.startswith("http"):
        return url_or_path
    return f"https://www.flipkart.com{url_or_path}"


_EXTRACT_FLIPKART_RESULTS_JS = """
(maxResults) => {
    const containers = document.querySelectorAll('div[data-id]');
    const products = [];
    for (const item of containers) {
        if (products.length >= maxResults) break;
        const dataId = item.getAttribute('data-id') || '';
        if (!dataId) continue;

        const links = Array.from(item.querySelectorAll('a[href*="/p/"]'));
        if (!links.length) continue;

        // Title is in the link with the longest text that isn't a price or badge
        const BADGES = ['bestseller', 'best seller', 'top rated', 'popular'];
        let titleLink = null;
        let bestLen = 0;
        for (const a of links) {
            const t = (a.innerText || '').trim();
            if (t.length <= 5 || t.startsWith('\\u20b9') || t.match(/^[\\d,]+$/)) continue;
            if (BADGES.includes(t.toLowerCase())) continue;
            if (t.length > bestLen) { bestLen = t.length; titleLink = a; }
        }
        if (!titleLink) continue;

        let href = titleLink.getAttribute('href') || '';

        // Skip sponsored results (fm=neo in URL or 'Sponsored'/'Ad' text)
        if (href.includes('fm=neo') || href.includes('fm=ads')) continue;
        const allSpans = Array.from(item.querySelectorAll('span, div'));
        const hasAd = allSpans.some(el => {
            const t = (el.innerText || '').trim();
            return (t === 'Ad' || t === 'Sponsored') && el.children.length === 0;
        });
        if (hasAd) continue;

        const title = titleLink.innerText.trim().substring(0, 200);

        // Price (current)
        const priceEl = item.querySelector('div.hZ3P6w') ||
            allSpans.find(el => {
                const t = (el.innerText || '').trim();
                return t.match(/^\\u20b9[\\d,]+$/) && el.children.length === 0;
            });
        const price = priceEl ? priceEl.innerText.trim() : '';

        // Rating
        const ratingEl = item.querySelector('div.MKiFS6') ||
            allSpans.find(el => {
                const t = (el.innerText || '').trim();
                return t.match(/^\\d\\.\\d$/) && el.children.length <= 1;
            });
        const rating = ratingEl ? ratingEl.innerText.trim() : '';

        // Reviews
        const reviewEl = item.querySelector('span.PvbNMB') ||
            allSpans.find(el => {
                const t = (el.innerText || '').trim();
                return t.match(/^\\([\\d,]+\\)$/);
            });
        const reviews = reviewEl ? reviewEl.innerText.trim() : '';

        // Image
        const imgEl = item.querySelector('img[src*="flixcart"]');
        const image = imgEl ? imgEl.getAttribute('src') : '';

        // URL
        if (href && !href.startsWith('http')) href = 'https://www.flipkart.com' + href;

        products.push({ title, price, rating, reviews, pid: dataId, url: href, image });
    }
    return products;
}
"""
