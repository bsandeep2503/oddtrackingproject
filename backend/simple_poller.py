#!/usr/bin/env python
"""
Live Game Poller - Simple version for testing continuous polling
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
    ],
    force=True
)

logger = logging.getLogger(__name__)

# Configuration
BACKEND_URL = "http://localhost:8000"
GAME_ID = 2
POLL_INTERVAL = 15  # seconds

print("\n" + "="*60)
print("STARTING LIVE POLLER")
print("="*60 + "\n")
logger.info("="*60)
logger.info("Starting Live Game Poller")
logger.info(f"Backend: {BACKEND_URL}")
logger.info(f"Game ID: {GAME_ID}")
logger.info(f"Poll Interval: {POLL_INTERVAL} seconds")
logger.info("="*60)

poll_count = 0
success_count = 0
error_count = 0

try:
    while True:
        poll_count += 1
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"\n[Poll #{poll_count}] {timestamp}")
        
        try:
            # Call the live scrape endpoint with longer timeout
            logger.info(f"  Sending request...")
            response = requests.post(
                f"{BACKEND_URL}/games/{GAME_ID}/scrape-live",
                timeout=60  # Longer timeout for browser launch
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'live_scraped':
                    success_count += 1
                    
                    # Log the results
                    logger.info(f"  SUCCESS")
                    logger.info(f"  Score: {data.get('score', 'Unknown')}")
                    logger.info(f"  Quarter: {data.get('quarter', 'Unknown')}")
                    
                    odds = data.get('odds', {})
                    logger.info(f"  Odds: Home={odds.get('home', 0.0):.2f}, Away={odds.get('away', 0.0):.2f}")
                    
                else:
                    error_count += 1
                    logger.warning(f"  Status: {data.get('status')}")
            
            else:
                error_count += 1
                logger.error(f"  HTTP {response.status_code}")
                    
        except Exception as e:
            error_count += 1
            logger.error(f"  Error: {e}")
        
        # Summary
        logger.info(f"  Summary: {success_count} successes, {error_count} errors from {poll_count} polls")
        logger.info(f"  Waiting {POLL_INTERVAL} seconds...")
        time.sleep(POLL_INTERVAL)

except KeyboardInterrupt:
    logger.info("\n\nInterrupted by user (Ctrl+C)")
finally:
    logger.info("\n" + "="*60)
    logger.info(f"Polling complete!")
    logger.info(f"Total polls: {poll_count}")
    logger.info(f"Successes: {success_count}")
    logger.info(f"Errors: {error_count}")
    logger.info("="*60 + "\n")
