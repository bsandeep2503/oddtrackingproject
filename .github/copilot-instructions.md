# NBA Odds Momentum - AI Coding Agent Instructions

## Project Overview
Full-stack application tracking NBA betting odds momentum across game quarters. Real-time web scraping of OddsPortal matches game state snapshots (score, moneyline odds, spreads) to analyze how odds shift during live games.

### Current Status: LIVE POLLING OPERATIONAL ✅
- Live game scraper fully implemented and tested
- Continuous polling system running on every 15 seconds
- Real-time data capture of Charlotte Hornets vs Philadelphia 76ers game
- Successfully capturing: score, quarter, and in-play moneyline odds
- Database persistence working (QuarterSnapshot records being saved)

## Architecture

### Backend (FastAPI + PostgreSQL)
- **Framework**: FastAPI with CORS enabled for frontend communication
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Key modules**:
  - `models.py`: Three core entities - `Game`, `OddsSnapshot`, `QuarterSnapshot`
  - `main.py`: REST API endpoints (startup events initialize DB, health checks)
  - `scraper.py`: Playwright-based web scraping of OddsPortal (both historical and live)
  - `db.py`: Session management, DB initialization, table reset utilities
- **Live Polling Scripts**:
  - `simple_poller.py`: Continuous polling script (runs every 15 seconds)
  - `run_live_poller.py`: Alternative polling script with advanced features

### Frontend (React + Vite)
- **Tech stack**: React 19, Vite, Recharts (visualization), Axios (HTTP)
- **Entry**: `src/main.jsx` with Vite HMR
- **API client**: Configured in `src/config.js` (default: `http://localhost:8000`)
- **Components**: `App.jsx` contains all UI (charts + table for quarter snapshots)

### Data Flow
**For Completed/Historical Games:**
1. Frontend button triggers `/games/{game_id}/scrape-live-quarter` POST
2. Backend uses Playwright to scrape OddsPortal, parses HTML with BeautifulSoup
3. Extracts: moneyline odds, score, spread data → creates `QuarterSnapshot` records
4. Frontend fetches `/games/{game_id}/quarters` to render Recharts visualizations

**For Live Games (NEW):**
1. `simple_poller.py` runs continuously, polling every 15 seconds
2. Sends POST request to `/games/{game_id}/scrape-live` endpoint
3. Backend launches Playwright browser, navigates to OddsPortal game URL
4. Clicks "In-Play Odds" button to access real-time odds (not pregame)
5. Extracts current score, quarter, and moneyline odds using regex patterns
6. Converts American odds to decimal format (-133/+104 → 1.75/2.04)
7. Returns JSON with timestamp, scores, odds, quarter
8. Poller saves snapshot to database as `QuarterSnapshot` record
9. Frontend visualizes momentum of odds throughout game

## Key Conventions & Patterns

### Database Models
- **QuarterSnapshot fields**: `stage` (pregame/Q1/Q2/Q3/final), `score_home`, `score_away`, `score_diff`, `ml_home`, `ml_away`, `spread`
- Game creation currently hardcoded (e.g., "NOP vs DEN") - modify in `main.py` create endpoint
- All timestamps use UTC (`datetime.utcnow()`)

### Scraping Logic
- **Updated selector structure**: OddsPortal now uses `.eventRow` divs instead of `.table-main tr.live`
- **Team parsing**: Extract from `[data-testid*='participant']` which contains format "Team1–Team2"
- **Odds extraction**: Use regex `\d+\.\d{2}` to find decimal odds numbers in the row text
- **Headless mode**: Playwright headless=True by default, wait_for_timeout(5000) for page load
- **Two scraper functions**:
  - `scrape_oddsportal_quarter(game_id)`: Finds **live** games (stage="live", score=0)
  - `scrape_completed_games(game_id)`: Finds **finished** games with final scores (stage="final")
- **Error handling**: Graceful fallbacks - logs errors but returns empty array on failure

### Frontend Rendering
- Charts (moneyline, spread, score diff) all read from `quarters` state (array of QuarterSnapshot objects)
- Data key mapping: `stage` for X-axis, `ml_home`/`ml_away`/`spread`/`score_diff` for lines
- No error boundaries - axios errors only console.log

## Developer Workflows

### Running Locally
1. **Backend**: 
   - Prerequisites: PostgreSQL running on `localhost:5432` with DB `nba_odds`, user `postgres:postgres`
   - `cd backend && pip install -r requirements.txt` (if exists) or install FastAPI, SQLAlchemy, Playwright, BeautifulSoup4
   - `uvicorn app.main:app --reload` (runs on :8000)
2. **Frontend**:
   - `cd frontend/nba-odds-frontend && npm install`
   - `npm run dev` (Vite dev server on :5173 typically)
   - `npm run build` for production

### Testing Approach
- `test_data.py`: Fake odds generation for local testing (used on startup if DB empty)
- `test_playwright.py`: Isolated Playwright tests (inspect selectors against live OddsPortal)
- No pytest/Jest setup detected - manual/exploratory testing currently

## Critical Integration Points

### CORS
- Backend allows all origins (`allow_origins=["*"]`) - suitable for local dev, restrict before production
- Preflight requests handled automatically by middleware

### Session Management
- `Depends(get_db)` pattern for SQLAlchemy sessions - auto-yields and closes per request
- On startup: `init_db()` creates tables, `reset_quarter_snapshots()` clears old data

### Frontend API Usage
- Always check `API_BASE_URL` in config.js before deploying to different environment
- Error handling: wrap axios calls in try/catch for production reliability
- No pagination/filtering - loads all quarters for a game (watch memory with large datasets)

## Common Tasks

| Task | Where | How |
|------|-------|-----|
| Add new betting metric | `models.py` (add column) + `scraper.py` (parse from HTML) + `App.jsx` (add chart) | Three-file sync required |
| Update OddsPortal selectors | `scraper.py` lines ~13-17 | Run `test_playwright.py` to validate |
| Change DB connection | `db.py` line 5 | Update `DATABASE_URL` string |
| New API endpoint | `main.py` | Use `Depends(get_db)` for session injection |
