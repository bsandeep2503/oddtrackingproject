from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re

# Test script to inspect quarter data in results
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://www.oddsportal.com/basketball/usa/nba/results/")
    
    print(f"Page title: {page.title()}")
    page.wait_for_timeout(5000)
    
    html = page.content()
    soup = BeautifulSoup(html, "html.parser")
    
    print("\n=== LOOKING FOR QUARTER DATA ===\n")
    
    # Get game rows
    rows = soup.select(".eventRow")
    game_rows = [r for r in rows if r.select("[data-testid*='participant']")]
    
    print(f"Found {len(game_rows)} game rows\n")
    
    if game_rows:
        # Check first 3 games
        for idx, row in enumerate(game_rows[:3]):
            print(f"\n--- GAME {idx + 1} ---")
            
            teams = row.select("[data-testid*='participant']")
            if teams:
                print(f"Teams: {teams[0].get_text(strip=True)}")
            
            row_text = row.get_text()
            print(f"\nFull row text (first 500 chars):\n{row_text[:500]}\n")
            
            # Look for scores
            score_pattern = r'(\d+)\s*[–-]\s*(\d+)'
            scores = re.findall(score_pattern, row_text)
            print(f"All scores found: {scores[:10]}")
            
            # Look for quarter data in parentheses
            paren_pattern = r'\(([^\)]+)\)'
            parens = re.findall(paren_pattern, row_text)
            print(f"Data in parentheses: {parens}")
            
            # Check for quarter patterns specifically
            quarter_pattern = r'(\d+)\s*:\s*(\d+)'
            quarters = re.findall(quarter_pattern, row_text)
            print(f"Quarter patterns found: {quarters[:10]}")
    
    browser.close()

