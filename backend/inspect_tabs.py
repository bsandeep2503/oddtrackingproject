#!/usr/bin/env python
"""
Debug script - inspect the structure of the odds tabs
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

game_url = "https://www.oddsportal.com/basketball/usa/nba/charlotte-hornets-philadelphia-76ers-KbK39OpA/"

p = sync_playwright().start()
browser = p.chromium.launch(headless=False)
page = browser.new_page()

page.goto(game_url, wait_until="load", timeout=15000)
time.sleep(3)

html = page.content()
soup = BeautifulSoup(html, "html.parser")

print("\n" + "="*60)
print("Looking for tabs/buttons structure...")
print("="*60)

# Find divs with "In-Play"
in_play_elements = soup.find_all(string=lambda text: text and "In-Play" in text)
print(f"\nFound {len(in_play_elements)} elements containing 'In-Play'")

for elem in in_play_elements[:3]:
    parent = elem.parent
    print(f"\nElement: {elem[:50]}")
    print(f"Parent tag: {parent.name}")
    print(f"Parent attrs: {parent.attrs}")
    print(f"Parent HTML: {str(parent)[:300]}")

# Look for divs with onclick or data attributes
print("\n" + "="*60)
print("Looking for clickable elements with 'In-Play'...")
print("="*60)

# Find parent divs/buttons that might be clickable
divs = soup.find_all(attrs={"data-testid": True})
print(f"\nFound {len(divs)} elements with data-testid attribute")

for div in divs[:10]:
    testid = div.get("data-testid", "")
    if "odd" in testid.lower() or "tab" in testid.lower():
        text = div.get_text(strip=True)[:100]
        print(f"  {testid}: {text}")

# Try using Playwright to find interactive elements
print("\n" + "="*60)
print("Testing Playwright selectors...")
print("="*60)

# Try different selectors
selectors = [
    "[data-testid*='Odd']",
    "[data-testid*='odd']",
    "div:has-text('In-Play')",
    "[role='tab']",
    "[role='button']"
]

for selector in selectors:
    try:
        elements = page.locator(selector).all()
        print(f"\n{selector}: Found {len(elements)} elements")
        for i, elem in enumerate(elements[:3]):
            try:
                text = elem.text_content()[:50]
                print(f"  [{i}] {text}")
            except:
                pass
    except Exception as e:
        print(f"\n{selector}: Error - {e}")

page.close()
browser.close()
p.stop()

print("\nDone!\n")
