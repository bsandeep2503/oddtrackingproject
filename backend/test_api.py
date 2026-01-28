#!/usr/bin/env python
"""
Test the full API endpoint
"""
import requests
import json
import time

BACKEND_URL = "http://localhost:8000"
GAME_ID = 2

print("\n" + "="*60)
print("TESTING LIVE SCRAPER API ENDPOINT")
print("="*60 + "\n")

print(f"Target: {BACKEND_URL}/games/{GAME_ID}/scrape-live")
print(f"Game ID: {GAME_ID}\n")

try:
    print("Sending POST request to backend...\n")
    response = requests.post(
        f"{BACKEND_URL}/games/{GAME_ID}/scrape-live",
        timeout=60
    )
    
    print(f"Response Status: {response.status_code}\n")
    
    if response.status_code == 200:
        data = response.json()
        print("Response Data:")
        print(json.dumps(data, indent=2))
        
        print("\n✓ SUCCESS - API is working correctly!")
        
        # Try to fetch the quarters endpoint
        print("\nFetching quarters from database...\n")
        quarters_response = requests.get(f"{BACKEND_URL}/games/{GAME_ID}/quarters")
        if quarters_response.status_code == 200:
            quarters = quarters_response.json()
            print(f"✓ Retrieved {len(quarters)} quarter snapshot(s)")
            if quarters:
                latest = quarters[-1]
                print(f"  Latest: {latest.get('stage')} - Score: {latest.get('score_away')} - {latest.get('score_home')}")
        
    else:
        print(f"✗ Error: {response.text}")

except Exception as e:
    print(f"✗ Error: {e}")
    print("\nMake sure the backend is running!")
    print(f"  Run: uvicorn app.main:app --reload")

print("\n" + "="*60 + "\n")
