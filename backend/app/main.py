from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from datetime import datetime
import logging
from dotenv import load_dotenv
load_dotenv()
from .scraper import scrape_oddsportal_quarter, scrape_completed_games
from .pinnacle import fetch_odds_by_sport
from .db import SessionLocal, init_db
from .models import Game, OddsSnapshot, QuarterSnapshot, LiveOddsSnapshot, Alert
from .insights import detect_momentum_events, get_insights_summary
from .replay import detect_gaps
from .sync_games import sync_games_from_oddsportal

logger = logging.getLogger(__name__)

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    # Database is initialized manually when starting the server
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health")
def health():
    return {"status": "ok"}

# ---------- Games & odds (existing) ----------
@app.post("/games/{game_id}/scrape-live-quarter")
def scrape_live_quarter(game_id: int, db: Session = Depends(get_db)):
    snapshots = scrape_oddsportal_quarter(game_id)
    if not snapshots:
        return {"status": "no live odds found"}
    db.add_all(snapshots)
    db.commit()
    return {"status": "scraped", "count": len(snapshots)}

from pydantic import BaseModel

class GameCreateRequest(BaseModel):
    home_team: str
    away_team: str
    oddsportal_url: str = None

@app.post("/games/create")
def create_game(payload: GameCreateRequest, db: Session = Depends(get_db)):
    try:
        game = Game(home_team=payload.home_team, away_team=payload.away_team, oddsportal_url=payload.oddsportal_url)
        db.add(game)
        db.commit()
        db.refresh(game)
        return {"game_id": game.id}
    except Exception as e:
        db.rollback()
        raise e

@app.put("/games/{game_id}")
def update_game(game_id: int, home_team: str = None, away_team: str = None, oddsportal_url: str = None, db: Session = Depends(get_db)):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        return {"error": "Game not found"}
    
    if home_team:
        game.home_team = home_team
    if away_team:
        game.away_team = away_team
    if oddsportal_url:
        game.oddsportal_url = oddsportal_url
    
    db.commit()
    return {"status": "updated"}

@app.get("/games")
def list_games(status: str = None, db: Session = Depends(get_db)):
    q = db.query(Game)
    if status:
        q = q.filter(Game.status == status)
    games = q.all()
    return jsonable_encoder(games)

@app.post("/games/sync")
def sync_games(db: Session = Depends(get_db)):
    games = sync_games_from_oddsportal()
    inserted = 0
    updated = 0

    for g in games:
        existing = db.query(Game).filter(Game.oddsportal_url == g["url"]).first()
        if existing:
            existing.home_team = g["home_team"]
            existing.away_team = g["away_team"]
            existing.status = g["status"]
            existing.pregame_ml_home = g.get("ml_home")
            existing.pregame_ml_away = g.get("ml_away")
            existing.pregame_spread = g.get("spread")
            existing.pregame_total = g.get("total")
            updated += 1
        else:
            db.add(Game(
                home_team=g["home_team"],
                away_team=g["away_team"],
                oddsportal_url=g["url"],
                status=g["status"],
                pregame_ml_home=g.get("ml_home"),
                pregame_ml_away=g.get("ml_away"),
                pregame_spread=g.get("spread"),
                pregame_total=g.get("total")
            ))
            inserted += 1

    db.commit()
    return {"inserted": inserted, "updated": updated, "total": len(games)}

@app.get("/games/{game_id}")
def get_game_info(game_id: int, db: Session = Depends(get_db)):
    """Get game info including team names and OddsPortal URL"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        return {"error": "Game not found"}
    return {
        "id": game.id,
        "home_team": game.home_team,
        "away_team": game.away_team,
        "oddsportal_url": game.oddsportal_url
    }

@app.get("/games/{game_id}/summary")
def game_summary(game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        return {"error": "Game not found"}
    
    latest = db.query(QuarterSnapshot).filter(QuarterSnapshot.game_id == game_id).order_by(QuarterSnapshot.timestamp.desc()).first()
    
    return {
        "game": {
            "id": game.id,
            "home_team": game.home_team,
            "away_team": game.away_team,
            "status": game.status,
            "start_time": game.start_time.isoformat() if game.start_time else None,
            "last_polled_at": game.last_polled_at.isoformat() if game.last_polled_at else None
        },
        "latest": latest
    }

@app.delete("/games/{game_id}/clear")
def clear_game_data(game_id: int, db: Session = Depends(get_db)):
    db.query(QuarterSnapshot).filter(QuarterSnapshot.game_id == game_id).delete()
    db.query(LiveOddsSnapshot).filter(LiveOddsSnapshot.game_id == game_id).delete()
    db.commit()
    return {"status": "cleared"}

@app.get("/games/{game_id}/odds")
def get_odds(game_id: int, db: Session = Depends(get_db)):
    snapshots = (
        db.query(OddsSnapshot)
        .filter(OddsSnapshot.game_id == game_id)
        .order_by(OddsSnapshot.timestamp)
        .all()
    )
    return snapshots

@app.post("/games/{game_id}/inject-fake-odds")
def inject_fake_odds(game_id: int, db: Session = Depends(get_db)):
    snapshots = generate_fake_odds(game_id)
    db.add_all(snapshots)
    db.commit()
    return {"status": "injected", "count": len(snapshots)}

# ---------- Quarter snapshots (new) ----------

@app.get("/games/{game_id}/quarters")
def get_quarter_snapshots(game_id: int, db: Session = Depends(get_db)):
    snapshots = (
        db.query(QuarterSnapshot)
        .filter(QuarterSnapshot.game_id == game_id)
        .order_by(QuarterSnapshot.id)
        .all()
    )
    return jsonable_encoder(snapshots)

@app.get("/games/{game_id}/insights")
def get_insights(game_id: int, db: Session = Depends(get_db)):
    # Get all snapshots (both quarter and live)
    quarter_snaps = (
        db.query(QuarterSnapshot)
        .filter(QuarterSnapshot.game_id == game_id)
        .order_by(QuarterSnapshot.timestamp)
        .all()
    )
    live_snaps = (
        db.query(LiveOddsSnapshot)
        .filter(LiveOddsSnapshot.game_id == game_id)
        .order_by(LiveOddsSnapshot.timestamp)
        .all()
    )

    # Convert to dicts for processing
    all_snaps = []
    for snap in quarter_snaps:
        all_snaps.append({
            'timestamp': snap.timestamp.isoformat(),
            'ml_home': snap.ml_home,
            'ml_away': snap.ml_away,
            'stage': snap.stage
        })
    for snap in live_snaps:
        all_snaps.append({
            'timestamp': snap.timestamp.isoformat(),
            'ml_home': snap.teamA_ml if snap.teamA_ml else None,
            'ml_away': snap.teamB_ml if snap.teamB_ml else None,
            'stage': f"Q{snap.quarter}" if snap.quarter else "live"
        })

    # Generate insights
    events = detect_momentum_events(all_snaps)
    summary = get_insights_summary(all_snaps)

    return {
        "summary": summary,
        "events": events
    }

@app.get("/games/{game_id}/replay")
def replay_game(game_id: int, speed: int = 2, db: Session = Depends(get_db)):
    # Get all snapshots (both quarter and live)
    quarter_snaps = (
        db.query(QuarterSnapshot)
        .filter(QuarterSnapshot.game_id == game_id)
        .order_by(QuarterSnapshot.timestamp)
        .all()
    )
    live_snaps = (
        db.query(LiveOddsSnapshot)
        .filter(LiveOddsSnapshot.game_id == str(game_id))
        .order_by(LiveOddsSnapshot.timestamp)
        .all()
    )

    # Convert to dicts for processing
    all_snaps = []
    for snap in quarter_snaps:
        all_snaps.append({
            'timestamp': snap.timestamp.isoformat(),
            'ml_home': snap.ml_home,
            'ml_away': snap.ml_away,
            'stage': snap.stage,
            'score_home': snap.score_home,
            'score_away': snap.score_away,
            'score_diff': snap.score_diff,
            'spread': snap.spread
        })
    for snap in live_snaps:
        all_snaps.append({
            'timestamp': snap.timestamp.isoformat(),
            'ml_home': snap.teamA_ml if snap.teamA_ml else None,
            'ml_away': snap.teamB_ml if snap.teamB_ml else None,
            'stage': f"Q{snap.quarter}" if snap.quarter else "live",
            'score_home': snap.teamA_score,
            'score_away': snap.teamB_score,
            'score_diff': snap.teamA_score - snap.teamB_score if snap.teamA_score is not None and snap.teamB_score is not None else None,
            'spread': snap.spread_line
        })

    # Sort by timestamp
    all_snaps.sort(key=lambda x: x['timestamp'])

    # speed = seconds per step
    return {
        "speed": speed,
        "count": len(all_snaps),
        "snapshots": jsonable_encoder(all_snaps)
    }

@app.get("/games/{game_id}/health")
def game_health(game_id: int, db: Session = Depends(get_db)):
    snaps = (
        db.query(QuarterSnapshot)
        .filter(QuarterSnapshot.game_id == game_id)
        .order_by(QuarterSnapshot.timestamp)
        .all()
    )
    gaps = detect_gaps(snaps, max_gap_seconds=120)
    return {
        "count": len(snaps),
        "gaps": gaps,
        "ok": len(gaps) == 0
    }

@app.post("/games/{game_id}/quarters/load-demo")
def load_demo_quarters(game_id: int, db: Session = Depends(get_db)):
    """
    Loads your NOP–DEN example as quarter snapshots for quick testing.
    """

    # Clear existing for that game (optional)
    db.query(QuarterSnapshot).filter(QuarterSnapshot.game_id == game_id).delete()

    base_time = datetime.utcnow()

    demo_rows = [
        # Pre-game
        dict(
            stage="pregame",
            score_home=0,
            score_away=0,
            score_diff=0,  # DEN - NOP = 0
            ml_home=1.133,  # DEN
            ml_away=6.00,   # NOP
            spread=-12.5,   # DEN -12.5
        ),
        # End Q1: 25 - 34 (NOP - DEN) => DEN +9
        dict(
            stage="Q1",
            score_home=34,   # DEN
            score_away=25,   # NOP
            score_diff=9,    # DEN +9
            ml_home=1.08,    # DEN
            ml_away=9.00,    # NOP
            spread=-10.5,    # DEN -10.5
        ),
        # Halftime: 47 - 53 (NOP - DEN) => DEN +6
        dict(
            stage="Q2",
            score_home=53,
            score_away=47,
            score_diff=6,
            ml_home=1.25,
            ml_away=4.00,
            spread=-6.5,
        ),
        # End Q3: 69 - 95 (NOP - DEN) => DEN +26
        dict(
            stage="Q3",
            score_home=95,
            score_away=69,
            score_diff=26,
            ml_home=1.001,
            ml_away=101.00,
            spread=-25.5,
        ),
        # Final: 88 - 122 (NOP - DEN) => DEN +34
        dict(
            stage="final",
            score_home=122,
            score_away=88,
            score_diff=34,
            ml_home=1.01,
            ml_away=101.00,
            spread=-12.5,  # result spread
        ),
    ]

    snapshots = []
    for i, row in enumerate(demo_rows):
        snap = QuarterSnapshot(
            game_id=game_id,
            stage=row["stage"],
            score_home=row["score_home"],
            score_away=row["score_away"],
            score_diff=row["score_diff"],
            ml_home=row["ml_home"],
            ml_away=row["ml_away"],
            spread=row["spread"],
            timestamp=base_time,  # same base time; you can offset if you want
        )
        snapshots.append(snap)

    db.add_all(snapshots)
    db.commit()

    return {"status": "demo_loaded", "count": len(snapshots)}


# ---------- Completed games scraper ----------

@app.post("/games/{game_id}/scrape-completed")
def scrape_completed(game_id: int, db: Session = Depends(get_db)):
    """
    Scrapes OddsPortal for COMPLETED games with quarter-by-quarter odds.
    Also updates game info with team names.
    """
    snapshots, game_info = scrape_completed_games(game_id)
    if not snapshots:
        return {"status": "no completed games found"}
    
    # First, update or create game with team names
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        game = Game(id=game_id, home_team="Unknown", away_team="Unknown")
        db.add(game)
    
    if game_info and game_info.get('home') and game_info.get('away'):
        game.home_team = game_info['home']
        game.away_team = game_info['away']
        db.commit()
    
    # Then add all snapshots
    db.add_all(snapshots)
    db.commit()
    
    return {
        "status": "completed_games_scraped",
        "count": len(snapshots),
        "stages": [s.stage for s in snapshots],
        "game": {
            "home_team": game.home_team,
            "away_team": game.away_team
        }
    }


@app.post("/games/{game_id}/scrape-live")
def scrape_live_game_endpoint(game_id: int, db: Session = Depends(get_db)):
    """
    Scrape a live game once. Should be called repeatedly to poll for updates.
    Returns current score and in-play odds.
    """
    import time
    import concurrent.futures
    from app.scraper import scrape_live_game, find_live_nba_game
    
    # Get the game and its URL from database
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        return {"status": "error", "message": "Game not found"}
    
    game_url = game.oddsportal_url
    
    # If no URL configured or if we want to find live games dynamically
    if not game_url:
        logger.info(f"No URL configured for game {game_id}, finding live NBA game...")
        game_url = find_live_nba_game()
        if game_url:
            game.oddsportal_url = game_url
            db.commit()
            logger.info(f"Updated game {game_id} with live game URL: {game_url}")
        else:
            return {"status": "error", "message": "No live NBA games found"}
    
    logger.info(f"Scraping live game {game_id} from: {game_url}")
    
    # Scrape the game with a timeout to avoid hanging requests
    result = None
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(scrape_live_game, game_url, game_id)
        try:
            result = future.result(timeout=25)
        except concurrent.futures.TimeoutError:
            logger.warning(f"Live scrape timed out for {game_url}")
            return {"status": "error", "message": "Live scrape timed out"}
    
    if not result:
        # If scraping failed, try to find a new live game
        logger.warning(f"Failed to scrape {game_url}, looking for new live game...")
        new_url = find_live_nba_game()
        if new_url and new_url != game_url:
            game.oddsportal_url = new_url
            db.commit()
            logger.info(f"Switched to new live game: {new_url}")
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(scrape_live_game, new_url, game_id)
                try:
                    result = future.result(timeout=25)
                except concurrent.futures.TimeoutError:
                    logger.warning(f"Live scrape timed out for {new_url}")
                    return {"status": "error", "message": "Live scrape timed out"}
    
    if result and result.get("quarter") == "final":
        logger.info("Current game is final, searching for a new live game...")
        new_url = find_live_nba_game()
        if new_url and new_url != game_url:
            game.oddsportal_url = new_url
            db.commit()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(scrape_live_game, new_url, game_id)
                try:
                    result = future.result(timeout=25)
                except concurrent.futures.TimeoutError:
                    logger.warning(f"Live scrape timed out for {new_url}")
                    return {"status": "error", "message": "Live scrape timed out"}

    if not result:
        return {"status": "error", "message": "Could not scrape game"}
    
    # Update game info if teams were extracted
    if result.get('home_team') and result.get('away_team'):
        game.home_team = result['home_team']
        game.away_team = result['away_team']
        db.commit()
    
    # Normalize quarter label to avoid leading zeros (e.g., Q004 -> Q4)
    import re
    stage = result.get('quarter', 'Unknown')
    if isinstance(stage, str):
        stage = re.sub(r'^Q0+(\d+)$', r'Q\1', stage)

    # Create a quarter snapshot for the current state
    snapshot = QuarterSnapshot(
        game_id=game_id,
        stage=stage,
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
    
    logger.info(f"Saved live snapshot for game {game_id}")
    
    return {
        "status": "live_scraped",
        "timestamp": result.get('timestamp'),
        "score": f"{result.get('away_team')} {result.get('score_away')} - {result.get('score_home')} {result.get('home_team')}",
        "quarter": stage,
        "odds": {
            "home": result.get('ml_home'),
            "away": result.get('ml_away')
        },
        "game": {
            "home_team": game.home_team,
            "away_team": game.away_team
        }
    }


@app.post("/games/{game_id}/scrape-pregame")
def scrape_pregame_game_endpoint(game_id: int, db: Session = Depends(get_db)):
    """
    Scrape pre-game odds for a game before it starts.
    Returns pre-game moneyline odds.
    """
    import time
    from app.scraper import scrape_pregame_game
    
    # Get the game and its URL from database
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        return {"status": "error", "message": "Game not found"}
    
    if not game.oddsportal_url:
        return {"status": "error", "message": "No OddsPortal URL configured for this game"}
    
    game_url = game.oddsportal_url
    
    logger.info(f"Scraping pre-game odds for {game_id} from: {game_url}")
    
    # Scrape the game
    result = scrape_pregame_game(game_url, game_id)
    
    if not result:
        return {"status": "error", "message": "Could not scrape game"}
    
    # Update game info if teams were extracted
    if result.get('home_team') and result.get('away_team'):
        game.home_team = result['home_team']
        game.away_team = result['away_team']
        db.commit()
    
    # Create a quarter snapshot for the pre-game state
    snapshot = QuarterSnapshot(
        game_id=game_id,
        stage="pregame",
        score_home=0,
        score_away=0,
        score_diff=0,
        ml_home=result.get('ml_home', 0.0),
        ml_away=result.get('ml_away', 0.0),
        spread=0.0,
        timestamp=datetime.utcnow()
    )
    
    db.add(snapshot)
    db.commit()
    
    logger.info(f"Saved pre-game snapshot for game {game_id}")
    
    return {
        "status": "pregame_scraped",
        "timestamp": result.get('timestamp'),
        "score": f"{result.get('away_team')} 0 - 0 {result.get('home_team')}",
        "quarter": "pregame",
        "odds": {
            "home": result.get('ml_home'),
            "away": result.get('ml_away')
        },
        "game": {
            "home_team": game.home_team,
            "away_team": game.away_team
        }
    }


# ---------- Pinnacle integration endpoints ----------
@app.post("/pinnacle/poll-once")
def pinnacle_poll_once(db: Session = Depends(get_db)):
    """Fetch current Pinnacle odds for NBA (sport_id=29) and store snapshots in `live_odds_snapshots`."""
    results = fetch_odds_by_sport(sport_id=29)
    if not results:
        return {"status": "no_data"}

    rows = []
    for r in results:
        snap = LiveOddsSnapshot(
            game_id=str(r.get('event_id') or f"{r.get('home')} vs {r.get('away')}"),
            timestamp=r.get('timestamp'),
            quarter=None,
            game_clock=None,
            teamA_score=None,
            teamB_score=None,
            teamA_ml=r.get('ml_home'),
            teamB_ml=r.get('ml_away'),
            spread_line=r.get('spread'),
            total_line=r.get('total')
        )
        rows.append(snap)

    db.add_all(rows)
    db.commit()
    return {"status": "stored", "count": len(rows)}


@app.get("/games/{game_id}/live-snapshots")
def get_live_snapshots(game_id: str, db: Session = Depends(get_db)):
    snaps = (
        db.query(LiveOddsSnapshot)
        .filter(LiveOddsSnapshot.game_id == str(game_id))
        .order_by(LiveOddsSnapshot.timestamp)
        .all()
    )
    return jsonable_encoder(snaps)


@app.get("/pinnacle/games")
def list_pinnacle_games(limit: int = 50, db: Session = Depends(get_db)):
    """Return distinct recent Pinnacle game ids with latest timestamp and basic info."""
    # Query recent snapshots and group by game_id using simple approach
    snaps = (
        db.query(LiveOddsSnapshot)
        .order_by(LiveOddsSnapshot.timestamp.desc())
        .limit(limit)
        .all()
    )

    seen = {}
    out = []
    for s in snaps:
        gid = s.game_id
        if gid in seen:
            continue
        seen[gid] = True
        out.append({
            "game_id": gid,
            "timestamp": s.timestamp,
            "teamA_score": s.teamA_score,
            "teamB_score": s.teamB_score,
            "teamA_ml": s.teamA_ml,
            "teamB_ml": s.teamB_ml,
            "spread": s.spread_line,
        })

    return out


@app.post("/pinnacle/demo-poll")
def demo_poll(db: Session = Depends(get_db)):
    """Generate sample Pinnacle game data for testing without real API."""
    from datetime import timedelta
    base_time = datetime.utcnow()
    game_id = "demo_hornets_76ers"
    
    # Clear old demo data
    db.query(LiveOddsSnapshot).filter(LiveOddsSnapshot.game_id == game_id).delete()
    db.commit()
    
    # Create 10 sample snapshots showing live odds movement
    snapshots = []
    quarters = [1, 1, 1, 2, 2, 2, 3, 3, 4, 4]
    clocks = ["7:30", "5:15", "2:00", "8:45", "4:20", "0:30", "6:10", "1:05", "9:20", "0:15"]
    scores_a = [15, 18, 21, 42, 50, 52, 70, 78, 95, 115]  # Hornets (away)
    scores_b = [12, 16, 20, 38, 48, 50, 68, 82, 98, 126]  # 76ers (home)
    ml_a = [2.10, 2.05, 2.00, 2.15, 1.95, 1.90, 3.50, 5.00, 15.00, 101.00]  # Hornets odds
    ml_b = [1.70, 1.75, 1.80, 1.65, 1.85, 1.90, 1.10, 1.05, 1.03, 1.01]  # 76ers odds
    
    for i in range(10):
        snap = LiveOddsSnapshot(
            game_id=game_id,
            timestamp=base_time + timedelta(minutes=i*5),
            quarter=quarters[i],
            game_clock=clocks[i],
            teamA_score=scores_a[i],
            teamB_score=scores_b[i],
            teamA_ml=ml_a[i],
            teamB_ml=ml_b[i],
            spread_line=-5.5 if i < 5 else -8.5,
            total_line=217.0 if i < 5 else 215.0
        )
        snapshots.append(snap)
    
    db.add_all(snapshots)
    db.commit()
    
    return {"status": "demo_loaded", "count": len(snapshots), "game_id": game_id}
