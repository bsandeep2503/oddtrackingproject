from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re


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

            start_time = None
            time_match = re.search(r"\b\d{1,2}:\d{2}\b", row_text)
            if time_match:
                start_time = time_match.group(0)

            games.append({
                "home_team": home_team,
                "away_team": away_team,
                "url": full_url,
                "status": status,
                "start_time": start_time
            })

        browser.close()

    return games