"""Capture and assert the local fake-Mongo owner journey (no live Telegram)."""

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:18796"


async def main():
    shots = ROOT / "img"
    shots.mkdir(exist_ok=True)
    evidence = {}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        for label, width, height in (("desktop", 1440, 1000), ("phone", 390, 844)):
            context = await browser.new_context(viewport={"width": width, "height": height})
            # No external Telegram scripts are needed for this token-based local fixture.
            await context.route("https://telegram.org/**", lambda route: route.abort())
            page = await context.new_page()
            errors = []
            page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
            await page.goto(BASE + "/botspot/dashboard")
            await page.screenshot(path=str(shots / f"{label}-01-sign-in.png"), full_page=True)
            await page.get_by_text("Use a dashboard token").click()
            await page.get_by_label("Dashboard token").fill("wrong")
            await page.get_by_role("button", name="Open", exact=True).click()
            await page.get_by_role("status").filter(has_text="Owner access required").wait_for()
            await page.screenshot(path=str(shots / f"{label}-02-wrong-token.png"), full_page=True)
            await page.get_by_label("Dashboard token").fill("local")
            await page.get_by_role("button", name="Open", exact=True).click()
            await page.get_by_role("heading", name="Usage", exact=True).wait_for()
            await page.screenshot(path=str(shots / f"{label}-03-usage.png"), full_page=True)
            layout = await page.evaluate("""() => ({width:innerWidth, scroll:document.documentElement.scrollWidth,
              tables:[...document.querySelectorAll('table')].map(t=>({width:t.getBoundingClientRect().width, wrap:t.parentElement.clientWidth}))})""")
            assert layout["scroll"] == width, layout
            assert all(row["width"] <= row["wrap"] + 1 for row in layout["tables"]), layout
            await (
                page.get_by_role("link", name="errors", exact=False)
                .filter(has_text="errors")
                .click()
            )
            await page.locator("#errors .trace").first.click()
            await page.locator("dialog[open]").wait_for()
            await page.screenshot(path=str(shots / f"{label}-04-traceback.png"), full_page=True)
            await page.keyboard.press("Escape")
            assert not await page.locator("dialog").is_visible()
            await page.locator("#errors .trace").first.click()
            await page.get_by_role("button", name="Close", exact=True).click()
            assert not await page.locator("dialog").is_visible()
            await page.locator("#errors a").first.click()
            await page.get_by_role("heading", name="Logs", exact=True).first.wait_for()
            assert "request_id=" in page.url
            await page.locator("table .trace").first.wait_for()
            await page.screenshot(path=str(shots / f"{label}-05-request-logs.png"), full_page=True)
            await page.get_by_role("link", name="Clear", exact=True).click()
            await page.get_by_label("Level", exact=True).select_option("ERROR")
            await page.get_by_label("Text", exact=True).fill("YouTube")
            await page.get_by_role("button", name="Filter", exact=True).click()
            await page.locator("table .trace").first.wait_for()
            await page.locator("th").first.click()
            assert await page.locator("th").first.get_attribute("aria-sort") == "descending"
            more = page.get_by_role("button", name="more")
            if await more.count():
                await more.first.click()
            await page.screenshot(path=str(shots / f"{label}-06-filtered-logs.png"), full_page=True)
            log_layout = await page.evaluate("""() => ({width:innerWidth, scroll:document.documentElement.scrollWidth,
              tables:[...document.querySelectorAll('table')].map(t=>({width:t.getBoundingClientRect().width, wrap:t.parentElement.clientWidth}))})""")
            assert log_layout["scroll"] == width, log_layout
            assert all(row["width"] <= row["wrap"] + 1 for row in log_layout["tables"]), log_layout
            await page.get_by_role("link", name="Bots", exact=True).click()
            assert await page.get_by_role("link", name="example_bot", exact=True).count() == 1
            assert "other_owner_bot" not in await page.locator("main").inner_text()
            await page.screenshot(path=str(shots / f"{label}-07-bots.png"), full_page=True)
            await page.get_by_role("link", name="Usage", exact=True).click()
            await page.get_by_role("link", name="Today", exact=True).click()
            result = await page.request.get(BASE + "/botspot/api/usage?days=1")
            assert result.status == 200
            report = await result.json()
            assert report["period"]["days"] == 1
            assert report["day"][0]["key"] == report["period"]["since"][:10]
            timing = await page.evaluate(
                """() => {const n=performance.getEntriesByType('navigation')[0];return {response_ms:n.responseEnd-n.requestStart, dom_ms:n.domContentLoadedEventEnd-n.startTime}}"""
            )
            assert not errors, errors
            evidence[label] = {
                "viewport": [width, height],
                "usage_layout": layout,
                "logs_layout": log_layout,
                "today_requests": report["total"]["requests"],
                "timing_fake_mongo_only": timing,
                "javascript_errors": errors,
                "checks": [
                    "wrong token denied",
                    "signed session",
                    "usage",
                    "error anchor",
                    "traceback Esc and close",
                    "request to logs",
                    "literal filters",
                    "sorting and expand",
                    "owner-only registry",
                    "return to Today",
                ],
            }
            await context.close()
        await browser.close()
    (ROOT / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


asyncio.run(main())
