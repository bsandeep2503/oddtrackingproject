#!/usr/bin/env python
"""
Debug script - extract full page text to see what's available
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

game_url = "https://www.oddsportal.com/basketball/usa/nba/charlotte-hornets-philadelphia-76ers-KbK39OpA/"

try:
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    print(f"\nNavigating to: {game_url}\n")
    page.goto(game_url, wait_until="load", timeout=15000)
    time.sleep(3)
    
    html = page.content()
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()
    
    print("="*60)
    print("FULL PAGE TEXT (first 3000 characters):")
    print("="*60)
    print(text[:3000])
    print("\n" + "="*60)
    
    # Look for specific elements
    print("\nSearching for buttons...")
    buttons = page.locator("button").all()
    print(f"Found {len(buttons)} buttons total")
    for i, btn in enumerate(buttons[:10]):
        try:
            text = btn.text_content()
            print(f"  Button {i}: {text[:50]}")
        except:
            pass
    
    print("\nSearching for 'In-Play' text anywhere...")
    if "In-Play" in text:
        print("✓ Found 'In-Play' in page text")
        # Find context
        idx = text.index("In-Play")
        print(f"Context: ...{text[max(0,idx-100):idx+150]}...")
    else:
        print("✗ 'In-Play' not found in page")
    
    print("\nSearching for score...")
    if "Hornets" in text and "76ers" in text:
        print("✓ Found team names")
        # Find score context
        idx = text.index("Hornets")
        print(f"Context: ...{text[idx:idx+200]}...")
    else:
        print("✗ Team names not found clearly")
    
    page.close()
    browser.close()
    p.stop()
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\nDone!\n")
