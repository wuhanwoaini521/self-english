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


def expect_pixel_book(page):
    expect(page.locator(".study-deck")).to_be_visible()
    assert "linear-gradient" in page.evaluate("getComputedStyle(document.body).backgroundImage")
    colors = page.evaluate(r"""() => {
      const values = [
        getComputedStyle(document.body).backgroundImage,
        getComputedStyle(document.querySelector('.study-deck > .card')).backgroundColor,
        getComputedStyle(document.querySelector('.deck-arrow.next')).color,
        getComputedStyle(document.querySelector('.tabbar')).backgroundColor,
      ];
      return values.flatMap(value => [...value.matchAll(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/g)]
        .map(match => match.slice(1, 4).map(Number)));
    }""")
    assert colors
    assert all(red == green == blue for red, green, blue in colors), colors
    pixel_layers = page.evaluate("""() => ['::before', '::after'].map(pseudo =>
      getComputedStyle(document.body, pseudo).backgroundImage)""")
    assert any(value != "none" for value in pixel_layers)
    layers = page.evaluate("""() => ['::before', '::after'].map(pseudo => {
      const style = getComputedStyle(document.querySelector('.study-deck'), pseudo);
      return {transform: style.transform, animation: style.animationName, transition: style.transitionDuration};
    })""")
    assert all(layer["transform"] != "none" for layer in layers)
    top = page.locator(".study-deck > .card").evaluate("""el => ({
      shadow: getComputedStyle(el).boxShadow,
      filter: getComputedStyle(el).filter,
    })""")
    assert top["shadow"] != "none"
    assert top["filter"] == "none"
    arrows = page.locator(".study-deck .deck-arrow")
    expect(arrows).to_have_count(2)
    for arrow in [arrows.first, arrows.last]:
        expect(arrow).to_be_visible()
        box = arrow.bounding_box()
        assert box["width"] >= 44 and box["height"] >= 44
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    return layers


def exercise(browser, url):
    desktop = browser.new_context(viewport={"width": 1366, "height": 850})
    mobile = browser.new_context(viewport={"width": 393, "height": 852}, has_touch=True, is_mobile=True)
    pc, phone = desktop.new_page(), mobile.new_page()
    first = "cet4-01-drop-course"
    for page in (pc, phone):
        page.route("https://fonts.**/*", lambda route: route.abort())
        page.goto(url + "/#/vocab")
        expect(page.locator(".vocab-word")).to_be_visible()
        expect(page.locator(".step-nav")).to_have_count(0)
        expect_pixel_book(page)

    pc.goto(url + "/#/reading")
    phone.goto(url + "/#/reading")
    expect(pc.get_by_role("heading", name="长篇精读")).to_be_visible()
    expect(pc.locator(".today-lesson-btn")).to_have_count(6)
    expect(phone.locator(".today-lesson-btn")).to_have_count(6)
    assert phone.evaluate("document.documentElement.scrollWidth <= innerWidth")

    pc.locator(".today-lesson-btn").first.click()
    phone.locator(".today-lesson-btn").first.click()
    expect(pc.locator(".passage-card")).to_be_visible()
    expect(pc.locator(".passage-card .passage-block")).to_have_count(1)
    expect(pc.locator(".study-deck")).to_have_count(1)
    expect(phone.locator(".passage-card")).to_be_visible()
    expect(phone.locator(".passage-card .passage-block")).to_have_count(1)
    assert pc.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert phone.evaluate("document.documentElement.scrollWidth <= innerWidth")
    expect(pc.get_by_role("button", name="会", exact=True)).to_have_count(0)

    pc_deck = pc.locator(".study-deck")
    first_paragraph = pc.locator(".passage-block .sentence").inner_text()
    expect(pc_deck).to_have_attribute("aria-label", "阅读，第 1 页，共 3 页")
    expect(pc_deck.locator(".deck-arrow.prev")).to_be_disabled()
    pc_deck.locator(".deck-arrow.next").click()
    expect(pc.locator(".study-deck")).to_have_attribute("aria-label", "阅读，第 2 页，共 3 页")
    assert pc.locator(".passage-block .sentence").inner_text() != first_paragraph
    pc.locator(".study-deck .deck-arrow.prev").click()
    expect(pc.locator(".passage-block .sentence")).to_have_text(first_paragraph)

    pc.locator(".study-deck").focus()
    pc.keyboard.press("ArrowRight")
    expect(pc.locator(".study-deck")).to_have_attribute("aria-label", "阅读，第 2 页，共 3 页")
    pc.keyboard.press("ArrowLeft")
    expect(pc.locator(".study-deck")).to_have_attribute("aria-label", "阅读，第 1 页，共 3 页")
    pc.locator(".study-deck .deck-arrow.next").click()
    pc.locator(".study-deck .deck-arrow.next").click()
    expect(pc.locator(".study-deck")).to_have_attribute("aria-label", "阅读，第 3 页，共 3 页")
    expect(pc.locator(".study-deck .deck-arrow.next")).to_be_disabled()
    pc.locator(".study-deck .deck-arrow.prev").click()
    pc.locator(".study-deck .deck-arrow.prev").click()
    expect(pc.locator(".study-deck")).to_have_attribute("aria-label", "阅读，第 1 页，共 3 页")

    pc.locator(".passage-card .speak").click()
    expect(pc.locator(".study-deck")).to_have_attribute("aria-label", "阅读，第 1 页，共 3 页")
    before = pc.locator(".passage-card .mark").count()
    assert before >= 1
    pc.locator(".passage-card .mark").first.click()
    expect(pc.locator(".study-deck")).to_have_attribute("aria-label", "阅读，第 1 页，共 3 页")
    expect(pc.locator(".gloss-card")).to_be_visible()
    expect(pc.get_by_role("button", name="会", exact=True)).to_be_visible()
    expect(pc.get_by_role("button", name="不会", exact=True)).to_have_count(0)
    held_refresh = {}
    def hold_article_refresh(route):
        held_refresh["route"] = route
    pc.route(f"**/api/readings/{first}", hold_article_refresh)
    pc.locator(".passage-card").evaluate("el => window.stablePassageBeforeMark = el")
    with pc.expect_request(f"**/api/readings/{first}"):
        pc.get_by_role("button", name="会", exact=True).click()
    expect(pc.locator(".gloss-card")).to_have_count(0)
    try:
        assert pc.evaluate("document.querySelector('.passage-card') === window.stablePassageBeforeMark")
        expect(pc.locator(".loading")).to_have_count(0)
    finally:
        held_refresh["route"].continue_()
    pc.unroute(f"**/api/readings/{first}")
    pc.wait_for_function(f"document.querySelectorAll('.passage-card .mark').length < {before}")
    assert pc.evaluate("document.querySelector('.passage-card') === window.stablePassageBeforeMark")
    after = pc.locator(".passage-card .mark").count()
    assert after < before

    phone_deck = phone.locator(".study-deck")
    phone_deck.evaluate("""deck => {
      const start = {bubbles: true, isPrimary: true, pointerId: 7, pointerType: 'touch', button: 0, buttons: 1, clientX: 200, clientY: 200};
      deck.dispatchEvent(new PointerEvent('pointerdown', start));
      deck.dispatchEvent(new PointerEvent('pointerup', {...start, buttons: 0, clientY: 320}));
    }""")
    expect(phone.locator(".study-deck")).to_have_attribute("aria-label", "阅读，第 1 页，共 3 页")
    phone_deck.evaluate("""deck => {
      const start = {bubbles: true, isPrimary: true, pointerId: 8, pointerType: 'touch', button: 0, buttons: 1, clientX: 200, clientY: 200};
      deck.dispatchEvent(new PointerEvent('pointerdown', start));
      deck.dispatchEvent(new PointerEvent('pointerup', {...start, buttons: 0, clientX: 80}));
    }""")
    expect(phone.locator(".study-deck")).to_have_attribute("aria-label", "阅读，第 2 页，共 3 页")
    phone.locator(".study-deck .deck-arrow.prev").click()
    expect(phone.locator(".study-deck")).to_have_attribute("aria-label", "阅读，第 1 页，共 3 页")
    phone.locator(".study-deck .deck-arrow.next").scroll_into_view_if_needed()
    assert phone.evaluate("scrollY") > 0
    phone.locator(".study-deck .deck-arrow.next").click()
    expect(phone.locator(".study-deck")).to_have_attribute("aria-label", "阅读，第 2 页，共 3 页")
    phone.wait_for_function("""() => {
      const rect = document.querySelector('.passage-block').getBoundingClientRect();
      return rect.top >= 0 && rect.top < innerHeight;
    }""")
    phone.locator(".study-deck .deck-arrow.prev").click()
    expect(phone.locator(".study-deck")).to_have_attribute("aria-label", "阅读，第 1 页，共 3 页")
    phone.reload()
    expect(phone.locator(".passage-card .mark")).to_have_count(after)

    phone.goto(url + "/#/vocab")
    expect(phone.locator(".vocab-word")).to_be_visible()
    pc.goto(url + "/#/vocab")
    expect(pc.locator(".vocab-word")).to_be_visible()
    expect(pc.locator(".vocab-grades .gloss-mark-btn")).to_contain_text("会")
    pc.emulate_media(reduced_motion="reduce")
    reduced_layers = pc.evaluate("""() => ['::before', '::after'].map(pseudo => {
      const style = getComputedStyle(document.querySelector('.study-deck'), pseudo);
      return {animation: style.animationName, transition: style.transitionDuration};
    })""")
    assert all(layer["animation"] == "none" and layer["transition"] == "0s" for layer in reduced_layers)
    pc.locator(".study-deck .deck-arrow.next").click()
    assert "第 2 页" in pc.locator(".study-deck").get_attribute("aria-label")
    pc.locator(".study-deck .deck-arrow.prev").click()
    pc.emulate_media(reduced_motion="no-preference")

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
        expect(phone.locator(".step-nav")).to_have_count(0)

    phone.goto(url + "/#/talk")
    expect(phone.get_by_role("heading", name="选一个话题")).to_be_visible()
    phone.locator(".today-lesson-btn").first.click()
    phone.locator("#talk-input").fill("I will drop the course before the deadline because the workload is too heavy.")
    phone.locator(".talk-actions .primary").click()
    expect(phone.locator(".talk-ok")).to_be_visible()

    pc.goto(url + "/#/today")
    expect(pc.locator(".today-task")).to_contain_text("这门选修该不该退")
    expect(pc.locator(".today-task .primary")).to_contain_text("阅读")
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

    pc.goto(url + f"/#/reading/{first}")
    expect(pc.locator(".quiz-card")).to_be_visible()
    pc.locator(".choice").first.click()
    expect(pc.locator(".choice.is-on")).to_be_visible()
    pc.get_by_role("button", name="读完了", exact=True).click()
    expect(pc.get_by_role("button", name="已经读完", exact=True)).to_be_visible()
    assert pc.request.get(url + "/api/today").json()["lesson_id"] != first
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
                thread.join(timeout=2)


if __name__ == "__main__":
    main()
