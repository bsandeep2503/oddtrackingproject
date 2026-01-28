#!/usr/bin/env python
"""
Debug - inspect In-Play page content
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

game_url = "https://www.oddsportal.com/basketball/usa/nba/charlotte-hornets-philadelphia-76ers-KbK39OpA/"

p = sync_playwright().start()
browser = p.chromium.launch(headless=True)
page = browser.new_page()

print(f"Navigating to: {game_url}\n")
page.goto(game_url, wait_until="load", timeout=15000)
time.sleep(3)

# Click In-Play Odds
try:
    in_play_link = page.locator("a[data-testid='sub-nav-inactive-tab']:has-text('In-Play')")
    if in_play_link.count() > 0:
        in_play_link.first.click()
        time.sleep(2)
        print("Clicked In-Play Odds tab\n")
except:
    pass

html = page.content()
soup = BeautifulSoup(html, "html.parser")
text = soup.get_text()

print("="*60)
print("IN-PLAY PAGE TEXT (first 2500 chars):")
print("="*60)
print(text[:2500])

print("\n" + "="*60)
print("Searching for score patterns...")
print("="*60)

# Look for all numbers
import re
numbers = re.findall(r'\d+', text[:1500])
print(f"Numbers found: {numbers[:30]}")

# Look for quarter
quarters = re.findall(r'(\d+)(?:st|nd|rd|th)?\s+Quarter', text)
print(f"Quarters found: {quarters}")

page.close()
browser.close()
p.stop()

print("\nDone!\n")
