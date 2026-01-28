from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from .base import Base

class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    home_team = Column(String)
    away_team = Column(String)
    oddsportal_url = Column(String)  # Store the OddsPortal game URL

class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"))
    timestamp = Column(DateTime)
    moneyline_home = Column(Float)
    moneyline_away = Column(Float)
    bookmaker = Column(String)

class QuarterSnapshot(Base):
    __tablename__ = "quarter_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"))

    # "pregame", "Q1", "Q2", "Q3", "final"
    stage = Column(String)

    # scores
    score_home = Column(Integer)
    score_away = Column(Integer)
    score_diff = Column(Integer)  # home - away (or away - home, your convention)

    # moneyline odds
    ml_home = Column(Float)
    ml_away = Column(Float)

    # full-game spread (from favorite perspective)
    spread = Column(Float)

    timestamp = Column(DateTime)


class LiveOddsSnapshot(Base):
    __tablename__ = "live_odds_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(String, index=True)
    timestamp = Column(DateTime)
    quarter = Column(Integer, nullable=True)
    game_clock = Column(String, nullable=True)
    teamA_score = Column(Integer, nullable=True)
    teamB_score = Column(Integer, nullable=True)
    teamA_ml = Column(Float, nullable=True)
    teamB_ml = Column(Float, nullable=True)
    spread_line = Column(Float, nullable=True)
    total_line = Column(Float, nullable=True)
