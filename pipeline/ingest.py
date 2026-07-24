"""Ingest StatsBomb open event data for a competition and cache it locally.

Usage:
    python3 ingest.py            # World Cup 2022 by default
"""
import os
import pickle

import pandas as pd
from statsbombpy import sb
from tqdm import tqdm

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
COMPETITION_ID = 43   # FIFA World Cup
SEASON_ID = 106       # 2022


def fetch_matches() -> pd.DataFrame:
    return sb.matches(competition_id=COMPETITION_ID, season_id=SEASON_ID)


def fetch_all_events(matches: pd.DataFrame) -> pd.DataFrame:
    """Download events for every match, with a local pickle cache per match."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    frames = []
    for _, m in tqdm(list(matches.iterrows()), desc="Downloading events"):
        match_id = m["match_id"]
        cache_path = os.path.join(CACHE_DIR, f"events_{match_id}.pkl")
        if os.path.exists(cache_path):
            with open(cache_path, "rb") as f:
                ev = pickle.load(f)
        else:
            ev = sb.events(match_id=match_id)
            with open(cache_path, "wb") as f:
                pickle.dump(ev, f)
        ev["match_id"] = match_id
        frames.append(ev)
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    matches = fetch_matches()
    print(f"Matches: {len(matches)}")
    events = fetch_all_events(matches)
    print(f"Total events: {len(events)}")
    out_path = os.path.join(CACHE_DIR, "all_events.pkl")
    with open(out_path, "wb") as f:
        pickle.dump(events, f)
    print(f"Saved combined events to {out_path}")
