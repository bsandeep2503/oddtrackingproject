import os
import requests
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Configuration: set these env vars in your environment
PINNACLE_API_BASE = os.environ.get("PINNACLE_API_BASE", "https://api.pinnacle.com")
PINNACLE_USERNAME = os.environ.get("PINNACLE_USERNAME")
PINNACLE_PASSWORD = os.environ.get("PINNACLE_PASSWORD")


def _auth():
    if PINNACLE_USERNAME and PINNACLE_PASSWORD:
        return (PINNACLE_USERNAME, PINNACLE_PASSWORD)
    return None


def fetch_odds_by_sport(sport_id: int = 29, league_ids: str = None):
    """Fetch moneyline/spread/total odds for a sport (default NBA sportId=29).

    Returns a list of dicts with keys: event_id, home, away, ml_home, ml_away, spread, total, timestamp
    """
    endpoint = f"{PINNACLE_API_BASE}/v2/odds"
    params = {"sportId": sport_id, "periods": 0}
    if league_ids:
        params["leagueIds"] = league_ids

    try:
        auth = _auth()
        resp = requests.get(endpoint, params=params, auth=auth, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results = []
        # Pinnacle returns 'events' in many responses; adapt to common structure
        events = data.get("events") or data.get("leagueEvents") or data.get("data") or []

        for ev in events:
            try:
                event_id = ev.get("id") or ev.get("eventId") or ev.get("event")
                home = ev.get("home") or ev.get("homeTeam") or ev.get("teams", [None, None])[1]
                away = ev.get("away") or ev.get("awayTeam") or ev.get("teams", [None, None])[0]

                # moneyline markets
                ml_home = None
                ml_away = None
                spread = None
                total = None

                markets = ev.get("periods") or ev.get("markets") or ev.get("lines") or []
                # Try to find moneyline/spread/total in returned markets
                for m in markets:
                    m_type = m.get("type") or m.get("market") or m.get("name")
                    if not m_type:
                        continue
                    m_type = str(m_type).lower()
                    if "moneyline" in m_type or "ml" in m_type:
                        # attempt to parse prices
                        prices = m.get("prices") or m.get("outcomes") or m.get("runners") or []
                        if len(prices) >= 2:
                            # best-effort extraction
                            ml_home = _safe_float(prices[0].get("price") or prices[0].get("priceDecimal") or prices[0].get("odds"))
                            ml_away = _safe_float(prices[1].get("price") or prices[1].get("priceDecimal") or prices[1].get("odds"))
                    if "spread" in m_type or "handicap" in m_type:
                        lines = m.get("lines") or m.get("prices") or []
                        if lines:
                            spread = _safe_float(lines[0].get("line") or lines[0].get("handicap") or lines[0].get("price"))
                    if "total" in m_type or "over/under" in m_type:
                        lines = m.get("lines") or m.get("prices") or []
                        if lines:
                            total = _safe_float(lines[0].get("line") or lines[0].get("total"))

                results.append({
                    "event_id": event_id,
                    "home": home,
                    "away": away,
                    "ml_home": ml_home,
                    "ml_away": ml_away,
                    "spread": spread,
                    "total": total,
                    "timestamp": datetime.utcnow(),
                })
            except Exception:
                logger.exception("Error parsing event")

        return results

    except Exception:
        logger.exception("Error fetching Pinnacle odds")
        return []


def _safe_float(v):
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        try:
            # handle American odds -> convert to decimal approximation
            iv = int(v)
            if iv > 0:
                return (iv / 100) + 1
            return (100 / abs(iv)) + 1
        except Exception:
            return None
