#!/usr/bin/env python3
"""
Diagnostic script to test:
1. Google Maps API functionality
2. Hospital data quality
3. Why nearby hospitals aren't being found
"""
import sys
sys.path.insert(0, '/home/anas/agentic')

import pandas as pd
from src.tools.location_resolver import get_location_resolver
from src.tools.hospital_search import get_hospital_search

def test_google_maps_api():
    """Test Google Maps Geocoding API"""
    print("\n" + "="*60)
    print("TEST 1: Google Maps API")
    print("="*60)

    resolver = get_location_resolver()

    # Test with a location that's NOT in our known areas
    test_locations = [
        "Nazimabad Block 3, Karachi",  # Not in known areas
        "Bahria Town Phase 4, Karachi",  # Not in known areas
        "Scheme 33, Karachi",  # Not in known areas
    ]

    for loc in test_locations:
        print(f"\n>>> Testing: {loc}")
        resolved = resolver.resolve(loc, use_google_fallback=True)
        print(f"    Resolved: {resolved.city}, ({resolved.lat:.4f}, {resolved.long:.4f})")
        print(f"    Confidence: {resolved.confidence}, Source: {resolved.source}")


def test_hospital_data():
    """Analyze hospital data to understand the issue"""
    print("\n" + "="*60)
    print("TEST 2: Hospital Data Analysis")
    print("="*60)

    search = get_hospital_search()
    df = search.df

    # How many hospitals in Karachi
    karachi_hospitals = df[df['CITY'].str.lower() == 'karachi']
    print(f"\nTotal hospitals in Karachi: {len(karachi_hospitals)}")

    # How many have AREA field filled
    with_area = karachi_hospitals[karachi_hospitals['AREA'].notna() & (karachi_hospitals['AREA'] != '')]
    print(f"Hospitals with AREA field: {len(with_area)}")

    # What areas are in the data
    print(f"\nUnique areas in Karachi data:")
    areas = with_area['AREA'].value_counts().head(20)
    for area, count in areas.items():
        print(f"  - {area}: {count}")

    # Check if any match our known areas
    print(f"\n\nLooking for known areas like 'Gulshan', 'DHA', etc:")
    gulshan = karachi_hospitals[karachi_hospitals['AREA'].str.lower().str.contains('gulshan', na=False)]
    print(f"  Hospitals with 'gulshan' in area: {len(gulshan)}")

    dha = karachi_hospitals[karachi_hospitals['AREA'].str.lower().str.contains('dha|defence', na=False)]
    print(f"  Hospitals with 'dha/defence' in area: {len(dha)}")

    jauhar = karachi_hospitals[karachi_hospitals['AREA'].str.lower().str.contains('jauhar', na=False)]
    print(f"  Hospitals with 'jauhar' in area: {len(jauhar)}")


def test_coordinate_matching():
    """Test if coordinate-based search would work better"""
    print("\n" + "="*60)
    print("TEST 3: Search with Known Coordinates")
    print("="*60)

    search = get_hospital_search()
    resolver = get_location_resolver()

    # Get actual Gulshan-e-Iqbal coordinates
    resolved = resolver.resolve("Gulshan-e-Iqbal, Karachi")
    print(f"\nGulshan-e-Iqbal coordinates: ({resolved.lat}, {resolved.long})")

    # Search with wider radius
    print("\nSearching within 20km radius (no city filter):")
    results = search.search(
        user_lat=resolved.lat,
        user_long=resolved.long,
        max_distance_km=20.0,
        limit=10
    )

    for i, h in enumerate(results, 1):
        print(f"  {i}. {h.name[:40]}...")
        print(f"     Area: {h.area or 'None'}, City: {h.city}")
        print(f"     Distance: {h.distance_km:.1f}km, Coords: ({h.lat}, {h.long})")


def test_hospital_coordinates():
    """Check what coordinates hospitals actually have"""
    print("\n" + "="*60)
    print("TEST 4: Hospital Coordinate Sources (WITH ADDRESS PARSING)")
    print("="*60)

    search = get_hospital_search()
    resolver = get_location_resolver()

    # Get Karachi hospitals with AREA="0" to test address parsing
    karachi = search.df[search.df['CITY'].str.lower() == 'karachi']
    karachi_bad_area = karachi[karachi['AREA'] == '0'].head(15)

    print("\nChecking coordinate resolution for Karachi hospitals (AREA='0'):")
    area_resolved = 0
    city_center = 0

    for _, row in karachi_bad_area.iterrows():
        area = row['AREA'] if pd.notna(row['AREA']) and row['AREA'].strip() else None
        address = row['ADDRESS'][:60] if row['ADDRESS'] else "No address"
        name = row['HOSPITAL NAME'][:35]

        # Test the new _extract_area_from_address method
        extracted = search._extract_area_from_address(row['ADDRESS'], row['CITY'])

        coords = search._get_hospital_coords(row)
        if coords:
            lat, long = coords
            # Check if it's city center
            is_city_center = abs(lat - 24.8607) < 0.01 and abs(long - 67.0011) < 0.01
            if is_city_center:
                source = "CITY CENTER ❌"
                city_center += 1
            else:
                source = f"AREA: {extracted} ✅"
                area_resolved += 1
        else:
            source = "NO COORDS"

        print(f"\n  {name}...")
        print(f"    Address: {address}...")
        print(f"    Extracted Area: {extracted}")
        print(f"    → {source}")

    print(f"\n📊 Summary: {area_resolved}/{area_resolved + city_center} resolved from address ({area_resolved/(area_resolved+city_center)*100:.0f}%)")


if __name__ == "__main__":
    print("\n🔍 SEHAT SAATHI - Diagnostic Tests\n")

    test_google_maps_api()
    test_hospital_data()
    test_coordinate_matching()
    test_hospital_coordinates()

    print("\n" + "="*60)
    print("Diagnosis Complete!")
    print("="*60)
