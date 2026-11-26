"""Run with uv run --with playwright==1.62 python -m tests.browser_learning."""

import os
import socket
import sqlite3
import tempfile
import threading
import time
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import uvicorn
from playwright.sync_api import expect, sync_playwright

from app import catalog
from app.main import app
from scripts.build_catalog import write_catalog


def exercise(browser, url):
    desktop = browser.new_context(viewport={"width": 1366, "height": 850})
    mobile = browser.new_context(viewport={"width": 393, "height": 852}, has_touch=True, is_mobile=True)
    pc, phone = desktop.new_page(), mobile.new_page()
    for page in (pc, phone):
        page.route("https://fonts.**/*", lambda route: route.abort())
        page.goto(url + "/#/vocab")
        expect(page.locator(".vocab-head")).to_contain_text("1/")
    pc.get_by_role("button", name="下一页").click()
    expect(pc.locator(".vocab-head")).to_contain_text("2/")
    phone.get_by_role("button", name="下一页").click()
    expect(phone.locator(".vocab-head")).to_contain_text("2/")
    expect(phone.locator(".error")).to_have_count(0)
    pc.get_by_role("button", name="下一页").click()
    expect(pc.locator(".vocab-head")).to_contain_text("3/")
    pc.get_by_role("button", name="下一页").click()
    expect(pc.locator(".vocab-head")).to_contain_text("4/")
    phone.get_by_role("button", name="下一页").click()
    expect(phone.locator(".error")).to_contain_text("另一端")
    expect(phone.locator(".vocab-head")).to_contain_text("4/")

    touch = mobile.new_cdp_session(phone)
    def swipe(selector):
        box = phone.locator(selector).bounding_box()
        x, y = box["x"] + box["width"] * .75, box["y"] + 12
        for event, points in [("touchStart", [{"x": x, "y": y}]),
                              ("touchMove", [{"x": x - 90, "y": y + 1}]), ("touchEnd", [])]:
            touch.send("Input.dispatchTouchEvent", {"type": event, "touchPoints": points})
    swipe(".study-deck")
    expect(phone.locator(".vocab-head")).to_contain_text("5/")
    expect(phone.locator(".error")).to_have_count(0)
    pc.reload()
    expect(pc.locator(".vocab-head")).to_contain_text("5/")
    total = int(pc.locator(".vocab-head .kicker").inner_text().split("/")[-1])
    for index in range(6, total + 1):
        pc.locator(".study-deck").press("ArrowRight")
        expect(pc.locator(".vocab-head")).to_contain_text(f"{index}/")
    pc.get_by_role("button", name="去回忆这些词").click()
    phone.reload()
    expect(phone.locator(".recall-card.is-front")).to_be_visible()
    swipe(".vocab-flip")
    expect(phone.locator(".vocab-head")).to_contain_text("2/")
    expect(phone.locator(".recall-card.is-front")).to_be_visible()
    expect(phone.locator(".grade")).to_have_count(0)
    pc.get_by_role("button", name="翻开看中文").click()
    def lose_ack(route):
        route.fetch()
        route.abort()
    pc.route("**/result", lose_ack, times=1)
    pc.get_by_role("button", name="记得", exact=True).click()
    expect(pc.locator(".error")).to_be_visible()
    pc.get_by_role("button", name="记得", exact=True).click()
    expect(pc.locator(".vocab-head")).to_contain_text("2/")
    assert len(pc.request.get(url + "/api/review/log").json()["items"]) == 1

    phone.goto(url + "/#/reading")
    expect(phone.locator(".passage-card")).to_be_visible()
    phone.locator(".passage-card .mark").first.click()
    expect(phone.locator(".gloss-card")).to_be_visible()
    phone.keyboard.press("Escape")
    swipe(".study-deck")
    expect(phone.locator(".study-deck .kicker").first).to_contain_text("第 2")
    expect(phone.locator(".quiz-card")).to_be_visible()
    assert phone.evaluate("document.documentElement.scrollWidth <= innerWidth")

    pc.goto(url + "/#/vocab/library")
    search = pc.get_by_placeholder("搜英文或中文")
    expect(search).to_be_visible()
    pending = []
    pc.route("**/api/feed?**q=slow**", lambda route: pending.append(route))
    with pc.expect_request("**/api/feed?**q=slow**"):
        search.fill("slow")
    search.fill("travel")
    expect(pc.locator(".list li")).to_have_count(7)
    pending[0].fulfill(json={"items": [], "total": 0})
    pc.get_by_role("button", name="再看 7 条").click()
    expect(pc.locator(".list li")).to_have_count(14)
    assert len(set(pc.locator(".list .english").all_text_contents())) == 14
    search.fill("")
    for label, sample in [("商务", "work"), ("阅读", "read")]:
        pc.locator("#view").get_by_role("button", name=label, exact=True).click()
        expect(pc.locator(".list .english").first).to_have_text(sample)
    for name in ("talk", "progress", "today"):
        phone.goto(url + "/#/" + name)
        expect(phone.locator("#view .card").first).to_be_visible()
        assert phone.evaluate("document.documentElement.scrollWidth <= innerWidth")
    phone.goto(url + "/#/talk")
    phone.locator("#talk-input").fill("A small coffee, please. Thank you.")
    phone.locator(".talk-actions .primary").click()
    expect(phone.locator(".talk-ok")).to_be_visible()
    phone.get_by_role("button", name="去做复盘", exact=True).click()
    phone.get_by_role("button", name="完成本课，接着下一课").click()
    expect(phone.locator(".today-task")).to_contain_text("问候")
    pc.goto(url + "/#/today")
    expect(pc.locator(".today-task")).to_contain_text("问候")
    for selector in (".today-task h1", ".today-task .audio-tag", ".today-task .primary"):
        ratio = pc.locator(selector).first.evaluate("""el => {
          function luminance(color) {
            const rgb = color.match(/[0-9.]+/g).slice(0, 3).map(n => Number(n) / 255);
            const [r, g, b] = rgb.map(c => c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4);
            return .2126 * r + .7152 * g + .0722 * b;
          }
          let parent = el;
          while (getComputedStyle(parent).backgroundColor === "rgba(0, 0, 0, 0)") parent = parent.parentElement;
          const a = luminance(getComputedStyle(el).color), b = luminance(getComputedStyle(parent).backgroundColor);
          return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
        }""")
        assert ratio >= 4.5, (selector, ratio)
    pc.locator(".today-lesson-btn.is-done").first.click()
    pc.locator(".step-nav").get_by_role("button", name="听读").click()
    pc.locator(".choice").first.click()
    expect(pc.locator(".choice.is-on")).to_be_visible()
    assert pc.request.get(url + "/api/today").json()["lesson_id"] == "greetings-a1"
    desktop.close()
    mobile.close()


def main():
    with tempfile.TemporaryDirectory() as folder, socket.socket() as sock:
        database = Path(folder) / "catalog.db"
        with closing(sqlite3.connect(database)) as conn:
            travel = [{"english": f"travel {i}", "chinese": "旅行"} for i in range(18)]
            write_catalog(conn, [], travel, [{"english": "work", "chinese": "工作"}], [("read", "读", "")])
        sock.bind(("127.0.0.1", 0))
        url = f"http://127.0.0.1:{sock.getsockname()[1]}"
        with patch.dict(os.environ, SELF_ENGLISH_LEARNING_DB=str(Path(folder) / "learning.db")), patch.object(catalog, "DB_PATH", database):
            server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
            thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
            thread.start()
            try:
                for _ in range(100):
                    if server.started:
                        break
                    time.sleep(.05)
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(executable_path=os.getenv("STUDY_TEST_CHROME"))
                    exercise(browser, url)
                    browser.close()
            finally:
                server.should_exit = True
                thread.join(10)


if __name__ == "__main__":
    main()
