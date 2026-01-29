#!/usr/bin/env python
"""
Game Scheduler and Orchestrator
Manages game lifecycle: scheduled -> live -> final
Polls active games and coordinates scraping
"""

import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from app.db import SessionLocal
from app.scraper import scrape_oddsportal_quarter
from app.models import Game
from app.insights import detect_momentum_events
from app.alerts import process_alerts

# Setup logging
log_dir = Path(__file__).parent
log_file = log_dir / "scheduler.log"

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
POLL_INTERVAL = 60  # seconds
CLOSE_TO_START_MINUTES = 15  # start polling 15 mins before game
FINAL_TIMEOUT_MINUTES = 20  # mark final if no score change for 20 mins

def get_games_to_poll():
    """Get all games that need polling"""
    db = SessionLocal()
    try:
        games = db.query(Game).filter(
            Game.status.in_(["scheduled", "live"])
        ).all()
        return games
    finally:
        db.close()

def update_game_status(game_id: int, status: str, db):
    """Update game status and last polled time"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if game:
        game.status = status
        game.last_polled_at = datetime.utcnow()
        db.commit()
        logger.info(f"Game {game_id} status updated to {status}")

def is_close_to_start(game: Game) -> bool:
    """Check if game is within 15 minutes of start"""
    if not game.start_time:
        return False
    now = datetime.utcnow()
    time_diff = (game.start_time - now).total_seconds() / 60
    return 0 <= time_diff <= CLOSE_TO_START_MINUTES

def should_mark_final(game: Game, latest_snapshots) -> bool:
    """Check if game should be marked final"""
    if not latest_snapshots:
        return False

    # If explicitly final quarter
    if any(s.stage == "final" for s in latest_snapshots):
        return True

    # If no score change for 20 minutes
    now = datetime.utcnow()
    recent_snaps = [s for s in latest_snapshots
                   if (now - s.timestamp).total_seconds() < FINAL_TIMEOUT_MINUTES * 60]

    if len(recent_snaps) < 2:
        return False

    # Check if scores are the same
    latest_score = (recent_snaps[-1].score_home, recent_snaps[-1].score_away)
    prev_score = (recent_snaps[0].score_home, recent_snaps[0].score_away)

    return latest_score == prev_score

def poll_game(game: Game):
    """Poll a single game for updates"""
    db = SessionLocal()
    try:
        logger.info(f"Polling game {game.id} ({game.home_team} vs {game.away_team}) - Status: {game.status}")

        # Scrape live odds
        snapshots = scrape_oddsportal_quarter(game.id)

        if snapshots:
            # Save snapshots
            db.add_all(snapshots)
            db.commit()

            # Detect momentum events and send alerts
            all_snaps = []
            for snap in snapshots:
                all_snaps.append({
                    'timestamp': snap.timestamp.isoformat(),
                    'ml_home': snap.ml_home,
                    'ml_away': snap.ml_away,
                    'stage': snap.stage
                })
            
            events = detect_momentum_events(all_snaps)
            if events:
                process_alerts(events, game.id, db)

            # Check if should mark final
            if should_mark_final(game, snapshots):
                update_game_status(game.id, "final", db)
            else:
                # Update last polled
                game.last_polled_at = datetime.utcnow()
                db.commit()

            logger.info(f"Game {game.id}: Saved {len(snapshots)} snapshots")
        else:
            logger.info(f"Game {game.id}: No live odds found")

    except Exception as e:
        logger.error(f"Error polling game {game.id}: {str(e)}")
        db.rollback()
    finally:
        db.close()

def main():
    """Main scheduler loop"""
    logger.info("="*60)
    logger.info("STARTING GAME SCHEDULER")
    logger.info(f"Poll Interval: {POLL_INTERVAL} seconds")
    logger.info(f"Close to start threshold: {CLOSE_TO_START_MINUTES} minutes")
    logger.info(f"Final timeout: {FINAL_TIMEOUT_MINUTES} minutes")
    logger.info("="*60)

    cycle_count = 0

    while True:
        cycle_count += 1
        cycle_start = datetime.now()

        logger.info(f"\n[Cycle #{cycle_count}] {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")

        games = get_games_to_poll()
        logger.info(f"Found {len(games)} games to check")

        for game in games:
            try:
                if game.status == "scheduled":
                    if is_close_to_start(game):
                        logger.info(f"Game {game.id} is close to start - starting live polling")
                        update_game_status(game.id, "live", SessionLocal())
                        poll_game(game)
                    else:
                        logger.info(f"Game {game.id} scheduled but not close to start")

                elif game.status == "live":
                    poll_game(game)

            except Exception as e:
                logger.error(f"Error processing game {game.id}: {str(e)}")

        # Sleep until next cycle
        cycle_time = (datetime.now() - cycle_start).total_seconds()
        sleep_time = max(0, POLL_INTERVAL - cycle_time)

        if sleep_time > 0:
            logger.info(f"Sleeping {sleep_time:.1f} seconds until next cycle")
            time.sleep(sleep_time)

if __name__ == "__main__":
    main()