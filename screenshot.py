# -*- coding: utf-8 -*-
"""Dashboard feature screenshot capture"""
import time
import os
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5000"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
os.makedirs(OUT_DIR, exist_ok=True)


def shot(page, name, clip=None, full_page=False):
    path = os.path.join(OUT_DIR, name)
    if full_page:
        page.screenshot(path=path, full_page=True)
    else:
        page.screenshot(path=path, clip=clip)
    print(f"[OK] {name}")


def click_btn(page, btn_id):
    """Click a button by ID via JS to avoid encoding issues in selectors."""
    page.evaluate(f"document.getElementById('{btn_id}').click()")


def take_screenshots():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
        )
        page = ctx.new_page()

        # Load and wait for data
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_selector("#kpi1:not(:empty)", timeout=10000)
        time.sleep(1.5)

        # 1. Full dashboard overview
        shot(page, "01_overview.png", full_page=True)

        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.4)

        # 2. Header + KPI cards
        kpi_box = page.locator("#kpi-row").bounding_box()
        shot(page, "02_kpi_cards.png", clip={
            "x": 0, "y": 0,
            "width": 1440,
            "height": int(kpi_box["y"] + kpi_box["height"] + 32),
        })

        # 3. Search & filter row
        sf_box = page.locator("#search-filter-row").bounding_box()
        shot(page, "03_search_filter.png", clip={
            "x": 0,
            "y": int(sf_box["y"] - 8),
            "width": 1440,
            "height": int(sf_box["height"] + 24),
        })

        # 4. Charts (bar + doughnut)
        bar_box = page.locator("#chart-bar-card").bounding_box()
        pie_box = page.locator("#chart-pie-card").bounding_box()
        top = min(bar_box["y"], pie_box["y"]) - 8
        bottom = max(bar_box["y"] + bar_box["height"],
                     pie_box["y"] + pie_box["height"]) + 12
        shot(page, "04_charts.png", clip={
            "x": 0, "y": int(top),
            "width": 1440, "height": int(bottom - top),
        })

        # 5. Ranking table
        page.locator("#rank-table-card").scroll_into_view_if_needed()
        time.sleep(0.4)
        tbl_box = page.locator("#rank-table-card").bounding_box()
        shot(page, "05_ranking_table.png", clip={
            "x": 0, "y": int(tbl_box["y"] - 4),
            "width": 1440, "height": min(860, int(tbl_box["height"] + 16)),
        })

        # Scroll search into view
        page.locator("#search-filter-row").scroll_into_view_if_needed()
        time.sleep(0.3)
        sf_box2 = page.locator("#search-filter-row").bounding_box()

        # 6 & 7: Use a tall viewport so filter + table are both visible
        page.set_viewport_size({"width": 1440, "height": 2000})
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.3)

        # 6. Region search results (서초)
        page.locator("#searchInput").fill("서초")   # 서초
        page.wait_for_timeout(700)
        sf_box_6 = page.locator("#search-filter-row").bounding_box()
        tbl_box_6 = page.locator("#rank-table-card").bounding_box()
        top6 = int(sf_box_6["y"] - 10)
        bot6 = int(tbl_box_6["y"] + min(tbl_box_6["height"], 380) + 16)
        shot(page, "06_search_region.png", clip={
            "x": 0, "y": top6, "width": 1440, "height": bot6 - top6,
        })

        # 7. Apartment name search (래미안)
        page.locator("#searchInput").fill("래미안")   # 래미안
        page.wait_for_timeout(1000)
        tbl_box_7 = page.locator("#rank-table-card").bounding_box()
        sf_box_7 = page.locator("#search-filter-row").bounding_box()
        top7 = int(sf_box_7["y"] - 10)
        bot7 = int(tbl_box_7["y"] + min(tbl_box_7["height"], 500) + 16)
        shot(page, "07_search_apt.png", clip={
            "x": 0, "y": top7, "width": 1440, "height": bot7 - top7,
        })

        # Restore viewport
        page.set_viewport_size({"width": 1440, "height": 900})

        # Clear and reset
        page.evaluate("clearSearch()")
        page.wait_for_timeout(400)

        # 8. Seoul filter active
        click_btn(page, "btn-서울")   # 서울
        page.wait_for_timeout(700)
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.4)
        shot(page, "08_filter_seoul.png", clip={
            "x": 0, "y": 0, "width": 1440, "height": 900,
        })

        # 9. Score explanation section
        click_btn(page, "btn-전체")   # 전체
        page.wait_for_timeout(300)
        page.locator("#score-explain-card").scroll_into_view_if_needed()
        time.sleep(0.6)
        explain_box = page.locator("#score-explain-card").bounding_box()
        shot(page, "09_score_explanation.png", clip={
            "x": 0,
            "y": max(0, int(explain_box["y"] - 10)),
            "width": 1440,
            "height": min(860, int(explain_box["height"] + 20)),
        })

        browser.close()


if __name__ == "__main__":
    take_screenshots()
    print("\n[DONE] Screenshots saved -> screenshots/")
