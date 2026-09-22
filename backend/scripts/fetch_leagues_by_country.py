"""Script to fetch all leagues from API-Football and filter by country."""

import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from football_data.api_football import APIFootballProvider


async def fetch_and_filter():
    """Fetch all leagues and filter by country."""
    provider = APIFootballProvider()
    
    try:
        await provider.connect()
        
        print("Fetching all leagues from API-Football...")
        leagues = await provider.get_leagues()
        print(f"Fetched {len(leagues)} leagues from provider")
        
        # Filter for our target countries
        target_countries = [
            "England", "Spain", "Italy", "Germany", "France", 
            "Portugal", "Turkey", "Greece", "Switzerland", 
            "Netherlands", "Belgium", "World"
        ]
        
        # Group by country
        by_country = {}
        for league in leagues:
            country = league.country or "Unknown"
            if country not in by_country:
                by_country[country] = []
            by_country[country].append(league)
        
        # Print leagues for target countries
        for country in target_countries:
            if country in by_country:
                print(f"\n=== {country} ===")
                for league in sorted(by_country[country], key=lambda x: int(x.provider_league_id) if x.provider_league_id.isdigit() else 0):
                    name = league.name.encode('ascii', 'replace').decode('ascii')
                    print(f"  {league.provider_league_id:>5} - {name}")
        
        # Also search for specific league names
        print("\n=== Search for specific leagues ===")
        search_terms = [
            "Swiss Super League", "Challenge League", "Super League",
            "Jupiler Pro League", "Challenger Pro League",
            "Eredivisie", "Eerste Divisie",
            "Süper Lig", "TFF", "Super League 1", "Football League",
            "Gamma Ethniki", "Primeira Liga", "Segunda Liga",
            "Championship", "League One", "League Two",
            "La Liga", "Segunda", "Serie A", "Serie B",
            "Bundesliga", "2. Bundesliga", "3. Liga",
            "Ligue 1", "Ligue 2",
        ]
        
        for term in search_terms:
            matches = [l for l in leagues if term.lower() in l.name.lower()]
            if matches:
                print(f"\n--- {term} ---")
                for m in sorted(matches, key=lambda x: int(x.provider_league_id) if x.provider_league_id.isdigit() else 0):
                    name = m.name.encode('ascii', 'replace').decode('ascii')
                    country = m.country.encode('ascii', 'replace').decode('ascii') if m.country else "N/A"
                    print(f"  {m.provider_league_id:>5} - {name} ({country})")
        
    finally:
        await provider.close()


if __name__ == "__main__":
    asyncio.run(fetch_and_filter())