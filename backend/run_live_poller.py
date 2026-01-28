#!/usr/bin/env python
"""
Live Game Poller - Continuously poll OddsPortal for live game odds updates
Runs every 30-60 seconds and stores snapshots in database
"""

import requests
import time
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
log_dir = Path(__file__).parent
log_file = log_dir / "live_poller.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Configuration
BACKEND_URL = "http://localhost:8000"
GAME_ID = 2
POLL_INTERVAL = 15  # seconds (faster for live testing)
MAX_POLLS = None  # None for unlimited

def poll_live_game():
    """Continuously poll live game endpoint"""
    
    logger.info("=" * 60)
    logger.info(f"Starting Live Game Poller")
    logger.info(f"Backend URL: {BACKEND_URL}")
    logger.info(f"Game ID: {GAME_ID}")
    logger.info(f"Poll Interval: {POLL_INTERVAL} seconds")
    logger.info(f"Max Polls: {MAX_POLLS if MAX_POLLS else 'Unlimited'}")
    logger.info("=" * 60)
    
    poll_count = 0
    success_count = 0
    error_count = 0
    
    try:
        while True:
            poll_count += 1
            
            # Check if we've hit max polls
            if MAX_POLLS and poll_count > MAX_POLLS:
                logger.info(f"Reached max polls ({MAX_POLLS}). Stopping.")
                break
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"\n[Poll #{poll_count}] {timestamp}")
            
            try:
                # Call the live scrape endpoint
                response = requests.post(
                    f"{BACKEND_URL}/games/{GAME_ID}/scrape-live",
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('status') == 'live_scraped':
                        success_count += 1
                        
                        # Log the results
                        logger.info(f"  Status: SUCCESS")
                        logger.info(f"  Score: {data.get('score', 'Unknown')}")
                        logger.info(f"  Quarter: {data.get('quarter', 'Unknown')}")
                        
                        odds = data.get('odds', {})
                        logger.info(f"  Odds: Home={odds.get('home', 0.0):.2f}, Away={odds.get('away', 0.0):.2f}")
                        
                    else:
                        error_count += 1
                        logger.warning(f"  Status: {data.get('status')}")
                        if 'message' in data:
                            logger.warning(f"  Message: {data.get('message')}")
                
                else:
                    error_count += 1
                    logger.error(f"  HTTP {response.status_code}: {response.text[:100]}")
                    
            except requests.exceptions.Timeout:
                error_count += 1
                logger.error(f"  TIMEOUT - Request took longer than 30 seconds")
                
            except requests.exceptions.RequestException as e:
                error_count += 1
                logger.error(f"  Request Error: {e}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"  Unexpected Error: {e}")
            
            # Summary
            logger.info(f"  Summary: {success_count} successes, {error_count} errors in {poll_count} polls")
            
            # Wait before next poll
            if not (MAX_POLLS and poll_count >= MAX_POLLS):
                logger.info(f"  Waiting {POLL_INTERVAL} seconds until next poll...")
                time.sleep(POLL_INTERVAL)
    
    except KeyboardInterrupt:
        logger.info("\n\nInterrupted by user (Ctrl+C)")
    
    finally:
        logger.info("\n" + "=" * 60)
        logger.info(f"Polling complete!")
        logger.info(f"Total polls: {poll_count}")
        logger.info(f"Successes: {success_count}")
        logger.info(f"Errors: {error_count}")
        logger.info(f"Log file: {log_file}")
        logger.info("=" * 60)

if __name__ == "__main__":
    poll_live_game()
