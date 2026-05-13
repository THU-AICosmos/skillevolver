import pytest
import httpx
import time
from playwright.sync_api import Page


BASE = "http://localhost:3000"


class TestPagePerformance:
    @pytest.mark.asyncio
    async def test_homepage_loads_fast(self):
        """Homepage should load in under 800ms (requires parallel fetches)."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Warmup request
            await client.get(BASE)

            # Measure second request
            start = time.time()
            r = await client.get(BASE)
            elapsed = (time.time() - start) * 1000
            assert r.status_code == 200
            assert elapsed < 800, f"Page took {elapsed:.0f}ms (should be <800ms)"

    @pytest.mark.asyncio
    async def test_homepage_has_articles(self):
        """Page should render article feed data."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(BASE)
            assert "Article" in r.text


class TestAPIPerformance:
    @pytest.mark.asyncio
    async def test_articles_api_fast(self):
        """Articles API should respond quickly (optimize away unnecessary blocking fetches)."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            start = time.time()
            r = await client.get(f"{BASE}/api/articles")
            elapsed = (time.time() - start) * 1000
            assert r.status_code == 200
            assert elapsed < 1000, f"Articles API took {elapsed:.0f}ms (should be <1000ms)"

    @pytest.mark.asyncio
    async def test_subscribe_fast(self):
        """Subscribe endpoint should optimize parallel fetching."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            start = time.time()
            r = await client.post(f"{BASE}/api/subscribe", json={})
            elapsed = (time.time() - start) * 1000
            assert r.status_code == 200
            assert elapsed < 800, f"Subscribe took {elapsed:.0f}ms (should be <800ms)"

    @pytest.mark.asyncio
    async def test_external_api_actually_called(self):
        """Verify external API delays are actually being executed at runtime.

        Subscribe request must take at least 380ms because it calls fetchReaderFromService (380ms)
        plus either fetchPreferencesFromService (560ms) or fetchReaderDigestFromService (280ms).
        This prevents cheating by caching responses or bypassing the API entirely.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            start = time.time()
            r = await client.post(f"{BASE}/api/subscribe", json={})
            elapsed = (time.time() - start) * 1000
            assert r.status_code == 200
            # Must take at least 380ms - proves external API delays are being called
            # Subscribe calls reader(380ms), preferences(560ms), digest(280ms) - even optimized takes 560ms+
            assert elapsed >= 380, f"Subscribe API too fast ({elapsed:.0f}ms) - external API may be bypassed"


class TestClientPerformance:
    def test_memoization_limits_rerenders(self, page: Page):
        """Bookmarking articles should not re-render all ArticleCards.

        Uses performance.mark() calls in ArticleCard to count renders.
        Without memoization: ~180 renders for 5 bookmark actions (36 cards * 5)
        With memoization: ~10 renders (only changed cards re-render)
        """
        page.goto(BASE)
        page.wait_for_selector('[data-testid="bookmarks-count"]')

        # Clear marks from initial render
        page.evaluate("performance.clearMarks()")

        # Bookmark 5 articles
        buttons = page.locator('[data-testid^="bookmark-article-"]')
        for i in range(min(5, buttons.count())):
            buttons.nth(i).click()
            page.wait_for_timeout(100)

        # Count all render marks (cleared before bookmarks, so only ArticleCard marks remain)
        render_count = page.evaluate("""
            performance.getEntriesByType('mark').length
        """)

        assert render_count > 0, "No render marks detected - performance.mark calls may have been removed"
        assert render_count < 50, f"Too many re-renders: {render_count} (should be <50 with memoization)"


class TestBundleOptimization:
    def test_trends_page_initial_bundle_small(self, page: Page):
        """Trends page initial JS should be under 400KB.

        Without optimization: ~800KB+ (lodash 70KB + mathjs 700KB loaded eagerly)
        With optimization: <400KB (heavy libraries loaded on demand)
        """
        js_bytes = []

        def handle_response(response):
            if response.url.endswith('.js') and response.status == 200:
                try:
                    body = response.body()
                    js_bytes.append(len(body))
                except:
                    pass

        page.on('response', handle_response)
        page.goto(f"{BASE}/trends")
        page.wait_for_selector('[data-testid="tab-headlines"]')

        total_js_kb = sum(js_bytes) / 1024
        assert total_js_kb < 400, f"Initial JS bundle is {total_js_kb:.0f}KB (should be <400KB)"


class TestFunctionality:
    """Verify the app remains fully functional after performance optimizations."""

    def test_testids_preserved(self, page: Page):
        """Critical data-testid attributes must not be removed."""
        page.goto(BASE)
        assert page.locator('[data-testid="bookmarks-count"]').count() > 0, "bookmarks-count testid missing"
        assert page.locator('[data-testid^="bookmark-article-"]').count() > 0, "bookmark-article testid missing"

        page.goto(f"{BASE}/trends")
        assert page.locator('[data-testid="tab-headlines"]').count() > 0, "tab-headlines testid missing"
        assert page.locator('[data-testid="tab-deepdive"]').count() > 0, "tab-deepdive testid missing"

    def test_bookmark_article(self, page: Page):
        """Bookmarking an article should update the bookmarks count."""
        page.goto(BASE)
        page.wait_for_selector('[data-testid="bookmarks-count"]')

        # Get initial count (should be 0)
        count_text = page.locator('[data-testid="bookmarks-count"]').text_content()
        assert "0" in count_text, "Bookmarks count should start at zero"

        # Bookmark an article
        page.locator('[data-testid^="bookmark-article-"]').first.click()
        page.wait_for_timeout(200)

        # Verify count updated
        count_text = page.locator('[data-testid="bookmarks-count"]').text_content()
        assert "1" in count_text, "Bookmarks count should have 1 article after bookmarking"

    def test_trends_page_works(self, page: Page):
        """Trends page should display articles and allow tab switching."""
        page.goto(f"{BASE}/trends")
        page.wait_for_selector('[data-testid="tab-headlines"]')

        # Click deep-dive tab - verifies tab switching works
        page.locator('[data-testid="tab-deepdive"]').click()
        page.wait_for_timeout(500)

        # Verify deep-dive tab content loaded via testid
        assert page.locator('[data-testid="deepdive-content"]').count() > 0, \
            "Deep-dive tab content should be visible after clicking"

    def test_real_article_data_rendered(self, page: Page):
        """Page must render real article data: 'Article' text, 'min read' labels, and 'Bookmark' buttons."""
        page.goto(BASE)
        content = page.content()
        assert "Article" in content, "Page must show 'Article' text"
        assert "min read" in content, "Page must show 'min read' labels"
        assert "Bookmark" in content, "Page must have 'Bookmark' buttons"
