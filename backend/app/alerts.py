"""
Alerts Service
Handles alert triggers, cooldowns, and notifications
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Optional
from .models import Alert

WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "https://httpbin.org/post")  # Default for testing

def should_alert(event: dict, last_alert_time: Optional[datetime]) -> bool:
    """Check if we should send an alert based on cooldown"""
    if not last_alert_time:
        return True
    
    cooldown_minutes = 10  # 10 minute cooldown per game
    return (datetime.utcnow() - last_alert_time).total_seconds() > (cooldown_minutes * 60)

def get_last_alert_time(game_id: int, db) -> Optional[datetime]:
    """Get timestamp of last alert for this game"""
    last_alert = db.query(Alert).filter(Alert.game_id == game_id).order_by(Alert.timestamp.desc()).first()
    return last_alert.timestamp if last_alert else None

def send_alert(msg: str, alert_type: str, game_id: int, db):
    """Send alert and record it"""
    try:
        # Send webhook
        response = requests.post(WEBHOOK_URL, json={"text": msg, "type": alert_type, "game_id": game_id}, timeout=5)
        response.raise_for_status()
        
        # Record in DB
        alert = Alert(
            game_id=game_id,
            type=alert_type,
            message=msg,
            timestamp=datetime.utcnow(),
            sent_to="webhook"
        )
        db.add(alert)
        db.commit()
        
        print(f"Alert sent: {msg}")
        
    except Exception as e:
        print(f"Failed to send alert: {e}")

def process_alerts(events: list, game_id: int, db):
    """Process momentum events and send alerts if needed"""
    for event in events:
        alert_type = event['type']
        
        # Only alert on major events
        if alert_type in ['underdog_surge', 'favorite_dip', 'reversal']:
            last_alert_time = get_last_alert_time(game_id, db)
            
            if should_alert(event, last_alert_time):
                send_alert(event['detail'], alert_type, game_id, db)