"""Script to fetch all leagues from API-Football, filter duplicates, and update mappings."""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from football_data.api_football import APIFootballProvider
from football_data.league_mappings import LeagueMapping


async def fetch_and_update():
    """Fetch all leagues from provider, filter duplicates, update mappings."""
    provider = APIFootballProvider()
    
    try:
        await provider.connect()
        
        # Fetch all leagues from provider
        print("Fetching all leagues from API-Football...")
        leagues = await provider.get_leagues()
        print(f"Fetched {len(leagues)} leagues from provider")
        
        # Filter duplicates by provider_league_id, keep first occurrence
        seen_ids = set()
        unique_leagues = []
        duplicates = []
        
        for league in leagues:
            pid = league.provider_league_id
            if pid not in seen_ids:
                seen_ids.add(pid)
                unique_leagues.append(league)
            else:
                duplicates.append(league)
        
        print(f"Unique leagues: {len(unique_leagues)}")
        print(f"Duplicates removed: {len(duplicates)}")
        
        # Show duplicates
        if duplicates:
            print("\nDuplicate leagues (same provider_league_id):")
            for d in duplicates:
                print(f"  - {d.name} (ID: {d.provider_league_id}, Country: {d.country})")
        
        # Print unique leagues with their IDs
        print("\nAll unique leagues:")
        for league in sorted(unique_leagues, key=lambda x: int(x.provider_league_id) if x.provider_league_id.isdigit() else 0):
            name = league.name.encode('ascii', 'replace').decode('ascii')
            country = league.country.encode('ascii', 'replace').decode('ascii') if league.country else "N/A"
            print(f"  {league.provider_league_id:>5} - {name:<40} ({country})")
        
        # Update the _DEFAULT_LEAGUE_IDS_API_FOOTBALL dict in api_football.py
        # We'll create a mapping from internal_id to provider_league_id
        # For now, just print the mapping that should be used
        
        print("\n--- Suggested mapping for _DEFAULT_LEAGUE_IDS_API_FOOTBALL ---")
        
        # Try to match with existing internal_ids
        for league in unique_leagues:
            # Try to find matching internal_id
            matched = False
            for internal_id, config in LeagueMapping._LEAGUES.items():
                if config.provider_ids.get("api_football", {}).get("league_id") == league.provider_league_id:
                    print(f'    "{internal_id}": ("{league.provider_league_id}", "2023"),  # {league.name}')
                    matched = True
                    break
            
            if not matched:
                # Try to match by name similarity
                for internal_id, config in LeagueMapping._LEAGUES.items():
                    if config.name.lower() in league.name.lower() or league.name.lower() in config.name.lower():
                        name = league.name.encode('ascii', 'replace').decode('ascii')
                        print(f'    "{internal_id}": ("{league.provider_league_id}", "2023"),  # {name} (matched by name)')
                        matched = True
                        break
            
            if not matched:
                name = league.name.encode('ascii', 'replace').decode('ascii')
                country = league.country.encode('ascii', 'replace').decode('ascii') if league.country else "N/A"
                print(f'    # UNKNOWN: "{league.provider_league_id}" - {name} ({country})')
        
    finally:
        await provider.close()


if __name__ == "__main__":
    asyncio.run(fetch_and_update())