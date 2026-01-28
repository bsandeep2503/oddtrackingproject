#!/usr/bin/env python
"""
Debug script to find live NBA games on OddsPortal
"""
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://www.oddsportal.com/basketball/usa/nba/')
    page.wait_for_timeout(5000)

    html = page.content()
    soup = BeautifulSoup(html, 'html.parser')

    print('Looking for eventRow elements...')
    rows = soup.select('.eventRow')
    print(f'Found {len(rows)} eventRow elements')

    for i, row in enumerate(rows):
        text = row.get_text()
        
        # Look for Washington Wizards or Portland Trail Blazers
        if 'washington' in text.lower() or 'wizards' in text.lower() or 'trail blazers' in text.lower() or 'portland' in text.lower():
            print(f'\nFound relevant row {i}:')
            print(text[:500])
            
            # Look for links
            links = row.select('a')
            for link in links:
                href = link.get('href')
                if href and '/basketball/usa/nba/' in href:
                    print(f'  NBA Link: {href}')
                    full_url = f"https://www.oddsportal.com{href}"
                    print(f'  Full URL: {full_url}')

    browser.close()