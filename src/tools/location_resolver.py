"""
Location Resolver - Converts Pakistani location references to coordinates

Supports:
- Known area coordinates (DHA, Gulberg, F-8, etc.)
- City center fallbacks
- Google Maps API integration (when available)
- WhatsApp location shares
- Comprehensive logging for debugging
"""
import os
import re
import httpx
import requests
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass

from ..core.config import get_settings
from ..core.logger import get_agent_logger, LogCategory


@dataclass
class ResolvedLocation:
    """Resolved location with coordinates and metadata"""
    lat: Optional[float] = None
    long: Optional[float] = None
    confidence: str = "none"  # high, medium, low, none
    city: Optional[str] = None
    area: Optional[str] = None
    search_radius_km: float = 10.0
    clarification_needed: Optional[str] = None
    source: str = "unknown"  # known_area, city_center, google_maps, whatsapp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resolved_lat": self.lat,
            "resolved_long": self.long,
            "confidence": self.confidence,
            "resolved_city": self.city,
            "resolved_area": self.area,
            "search_radius_km": self.search_radius_km,
            "clarification_needed": self.clarification_needed,
            "source": self.source
        }


class LocationResolver:
    """
    Resolve Pakistani location references to coordinates.

    Priority:
    1. Direct coordinates (WhatsApp location share)
    2. Known area lookup (fast, offline)
    3. Google Maps API (if key available)
    4. City center fallback (wide radius)
    """

    # Known area coordinates for major Pakistani cities
    # Format: (area_name, city) -> (lat, long)
    KNOWN_AREAS: Dict[Tuple[str, str], Tuple[float, float]] = {
        # Karachi Areas
        ("gulistan-e-jauhar", "karachi"): (24.9165, 67.1255),
        ("gulistan e jauhar", "karachi"): (24.9165, 67.1255),
        ("jauhar", "karachi"): (24.9165, 67.1255),
        ("dha phase 1", "karachi"): (24.8089, 67.0549),
        ("dha phase 2", "karachi"): (24.8150, 67.0380),
        ("dha phase 4", "karachi"): (24.8050, 67.0650),
        ("dha phase 5", "karachi"): (24.7937, 67.0513),
        ("dha phase 6", "karachi"): (24.7850, 67.0610),
        ("dha phase 7", "karachi"): (24.7750, 67.0750),
        ("dha phase 8", "karachi"): (24.7650, 67.0850),
        ("defence", "karachi"): (24.8000, 67.0500),
        ("dha", "karachi"): (24.8000, 67.0500),
        ("clifton", "karachi"): (24.8138, 67.0300),
        ("sea view", "karachi"): (24.8050, 67.0180),
        ("saddar", "karachi"): (24.8607, 67.0104),
        ("north nazimabad", "karachi"): (24.9420, 67.0512),
        ("nazimabad", "karachi"): (24.9214, 67.0334),
        ("korangi", "karachi"): (24.8340, 67.1285),
        ("landhi", "karachi"): (24.8460, 67.2130),
        ("malir", "karachi"): (24.8933, 67.1970),
        ("shah faisal", "karachi"): (24.8750, 67.1100),
        ("fb area", "karachi"): (24.9263, 67.0563),
        ("federal b area", "karachi"): (24.9263, 67.0563),
        ("pechs", "karachi"): (24.8700, 67.0670),
        ("smchs", "karachi"): (24.8600, 67.0750),
        ("tariq road", "karachi"): (24.8760, 67.0640),
        ("bahadurabad", "karachi"): (24.8795, 67.0735),
        ("gulshan-e-iqbal", "karachi"): (24.9200, 67.0900),
        ("gulshan", "karachi"): (24.9200, 67.0900),
        ("johar", "karachi"): (24.9165, 67.1255),
        ("site area", "karachi"): (24.8900, 66.9850),
        ("north karachi", "karachi"): (24.9700, 67.0500),
        ("orangi", "karachi"): (24.9450, 66.9850),
        ("lyari", "karachi"): (24.8700, 66.9900),
        ("kemari", "karachi"): (24.8350, 66.9650),
        ("liaquatabad", "karachi"): (24.9100, 67.0350),
        ("garden", "karachi"): (24.8650, 67.0200),
        ("i.i. chundrigar", "karachi"): (24.8530, 67.0080),
        ("ii chundrigar", "karachi"): (24.8530, 67.0080),
        ("shahrah-e-faisal", "karachi"): (24.8650, 67.0800),
        ("university road", "karachi"): (24.9300, 67.1100),
        ("karachi university", "karachi"): (24.9400, 67.1200),
        ("nipa", "karachi"): (24.9050, 67.0750),
        ("airport", "karachi"): (24.9065, 67.1607),
        ("bin qasim", "karachi"): (24.8100, 67.3500),

        # Lahore Areas
        ("dha", "lahore"): (31.4744, 74.3587),
        ("dha phase 1", "lahore"): (31.4900, 74.3650),
        ("dha phase 2", "lahore"): (31.4850, 74.3700),
        ("dha phase 3", "lahore"): (31.4800, 74.3750),
        ("dha phase 4", "lahore"): (31.4750, 74.3800),
        ("dha phase 5", "lahore"): (31.4700, 74.3850),
        ("dha phase 6", "lahore"): (31.4650, 74.3900),
        ("defence", "lahore"): (31.4744, 74.3587),
        ("gulberg", "lahore"): (31.5150, 74.3514),
        ("gulberg 1", "lahore"): (31.5180, 74.3450),
        ("gulberg 2", "lahore"): (31.5150, 74.3514),
        ("gulberg 3", "lahore"): (31.5120, 74.3580),
        ("model town", "lahore"): (31.4836, 74.3164),
        ("johar town", "lahore"): (31.4692, 74.2721),
        ("bahria town", "lahore"): (31.3625, 74.1820),
        ("cantt", "lahore"): (31.5350, 74.3610),
        ("cantonment", "lahore"): (31.5350, 74.3610),
        ("garden town", "lahore"): (31.5010, 74.3300),
        ("faisal town", "lahore"): (31.4920, 74.3050),
        ("iqbal town", "lahore"): (31.4850, 74.2900),
        ("township", "lahore"): (31.4600, 74.2650),
        ("wapda town", "lahore"): (31.4550, 74.2850),
        ("valencia", "lahore"): (31.4500, 74.2750),
        ("state life", "lahore"): (31.4680, 74.2650),
        ("sabzazar", "lahore"): (31.5250, 74.2900),
        ("allama iqbal town", "lahore"): (31.4850, 74.2900),
        ("cavalry ground", "lahore"): (31.5300, 74.3700),
        ("askari", "lahore"): (31.5100, 74.3800),
        ("pcsir", "lahore"): (31.5080, 74.3100),
        ("liberty", "lahore"): (31.5180, 74.3500),
        ("mall road", "lahore"): (31.5570, 74.3240),
        ("anarkali", "lahore"): (31.5600, 74.3150),
        ("old lahore", "lahore"): (31.5800, 74.3100),
        ("data darbar", "lahore"): (31.5700, 74.3050),
        ("shalimar", "lahore"): (31.5950, 74.3400),
        ("shahdara", "lahore"): (31.6100, 74.3000),
        ("airport", "lahore"): (31.5216, 74.4036),

        # Islamabad Sectors
        ("f-5", "islamabad"): (33.7350, 73.1020),
        ("f-6", "islamabad"): (33.7294, 73.0931),
        ("f-7", "islamabad"): (33.7195, 73.0711),
        ("f-8", "islamabad"): (33.7085, 73.0494),
        ("f-9", "islamabad"): (33.6980, 73.0280),
        ("f-10", "islamabad"): (33.6956, 73.0159),
        ("f-11", "islamabad"): (33.6850, 72.9950),
        ("g-5", "islamabad"): (33.7220, 73.1100),
        ("g-6", "islamabad"): (33.7150, 73.0950),
        ("g-7", "islamabad"): (33.7050, 73.0750),
        ("g-8", "islamabad"): (33.6950, 73.0550),
        ("g-9", "islamabad"): (33.6889, 73.0283),
        ("g-10", "islamabad"): (33.6750, 73.0100),
        ("g-11", "islamabad"): (33.6650, 72.9900),
        ("i-8", "islamabad"): (33.6678, 73.0780),
        ("i-9", "islamabad"): (33.6550, 73.0550),
        ("i-10", "islamabad"): (33.6450, 73.0120),
        ("e-7", "islamabad"): (33.7400, 73.0700),
        ("e-11", "islamabad"): (33.7050, 72.9700),
        ("d-12", "islamabad"): (33.6700, 72.9500),
        ("blue area", "islamabad"): (33.7100, 73.0577),
        ("jinnah super", "islamabad"): (33.7150, 73.0650),
        ("super market", "islamabad"): (33.7150, 73.0650),
        ("melody", "islamabad"): (33.7080, 73.0500),
        ("centaurus", "islamabad"): (33.7050, 73.0550),
        ("pims", "islamabad"): (33.6920, 73.0480),
        ("faisal mosque", "islamabad"): (33.7295, 73.0372),
        ("bahria town", "islamabad"): (33.5200, 73.1200),
        ("dha", "islamabad"): (33.5800, 73.1500),
        ("pwt", "islamabad"): (33.6400, 73.1000),

        # Rawalpindi Areas
        ("saddar", "rawalpindi"): (33.5970, 73.0550),
        ("commercial market", "rawalpindi"): (33.5950, 73.0500),
        ("raja bazaar", "rawalpindi"): (33.6000, 73.0650),
        ("satellite town", "rawalpindi"): (33.6150, 73.0700),
        ("westridge", "rawalpindi"): (33.5700, 73.0300),
        ("chaklala", "rawalpindi"): (33.5600, 73.0900),
        ("airport", "rawalpindi"): (33.6167, 73.0991),
        ("bahria town", "rawalpindi"): (33.5200, 73.1200),
        ("dha", "rawalpindi"): (33.5200, 73.1400),
        ("committee chowk", "rawalpindi"): (33.5900, 73.0650),
        ("murree road", "rawalpindi"): (33.6050, 73.0750),

        # Faisalabad Areas
        ("d ground", "faisalabad"): (31.4180, 73.0850),
        ("peoples colony", "faisalabad"): (31.4350, 73.0650),
        ("madina town", "faisalabad"): (31.4250, 73.0950),
        ("jinnah colony", "faisalabad"): (31.4150, 73.1000),
        ("ghulam muhammad abad", "faisalabad"): (31.4050, 73.1100),
        ("civil lines", "faisalabad"): (31.4200, 73.0800),
        ("clock tower", "faisalabad"): (31.4180, 73.0770),

        # Multan Areas
        ("cantt", "multan"): (30.1800, 71.4700),
        ("gulgasht", "multan"): (30.2050, 71.4550),
        ("bosan road", "multan"): (30.2100, 71.4400),
        ("wapda town", "multan"): (30.1950, 71.4800),
        ("shah rukn e alam", "multan"): (30.1970, 71.5100),
        ("qasim bela", "multan"): (30.2000, 71.4650),

        # Peshawar Areas
        ("hayatabad", "peshawar"): (33.9850, 71.4350),
        ("university town", "peshawar"): (34.0050, 71.5000),
        ("saddar", "peshawar"): (34.0100, 71.5700),
        ("cantt", "peshawar"): (34.0000, 71.5400),
        ("ring road", "peshawar"): (33.9950, 71.4800),

        # Quetta Areas
        ("cantt", "quetta"): (30.1900, 66.9800),
        ("jinnah road", "quetta"): (30.1850, 66.9950),
        ("satellite town", "quetta"): (30.1750, 66.9700),
        ("brewery road", "quetta"): (30.1700, 67.0100),

        # Hyderabad Areas
        ("latifabad", "hyderabad"): (25.4100, 68.3350),
        ("qasimabad", "hyderabad"): (25.3750, 68.3250),
        ("cantonment", "hyderabad"): (25.3850, 68.3600),
        ("saddar", "hyderabad"): (25.3900, 68.3700),
    }

    # City center coordinates (fallback)
    CITY_CENTERS: Dict[str, Tuple[float, float]] = {
        "karachi": (24.8607, 67.0011),
        "lahore": (31.5204, 74.3587),
        "islamabad": (33.6844, 73.0479),
        "rawalpindi": (33.5651, 73.0169),
        "faisalabad": (31.4504, 73.1350),
        "multan": (30.1575, 71.5249),
        "peshawar": (34.0151, 71.5249),
        "quetta": (30.1798, 66.9750),
        "hyderabad": (25.3960, 68.3578),
        "sialkot": (32.4945, 74.5229),
        "gujranwala": (32.1877, 74.1945),
        "bahawalpur": (29.3956, 71.6836),
        "sargodha": (32.0836, 72.6711),
        "sukkur": (27.7052, 68.8574),
        "larkana": (27.5570, 68.2028),
        "mardan": (34.1986, 72.0404),
        "abbottabad": (34.1688, 73.2215),
        "mirpur": (33.1463, 73.7510),
        "muzaffarabad": (34.3700, 73.4711),
        "gwadar": (25.1264, 62.3225),
        "gilgit": (35.9208, 74.3144),
    }

    # City name variations/aliases
    CITY_ALIASES: Dict[str, str] = {
        "khi": "karachi",
        "kci": "karachi",
        "lhr": "lahore",
        "lhe": "lahore",
        "isb": "islamabad",
        "isl": "islamabad",
        "rwp": "rawalpindi",
        "pindi": "rawalpindi",
        "fsb": "faisalabad",
        "fsd": "faisalabad",
        "mux": "multan",
        "pew": "peshawar",
        "uet": "quetta",
        "hyd": "hyderabad",
        "skp": "sialkot",
        "gwl": "gujranwala",
        "bwp": "bahawalpur",
    }

    def __init__(self, google_maps_api_key: Optional[str] = None):
        """Initialize with optional Google Maps API key"""
        settings = get_settings()
        self.google_maps_api_key = google_maps_api_key or settings.google_maps_api_key or os.getenv("GOOGLE_MAP_API")
        self._http_client: Optional[httpx.AsyncClient] = None
        self.logger = get_agent_logger()

        if self.google_maps_api_key:
            print(f"✓ LocationResolver initialized with Google Maps API")
        else:
            print(f"✓ LocationResolver initialized (offline mode - no Google Maps API key)")

    def _normalize_text(self, text: str) -> str:
        """Normalize location text for matching"""
        # Convert to lowercase
        text = text.lower().strip()
        # Remove common punctuation
        text = re.sub(r'[,\.\-]', ' ', text)
        # Normalize spaces
        text = re.sub(r'\s+', ' ', text)
        return text

    def _extract_city(self, text: str) -> Optional[str]:
        """Extract city name from text"""
        text_lower = self._normalize_text(text)

        # Check for aliases first
        for alias, city in self.CITY_ALIASES.items():
            if alias in text_lower.split():
                return city

        # Check for city names
        for city in self.CITY_CENTERS.keys():
            if city in text_lower:
                return city

        return None

    def _extract_area(self, text: str, city: Optional[str]) -> Optional[Tuple[str, float, float]]:
        """Extract area and coordinates from text"""
        text_lower = self._normalize_text(text)
        # Also create version with hyphens for sectors like F-8, G-9
        text_with_hyphens = text.lower().strip()

        # Try to match known areas
        for (area, area_city), coords in self.KNOWN_AREAS.items():
            # Match if area is in text and city matches (or no city specified)
            # Check both normalized version (spaces) and original (with hyphens)
            area_no_hyphen = area.replace('-', ' ')
            if area in text_lower or area_no_hyphen in text_lower or area in text_with_hyphens:
                if not city or city == area_city:
                    return (area.replace('-', ' ').title(), coords[0], coords[1])

        return None

    def resolve(
        self,
        location_text: str,
        city_hint: Optional[str] = None,
        lat: Optional[float] = None,
        long: Optional[float] = None,
        session_id: str = "system",
        use_google_fallback: bool = True
    ) -> ResolvedLocation:
        """
        Resolve location text to coordinates.

        Args:
            location_text: Location description (e.g., "Gulistan-e-Jauhar Karachi")
            city_hint: City name if known from context
            lat: Direct latitude if available (WhatsApp location)
            long: Direct longitude if available (WhatsApp location)
            session_id: For logging purposes
            use_google_fallback: Whether to use Google Maps API if local resolution fails

        Returns:
            ResolvedLocation with coordinates and metadata
        """
        self.logger.log_tool_call(
            session_id=session_id,
            agent_name="LocationResolver",
            tool_name="resolve_location",
            inputs={"location_text": location_text, "city_hint": city_hint, "has_coords": lat is not None},
            category=LogCategory.LOCATION
        )

        # If direct coordinates provided (WhatsApp location share)
        if lat is not None and long is not None:
            city = self._find_nearest_city(lat, long)
            self.logger.log_reasoning(
                session_id=session_id,
                agent_name="LocationResolver",
                thought=f"Direct coordinates provided via WhatsApp. Nearest city: {city}",
                category=LogCategory.LOCATION,
                data={"lat": lat, "long": long, "source": "whatsapp"}
            )
            return ResolvedLocation(
                lat=lat,
                long=long,
                confidence="high",
                city=city,
                search_radius_km=5.0,
                source="whatsapp"
            )

        # Normalize inputs
        text = self._normalize_text(location_text)
        city = city_hint.lower() if city_hint else self._extract_city(text)
        if city:
            city = self.CITY_ALIASES.get(city, city)

        self.logger.log_reasoning(
            session_id=session_id,
            agent_name="LocationResolver",
            thought=f"Analyzing location text: '{location_text}' → Extracted city: {city or 'None'}",
            category=LogCategory.LOCATION
        )

        # Try to extract area and get coordinates
        area_result = self._extract_area(text, city)
        if area_result:
            area_name, resolved_lat, resolved_long = area_result
            self.logger.log_tool_result(
                session_id=session_id,
                agent_name="LocationResolver",
                tool_name="resolve_location",
                result_summary=f"Matched known area: {area_name}, {city}",
                success=True,
                category=LogCategory.LOCATION,
                data={"lat": resolved_lat, "long": resolved_long, "confidence": "high"}
            )
            return ResolvedLocation(
                lat=resolved_lat,
                long=resolved_long,
                confidence="high",
                city=city.title() if city else None,
                area=area_name,
                search_radius_km=5.0,
                source="known_area"
            )

        # Try Google Maps API if available and enabled
        if use_google_fallback and self.google_maps_api_key and city:
            self.logger.log_reasoning(
                session_id=session_id,
                agent_name="LocationResolver",
                thought=f"Local area lookup failed. Trying Google Maps Geocoding API...",
                category=LogCategory.LOCATION
            )
            google_result = self._resolve_with_google_sync(location_text, city, session_id)
            if google_result and google_result.confidence == "high":
                return google_result

        # Fallback to city center
        if city and city in self.CITY_CENTERS:
            coords = self.CITY_CENTERS[city]
            self.logger.log_tool_result(
                session_id=session_id,
                agent_name="LocationResolver",
                tool_name="resolve_location",
                result_summary=f"Using city center fallback for {city}",
                success=True,
                category=LogCategory.LOCATION,
                data={"lat": coords[0], "long": coords[1], "confidence": "low"}
            )
            return ResolvedLocation(
                lat=coords[0],
                long=coords[1],
                confidence="low",
                city=city.title(),
                search_radius_km=15.0,  # Wider radius for city-level
                clarification_needed=f"Aap {city.title()} ke kis area mein hain? (Which area in {city.title()}?)",
                source="city_center"
            )

        # Unable to resolve
        self.logger.log_tool_result(
            session_id=session_id,
            agent_name="LocationResolver",
            tool_name="resolve_location",
            result_summary="Could not resolve location",
            success=False,
            category=LogCategory.LOCATION
        )
        return ResolvedLocation(
            confidence="none",
            clarification_needed="Please share your location or tell me your area and city (e.g., 'Gulistan-e-Jauhar, Karachi')"
        )

    def _resolve_with_google_sync(
        self,
        location_text: str,
        city_hint: Optional[str] = None,
        session_id: str = "system"
    ) -> Optional[ResolvedLocation]:
        """
        Synchronous Google Maps Geocoding API call.

        Returns ResolvedLocation or None if geocoding fails.
        """
        if not self.google_maps_api_key:
            return None

        try:
            log_id = self.logger.log_tool_call(
                session_id=session_id,
                agent_name="LocationResolver",
                tool_name="google_maps_geocode",
                inputs={"query": location_text, "city_hint": city_hint},
                category=LogCategory.LOCATION
            )

            # Build search query
            query = location_text
            if city_hint:
                query = f"{location_text}, {city_hint}, Pakistan"
            else:
                query = f"{location_text}, Pakistan"

            # Call Google Geocoding API
            response = requests.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={
                    "address": query,
                    "key": self.google_maps_api_key,
                    "region": "pk",
                    "components": "country:PK"
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if data["status"] == "OK" and data["results"]:
                result = data["results"][0]
                location = result["geometry"]["location"]

                # Extract city and area from address components
                city = None
                area = None
                formatted_address = result.get("formatted_address", "")

                for component in result.get("address_components", []):
                    types = component.get("types", [])
                    if "locality" in types:
                        city = component["long_name"]
                    elif "sublocality_level_1" in types or "sublocality" in types:
                        area = component["long_name"]
                    elif "administrative_area_level_2" in types and not city:
                        city = component["long_name"]

                self.logger.log_tool_result(
                    session_id=session_id,
                    agent_name="LocationResolver",
                    tool_name="google_maps_geocode",
                    result_summary=f"Google Maps resolved to: {area or ''}, {city or 'Pakistan'}",
                    success=True,
                    log_id=log_id,
                    category=LogCategory.LOCATION,
                    data={
                        "lat": location["lat"],
                        "long": location["lng"],
                        "formatted_address": formatted_address
                    }
                )

                return ResolvedLocation(
                    lat=location["lat"],
                    long=location["lng"],
                    confidence="high",
                    city=city,
                    area=area,
                    search_radius_km=5.0,
                    source="google_maps"
                )
            else:
                self.logger.log_tool_result(
                    session_id=session_id,
                    agent_name="LocationResolver",
                    tool_name="google_maps_geocode",
                    result_summary=f"Google Maps returned no results (status: {data['status']})",
                    success=False,
                    log_id=log_id,
                    category=LogCategory.LOCATION
                )
                return None

        except Exception as e:
            self.logger.log_error(
                session_id=session_id,
                agent_name="LocationResolver",
                error=f"Google Maps API error: {str(e)}",
                category=LogCategory.LOCATION
            )
            return None

    async def resolve_with_google(
        self,
        location_text: str,
        city_hint: Optional[str] = None
    ) -> ResolvedLocation:
        """
        Resolve location using Google Maps Geocoding API.

        Falls back to local resolution if API unavailable.
        """
        # First try local resolution
        local_result = self.resolve(location_text, city_hint)
        if local_result.confidence == "high":
            return local_result

        # If no API key, return local result
        if not self.google_maps_api_key:
            return local_result

        try:
            # Initialize HTTP client if needed
            if not self._http_client:
                self._http_client = httpx.AsyncClient(timeout=10.0)

            # Build search query
            query = location_text
            if city_hint:
                query = f"{location_text}, {city_hint}, Pakistan"
            else:
                query = f"{location_text}, Pakistan"

            # Call Google Geocoding API
            response = await self._http_client.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={
                    "address": query,
                    "key": self.google_maps_api_key,
                    "region": "pk",  # Pakistan region bias
                    "components": "country:PK"  # Restrict to Pakistan
                }
            )
            response.raise_for_status()
            data = response.json()

            if data["status"] == "OK" and data["results"]:
                result = data["results"][0]
                location = result["geometry"]["location"]

                # Extract city and area from address components
                city = None
                area = None
                for component in result.get("address_components", []):
                    if "locality" in component["types"]:
                        city = component["long_name"]
                    elif "sublocality" in component["types"]:
                        area = component["long_name"]
                    elif "administrative_area_level_2" in component["types"] and not city:
                        city = component["long_name"]

                return ResolvedLocation(
                    lat=location["lat"],
                    long=location["lng"],
                    confidence="high",
                    city=city,
                    area=area,
                    search_radius_km=5.0,
                    source="google_maps"
                )

        except Exception as e:
            print(f"Google Geocoding error: {e}")

        # Return local result if Google failed
        return local_result

    def _find_nearest_city(self, lat: float, long: float) -> Optional[str]:
        """Find nearest city to given coordinates"""
        from math import radians, sin, cos, sqrt, atan2

        min_distance = float('inf')
        nearest_city = None

        for city, (city_lat, city_long) in self.CITY_CENTERS.items():
            # Haversine distance
            R = 6371  # Earth's radius in km
            lat1, lon1, lat2, lon2 = map(radians, [lat, long, city_lat, city_long])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            distance = R * c

            if distance < min_distance:
                min_distance = distance
                nearest_city = city

        return nearest_city.title() if nearest_city else None

    def get_city_center(self, city: str) -> Optional[Tuple[float, float]]:
        """Get city center coordinates"""
        city_lower = city.lower()
        city_lower = self.CITY_ALIASES.get(city_lower, city_lower)
        return self.CITY_CENTERS.get(city_lower)

    def get_known_areas(self, city: str) -> List[str]:
        """Get list of known areas in a city"""
        city_lower = city.lower()
        city_lower = self.CITY_ALIASES.get(city_lower, city_lower)
        areas = []
        for (area, area_city) in self.KNOWN_AREAS.keys():
            if area_city == city_lower:
                areas.append(area.replace('-', ' ').title())
        return sorted(set(areas))


# Global instance
_resolver: Optional[LocationResolver] = None


def get_location_resolver(google_maps_api_key: Optional[str] = None) -> LocationResolver:
    """Get or create location resolver instance"""
    global _resolver
    if _resolver is None:
        _resolver = LocationResolver(google_maps_api_key)
    return _resolver
