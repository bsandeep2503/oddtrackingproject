from .models import OddsSnapshot
from datetime import datetime, timedelta

def generate_fake_odds(game_id: int):
    base_time = datetime.utcnow()
    return [
        OddsSnapshot(
            game_id=game_id,
            timestamp=base_time + timedelta(minutes=i),
            moneyline_home=1.8 + i * 0.01,
            moneyline_away=2.0 - i * 0.01,
            bookmaker="TestBook"
        )
        for i in range(10)
    ]
