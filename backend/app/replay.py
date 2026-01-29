from datetime import timedelta
from typing import List

def detect_gaps(snaps, max_gap_seconds=120):
    gaps = []
    for i in range(1, len(snaps)):
        delta = (snaps[i].timestamp - snaps[i-1].timestamp).total_seconds()
        if delta > max_gap_seconds:
            gaps.append({
                "from": snaps[i-1].timestamp.isoformat(),
                "to": snaps[i].timestamp.isoformat(),
                "gap_seconds": int(delta)
            })
    return gaps