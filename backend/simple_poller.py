#!/usr/bin/env python
"""
Live Game Poller - Simple version for testing continuous polling
"""
import time
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from app.db import SessionLocal
from app.scraper import scrape_oddsportal_quarter

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
POLL_INTERVAL = 60  # seconds

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
            # Scrape directly and save to DB
            logger.info(f"  Scraping live game...")
            db = SessionLocal()
            try:
                snapshots = scrape_oddsportal_quarter(GAME_ID)
                if snapshots:
                    db.add_all(snapshots)
                    db.commit()
                    success_count += 1
                    logger.info(f"  SUCCESS - Saved {len(snapshots)} snapshots")
                else:
                    error_count += 1
                    logger.info(f"  No live odds found")
            except Exception as e:
                db.rollback()
                error_count += 1
                logger.error(f"  ERROR: {str(e)}")
            finally:
                db.close()
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
