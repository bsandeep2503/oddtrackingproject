from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from .models import QuarterSnapshot
import logging
import re
import time
import html
import json
import random
# asyncio removed (sync Playwright)

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

def _random_user_agent():
    return random.choice(USER_AGENTS)

def _jitter(min_s: float = 0.3, max_s: float = 1.2) -> float:
    return random.uniform(min_s, max_s)

def _goto_with_retries(page, url: str, attempts: int = 3):
    last_err = None
    for i in range(attempts):
        try:
            wait_until = "load" if i == 0 else "domcontentloaded"
            page.goto(url, wait_until=wait_until, timeout=15000)
            return True
        except Exception as e:
            last_err = e
            time.sleep(1.0 + i * 1.2 + _jitter(0.2, 0.8))
    logger.warning(f"Navigation failed after {attempts} attempts: {last_err}")
    return False

def _stage_from_header(header_data) -> str:
    if not header_data:
        return None
    stage = (header_data.get("event_stage") or "").lower()
    if "final" in stage or "finished" in stage:
        return "final"
    if "halftime" in stage or "half-time" in stage:
        return "Q2"
    q_match = re.search(r"(\d)(?:st|nd|rd|th)?\s*quarter", stage)
    if q_match:
        return f"Q{q_match.group(1)}"
    if "live" in stage:
        return "live"
    return None


def extract_event_header_data(html_text: str):
    """
    Extract event header JSON from OddsPortal page.
    Returns dict with home/away/start_time/prematch_url if found.
    """
    m = re.search(r'id="react-event-header"[^>]*data="([^"]+)"', html_text)
    if not m:
        return None
    raw = html.unescape(m.group(1))
    try:
        data = json.loads(raw)
        start_ts = data.get("eventBody", {}).get("startDate")
        home = data.get("eventData", {}).get("home")
        away = data.get("eventData", {}).get("away")
        prematch_url = data.get("eventBody", {}).get("tabs", {}).get("eventDetail", {}).get("prematch", {}).get("url")
        event_stage = data.get("eventBody", {}).get("eventStageName")
        is_live = data.get("eventData", {}).get("isLive")
        is_finished = data.get("eventData", {}).get("isFinished")

        start_time = None
        if start_ts:
            start_time = datetime.utcfromtimestamp(start_ts)

        return {
            "home": home,
            "away": away,
            "start_time": start_time,
            "prematch_url": prematch_url,
            "event_stage": event_stage,
            "is_live": is_live,
            "is_finished": is_finished
        }
    except Exception as e:
        logger.warning(f"Failed to parse react-event-header JSON: {e}")
        return None

def find_live_nba_game():
    """
    Finds the URL of the currently live NBA game on OddsPortal.
    Returns the game URL if found, None otherwise.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
            context = browser.new_context(
                user_agent=_random_user_agent(),
                locale="en-US",
                timezone_id="America/New_York",
                viewport={"width": 1280, "height": 720}
            )
            page = context.new_page()
            _goto_with_retries(page, "https://www.oddsportal.com/basketball/usa/nba/")
            page.wait_for_timeout(int(_jitter(2500, 4500)))
            
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            # Look for games with scores (indicating live or finished)
            rows = soup.select(".eventRow")
            
            for row in rows:
                row_text = row.get_text()
                print(f"Row text: {row_text[:100]}")  # Debug
                
                # Skip rows that look like finished games
                if re.search(r"\b(final|ft|finished)\b", row_text, re.IGNORECASE):
                    continue

                # Look for patterns like "Team1 score1:score2 Team2" 
                # Find all numbers in the row that could be scores
                numbers = re.findall(r'\d+', row_text)
                print(f"Numbers found: {numbers[:10]}")  # Debug
                
                # Look for consecutive numbers that could be scores
                for i in range(len(numbers) - 1):
                    score1 = int(numbers[i])
                    score2 = int(numbers[i+1])
                    if score1 < 200 and score2 < 200 and score1 > 0 and score2 > 0:
                        # Check if this looks like a score pattern (not time, not odds)
                        # Skip if it looks like time (e.g., 19 30 for 19:30)
                        if not (score1 in [19,20,21,22] and score2 in [0,30]):
                            # Require live indicator
                            if not re.search(r"\bQ\d\b|Quarter|Live", row_text, re.IGNORECASE):
                                continue
                            print(f"Potential scores: {score1}-{score2}")  # Debug
                            # Get the game link
                            links = row.select('a[href*="/basketball/usa/nba/"]')
                            for link in links:
                                href = link.get('href')
                                if href and '/basketball/usa/nba/' in href and not href.endswith('/') and len(href) > len('/basketball/usa/nba/'):
                                    full_url = f"https://www.oddsportal.com{href}"
                                    logger.info(f"Found NBA game with potential scores {score1}-{score2}: {full_url}")
                                    browser.close()
                                    return full_url
            
            logger.info("No NBA games with scores found")
            browser.close()
            return None
            
    except Exception as e:
        logger.error(f"Error finding live NBA game: {e}")
        return None

def scrape_oddsportal_quarter(game_id: int):
    """
    Scrapes OddsPortal for live NBA game odds.
    Updated for current OddsPortal structure using .eventRow divs.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
            context = browser.new_context(
                user_agent=_random_user_agent(),
                locale="en-US",
                timezone_id="America/New_York",
                viewport={"width": 1280, "height": 720}
            )
            page = context.new_page()
            _goto_with_retries(page, "https://www.oddsportal.com/basketball/usa/nba/")

            page.wait_for_timeout(int(_jitter(2500, 4500)))
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            snapshots = []
            
            # Get all game rows (eventRow divs)
            rows = soup.select(".eventRow")
            if not rows:
                logger.warning("No eventRow elements found")
                browser.close()
                return []

            # Filter to rows with team data
            game_rows = [r for r in rows if r.select("[data-testid*='participant']")]
            if not game_rows:
                logger.warning("No game rows with teams found")
                browser.close()
                return []

            # Process each game row
            for row in game_rows:
                try:
                    teams = row.select("[data-testid*='participant']")
                    if not teams:
                        continue
                    
                    team_text = teams[0].get_text(strip=True)
                    # Split by em dash or hyphen
                    team_split = team_text.replace('–', '|').replace(' - ', '|').split('|')
                    
                    if len(team_split) < 2:
                        continue
                    
                    # Remove numbers from both ends of each team name
                    away_team = team_split[0].strip()
                    away_team = re.sub(r'^\d+\s*', '', away_team)  # Remove leading digits
                    away_team = re.sub(r'\s*\d+$', '', away_team)  # Remove trailing digits
                    
                    home_team = team_split[1].strip()
                    home_team = re.sub(r'^\d+\s*', '', home_team)  # Remove leading digits
                    home_team = re.sub(r'\s*\d+$', '', home_team)  # Remove trailing digits
                    
                    # Extract odds from row text
                    row_text = row.get_text()
                    decimals = re.findall(r'\d+\.\d{2}', row_text)
                    
                    ml_home = None
                    ml_away = None
                    
                    if len(decimals) >= 2:
                        try:
                            ml_home = float(decimals[0])
                            ml_away = float(decimals[1])
                        except ValueError:
                            pass
                    
                    # Skip rows without valid odds
                    if not (ml_home and ml_away):
                        logger.debug(f"No valid odds found for {home_team} vs {away_team}")
                        continue
                    
                    # Create quarter snapshot
                    snapshot = QuarterSnapshot(
                        game_id=game_id,
                        stage="live",
                        score_home=0,
                        score_away=0,
                        score_diff=0,
                        ml_home=ml_home,
                        ml_away=ml_away,
                        spread=0.0,
                        timestamp=datetime.now(timezone.utc)
                    )
                    
                    snapshots.append(snapshot)
                    logger.info(f"Scraped: {home_team} vs {away_team} - Odds: {ml_home}/{ml_away}")
                    
                    # Return first live game found
                    if snapshots:
                        break
                
                except Exception as e:
                    logger.error(f"Error processing game row: {e}")
                    continue
            
            browser.close()
            return snapshots

    except Exception as e:
        logger.error(f"Scraper error: {e}")
        return []


def scrape_completed_games(game_id: int):
    """
    Scrapes OddsPortal results page for a completed NBA game.
    Returns (snapshots, game_info) where snapshots include pregame + final.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
            context = browser.new_context(
                user_agent=_random_user_agent(),
                locale="en-US",
                timezone_id="America/New_York",
                viewport={"width": 1280, "height": 720}
            )
            page = context.new_page()
            _goto_with_retries(page, "https://www.oddsportal.com/basketball/usa/nba/results/")
            time.sleep(_jitter(1.5, 3.0))

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            rows = soup.select(".eventRow")
            if not rows:
                browser.close()
                return [], {}

            # Find first row with a plausible final score
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

                row_text = row.get_text(" ")
                score_match = re.search(r'(\d{2,3})\s*[–-]\s*(\d{2,3})', row_text)
                if not score_match:
                    continue

                score_home = int(score_match.group(1))
                score_away = int(score_match.group(2))
                if not (50 <= score_home <= 160 and 50 <= score_away <= 160):
                    continue

                # Try to grab any visible decimal odds for pregame/final
                decimals = re.findall(r'\d+\.\d{2}', row_text)
                ml_home = float(decimals[0]) if len(decimals) >= 1 else 0.0
                ml_away = float(decimals[1]) if len(decimals) >= 2 else 0.0

                snapshots = [
                    QuarterSnapshot(
                        game_id=game_id,
                        stage="pregame",
                        score_home=0,
                        score_away=0,
                        score_diff=0,
                        ml_home=ml_home,
                        ml_away=ml_away,
                        spread=0.0,
                        timestamp=datetime.now(timezone.utc)
                    ),
                    QuarterSnapshot(
                        game_id=game_id,
                        stage="final",
                        score_home=score_home,
                        score_away=score_away,
                        score_diff=score_home - score_away,
                        ml_home=ml_home,
                        ml_away=ml_away,
                        spread=0.0,
                        timestamp=datetime.now(timezone.utc)
                    )
                ]

                browser.close()
                return snapshots, {
                    "home": home_team,
                    "away": away_team,
                    "score_home": score_home,
                    "score_away": score_away
                }

            browser.close()
            return [], {}

    except Exception as e:
        logger.error(f"Completed games scraper error: {e}")
        return [], {}

def scrape_live_game(game_url: str, game_id: int):
    """
    Scrapes live NBA game odds from OddsPortal during the game.
    Extracts current score and in-play moneyline odds.
    
    Args:
        game_url: Full OddsPortal URL for the game
        game_id: Database game ID for storing snapshots
    
    Returns:
        dict with score, odds, quarter, time
    """
    browser = None
    page = None
    p = None
    
    try:
        p = sync_playwright().start()
        logger.info("Playwright started")
        
        # Use headless=True for production (less memory, no UI)
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        logger.info("Browser launched")

        context = browser.new_context(
            user_agent=_random_user_agent(),
            locale="en-US",
            timezone_id="America/New_York",
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()
        logger.info("Page created")

        logger.info(f"Navigating to: {game_url}")
        _goto_with_retries(page, game_url, attempts=3)

        # Wait a bit for JavaScript to render
        time.sleep(_jitter(2.0, 4.0))
        
        # Click "In-Play Odds" tab to get live odds
        try:
            # Look for the "In-Play Odds" link
            in_play_link = page.locator("a[data-testid='sub-nav-inactive-tab']:has-text('In-Play')")
            link_count = in_play_link.count()
            logger.info(f"Found {link_count} 'In-Play Odds' tabs")

            if link_count > 0:
                logger.info("Attempting to click In-Play Odds tab...")
                in_play_link.first.click(timeout=5000)
                time.sleep(2)
                logger.info("✓ Clicked In-Play Odds tab, waiting for page update")
                # Get updated content after clicking
                html = page.content()
            else:
                # Maybe the In-Play tab is already active
                in_play_active = page.locator("a[data-testid='sub-nav-active-tab']:has-text('In-Play')")
                if in_play_active.count() > 0:
                    logger.info("✓ In-Play Odds tab already active")
                else:
                    logger.warning("✗ Could not find In-Play Odds tab - trying to extract from pre-match view")
        except Exception as e:
            logger.warning(f"Could not click In-Play Odds tab: {e}")
            logger.info("Continuing with current page content...")
        
        # Get the page content
        logger.info("Extracting page content")
        html = page.content()
        logger.info(f"HTML length: {len(html)} bytes")
        try:
            from pathlib import Path
            debug_dir = Path(__file__).resolve().parent
            debug_html_path = debug_dir / "debug_page_html.html"
            with open(debug_html_path, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info(f"Saved page HTML to {debug_html_path}")
        except Exception as write_err:
            logger.warning(f"Failed to write debug HTML: {write_err}")
        
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()
        normalized_text = text.replace("\xa0", " ")
        logger.info(f"Extracted text length: {len(text)} characters")

        # Pull structured event header data (teams, stage, status)
        header_data = extract_event_header_data(html)

        # Detect event status from JSON-LD if present
        event_status = None
        try:
            import json
            for script in soup.find_all("script", type="application/ld+json"):
                data = script.string
                if not data:
                    continue
                obj = json.loads(data)
                if isinstance(obj, dict) and obj.get("eventStatus"):
                    status = obj.get("eventStatus")
                    if isinstance(status, dict):
                        event_status = status.get("@id") or status.get("name")
                    else:
                        event_status = status
                    break
        except Exception as status_err:
            logger.debug(f"Failed to parse event status: {status_err}")
        
        # Debug: save text to file
        try:
            from pathlib import Path
            debug_dir = Path(__file__).resolve().parent
            debug_text_path = debug_dir / "debug_page_text.txt"
            with open(debug_text_path, "w", encoding="utf-8") as f:
                f.write(text)
            logger.info(f"Saved page text to {debug_text_path}")
        except Exception as write_err:
            logger.warning(f"Failed to write debug text: {write_err}")
        
        # Extract team names from page title or header
        logger.info("Extracting team names...")
        title = soup.find('title')
        h1 = soup.find('h1')

        if header_data and header_data.get("home") and header_data.get("away"):
            home_team = header_data["home"]
            away_team = header_data["away"]
            logger.info(f"✓ Extracted teams from event header: {away_team} vs {home_team}")
        elif title:
            title_text = title.get_text()
            logger.debug(f"Page title: {title_text}")

            # Try multiple patterns for title
            title_patterns = [
                r'(.+?)\s*[-–]\s*(.+?)\s+Odds',  # "Team1 - Team2 Odds"
                r'(.+?)\s*[-–]\s*(.+?)\s+Predictions',  # "Team1 - Team2 Predictions"
                r'(.+?)\s*[-–]\s*(.+?)\s+Basketball',  # "Team1 - Team2 Basketball"
            ]

            for pattern in title_patterns:
                title_match = re.search(pattern, title_text)
                if title_match:
                    away_team = title_match.group(1).strip()
                    home_team = title_match.group(2).strip()
                    logger.info(f"✓ Extracted teams from title: {away_team} vs {home_team}")
                    break
            else:
                # Try H1 element
                if h1:
                    h1_text = h1.get_text()
                    logger.debug(f"H1: {h1_text}")
                    h1_match = re.search(r'(.+?)\s+vs\s+(.+?)\s*-', h1_text)
                    if h1_match:
                        away_team = h1_match.group(1).strip()
                        home_team = h1_match.group(2).strip()
                        logger.info(f"✓ Extracted teams from H1: {away_team} vs {home_team}")
                    else:
                        logger.warning("✗ Could not extract teams from H1")
                        away_team = "Away Team"
                        home_team = "Home Team"
                else:
                    logger.warning("✗ Could not find title or H1")
                    away_team = "Away Team"
                    home_team = "Home Team"
        else:
            logger.warning("✗ No title found")
            away_team = "Away Team"
            home_team = "Home Team"
        
        # Extract live scores
        logger.info("Extracting live scores...")
        score_home = 0
        score_away = 0

        # Prefer team-name anchored score extraction to avoid matching timestamps
        team_score_pattern = rf"{re.escape(away_team)}\D*(\d{{1,3}})\D+(\d{{1,3}})\D*{re.escape(home_team)}"
        team_score_match = re.search(team_score_pattern, text)
        if team_score_match:
            score_away = int(team_score_match.group(1))
            score_home = int(team_score_match.group(2))
            logger.info(f"✓ Live score (team-anchored): {away_team} {score_away} - {score_home} {home_team}")
        else:
            logger.warning("✗ Could not extract live scores, using 0-0")
        
        # If event is scheduled and no live score found, treat as not live
        if event_status and "EventScheduled" in str(event_status) and score_home == 0 and score_away == 0:
            logger.info("Event appears scheduled with no live score; skipping as not live")
            return None

        # Extract quarter and time
        current_quarter = "Q1"  # Default
        current_time = "00:00"

        # Detect final games early
        if "final result" in normalized_text.lower() or re.search(r"\bfinal\b", normalized_text, re.IGNORECASE):
            current_quarter = "final"

        # Prefer event header stage if present
        header_stage = _stage_from_header(header_data)
        if header_stage:
            current_quarter = header_stage
        
        # Look for quarter indicators only if game is not final
        if current_quarter != "final":
            quarter_patterns = [
                r'\b\d{1,2}:\d{2}(\d)(?:st|nd|rd|th)?\s*Quarter',
                r'(?<!\d)(\d{1,2})(?:st|nd|rd|th)?\s*Quarter',
                r'\b(\d+)Q\b',
                r'\bQ(\d+)\b',
                r'\bQuarter\s+(\d+)\b',
            ]

            for pattern in quarter_patterns:
                quarter_match = re.search(pattern, normalized_text, re.IGNORECASE)
                if quarter_match:
                    quarter_num = quarter_match.group(1) or quarter_match.group(2)
                    logger.info(f"Quarter match: pattern={pattern}, match='{quarter_match.group(0)}', groups={quarter_match.groups()}, quarter_num={quarter_num}")
                    try:
                        current_quarter = f"Q{int(quarter_num)}"
                    except (TypeError, ValueError):
                        current_quarter = f"Q{quarter_num}"
                    logger.info(f"✓ Current quarter: {current_quarter}")
                    break
        
        # Look for time remaining
        time_patterns = [
            r'(\d+):(\d+)',  # 7:30
            r'(\d+)\'(\d+)"',  # 7'30"
        ]
        
        for pattern in time_patterns:
            time_match = re.search(pattern, normalized_text)
            if time_match:
                minutes = time_match.group(1)
                seconds = time_match.group(2)
                current_time = f"{minutes}:{seconds}"
                logger.info(f"✓ Time remaining: {current_time}")
                break
        
        # Extract live moneyline odds
        logger.info("Extracting moneyline odds...")
        # Look for American odds pairs: +XXX -YYY or -XXX +YYY
        odds_pair_pattern = r'([+-]\d{2,3})\s*([+-]\d{2,3})'
        pair_matches = re.findall(odds_pair_pattern, text)
        
        ml_home = 0.0
        ml_away = 0.0
        
        logger.info(f"Found {len(pair_matches)} odds pairs")
        if len(pair_matches) > 0:
            logger.debug(f"Odds pairs: {pair_matches[:5]}")
            # Filter valid pairs (one positive, one negative)
            valid_pairs = [p for p in pair_matches if (p[0].startswith('-') and p[1].startswith('+')) or (p[0].startswith('+') and p[1].startswith('-'))]
            if valid_pairs:
                # Sort by the absolute value of the favorite's odds (lowest number first = best odds)
                valid_pairs.sort(key=lambda x: min(abs(int(x[0])), abs(int(x[1]))))
                logger.debug(f"Sorted valid pairs: {valid_pairs[:3]}")
                pair = valid_pairs[0]
                odds1 = int(pair[0])
                odds2 = int(pair[1])
                # The negative one is the favorite
                if odds1 < 0:
                    home_american = odds1
                    away_american = odds2
                else:
                    home_american = odds2
                    away_american = odds1
                
                # Convert to decimal
                ml_home = american_to_decimal(home_american)
                ml_away = american_to_decimal(away_american)
                logger.info(f"✓ Extracted odds: {ml_home:.2f} / {ml_away:.2f}")
            else:
                logger.warning("No valid odds pairs found")
        else:
            logger.warning(f"✗ No odds pairs found")
        

        # Fallback to decimal odds if American odds not found
        if (ml_home == 0.0 or ml_away == 0.0):
            decimal_candidates = [float(d) for d in re.findall(r"\d+\.\d{2}", text) if float(d) > 1.01]
            if len(decimal_candidates) >= 2:
                ml_home = decimal_candidates[0]
                ml_away = decimal_candidates[1]
                logger.info(f"✓ Fallback decimal odds: {ml_home:.2f} / {ml_away:.2f}")
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "score_home": score_home,
            "score_away": score_away,
            "ml_home": ml_home,
            "ml_away": ml_away,
            "quarter": current_quarter,
            "time": current_time,
            "home_team": home_team,
            "away_team": away_team
        }
        
        return result
    
    except Exception as e:
        logger.error(f"Live game scraper error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None
    
    finally:
        # Ensure browser is closed properly
        try:
            if page:
                page.close()
            if browser:
                browser.close()
            if p:
                p.stop()
        except:
            pass


def scrape_pregame_game(game_url: str, game_id: int):
    """
    Scrapes pre-game NBA odds from OddsPortal before the game starts.
    Extracts pre-game moneyline odds.
    
    Args:
        game_url: Full OddsPortal URL for the game
        game_id: Database game ID for storing snapshots
    
    Returns:
        dict with score, odds, quarter, time
    """
    browser = None
    page = None
    p = None
    
    try:
        p = sync_playwright().start()
        logger.info("Playwright started for pre-game")
        
        # Use headless=True for production (less memory, no UI)
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        logger.info("Browser launched")

        context = browser.new_context(
            user_agent=_random_user_agent(),
            locale="en-US",
            timezone_id="America/New_York",
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()
        logger.info("Page created")

        logger.info(f"Navigating to: {game_url}")
        _goto_with_retries(page, game_url, attempts=3)

        # Wait a bit for JavaScript to render
        time.sleep(_jitter(2.0, 4.0))
        
        # For pre-game, we don't click "In-Play Odds" - use the default pre-match view
        
        # Get the page content
        logger.info("Extracting page content")
        html = page.content()
        logger.info(f"HTML length: {len(html)} bytes")
        
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()
        logger.info(f"Extracted text length: {len(text)} characters")

        # Pull structured event header data
        header_data = extract_event_header_data(html)

        # Prefer event header data for team names
        logger.info("Extracting team names...")
        title = soup.find('title')
        h1 = soup.find('h1')

        if header_data and header_data.get("home") and header_data.get("away"):
            home_team = header_data["home"]
            away_team = header_data["away"]
            logger.info(f"✓ Extracted teams from event header: {away_team} vs {home_team}")
        elif title:
            title_text = title.get_text()
            logger.debug(f"Page title: {title_text}")

            # Try multiple patterns for title
            title_patterns = [
                r'(.+?)\s*[-–]\s*(.+?)\s+Odds',  # "Team1 - Team2 Odds"
                r'(.+?)\s*[-–]\s*(.+?)\s+Predictions',  # "Team1 - Team2 Predictions"
                r'(.+?)\s*[-–]\s*(.+?)\s+Basketball',  # "Team1 - Team2 Basketball"
            ]

            for pattern in title_patterns:
                title_match = re.search(pattern, title_text)
                if title_match:
                    away_team = title_match.group(1).strip()
                    home_team = title_match.group(2).strip()
                    logger.info(f"✓ Extracted teams from title: {away_team} vs {home_team}")
                    break
            else:
                # Try H1 element
                if h1:
                    h1_text = h1.get_text()
                    logger.debug(f"H1: {h1_text}")
                    h1_match = re.search(r'(.+?)\s+vs\s+(.+?)\s*-', h1_text)
                    if h1_match:
                        away_team = h1_match.group(1).strip()
                        home_team = h1_match.group(2).strip()
                        logger.info(f"✓ Extracted teams from H1: {away_team} vs {home_team}")
                    else:
                        logger.warning("✗ Could not extract teams from H1")
                        away_team = "Away Team"
                        home_team = "Home Team"
                else:
                    logger.warning("✗ Could not find title or H1")
                    away_team = "Away Team"
                    home_team = "Home Team"
        else:
            logger.warning("✗ No title found")
            away_team = "Away Team"
            home_team = "Home Team"
        
        # For pre-game, score is 0-0, don't extract live scores
        score_home = 0
        score_away = 0
        logger.info(f"✓ Pre-game score: {away_team} {score_away} - {score_home} {home_team}")
        
        # Quarter is pregame
        current_quarter = "pregame"
        current_time = "00:00"
        logger.info(f"✓ Current quarter: {current_quarter}, Time: {current_time}")
        
        # Extract pre-game moneyline odds
        logger.info("Extracting pre-game moneyline odds...")
        # Look for American odds pairs: +XXX -YYY or -XXX +YYY
        odds_pair_pattern = r'([+-]\d{2,3})\s*([+-]\d{2,3})'
        pair_matches = re.findall(odds_pair_pattern, text)
        
        ml_home = 0.0
        ml_away = 0.0
        
        logger.info(f"Found {len(pair_matches)} odds pairs")
        if len(pair_matches) > 0:
            logger.debug(f"Odds pairs: {pair_matches[:5]}")
            # Filter valid pairs (one positive, one negative)
            valid_pairs = [p for p in pair_matches if (p[0].startswith('-') and p[1].startswith('+')) or (p[0].startswith('+') and p[1].startswith('-'))]
            if valid_pairs:
                # Sort by the absolute value of the favorite's odds (lowest number first = best odds)
                valid_pairs.sort(key=lambda x: min(abs(int(x[0])), abs(int(x[1]))))
                logger.debug(f"Sorted valid pairs: {valid_pairs[:3]}")
                pair = valid_pairs[0]
                odds1 = int(pair[0])
                odds2 = int(pair[1])
                # The negative one is the favorite
                if odds1 < 0:
                    home_american = odds1
                    away_american = odds2
                else:
                    home_american = odds2
                    away_american = odds1
                
                # Convert to decimal
                ml_home = american_to_decimal(home_american)
                ml_away = american_to_decimal(away_american)
                logger.info(f"✓ Extracted odds: {ml_home:.2f} / {ml_away:.2f}")
            else:
                logger.warning("No valid odds pairs found")
        else:
            logger.warning(f"✗ No odds pairs found")
        

        # Fallback to decimal odds if American odds not found
        if (ml_home == 0.0 or ml_away == 0.0):
            decimal_candidates = [float(d) for d in re.findall(r"\d+\.\d{2}", text) if float(d) > 1.01]
            if len(decimal_candidates) >= 2:
                ml_home = decimal_candidates[0]
                ml_away = decimal_candidates[1]
                logger.info(f"✓ Fallback decimal odds: {ml_home:.2f} / {ml_away:.2f}")
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "score_home": score_home,
            "score_away": score_away,
            "ml_home": ml_home,
            "ml_away": ml_away,
            "quarter": current_quarter,
            "time": current_time,
            "home_team": home_team,
            "away_team": away_team,
            "start_time": header_data.get("start_time") if header_data else None,
            "prematch_url": header_data.get("prematch_url") if header_data else None
        }
        
        return result
    
    except Exception as e:
        logger.error(f"Pre-game scraper error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None
    
    finally:
        # Ensure browser is closed properly
        try:
            if page:
                page.close()
            if browser:
                browser.close()
            if p:
                p.stop()
        except:
            pass


def american_to_decimal(american_odds: int) -> float:
    """Convert American moneyline odds to decimal odds"""
    try:
        if american_odds > 0:
            return (american_odds / 100) + 1
        else:
            return (100 / abs(american_odds)) + 1
    except:
        return 0.0

