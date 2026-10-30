"""End-to-end browser walkthrough + screenshots (Playwright, headless Chromium).

Requires the app running (API :8000, frontend :4173 or set BASE_URL) on a freshly
seeded database.  Usage:  python scripts/browser_e2e.py
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("BASE_URL", "http://localhost:4173")
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
problems: list[str] = []


def watch(page):
    page.on("console", lambda m: m.type == "error" and problems.append(f"console: {m.text}"))
    page.on("response", lambda r: r.status >= 400 and "/api/" in r.url and problems.append(f"HTTP {r.status} {r.url}"))
    page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))


def shot(page, name, full=False):
    page.wait_for_timeout(400)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
    print("saved", name)


def login(page, label):
    page.goto(f"{BASE}/login")
    page.get_by_role("button", name=label).click()


def send(page, text):
    box = page.get_by_label("Message VSR AI Assistant")
    box.fill(text)
    with page.expect_response(lambda r: r.url.endswith("/api/chat") and r.request.method == "POST") as resp:
        box.press("Enter")
    assert resp.value.ok, f"chat failed: {resp.value.status}"
    page.wait_for_timeout(500)


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    page = ctx.new_page()
    watch(page)

    page.goto(BASE)
    expect(page.get_by_role("heading", name="Customer support that shows its work.")).to_be_visible()
    shot(page, "01-landing", full=True)
    page.goto(f"{BASE}/login")
    expect(page.get_by_text("Demo accounts")).to_be_visible()
    shot(page, "02-sign-in")

    # ---- customer: Pardha
    login(page, "Pardha Saradhi (customer)")
    page.wait_for_url("**/app/chat")
    expect(page.get_by_text("what can I help with?")).to_be_visible()
    shot(page, "03-chat-empty")

    send(page, "Where is my order ORD-1001?")
    expect(page.get_by_text("expected to arrive on")).to_be_visible()
    send(page, "Can I return it?")
    expect(page.get_by_text("Using ORD-1001 from earlier")).to_be_visible()  # memory
    send(page, "What about ORD-1002, can I return that one?")
    expect(page.get_by_text("is eligible for return")).to_be_visible()
    page.get_by_role("button", name="policy source").last.click()
    shot(page, "04-chat-memory-route-strip-citations")
    send(page, "I'd like a refund for it, the strap broke")
    expect(page.get_by_text("is waiting for admin approval")).to_be_visible()
    expect(page.get_by_text("return shipping fee is waived")).to_be_visible()  # "broke" = defective
    shot(page, "05-chat-refund-pending-approval")

    page.get_by_role("button", name="New conversation").click()
    send(page, "Recommend noise-cancelling headphones under $300")
    expect(page.get_by_text("Here are my top picks")).to_be_visible()
    shot(page, "06-chat-product-recommendations")
    page.get_by_role("button", name="New conversation").click()
    send(page, "Do you offer student discounts?")
    expect(page.get_by_text("couldn't find that in VSR Store's policy documents")).to_be_visible()
    shot(page, "07-chat-abstains-unsupported")
    # cross-customer protection, through the UI
    send(page, "Where is ORD-1006?")
    expect(page.get_by_text("couldn't find order ORD-1006 on your account")).to_be_visible()

    page.get_by_role("link", name="My orders").click()
    expect(page.get_by_text("ORD-1001").first).to_be_visible()
    shot(page, "08-my-orders")
    page.get_by_role("link", name="Returns & refunds").click()
    expect(page.get_by_role("heading", name="Refund requests")).to_be_visible()
    expect(page.get_by_text("pending").first).to_be_visible()
    shot(page, "09-returns-refunds")
    page.get_by_role("link", name="Product catalog").click()
    expect(page.get_by_text("Halden Aria Pro Headphones")).to_be_visible()
    shot(page, "10-product-catalog")
    page.get_by_role("link", name="AI evaluation").click()
    expect(page.get_by_text("Intent routing accuracy")).to_be_visible()
    shot(page, "11-evaluation-dashboard", full=True)

    # customer cannot reach the admin dashboard (client guard)
    page.goto(f"{BASE}/admin")
    page.wait_for_url("**/app/chat")
    page.get_by_role("button", name="Sign out").click()

    # ---- admin: approve the refund
    login(page, "Gopireddy VSR (admin)")
    page.wait_for_url("**/admin")
    expect(page.get_by_text("Refunds waiting for approval")).to_be_visible()
    expect(page.get_by_role("button", name="Approve")).to_be_visible()
    shot(page, "12-admin-dashboard-pending-approval", full=True)
    page.get_by_placeholder("Note to customer (optional)").fill("Photos verified, thanks for your patience.")
    with page.expect_response(lambda r: "/decision" in r.url) as resp:
        page.get_by_role("button", name="Approve").click()
    assert resp.value.ok, resp.value.status
    expect(page.get_by_text("No refunds are waiting")).to_be_visible()
    expect(page.get_by_text("Gopireddy VSR (Support Lead)").first).to_be_visible()
    shot(page, "13-admin-dashboard-after-approval", full=True)
    page.get_by_role("button", name="Sign out").click()

    # ---- customer sees the resumed workflow's message
    login(page, "Pardha Saradhi (customer)")
    page.wait_for_url("**/app/chat")
    # most recently updated conversation is first in the history sidebar
    page.locator("aside button", has_text="messages").first.click()
    expect(page.get_by_text("Decision from VSR support team")).to_be_visible()
    expect(page.locator("text=by our support team").last).to_be_visible()
    expect(page.get_by_text("is waiting for admin approval")).to_have_count(0)  # pending card resolved
    expect(page.get_by_text("was approved by the support team")).to_be_visible()
    page.get_by_text("Decision from VSR support team").scroll_into_view_if_needed()
    shot(page, "14-chat-refund-approved-notification")

    # ---- mobile
    m = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    mp = m.new_page()
    watch(mp)
    mp.goto(f"{BASE}/login")
    mp.get_by_role("button", name="Pardha Saradhi (customer)").click()
    mp.wait_for_url("**/app/chat")
    send(mp, "Can I cancel ORD-1004?")
    expect(mp.get_by_text("can be cancelled at no cost").first).to_be_visible()
    shot(mp, "15-mobile-chat")
    mp.goto(f"{BASE}/")
    shot(mp, "16-mobile-landing")
    browser.close()

expected_401 = [x for x in problems if "401" in x]
real = [x for x in problems if x not in expected_401]
print("problems:", real or "none")
sys.exit(1 if real else 0)
