#!/usr/bin/env python
"""
Load demo data directly into database
"""
import sys
sys.path.insert(0, '.')

from app.db import SessionLocal, init_db
from app.models import Game, QuarterSnapshot
from datetime import datetime

print("\n" + "="*70)
print("Loading Demo Data into Database")
print("="*70 + "\n")

try:
    # Initialize database
    init_db()
    print("[1] Database tables created\n")
    
    db = SessionLocal()
    
    # Create game
    game = Game(id=2, home_team="Philadelphia 76ers", away_team="Charlotte Hornets")
    db.merge(game)  # Use merge to avoid conflicts
    db.commit()
    print("[2] Game created: Charlotte Hornets vs Philadelphia 76ers\n")
    
    # Clear old quarters
    db.query(QuarterSnapshot).filter(QuarterSnapshot.game_id == 2).delete()
    db.commit()
    print("[3] Old quarter snapshots cleared\n")
    
    # Create demo quarters
    base_time = datetime.utcnow()
    demo_rows = [
        {"stage": "pregame", "score_home": 0, "score_away": 0, "score_diff": 0, "ml_home": 1.19, "ml_away": 4.91, "spread": -15.5},
        {"stage": "Q1", "score_home": 25, "score_away": 28, "score_diff": -3, "ml_home": 1.25, "ml_away": 4.50, "spread": -14},
        {"stage": "Q2", "score_home": 50, "score_away": 52, "score_diff": -2, "ml_home": 1.22, "ml_away": 4.70, "spread": -13},
        {"stage": "Q3", "score_home": 75, "score_away": 85, "score_diff": -10, "ml_home": 1.10, "ml_away": 8.00, "spread": -16},
    ]
    
    for row in demo_rows:
        snap = QuarterSnapshot(
            game_id=2,
            stage=row["stage"],
            score_home=row["score_home"],
            score_away=row["score_away"],
            score_diff=row["score_diff"],
            ml_home=row["ml_home"],
            ml_away=row["ml_away"],
            spread=row["spread"],
            timestamp=base_time,
        )
        db.add(snap)
    
    db.commit()
    print("[4] Demo quarter snapshots created")
    print(f"    - Pregame")
    print(f"    - Q1 (Hornets 28, 76ers 25)")
    print(f"    - Q2 (Hornets 52, 76ers 50)")
    print(f"    - Q3 (Hornets 85, 76ers 75)\n")
    
    # Verify
    quarters = db.query(QuarterSnapshot).filter(QuarterSnapshot.game_id == 2).all()
    print(f"[5] Verification: {len(quarters)} snapshots in database\n")
    
    db.close()
    
    print("="*70)
    print("SUCCESS! Demo data loaded.")
    print("="*70)
    print("\nNow:")
    print("  1. Make sure backend is running: uvicorn app.main:app --reload")
    print("  2. Refresh browser: http://localhost:5173")
    print("="*70 + "\n")
    
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
