"""
Live Game Poller - Continuously polls OddsPortal for live game data
Runs in a loop, capturing odds and score every 30-60 seconds
"""

import time
import sys
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.insert(0, '/nba-odds-momentum/backend')

from app.db import Base, get_db, DATABASE_URL
from app.models import Game, QuarterSnapshot
from app.scraper import scrape_live_game
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('live_poller.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database setup
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def poll_live_game(game_url: str, game_id: int, poll_interval: int = 30, max_polls: int = None):
    """
    Continuously poll a live game for updates.
    
    Args:
        game_url: OddsPortal game URL
        game_id: Game ID in database
        poll_interval: Seconds between polls (default 30)
        max_polls: Max number of polls before stopping (None = infinite)
    """
    
    logger.info(f"Starting live game poller for game {game_id}")
    logger.info(f"URL: {game_url}")
    logger.info(f"Poll interval: {poll_interval} seconds\n")
    
    poll_count = 0
    snapshots_saved = 0
    
    try:
        while True:
            poll_count += 1
            
            if max_polls and poll_count > max_polls:
                logger.info(f"Reached max polls ({max_polls}). Stopping.")
                break
            
            logger.info(f"\n{'='*70}")
            logger.info(f"Poll #{poll_count} - {datetime.now().strftime('%H:%M:%S')}")
            logger.info(f"{'='*70}")
            
            # Scrape the live game
            result = scrape_live_game(game_url, game_id)
            
            if not result:
                logger.warning("Failed to scrape game data. Retrying...")
                time.sleep(poll_interval)
                continue
            
            # Log the current state
            logger.info(f"Score: {result['away_team']} {result['score_away']} - {result['score_home']} {result['home_team']}")
            logger.info(f"Quarter: {result['quarter']} | Time: {result['time']}")
            logger.info(f"Odds: Away {result['ml_away']:.2f} / Home {result['ml_home']:.2f}")
            
            # Save to database
            try:
                db = Session()
                
                # Ensure game exists
                game = db.query(Game).filter(Game.id == game_id).first()
                if not game:
                    game = Game(
                        id=game_id,
                        home_team=result.get('home_team', 'Unknown'),
                        away_team=result.get('away_team', 'Unknown')
                    )
                    db.add(game)
                    db.commit()
                else:
                    game.home_team = result.get('home_team', game.home_team)
                    game.away_team = result.get('away_team', game.away_team)
                    db.commit()
                
                # Create snapshot
                snapshot = QuarterSnapshot(
                    game_id=game_id,
                    stage=result.get('quarter', 'Unknown'),
                    score_home=result.get('score_home', 0),
                    score_away=result.get('score_away', 0),
                    score_diff=result.get('score_home', 0) - result.get('score_away', 0),
                    ml_home=result.get('ml_home', 0.0),
                    ml_away=result.get('ml_away', 0.0),
                    spread=0.0,
                    timestamp=datetime.utcnow()
                )
                
                db.add(snapshot)
                db.commit()
                db.close()
                
                snapshots_saved += 1
                logger.info(f"Snapshot saved (Total: {snapshots_saved})")
                
            except Exception as e:
                logger.error(f"Error saving snapshot: {e}")
            
            # Wait before next poll
            logger.info(f"Next poll in {poll_interval} seconds...")
            time.sleep(poll_interval)
    
    except KeyboardInterrupt:
        logger.info("\n\nPoller stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Fatal error in poller: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        logger.info(f"\nPoller finished. Total polls: {poll_count}, Snapshots saved: {snapshots_saved}")


if __name__ == "__main__":
    # Charlotte Hornets vs Philadelphia 76ers live game
    game_url = "https://www.oddsportal.com/basketball/usa/nba/charlotte-hornets-philadelphia-76ers-KbK39OpA/"
    game_id = 2
    
    # Poll every 30 seconds, indefinitely
    poll_live_game(game_url, game_id, poll_interval=30, max_polls=None)
    
    # Or for testing, poll 10 times:
    # poll_live_game(game_url, game_id, poll_interval=5, max_polls=10)
