#!/usr/bin/env python
"""
Debug script to test the live game scraper with visibility
"""
import sys
import time
from pathlib import Path

# Add the app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.scraper import scrape_live_game
import logging

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

print("\n" + "="*60)
print("TESTING LIVE GAME SCRAPER")
print("="*60 + "\n")

# Test with the Charlotte vs Philly game
game_url = "https://www.oddsportal.com/basketball/usa/nba/charlotte-hornets-philadelphia-76ers-KbK39OpA/"

print(f"Testing URL: {game_url}\n")

try:
    result = scrape_live_game(game_url, game_id=2)
    
    print("\n" + "="*60)
    print("SCRAPER RESULT")
    print("="*60)
    
    if result:
        for key, value in result.items():
            print(f"  {key}: {value}")
    else:
        print("  RESULT: None (Error occurred)")
        
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60 + "\n")
