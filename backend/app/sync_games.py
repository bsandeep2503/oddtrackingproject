from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
from datetime import datetime
from .scraper import scrape_pregame_game


def sync_games_from_oddsportal():
    """
    Scrape scheduled + live NBA games from OddsPortal NBA page.
    Returns list of dicts: {home_team, away_team, url, status, start_time}
    """
    url = "https://www.oddsportal.com/basketball/usa/nba/"
    games = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_timeout(5000)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        rows = soup.select(".eventRow")
        for row in rows:
            teams = row.select("[data-testid*='participant']")
            if not teams:
                continue

            team_text = teams[0].get_text(strip=True)
            team_split = team_text.replace('–', '|').replace(' - ', '|').split('|')
            if len(team_split) < 2:
                continue

            away_team = re.sub(r'^\d+\s*|\s*\d+$', '', team_split[0]).strip()
            home_team = re.sub(r'^\d+\s*|\s*\d+$', '', team_split[1]).strip()

            link = row.select_one("a[href*='/basketball/usa/nba/']")
            if not link:
                continue
            href = link.get("href")
            full_url = f"https://www.oddsportal.com{href}"

            row_text = row.get_text(" ").lower()
            status = "scheduled"
            if "live" in row_text or re.search(r"\bq\d\b", row_text):
                status = "live"
            if "final" in row_text or "ft" in row_text:
                status = "final"

            # Start time (if visible)
            start_time = None
            time_match = re.search(r"\b\d{1,2}:\d{2}\b", row_text)
            if time_match:
                # store as string for now (convert in DB layer if needed)
                start_time = time_match.group(0)

            # Pregame odds from row (decimal odds often visible on list page)
            # Grab first two decimal odds as MLs if present
            decimals = re.findall(r"\d+\.\d{2}", row_text)
            ml_home = None
            ml_away = None
            if len(decimals) >= 2:
                ml_away = float(decimals[0])
                ml_home = float(decimals[1])

            # Spread + total (basic regex, may need tuning)
            spread = None
            total = None
            spread_match = re.search(r"([+-]\d+(\.\d+)?)\s*\(?-?\d{2,3}\)?", row_text)
            total_match = re.search(r"\b(2\d{2}(\.\d+)?)\b", row_text)
            if spread_match:
                try:
                    spread = float(spread_match.group(1))
                except:
                    pass
            if total_match:
                try:
                    total = float(total_match.group(1))
                except:
                    pass

            pre = None
            if status == "scheduled":
                pre = scrape_pregame_game(full_url, 0)

            games.append({
                "home_team": home_team,
                "away_team": away_team,
                "url": full_url,
                "status": status,
                "start_time": pre.get("start_time") if pre else start_time,
                "ml_home": pre.get("ml_home") if pre else ml_home,
                "ml_away": pre.get("ml_away") if pre else ml_away,
                "spread": spread,
                "total": total
            })

        browser.close()

    return games