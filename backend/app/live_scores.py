import requests
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def fetch_live_scores_by_date(date_str=None):
    """Fetch NBA scoreboard from ESPN public API for given date (YYYYMMDD).

    Returns a list of events with keys: event_id, home, away, home_score, away_score, quarter, clock, timestamp
    """
    base = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    params = {}
    if date_str:
        params["dates"] = date_str

    try:
        r = requests.get(base, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        events = []
        for ev in data.get("events", []):
            try:
                event_id = ev.get("id")
                competitions = ev.get("competitions", [])
                if not competitions:
                    continue
                comp = competitions[0]
                competitors = comp.get("competitors", [])
                if len(competitors) < 2:
                    continue

                # ESPN orders competitors with homeAway field
                home = None
                away = None
                home_score = None
                away_score = None
                for c in competitors:
                    if c.get("homeAway") == "home":
                        home = c.get("team", {}).get("displayName")
                        home_score = _safe_int(c.get("score"))
                    else:
                        away = c.get("team", {}).get("displayName")
                        away_score = _safe_int(c.get("score"))

                status = comp.get("status", {})
                quarter = status.get("period")
                clock = status.get("displayClock") or status.get("clock")

                events.append({
                    "event_id": str(event_id),
                    "home": home,
                    "away": away,
                    "home_score": home_score,
                    "away_score": away_score,
                    "quarter": quarter,
                    "clock": clock,
                    "timestamp": datetime.utcnow(),
                })
            except Exception:
                logger.exception("Error parsing ESPN event")

        return events
    except Exception:
        logger.exception("Error fetching ESPN scoreboard")
        return []


def _safe_int(v):
    try:
        if v is None or v == "":
            return None
        return int(v)
    except Exception:
        return None
