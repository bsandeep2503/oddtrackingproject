"""
Odds Insights Service
Calculates win probabilities, momentum swings, and betting signals
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta

def implied_prob(decimal_odds: float) -> Optional[float]:
    """Convert decimal odds to implied probability (0-1)"""
    if not decimal_odds or decimal_odds <= 1:
        return None
    return 1 / decimal_odds

def swing_pct(prev: float, cur: float) -> Optional[float]:
    """Calculate percentage point swing between two probabilities"""
    if prev is None or cur is None:
        return None
    return round((cur - prev) * 100, 2)

def detect_momentum_events(snapshots: List[Dict]) -> List[Dict]:
    """
    Analyze snapshots for momentum events
    Returns list of insight events
    """
    events = []

    if len(snapshots) < 2:
        return events

    # Sort by timestamp
    sorted_snaps = sorted(snapshots, key=lambda x: x['timestamp'])

    for i in range(1, len(sorted_snaps)):
        prev = sorted_snaps[i-1]
        curr = sorted_snaps[i]

        # Calculate probabilities
        prev_home_prob = implied_prob(prev.get('ml_home'))
        prev_away_prob = implied_prob(prev.get('ml_away'))
        curr_home_prob = implied_prob(curr.get('ml_home'))
        curr_away_prob = implied_prob(curr.get('ml_away'))

        if not all([prev_home_prob, prev_away_prob, curr_home_prob, curr_away_prob]):
            continue

        # Favorite dip: favorite prob drops > 8% within 2 snapshots
        home_swing = swing_pct(prev_home_prob, curr_home_prob)
        away_swing = swing_pct(prev_away_prob, curr_away_prob)

        if home_swing and home_swing < -8:
            events.append({
                "timestamp": curr['timestamp'],
                "type": "favorite_dip",
                "detail": f"Home prob dropped {abs(home_swing)}% to {curr_home_prob:.1%}"
            })

        if away_swing and away_swing < -8:
            events.append({
                "timestamp": curr['timestamp'],
                "type": "favorite_dip",
                "detail": f"Away prob dropped {abs(away_swing)}% to {curr_away_prob:.1%}"
            })

        # Underdog surge: underdog prob rises > 8% within 2 snapshots
        if home_swing and home_swing > 8:
            events.append({
                "timestamp": curr['timestamp'],
                "type": "underdog_surge",
                "detail": f"Home prob surged {home_swing}% to {curr_home_prob:.1%}"
            })

        if away_swing and away_swing > 8:
            events.append({
                "timestamp": curr['timestamp'],
                "type": "underdog_surge",
                "detail": f"Away prob surged {away_swing}% to {curr_away_prob:.1%}"
            })

        # Reversal: prob crosses 50% line
        if prev_home_prob <= 0.5 < curr_home_prob:
            events.append({
                "timestamp": curr['timestamp'],
                "type": "reversal",
                "detail": f"Home crossed 50% to {curr_home_prob:.1%}"
            })

        if prev_away_prob <= 0.5 < curr_away_prob:
            events.append({
                "timestamp": curr['timestamp'],
                "type": "reversal",
                "detail": f"Away crossed 50% to {curr_away_prob:.1%}"
            })

    # Stabilizing: swing < 2% for 3 snapshots (check last 3)
    if len(sorted_snaps) >= 3:
        recent = sorted_snaps[-3:]
        swings = []
        for j in range(1, len(recent)):
            p_home = implied_prob(recent[j-1]['ml_home'])
            c_home = implied_prob(recent[j]['ml_home'])
            if p_home and c_home:
                swings.append(abs(swing_pct(p_home, c_home)))

        if swings and all(s < 2 for s in swings):
            events.append({
                "timestamp": recent[-1]['timestamp'],
                "type": "stabilizing",
                "detail": f"Stable odds, swings < 2% over last 3 polls"
            })

    return events

def get_insights_summary(snapshots: List[Dict]) -> Dict:
    """Generate summary stats from snapshots"""
    if not snapshots:
        return {"favorite": None, "current_prob_home": None, "current_prob_away": None}

    # Get latest snapshot
    latest = max(snapshots, key=lambda x: x['timestamp'])

    home_prob = implied_prob(latest.get('ml_home'))
    away_prob = implied_prob(latest.get('ml_away'))

    favorite = "home" if home_prob and home_prob > 0.5 else "away"

    return {
        "favorite": favorite,
        "current_prob_home": round(home_prob, 3) if home_prob else None,
        "current_prob_away": round(away_prob, 3) if away_prob else None
    }