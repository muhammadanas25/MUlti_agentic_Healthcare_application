"""
Hospital Search Tool - In-memory hospital search with distance calculations

Features:
- Load hospitals from CSV into memory
- Haversine distance calculation
- Capability inference from hospital names
- City and area filtering
- Specialty-based search
- Comprehensive logging for debugging and UI display
"""
import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from .location_resolver import LocationResolver, ResolvedLocation, get_location_resolver
from ..core.logger import get_agent_logger, LogCategory


@dataclass
class HospitalResult:
    """Hospital search result with distance and inferred capabilities"""
    id: int
    name: str
    city: str
    area: Optional[str]
    address: str
    contact: str
    doctors_count: int
    distance_km: float
    google_maps_link: Optional[str] = None
    lat: Optional[float] = None
    long: Optional[float] = None
    capabilities: Dict[str, bool] = field(default_factory=dict)
    capability_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "hospital_name": self.name,
            "city": self.city,
            "area": self.area,
            "address": self.address,
            "contact": self.contact,
            "doctors_count": self.doctors_count,
            "distance_km": round(self.distance_km, 2),
            "google_maps_link": self.google_maps_link,
            "lat": self.lat,
            "long": self.long,
            "capabilities": self.capabilities,
            "capability_score": round(self.capability_score, 2)
        }


class HospitalSearchTool:
    """
    In-memory hospital search with distance calculations.

    Loads hospital data from CSV and provides fast search capabilities
    with haversine distance calculation and capability inference.
    """

    # Capability patterns for inference from hospital names
    CAPABILITY_PATTERNS = {
        "emergency": [
            "hospital", "medical center", "medical centre", "teaching", "general",
            "civil hospital", "emergency", "trauma"
        ],
        "icu": [
            "teaching hospital", "general hospital", "medical center", "medical centre",
            "icu", "critical care", "intensive care"
        ],
        "cardiac": [
            "heart", "cardiac", "cardio", "cardiovascular", "chest", "nicvd",
            "national institute of cardiovascular"
        ],
        "pediatric": [
            "children", "child", "pediatric", "paediatric", "kids", "baby"
        ],
        "maternity": [
            "maternity", "mother", "women", "gynae", "gynaecology", "obstetric",
            "obs", "lady", "female"
        ],
        "orthopedic": [
            "orthopedic", "orthopaedic", "bone", "joint", "spine", "fracture"
        ],
        "eye": [
            "eye", "ophthalmic", "ophthalmology", "vision", "lrbt", "layton"
        ],
        "cancer": [
            "cancer", "oncology", "tumor", "shaukat khanum", "skmc"
        ],
        "kidney": [
            "kidney", "renal", "nephrology", "dialysis", "sindh institute of urology"
        ],
        "mental": [
            "mental", "psychiatric", "psychology", "brain"
        ],
        "dental": [
            "dental", "dentist", "teeth", "oral"
        ],
        "skin": [
            "skin", "dermatology", "derma"
        ],
        "general": [
            "general", "multispecialty", "multi-specialty", "family"
        ],
        "clinic": [
            "clinic", "dispensary", "diagnostic"
        ]
    }

    # Tier classification for hospitals
    TIER_PATTERNS = {
        "tier_1": {  # Full emergency capabilities, major hospitals
            "patterns": [
                "teaching hospital", "medical college", "general hospital",
                "civil hospital", "jinnah hospital", "aga khan", "shifa",
                "shaukat khanum", "services hospital", "mayo hospital",
                "lady reading", "nishtar", "dow university", "pims"
            ],
            "score_multiplier": 1.5
        },
        "tier_2": {  # Good emergency capabilities
            "patterns": [
                "hospital", "medical center", "medical centre", "healthcare"
            ],
            "score_multiplier": 1.2
        },
        "tier_3": {  # Basic/specialty care
            "patterns": [
                "clinic", "dispensary", "diagnostic", "laboratory", "lab"
            ],
            "score_multiplier": 0.8
        }
    }

    def __init__(self, csv_path: Optional[str] = None):
        """Initialize with hospital CSV data"""
        if csv_path is None:
            # Default path - use updated file with pre-computed coordinates
            csv_path = Path(__file__).parent.parent.parent / "data" / "Hospitals_updated.csv"
            # Fallback to original if updated doesn't exist
            if not csv_path.exists():
                csv_path = Path(__file__).parent.parent.parent / "data" / "hospitals.csv"

        self.df = self._load_csv(csv_path)
        self.location_resolver = get_location_resolver()
        self.logger = get_agent_logger()

        # Check if we have pre-computed coordinates
        self.has_precomputed_coords = "Lat" in self.df.columns and "Long" in self.df.columns

        # Pre-build city index for fast filtering
        self.city_index: Dict[str, List[int]] = {}
        self._build_city_index()

        # Pre-compute capabilities for all hospitals
        self._compute_all_capabilities()

        coords_status = "with coordinates" if self.has_precomputed_coords else "without coordinates"
        print(f"✓ HospitalSearchTool initialized with {len(self.df)} hospitals ({coords_status}) across {len(self.city_index)} cities")

    def _load_csv(self, csv_path) -> pd.DataFrame:
        """Load and clean hospital CSV"""
        df = pd.read_csv(csv_path)

        # Clean column names
        df.columns = df.columns.str.strip()

        # Ensure required columns exist
        required = ["HOSPITAL NAME", "CITY", "ADDRESS", "CONTACT"]
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        # Clean data
        df["HOSPITAL NAME"] = df["HOSPITAL NAME"].fillna("Unknown Hospital")
        df["CITY"] = df["CITY"].fillna("Unknown").str.strip().str.title()
        df["AREA"] = df["AREA"].fillna("").str.strip()
        df["ADDRESS"] = df["ADDRESS"].fillna("")
        df["CONTACT"] = df["CONTACT"].fillna("").astype(str)
        df["DOCTORS"] = pd.to_numeric(df["DOCTORS"], errors="coerce").fillna(0).astype(int)

        # Handle pre-computed coordinates if available (from Hospitals_updated.csv)
        if "Lat" in df.columns:
            df["Lat"] = pd.to_numeric(df["Lat"], errors="coerce")
        if "Long" in df.columns:
            df["Long"] = pd.to_numeric(df["Long"], errors="coerce")
        if "Google Map Link" in df.columns:
            df["Google Map Link"] = df["Google Map Link"].fillna("")

        # Add index column
        df["_idx"] = range(len(df))

        return df

    def _build_city_index(self):
        """Build index of hospitals by city for fast filtering"""
        for idx, row in self.df.iterrows():
            city = row["CITY"].lower()
            if city not in self.city_index:
                self.city_index[city] = []
            self.city_index[city].append(idx)

    def _compute_all_capabilities(self):
        """Pre-compute capabilities for all hospitals"""
        self.df["_capabilities"] = self.df["HOSPITAL NAME"].apply(self._infer_capabilities)
        self.df["_tier"] = self.df["HOSPITAL NAME"].apply(self._get_tier)

    def _infer_capabilities(self, hospital_name: str) -> Dict[str, bool]:
        """Infer hospital capabilities from name"""
        name_lower = hospital_name.lower()
        capabilities = {}

        for capability, patterns in self.CAPABILITY_PATTERNS.items():
            capabilities[capability] = any(pattern in name_lower for pattern in patterns)

        return capabilities

    def _get_tier(self, hospital_name: str) -> str:
        """Get hospital tier from name"""
        name_lower = hospital_name.lower()

        for tier, config in self.TIER_PATTERNS.items():
            if any(pattern in name_lower for pattern in config["patterns"]):
                return tier

        return "tier_2"  # Default

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in km between two points using Haversine formula"""
        R = 6371  # Earth's radius in km

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))

        return R * c

    def search(
        self,
        user_lat: float,
        user_long: float,
        city: Optional[str] = None,
        area: Optional[str] = None,
        max_distance_km: float = 10.0,
        limit: int = 5,
        specialty: Optional[str] = None,
        requires_emergency: bool = False,
        requires_icu: bool = False,
        session_id: str = "system"
    ) -> List[HospitalResult]:
        """
        Search for hospitals near user location.

        Args:
            user_lat: User's latitude
            user_long: User's longitude
            city: Filter by city (optional, for faster search)
            area: Filter by area (optional)
            max_distance_km: Maximum distance in km
            limit: Maximum results to return
            specialty: Required specialty (cardiac, pediatric, etc.)
            requires_emergency: Must have emergency services
            requires_icu: Must have ICU
            session_id: For logging purposes

        Returns:
            List of HospitalResult sorted by distance
        """
        # Log search request
        log_id = self.logger.log_tool_call(
            session_id=session_id,
            agent_name="HospitalSearch",
            tool_name="search_hospitals",
            inputs={
                "lat": user_lat,
                "long": user_long,
                "city": city,
                "area": area,
                "max_distance_km": max_distance_km,
                "specialty": specialty,
                "requires_emergency": requires_emergency
            },
            category=LogCategory.HOSPITAL
        )

        self.logger.log_reasoning(
            session_id=session_id,
            agent_name="HospitalSearch",
            thought=f"Searching hospitals within {max_distance_km}km of ({user_lat:.4f}, {user_long:.4f})"
                    + (f" in {city}" if city else "")
                    + (f" with specialty: {specialty}" if specialty else ""),
            category=LogCategory.HOSPITAL
        )

        # Start with full dataset or city subset
        if city:
            city_lower = city.lower()
            if city_lower in self.city_index:
                working_df = self.df.iloc[self.city_index[city_lower]].copy()
            else:
                # City not found, search all
                working_df = self.df.copy()
        else:
            working_df = self.df.copy()

        # Filter by area if specified
        if area:
            area_lower = area.lower()
            working_df = working_df[
                working_df["AREA"].str.lower().str.contains(area_lower, na=False)
            ]

        # Filter by specialty/capability
        if specialty:
            specialty_lower = specialty.lower()
            # Find matching capability category
            capability_key = None
            for cap_name, patterns in self.CAPABILITY_PATTERNS.items():
                if specialty_lower in patterns or specialty_lower == cap_name:
                    capability_key = cap_name
                    break

            if capability_key:
                working_df = working_df[
                    working_df["_capabilities"].apply(lambda x: x.get(capability_key, False))
                ]

        # Filter by emergency/ICU requirements
        if requires_emergency:
            working_df = working_df[
                working_df["_capabilities"].apply(lambda x: x.get("emergency", False))
            ]

        if requires_icu:
            working_df = working_df[
                working_df["_capabilities"].apply(lambda x: x.get("icu", False))
            ]

        if len(working_df) == 0:
            return []

        # Calculate distances using area coordinates
        results = []
        for idx, row in working_df.iterrows():
            # Get hospital coordinates from area/city
            hospital_coords = self._get_hospital_coords(row)

            if hospital_coords:
                hospital_lat, hospital_long = hospital_coords
                distance = self.haversine_distance(
                    user_lat, user_long, hospital_lat, hospital_long
                )
            else:
                # Can't calculate distance, assign large distance
                distance = 999.0
                hospital_lat, hospital_long = None, None

            if distance <= max_distance_km:
                # Calculate capability score
                tier = row["_tier"]
                tier_multiplier = self.TIER_PATTERNS.get(tier, {}).get("score_multiplier", 1.0)
                doctors_factor = min(row["DOCTORS"] / 10, 2.0)  # Cap at 2x
                capability_score = (1 / max(distance, 0.1)) * tier_multiplier * (1 + doctors_factor * 0.1)

                # Get Google Maps link - use pre-computed if available
                precomputed_link = row.get("Google Map Link", "") if self.has_precomputed_coords else ""
                if precomputed_link and len(precomputed_link) > 10:
                    maps_link = precomputed_link
                elif hospital_lat and hospital_long:
                    maps_link = f"https://www.google.com/maps/search/?api=1&query={hospital_lat},{hospital_long}"
                else:
                    # Use address for maps link
                    address_encoded = row["ADDRESS"].replace(" ", "+")
                    maps_link = f"https://www.google.com/maps/search/?api=1&query={address_encoded}"

                results.append(HospitalResult(
                    id=int(row["_idx"]),
                    name=row["HOSPITAL NAME"],
                    city=row["CITY"],
                    area=row["AREA"] if row["AREA"] else None,
                    address=row["ADDRESS"],
                    contact=row["CONTACT"],
                    doctors_count=row["DOCTORS"],
                    distance_km=distance,
                    google_maps_link=maps_link,
                    lat=hospital_lat,
                    long=hospital_long,
                    capabilities=row["_capabilities"],
                    capability_score=capability_score
                ))

        # Sort by distance
        results.sort(key=lambda x: x.distance_km)

        # Log results
        final_results = results[:limit]
        if final_results:
            self.logger.log_tool_result(
                session_id=session_id,
                agent_name="HospitalSearch",
                tool_name="search_hospitals",
                result_summary=f"Found {len(final_results)} hospitals. Nearest: {final_results[0].name} ({final_results[0].distance_km:.1f}km)",
                success=True,
                log_id=log_id,
                category=LogCategory.HOSPITAL,
                data={
                    "total_found": len(final_results),
                    "hospitals": [{"name": h.name, "distance_km": h.distance_km, "city": h.city} for h in final_results[:3]]
                }
            )
        else:
            self.logger.log_tool_result(
                session_id=session_id,
                agent_name="HospitalSearch",
                tool_name="search_hospitals",
                result_summary=f"No hospitals found within {max_distance_km}km",
                success=False,
                log_id=log_id,
                category=LogCategory.HOSPITAL
            )

        return final_results

    def _get_hospital_coords(self, row) -> Optional[Tuple[float, float]]:
        """Get coordinates for a hospital based on pre-computed coords, area, or city"""
        # First, check for pre-computed coordinates (from Hospitals_updated.csv)
        if self.has_precomputed_coords:
            lat = row.get("Lat")
            long = row.get("Long")
            if pd.notna(lat) and pd.notna(long) and lat != 0 and long != 0:
                return (float(lat), float(long))

        # Fallback: try to resolve from area/address (for old CSV or missing coords)
        area = row["AREA"].strip() if row["AREA"] else None
        city = row["CITY"].strip()
        address = row["ADDRESS"] if row["ADDRESS"] else ""

        # Check if area is valid (not empty, not just "0", not just numbers)
        area_is_valid = area and len(area) > 1 and not area.isdigit()

        # Try to resolve area first (if valid)
        if area_is_valid:
            location = f"{area}, {city}"
            resolved = self.location_resolver.resolve(location, city, use_google_fallback=False)
            if resolved.lat and resolved.confidence in ["high", "medium"]:
                return (resolved.lat, resolved.long)

        # If area is garbage ("0", empty, etc.), try to extract area from ADDRESS
        if address:
            extracted_area = self._extract_area_from_address(address, city)
            if extracted_area:
                location = f"{extracted_area}, {city}"
                resolved = self.location_resolver.resolve(location, city, use_google_fallback=False)
                if resolved.lat and resolved.confidence in ["high", "medium"]:
                    return (resolved.lat, resolved.long)

        # Fallback to city center
        city_coords = self.location_resolver.get_city_center(city)
        if city_coords:
            return city_coords

        return None

    def _extract_area_from_address(self, address: str, city: str) -> Optional[str]:
        """
        Extract known area names from ADDRESS field.

        This handles cases where AREA field is garbage ("0") but ADDRESS
        contains useful info like "B-87 Block 1, Gulistan E Jauhar, Karachi"
        """
        if not address:
            return None

        address_lower = address.lower()
        city_lower = city.lower()

        # Get known areas for this city from location resolver
        known_areas = self.location_resolver.KNOWN_AREAS

        # Find matching areas - check each known area for this city
        matched_areas = []
        for (area_name, area_city), coords in known_areas.items():
            if area_city != city_lower:
                continue

            # Normalize area name for matching
            area_variants = [
                area_name,
                area_name.replace('-', ' '),
                area_name.replace('-', ''),
                area_name.replace(' e ', '-e-'),  # gulshan e iqbal -> gulshan-e-iqbal
                area_name.replace(' ', ''),
            ]

            for variant in area_variants:
                if variant in address_lower:
                    # Longer matches are more specific, so track length
                    matched_areas.append((len(area_name), area_name))
                    break

        if matched_areas:
            # Return the longest (most specific) match
            matched_areas.sort(reverse=True)
            return matched_areas[0][1]

        return None

    def search_by_location_text(
        self,
        location_text: str,
        specialty: Optional[str] = None,
        max_distance_km: float = 10.0,
        limit: int = 5,
        requires_emergency: bool = False,
        session_id: str = "system"
    ) -> Tuple[List[HospitalResult], ResolvedLocation]:
        """
        Search hospitals by location text (convenience method).

        Resolves location text to coordinates, then searches.
        """
        self.logger.log_reasoning(
            session_id=session_id,
            agent_name="HospitalSearch",
            thought=f"Processing location text search: '{location_text}'",
            category=LogCategory.HOSPITAL
        )

        # Resolve location
        resolved = self.location_resolver.resolve(location_text, session_id=session_id)

        if not resolved.lat or not resolved.long:
            self.logger.log_tool_result(
                session_id=session_id,
                agent_name="HospitalSearch",
                tool_name="search_by_location_text",
                result_summary=f"Could not resolve location: {location_text}",
                success=False,
                category=LogCategory.HOSPITAL
            )
            return [], resolved

        # Use resolved location's search radius if low confidence
        search_radius = min(max_distance_km, resolved.search_radius_km)

        # Search
        results = self.search(
            user_lat=resolved.lat,
            user_long=resolved.long,
            city=resolved.city,
            max_distance_km=search_radius,
            limit=limit,
            specialty=specialty,
            requires_emergency=requires_emergency,
            session_id=session_id
        )

        return results, resolved

    def get_cities(self) -> List[str]:
        """Get list of all cities in dataset"""
        return sorted(self.city_index.keys())

    def get_hospitals_in_city(self, city: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all hospitals in a city"""
        city_lower = city.lower()
        if city_lower not in self.city_index:
            return []

        hospitals = self.df.iloc[self.city_index[city_lower]]
        return [
            {
                "name": row["HOSPITAL NAME"],
                "area": row["AREA"],
                "contact": row["CONTACT"],
                "doctors": row["DOCTORS"]
            }
            for _, row in hospitals.head(limit).iterrows()
        ]

    def format_results_for_patient(
        self,
        results: List[HospitalResult],
        language: str = "mixed"  # mixed, urdu, english
    ) -> str:
        """Format search results for patient-friendly display"""
        if not results:
            if language == "urdu":
                return "آپ کے قریب کوئی ہسپتال نہیں ملا۔ براہ کرم اپنا علاقہ بتائیں۔"
            return "No hospitals found nearby. Please specify your area."

        lines = []

        if language == "urdu":
            lines.append("🏥 *قریبی ہسپتال:*\n")
        else:
            lines.append("🏥 *Nearest Hospitals:*\n")

        for i, hospital in enumerate(results[:5], 1):
            lines.append(f"*{i}. {hospital.name}*")

            if hospital.area:
                lines.append(f"   📍 {hospital.area}, {hospital.city}")
            else:
                lines.append(f"   📍 {hospital.city}")

            lines.append(f"   📞 {hospital.contact}")
            lines.append(f"   🚗 {hospital.distance_km:.1f} km door")

            if hospital.google_maps_link:
                lines.append(f"   🗺️ [Map]({hospital.google_maps_link})")

            # Show relevant capabilities
            caps = []
            if hospital.capabilities.get("emergency"):
                caps.append("Emergency")
            if hospital.capabilities.get("icu"):
                caps.append("ICU")
            if hospital.capabilities.get("cardiac"):
                caps.append("Cardiac")
            if hospital.capabilities.get("pediatric"):
                caps.append("Pediatric")

            if caps:
                lines.append(f"   ✅ {', '.join(caps)}")

            lines.append("")

        lines.append("📞 *Emergency: 1122*")

        return "\n".join(lines)


# Global instance
_search_tool: Optional[HospitalSearchTool] = None


def get_hospital_search(csv_path: Optional[str] = None) -> HospitalSearchTool:
    """Get or create hospital search tool instance"""
    global _search_tool
    if _search_tool is None:
        _search_tool = HospitalSearchTool(csv_path)
    return _search_tool
