"""One-time setup: creates the restricted "RCA Follow-up" LibreChat agent used
by the dashboard's "Follow up" button.

This agent is deliberately scoped to exactly two tools — get_investigation and
drill_deeper (see src/rca/mcp_server.py) — and nothing else: no raw ClickHouse
access (the `clickhouse` MCP server is not attached), no scan/investigate
tools that could run a fresh dataset-wide query. It only ever reads from the
`investigations` table (already-computed, validated results) or re-runs a
drill scoped to an existing investigation's own date window. That's the
"hard restriction" the follow-up chat flow relies on to avoid hallucination:
the agent cannot reach raw event data even if asked to.

LibreChat's agent-creation endpoint (POST /api/agents) rejects a plain HTTP
client even with the right cookies/bearer token (an origin/CSRF guard beyond
simple headers — "Illegal request"), so this drives the real browser UI with
Playwright instead of calling the API directly. Requires:
    pip install playwright && playwright install chromium

Usage:
    cd librechat && python create_followup_agent.py

Prints the created agent's id — put that in the main project's .env as
LIBRECHAT_FOLLOWUP_AGENT_ID so the dashboard can build the deep-link URL.
"""

import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("LIBRECHAT_BASE_URL", "http://localhost:3080")
EMAIL = os.environ.get("LIBRECHAT_SETUP_EMAIL", "rca-setup@example.com")
PASSWORD = os.environ.get("LIBRECHAT_SETUP_PASSWORD", "RcaSetup123!")
NAME = os.environ.get("LIBRECHAT_SETUP_NAME", "RCA Setup")

AGENT_NAME = "RCA Follow-up"
AGENT_DESCRIPTION = "Scoped follow-up on one already-computed incident investigation"
AGENT_INSTRUCTIONS = (
    "You are a narrow follow-up assistant for ONE already-computed ad-metrics "
    "investigation. You only have two tools: get_investigation(id) loads the "
    "existing decomposition, drill_down tree, and narrative for the incident id "
    "given to you at the start of this conversation — always call this first. "
    "drill_deeper(id, dimension, value) goes one level deeper into a named "
    "segment, reusing that investigation's own date window only. Never claim "
    "access to raw event data, a different date range, or a different incident "
    "than the one you were given."
)


def _login_or_register(page) -> None:
    page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1000)
    page.fill('input[name="email"]', EMAIL)
    page.fill('input[name="password"]', PASSWORD)
    page.click('button:has-text("Continue")')
    page.wait_for_timeout(2000)
    if "/login" not in page.url:
        return

    print(f"No existing account for {EMAIL}, registering one...", file=sys.stderr)
    page.goto(f"{BASE_URL}/register", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1000)
    page.fill('input[name="name"]', NAME)
    page.fill('input[name="email"]', EMAIL)
    page.fill('input[name="password"]', PASSWORD)
    page.fill('input[name="confirm_password"]', PASSWORD)
    page.click('button:has-text("Continue")')
    page.wait_for_timeout(2500)


def create_followup_agent() -> str:
    created = {}

    def on_request(request):
        if request.method == "POST" and request.url.endswith("/api/agents"):
            created["seen_create"] = True

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1400, "height": 950})
        page = ctx.new_page()
        page.on("request", on_request)

        try:
            _login_or_register(page)

            page.click('[aria-label="Agent Builder"]')
            page.wait_for_timeout(1000)
            page.fill('input[placeholder="Agent name"]', AGENT_NAME)
            page.fill('input[placeholder="What this agent does"]', AGENT_DESCRIPTION)
            page.fill("textarea", AGENT_INSTRUCTIONS)

            # Model: Google -> gemini-flash-lite-latest (native endpoint — required
            # for MCP tool calls; the OpenAI-compat "Gemini" endpoint 400s on them).
            page.locator("text=Select a model").first.click()
            page.wait_for_timeout(400)
            page.click("text=Select a provider")
            page.wait_for_timeout(400)
            page.click("text=Google")
            page.wait_for_timeout(400)
            page.click("text=Model Parameters >> xpath=preceding-sibling::button | ./preceding::button[1]")
            page.wait_for_timeout(500)

            # Tools: open rca-investigator's tool picker and select only the two
            # scoped tools (not the whole collection, not the clickhouse server).
            # Clicking the card itself toggles-select the WHOLE collection (all 6
            # tools) — the per-tool picker only opens via the "Configure" (gear)
            # button that fades in on hover, bottom-right of the card.
            page.click("text=TOOLS >> xpath=following::button[1]")
            page.wait_for_timeout(800)
            card = page.get_by_role("button", name="rca-investigator MCP servers")
            card.hover()
            page.wait_for_timeout(300)
            card.locator("xpath=..").get_by_label("Configure").click(force=True)
            page.wait_for_timeout(800)
            dialog = page.get_by_role("dialog")
            dialog.get_by_text("get_investigation", exact=True).click()
            page.wait_for_timeout(300)
            dialog.get_by_text("drill_deeper", exact=True).click()
            page.wait_for_timeout(300)
            dialog.locator("svg").last.click(force=True)  # close tool-detail dialog
            page.wait_for_timeout(500)
            # Close the Tool Library panel via its own X (top right, the larger
            # of the two lucide "x" icons on the page at this point — the other
            # is the unrelated sidebar-collapse icon).
            page.locator("svg.lucide-x").nth(1).click(force=True)
            page.wait_for_timeout(500)

            page.locator('button:has-text("Create")').last.click()
            page.wait_for_timeout(2500)

            if not created.get("seen_create"):
                raise RuntimeError("Never saw the agent-creation request fire — UI flow may have changed.")

            # Read back the id via the app's own (authenticated) fetch, by opening
            # the agent picker and capturing the list response.
            agent_id_holder = {}

            def on_response(response):
                if re.search(r"/api/agents\?", response.url):
                    try:
                        data = response.json()
                        for a in data.get("data", []):
                            if a["name"] == AGENT_NAME:
                                agent_id_holder["id"] = a["id"]
                    except Exception:
                        pass

            page.on("response", on_response)
            page.click(f"text={AGENT_NAME}")
            page.wait_for_timeout(1200)
        except Exception:
            # This drives a UI with no stable API contract, so a selector can
            # break on any LibreChat update -- capture exactly what the page
            # looked like at the moment of failure instead of leaving whoever
            # hits this to debug a bare Playwright stack trace blind.
            debug_dir = Path(__file__).resolve().parent / ".debug"
            debug_dir.mkdir(exist_ok=True)
            try:
                page.screenshot(path=str(debug_dir / "create_followup_agent_failure.png"), full_page=True)
                (debug_dir / "create_followup_agent_failure.html").write_text(page.content())
                print(f"Saved failure screenshot + HTML to {debug_dir}/", file=sys.stderr)
            except Exception:
                pass  # the page itself may be gone/crashed; don't mask the real error with this
            raise
        finally:
            browser.close()

    if "id" not in agent_id_holder:
        raise RuntimeError("Agent created but could not read back its id — check LibreChat manually.")
    return agent_id_holder["id"]


if __name__ == "__main__":
    agent_id = create_followup_agent()
    print(f"Created agent: {AGENT_NAME} (id={agent_id})")
    print(f"\nAdd to your project .env:\nLIBRECHAT_FOLLOWUP_AGENT_ID={agent_id}")
