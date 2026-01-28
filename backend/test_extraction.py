#!/usr/bin/env python
"""
Test the updated scraper logic for extracting team names
"""
from bs4 import BeautifulSoup
import re

# Sample HTML content from OddsPortal (simplified)
sample_html = """
<html>
<head>
<title>Charlotte Hornets - Philadelphia 76ers Basketball NBA Betting Odds</title>
</head>
<body>
<div class="breadcrumb">NBA > Charlotte Hornets - Philadelphia 76ers</div>
<div class="score">Charlotte Hornets 87–53 Philadelphia 76ers</div>
<div class="quarter">3rd Quarter 5'</div>
<div class="odds">-133+114</div>
</body>
</html>
"""

def test_team_extraction(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()

    # Extract team names from page title
    title = soup.find('title')
    if title:
        title_text = title.get_text()
        print(f"Page title: {title_text}")

        # Look for pattern like "Team1 - Team2 Basketball NBA Betting Odds"
        title_match = re.search(r'(.+?)\s*[-–]\s*(.+?)\s+Basketball', title_text)
        if title_match:
            away_team = title_match.group(1).strip()
            home_team = title_match.group(2).strip()
            print(f"✓ Extracted teams from title: {away_team} vs {home_team}")
        else:
            print("✗ Could not extract teams from title")

    # Test score extraction with dynamic team names
    away_team = "Charlotte Hornets"
    home_team = "Philadelphia 76ers"

    # Build dynamic regex patterns
    away_escaped = re.escape(away_team)
    home_escaped = re.escape(home_team)

    score_patterns = [
        rf'{away_escaped}\s*(\d+)\s*[-–]\s*(\d+)\s*{home_escaped}',
        rf'{home_escaped}\s*(\d+)\s*[-–]\s*(\d+)\s*{away_escaped}',
    ]

    for pattern in score_patterns:
        score_match = re.search(pattern, text)
        if score_match:
            print(f"✓ Matched score pattern: {pattern}")
            groups = score_match.groups()
            print(f"Score: {groups[0]} - {groups[1]}")
            break
    else:
        print("✗ No score pattern matched")

    # Test quarter extraction
    quarter_patterns = [
        (r'(\d+)(?:st|nd|rd|th)?\s+Quarter\s+(\d+)\'', 'quarter_and_time'),
        (r'(\d+)(?:st|nd|rd|th)?\s+Quarter', 'just_quarter'),
    ]

    for pattern, ptype in quarter_patterns:
        quarter_match = re.search(pattern, text)
        if quarter_match:
            print(f"✓ Matched quarter pattern: {pattern}")
            groups = quarter_match.groups()
            if ptype == 'quarter_and_time':
                q_num = int(groups[0])
                print(f"Quarter: Q{q_num}, Time: {groups[1]}:00")
            elif ptype == 'just_quarter':
                q_num = int(groups[0])
                print(f"Quarter: Q{q_num}")
            break
    else:
        print("✗ No quarter pattern matched")

if __name__ == "__main__":
    print("Testing team name and data extraction...")
    test_team_extraction(sample_html)