#!/usr/bin/env python
"""
Debug script to check what the page title actually contains
"""
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re

def debug_title_extraction():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        url = 'https://www.oddsportal.com/basketball/usa/nba/charlotte-hornets-philadelphia-76ers-KbK39OpA/'
        page.goto(url)
        page.wait_for_timeout(3000)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        title = soup.find('title')
        if title:
            title_text = title.get_text()
            print(f"Raw title text: '{title_text}'")
            print(f"Title repr: {repr(title_text)}")

            # Try different extraction patterns
            patterns = [
                r'(.+?)\s*[-–]\s*(.+?)\s+Basketball',
                r'([^<>]+?)\s*[-–]\s*([^<>]+?)\s+Basketball',
                r'(.+?)\s*-\s*(.+?)\s+Basketball',
                r'Charlotte\s+Hornets\s*-\s*Philadelphia\s+76ers',
            ]

            for i, pattern in enumerate(patterns):
                match = re.search(pattern, title_text)
                if match:
                    print(f"Pattern {i+1} matched: {match.groups()}")
                else:
                    print(f"Pattern {i+1} failed")

        # Check for other elements that might contain team names
        print("\nChecking other elements...")
        h1 = soup.find('h1')
        if h1:
            print(f"H1: {h1.get_text()}")

        # Look for elements with team names
        team_elements = soup.select('[data-testid*="participant"], .participant, .team')
        for elem in team_elements[:5]:  # First 5
            print(f"Team element: {elem.get_text().strip()}")

        browser.close()

if __name__ == "__main__":
    debug_title_extraction()