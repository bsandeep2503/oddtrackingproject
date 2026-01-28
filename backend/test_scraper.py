#!/usr/bin/env python
"""Test the scraper directly"""
import sys
import logging
sys.path.insert(0, '.')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

print('Testing scraper directly...')
try:
    from app.scraper import scrape_live_game
    
    game_url = 'https://www.oddsportal.com/basketball/usa/nba/charlotte-hornets-philadelphia-76ers-KbK39OpA/'
    print('Calling scrape_live_game...')
    result = scrape_live_game(game_url, 2)
    print(f'Result: {result}')
except Exception as e:
    import traceback
    print(f'Error: {e}')
    traceback.print_exc()
