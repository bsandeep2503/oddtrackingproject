"""
Simple poller script to poll Pinnacle API and store live odds snapshots.

Run once:
    python pinnacle_poller.py --once

Run continuous:
    python pinnacle_poller.py

Set env vars: PINNACLE_USERNAME, PINNACLE_PASSWORD (and PINNACLE_API_BASE if needed)
"""
import time
import argparse
from app.pinnacle import fetch_odds_by_sport
from app.live_scores import fetch_live_scores_by_date
from app.db import SessionLocal
from app.models import LiveOddsSnapshot


def _match_event(p_ev, live_events):
    """Try to find a matching live event by event_id or team name similarity."""
    # Exact event id match
    pid = str(p_ev.get("event_id"))
    for le in live_events:
        if pid and le.get("event_id") and pid == str(le.get("event_id")):
            return le

    # Fallback: match by team names (case-insensitive substring)
    ph = (p_ev.get("home") or "").lower() if p_ev.get("home") else ""
    pa = (p_ev.get("away") or "").lower() if p_ev.get("away") else ""
    for le in live_events:
        lh = (le.get("home") or "").lower() if le.get("home") else ""
        la = (le.get("away") or "").lower() if le.get("away") else ""
        if ph and pa and ((ph in lh and pa in la) or (ph in la and pa in lh)):
            return le

    return None


def store_once():
    db = SessionLocal()
    try:
        results = fetch_odds_by_sport(sport_id=29)
        # pull today's live scores from ESPN to merge
        live_events = fetch_live_scores_by_date()

        rows = []
        for r in results:
            # try to match to a live event
            matched = _match_event(r, live_events)

            teamA_score = None
            teamB_score = None
            quarter = None
            clock = None

            if matched:
                # ESPN uses home/away fields
                teamA_score = matched.get('away_score')
                teamB_score = matched.get('home_score')
                quarter = matched.get('quarter')
                clock = matched.get('clock')

            snap = LiveOddsSnapshot(
                game_id=str(r.get('event_id') or f"{r.get('home')} vs {r.get('away')}"),
                timestamp=r.get('timestamp'),
                quarter=quarter,
                game_clock=clock,
                teamA_score=teamA_score,
                teamB_score=teamB_score,
                teamA_ml=r.get('ml_home'),
                teamB_ml=r.get('ml_away'),
                spread_line=r.get('spread'),
                total_line=r.get('total')
            )
            rows.append(snap)

        if rows:
            db.add_all(rows)
            db.commit()
        return len(rows)
    finally:
        db.close()


def main(loop: bool):
    try:
        while True:
            count = store_once()
            print(f"Stored {count} Pinnacle snapshots")
            if not loop:
                break
            time.sleep(60)
    except KeyboardInterrupt:
        print("Poller stopped")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    main(loop=not args.once)
