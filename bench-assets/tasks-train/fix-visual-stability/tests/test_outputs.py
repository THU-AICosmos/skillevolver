import pytest
import subprocess
from playwright.sync_api import sync_playwright


class TestModeFlickerFixed:
    """Verify appearance mode flicker prevention pattern is implemented."""

    def test_no_mode_flicker(self):
        """Appearance mode should be applied fast enough to prevent visible flicker."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Check if there's an inline script that applies mode before React hydration
            page.goto("http://localhost:3000", wait_until="domcontentloaded")

            # Look for inline script pattern that prevents flicker:
            # - Should read localStorage('appearance') and apply styles/class/attribute
            # - In Next.js, this is added via dangerouslySetInnerHTML
            has_mode_script = page.evaluate("""
                () => {
                    const scripts = document.querySelectorAll('script');
                    for (const script of scripts) {
                        const content = script.textContent || script.innerHTML || '';
                        if (content.includes('localStorage') &&
                            (content.includes('appearance') || content.includes('mode')) &&
                            (content.includes('classList') || content.includes('className') ||
                             content.includes('setAttribute') || content.includes('data-mode') ||
                             content.includes('getElementById') || content.includes('style'))) {
                            return true;
                        }
                    }
                    return false;
                }
            """)
            browser.close()

        assert has_mode_script, \
            "Missing mode flicker prevention. Add inline <script> in <head> to apply appearance from localStorage before React hydrates."


class TestLayoutShiftMetrics:
    """Runtime verification of Core Web Vitals."""

    def test_cls_acceptable(self):
        """CLS should be under 0.1 (Google's 'good' threshold)."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Use correct CLS session window calculation
            page.add_init_script("""
                window.__clsVal = 0;
                let winScore = 0;
                let winBegin = 0;
                let prevShift = 0;

                new PerformanceObserver((list) => {
                    for (const entry of list.getEntries()) {
                        if (entry.hadRecentInput) continue;

                        const sec = entry.startTime / 1000;

                        const freshWindow =
                            winBegin === 0 ||
                            (sec - prevShift) > 1 ||
                            (sec - winBegin) > 5;

                        if (freshWindow) {
                            winScore = 0;
                            winBegin = sec;
                        }

                        winScore += entry.value;
                        prevShift = sec;

                        if (winScore > window.__clsVal) {
                            window.__clsVal = winScore;
                        }
                    }
                }).observe({ type: 'layout-shift', buffered: true });
            """)

            # 1. Load page
            page.goto("http://localhost:3000", wait_until="networkidle")

            # 2. Wait for late-loading content (headline at 1200ms, alert at 2800ms, sidebar, browse bar)
            page.wait_for_timeout(3500)

            # 3. Scroll to bottom
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)

            # 4. Scroll back to top
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1000)

            # 5. Trigger UI action: navigate to next page
            next_btn = page.query_selector('[data-testid="next-page-btn"]')
            if next_btn and next_btn.is_enabled():
                next_btn.click()
                page.wait_for_timeout(1000)
                prev_btn = page.query_selector('[data-testid="prev-page-btn"]')
                if prev_btn and prev_btn.is_enabled():
                    prev_btn.click()
                    page.wait_for_timeout(1000)

            # 6. Final wait for any remaining shifts
            page.wait_for_timeout(1000)

            cls = page.evaluate("window.__clsVal")
            browser.close()

        print(f"CLS value: {cls}")
        assert cls < 0.1, f"CLS is {cls}, should be under 0.1 (Google's 'good' threshold)"


class TestBlogFunctions:
    """Verify blog app still works after fixes."""

    def test_app_responds_200(self):
        """App should respond with HTTP 200."""
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "http://localhost:3000"],
            capture_output=True, text=True
        )
        assert result.stdout == "200", "App not responding"

    def test_articles_render(self):
        """Articles should be visible on page."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("http://localhost:3000", wait_until="networkidle")

            # Wait for article cards to appear
            page.wait_for_selector('[data-testid="article-card"]', timeout=8000)
            cards = page.query_selector_all('[data-testid="article-card"]')
            browser.close()

        assert len(cards) > 0, "No articles visible on page"


class TestTypographyLoading:
    """Verify font loading is optimized."""

    def test_foit_prevented(self):
        """CSS should have font-display: swap to prevent FOIT."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("http://localhost:3000", wait_until="networkidle")

            has_swap = page.evaluate("""
                () => [...document.fonts].some(f => f.display === 'swap')
            """)

            browser.close()

        assert has_swap, \
            "Missing font-display: swap. Add to @font-face rules to prevent Flash of Invisible Text (FOIT)."


class TestCoverImageDimensions:
    """Verify cover images have dimensions to prevent layout shift."""

    def test_images_no_cls(self):
        """Article cover images should have width and height attributes to prevent CLS."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("http://localhost:3000", wait_until="networkidle")

            # Wait for articles to load
            page.wait_for_selector('[data-testid="article-card"]', timeout=8000)

            img_info = page.evaluate("""
                () => {
                    const covers = document.querySelectorAll('[data-testid="article-cover"]');
                    let sized = 0;
                    for (const img of covers) {
                        const hasW = img.hasAttribute('width') || img.style.width ||
                            getComputedStyle(img).aspectRatio !== 'auto';
                        const hasH = img.hasAttribute('height') || img.style.height ||
                            getComputedStyle(img).aspectRatio !== 'auto';
                        if (hasW && hasH) sized++;
                    }
                    return { total: covers.length, sized };
                }
            """)

            browser.close()

        assert img_info['total'] > 0, "No article cover images found"
        assert img_info['sized'] == img_info['total'], \
            f"Only {img_info['sized']}/{img_info['total']} cover images have dimensions. Add width/height attributes to prevent CLS."
