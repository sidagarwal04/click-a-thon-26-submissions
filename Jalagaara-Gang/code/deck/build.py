"""Build the pitch deck: HTML -> landscape PDF via headless Chrome.

Screenshots are inlined as data URIs so the HTML is a single self-contained file — Chrome's
PDF renderer will not reliably resolve relative image paths from a file:// URL, and a deck
that silently ships with missing images is worse than one that fails loudly.

    python deck/build.py
"""
from __future__ import annotations

import base64
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMG = ROOT / "public" / "Images"
DECK = ROOT / "deck"
HTML = DECK / "pitch-deck.html"
PDF = ROOT / "pitch-deck.pdf"

CHROME = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]


def data_uri(name: str) -> str:
    p = IMG / f"{name}.png"
    if not p.exists():
        raise SystemExit(f"missing screenshot: {p}")
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def find_chrome() -> str:
    for c in CHROME:
        if pathlib.Path(c).exists():
            return c
    found = shutil.which("chrome") or shutil.which("chromium")
    if found:
        return found
    raise SystemExit("Chrome/Edge not found — needed to render the PDF")


def main() -> None:
    from slides import render  # local module, keeps this file about the build only

    html = render(
        dashboard=data_uri("Dashboard"),
        replay=data_uri("Replay the anamoly"),
        trace=data_uri("Langfuse-detect-decompose-drilldown"),
        depth=data_uri("Langfuse-depth-populate"),
        chat=data_uri("Chat"),
    )
    HTML.write_text(html, encoding="utf-8")
    print(f"  html  {HTML}  ({len(html)/1e6:.1f} MB)")

    chrome = find_chrome()
    subprocess.run(
        [chrome, "--headless", "--disable-gpu", "--no-sandbox",
         "--no-pdf-header-footer", "--print-to-pdf-no-header",
         f"--print-to-pdf={PDF}", HTML.as_uri()],
        check=True, capture_output=True, timeout=180,
    )
    if not PDF.exists():
        raise SystemExit("Chrome ran but produced no PDF")
    print(f"  pdf   {PDF}  ({PDF.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    sys.path.insert(0, str(DECK))
    main()
