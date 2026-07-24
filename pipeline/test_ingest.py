"""Smoke test: verify we can pull StatsBomb open data for World Cup 2022."""
from statsbombpy import sb

# World Cup 2022: competition_id=43, season_id=106 (per the handbook)
matches = sb.matches(competition_id=43, season_id=106)
print(f"Matches found: {len(matches)}")
print(matches[["match_id", "home_team", "away_team", "competition_stage"]].head(5))

final = matches[matches["competition_stage"] == "Final"].iloc[0]
print(f"\nFinal: {final['home_team']} vs {final['away_team']} (match_id={final['match_id']})")

events = sb.events(match_id=final["match_id"])
print(f"Events in final: {len(events)}")
print(f"Event types: {events['type'].value_counts().head(8).to_dict()}")

# Sanity: players present in the final
players = events["player"].dropna().unique()
print(f"Players involved: {len(players)}")
print("Sample:", list(players[:5]))
