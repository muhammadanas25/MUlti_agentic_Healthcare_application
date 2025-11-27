# Sehat Saathi: Multi-Agent Hospital Search & Emergency Routing System

## Executive Summary

Your hospital dataset contains **8,651 hospitals across 127 Pakistani cities** with lat/long coordinates. This document outlines a comprehensive multi-agent architecture for intelligent hospital search, emergency routing, and provider-side demand management.

---

## Part 1: Architecture Overview

### Agent Decomposition Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                           │
│         (Routes requests, manages conversation state)           │
└─────────────────────────┬───────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   TRIAGE      │ │   LOCATION    │ │   HOSPITAL    │
│   AGENT       │ │   AGENT       │ │   SEARCH      │
│               │ │               │ │   AGENT       │
│ • Emergency   │ │ • Geocoding   │ │ • CSV Query   │
│   assessment  │ │ • WhatsApp    │ │ • Filtering   │
│ • Resource    │ │   location    │ │ • Distance    │
│   needs       │ │ • Vague refs  │ │   ranking     │
└───────────────┘ └───────────────┘ └───────────────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          ▼
              ┌───────────────────────┐
              │   PROVIDER AGENT      │
              │                       │
              │ • Demand estimation   │
              │ • Arrival tracking    │
              │ • Resource allocation │
              └───────────────────────┘
```

---

## Part 2: Data Layer Strategy

### Option A: In-Memory DataFrame with Tool Calls (Recommended for <50k records)

```python
# Agent loads CSV into memory, uses pandas for queries
# Best for: Fast responses, complex filtering, no external dependencies

TOOL: search_hospitals
Parameters:
  - city: str (optional)
  - area: str (optional) 
  - user_lat: float
  - user_long: float
  - max_distance_km: float (default: 10)
  - limit: int (default: 5)
```

### Option B: SQLite with Natural Language to SQL

```python
# Convert CSV to SQLite, agent generates SQL queries
# Best for: Complex multi-condition queries, aggregations

TOOL: query_hospital_db
Parameters:
  - natural_language_query: str  # Agent converts this to SQL
```

### Option C: Vector Search + Structured Filters (For semantic search)

```python
# Embed hospital descriptions, combine with structured filters
# Best for: "Find a hospital good for heart conditions near me"
```

### Recommendation for Your Use Case

**Use Option A (In-Memory DataFrame)** because:
1. 8,651 records fits easily in memory
2. Distance calculations need lat/long math (pandas + haversine)
3. Fast iteration, no infrastructure setup
4. Direct filtering by city/area is fast

---

## Part 3: Tool Definitions for Hospital Search Agent

### Tool 1: `search_hospitals_by_location`

```json
{
  "name": "search_hospitals_by_location",
  "description": "Search for hospitals near a given location. Returns hospitals sorted by distance.",
  "parameters": {
    "type": "object",
    "properties": {
      "user_lat": {
        "type": "number",
        "description": "User's latitude coordinate"
      },
      "user_long": {
        "type": "number",
        "description": "User's longitude coordinate"
      },
      "city": {
        "type": "string",
        "description": "City name to filter (optional, for faster search)"
      },
      "max_distance_km": {
        "type": "number",
        "description": "Maximum distance in kilometers (default: 10)"
      },
      "limit": {
        "type": "integer",
        "description": "Maximum number of results to return (default: 5)"
      }
    },
    "required": ["user_lat", "user_long"]
  }
}
```

### Tool 2: `geocode_location`

```json
{
  "name": "geocode_location",
  "description": "Convert a location name, address, or vague reference to coordinates. Handles Pakistani location formats including areas like 'Gulistan-e-Jauhar', 'DHA Phase 5', etc.",
  "parameters": {
    "type": "object",
    "properties": {
      "location_text": {
        "type": "string",
        "description": "Location description (e.g., 'Gulistan-e-Jauhar Karachi', 'near Jinnah Hospital Lahore', 'F-8 Islamabad')"
      },
      "city_hint": {
        "type": "string",
        "description": "City name if known from context"
      }
    },
    "required": ["location_text"]
  }
}
```

### Tool 3: `filter_hospitals_by_capability`

```json
{
  "name": "filter_hospitals_by_capability",
  "description": "Filter hospitals based on emergency capability requirements. Note: Since your CSV doesn't have capability data, this would filter by hospital name patterns or require enrichment.",
  "parameters": {
    "type": "object",
    "properties": {
      "hospital_ids": {
        "type": "array",
        "items": {"type": "string"},
        "description": "List of hospital IDs to filter"
      },
      "requires_icu": {"type": "boolean"},
      "requires_ventilator": {"type": "boolean"},
      "requires_blood_bank": {"type": "boolean"},
      "requires_emergency": {"type": "boolean"},
      "specialty_needed": {
        "type": "string",
        "description": "e.g., 'cardiac', 'trauma', 'pediatric', 'maternity'"
      }
    },
    "required": ["hospital_ids"]
  }
}
```

---

## Part 4: Agent Prompts

### 4.1 Orchestrator Agent Prompt

```
You are the Sehat Saathi Orchestrator - a healthcare emergency coordination system for Pakistan. Your role is to route incoming requests to specialized sub-agents and synthesize their responses.

## Your Sub-Agents:
1. TRIAGE_AGENT: Assesses emergency type and required medical resources
2. LOCATION_AGENT: Resolves user location from various input formats
3. HOSPITAL_SEARCH_AGENT: Queries hospital database and ranks by suitability
4. PROVIDER_AGENT: Manages hospital-side operations (arrivals, capacity)

## Routing Logic:
- User describes symptoms/emergency → TRIAGE_AGENT first
- User provides location (any format) → LOCATION_AGENT
- Need to find hospitals → HOSPITAL_SEARCH_AGENT (after location resolved)
- Hospital needs capacity update → PROVIDER_AGENT

## Response Format:
Always provide:
1. Emergency severity assessment (if applicable)
2. Top 3 recommended hospitals with distance
3. Contact numbers
4. Google Maps links for navigation
5. Estimated response time guidance

## Language:
- Respond in the same language as the user (Urdu/English/Roman Urdu)
- Use simple, clear instructions suitable for emergencies
- Include phone numbers prominently
`
### 4.3 Location Agent Prompt

```
You are the LOCATION_AGENT for Sehat Saathi. Your role is to resolve user locations into coordinates for hospital search.

## Location Input Types You Handle:

### 1. WhatsApp Location Share
- Format: Coordinates provided directly
- Action: Use coordinates as-is

### 2. Specific Address
- Example: "House 45, Block 5, Gulistan-e-Jauhar, Karachi"
- Action: Use geocoding tool with full address

### 3. Area/Neighborhood Reference
- Example: "Gulistan-e-Jauhar Karachi", "DHA Phase 6", "F-8 Islamabad"
- Action: Map to known area centroid coordinates

### 4. Landmark-Based
- Example: "Near Jinnah Hospital", "Opposite Dolmen Mall Clifton"
- Action: Geocode landmark, user is nearby

### 5. Vague/Partial
- Example: "Main shahrah-e-faisal", "Saddar area"
- Action: Request clarification OR use area centroid with wider search radius

## Pakistan-Specific Knowledge:

### Karachi Areas (Sample Coordinates):
- Gulistan-e-Jauhar: 24.9165, 67.1255
- DHA Phase 5: 24.7937, 67.0513
- Clifton: 24.8138, 67.0300
- Saddar: 24.8607, 67.0104
- North Nazimabad: 24.9420, 67.0512
- Korangi: 24.8340, 67.1285

### Lahore Areas:
- DHA: 31.4744, 74.3587
- Gulberg: 31.5150, 74.3514
- Model Town: 31.4836, 74.3164
- Johar Town: 31.4692, 74.2721

### Islamabad Sectors:
- F-6: 33.7294, 73.0931
- F-7: 33.7195, 73.0711
- F-8: 33.7085, 73.0494
- G-9: 33.6889, 73.0283
- I-8: 33.6678, 73.0780

## Output Format:
{
  "resolved_lat": 24.9165,
  "resolved_long": 67.1255,
  "confidence": "high|medium|low",
  "resolved_city": "Karachi",
  "resolved_area": "Gulistan-e-Jauhar",
  "search_radius_km": 5,  // Wider if low confidence
  "clarification_needed": null  // or "Which block in Gulistan-e-Jauhar?"
}

## When to Ask for Clarification:
- Only if location is genuinely ambiguous AND time permits
- For CRITICAL emergencies, use best estimate with wider radius
- Never delay emergency response for perfect location
```

### 4.4 Hospital Search Agent Prompt

```
You are the HOSPITAL_SEARCH_AGENT for Sehat Saathi. You query the hospital database and rank results by suitability for the emergency.

## Available Data Fields:
- HOSPITAL NAME
- CITY
- AREA
- ADDRESS
- DOCTORS (count)
- CONTACT
- Lat, Long (coordinates)
- Google Map Link

## Search Strategy:

### Step 1: City Filter
- First filter to user's city (reduces from 8651 to ~500-2000)

### Step 2: Distance Calculation
- Use Haversine formula for accurate distance
- Sort by distance ascending

### Step 3: Capability Inference (Since data lacks explicit capabilities)
Infer from hospital name:
- "Teaching Hospital", "Medical Center", "General Hospital" → Full emergency services
- "Children's Hospital", "Child Care" → Pediatric
- "Heart", "Cardiac", "Cardio" → Cardiac care
- "Eye", "Ophthalmic" → Eye emergencies
- "Maternity", "Mother", "Women" → Obstetric
- "Trauma", "Accident" → Trauma care
- "ICU", "Critical Care" → ICU available
- "Clinic" → Limited emergency capacity

### Step 4: Ranking Score
```
score = (1 / distance_km) * capability_match * doctor_count_factor
```

## Query Patterns:

### Pattern 1: Nearest Any Hospital
```python
hospitals_in_city = df[df['CITY'] == user_city]
hospitals_in_city['distance'] = haversine(user_lat, user_long, hospital_lat, hospital_long)
return hospitals_in_city.nsmallest(5, 'distance')
```

### Pattern 2: Nearest with Capability
```python
# Filter by name patterns for capability
cardiac_keywords = ['heart', 'cardiac', 'cardio', 'chest']
capable_hospitals = hospitals_in_city[
    hospitals_in_city['HOSPITAL NAME'].str.lower().str.contains('|'.join(cardiac_keywords))
]
```

### Pattern 3: Area-Specific Search
```python
hospitals_in_area = df[
    (df['CITY'] == user_city) & 
    (df['AREA'].str.contains(user_area, case=False, na=False))
]
```

## Output Format:
{
  "search_params": {
    "user_location": [lat, long],
    "city": "Karachi",
    "capability_filter": "cardiac",
    "search_radius_km": 10
  },
  "results": [
    {
      "rank": 1,
      "hospital_name": "National Institute of Cardiovascular Diseases",
      "distance_km": 2.3,
      "address": "...",
      "contact": "021-99201271",
      "google_maps_link": "https://...",
      "capability_match": "high",
      "doctors_count": 45
    }
  ],
  "total_found": 12,
  "search_note": "Showing cardiac-specialized hospitals. For general emergency, more options available."
}
```

### 4.5 Provider Agent Prompt

```
You are the PROVIDER_AGENT for Sehat Saathi. You manage hospital-side operations including patient arrivals, capacity tracking, and resource demand estimation.

## Core Functions:

### 1. Arrival Registration
When a patient is routed to a hospital:
{
  "action": "register_arrival",
  "hospital_id": "...",
  "patient_id": "anonymous_hash",
  "estimated_arrival_minutes": 15,
  "emergency_type": "cardiac",
  "resources_needed": ["icu", "ventilator"],
  "transport_type": "ambulance"
}

### 2. Capacity Tracking
Maintain real-time estimates:
{
  "hospital_id": "...",
  "current_capacity": {
    "emergency_beds": {"total": 20, "available": 5},
    "icu_beds": {"total": 10, "available": 2},
    "ventilators": {"total": 8, "available": 3},
    "blood_units": {"O+": 15, "O-": 5, "A+": 20, ...}
  },
  "incoming_patients": [
    {"eta_minutes": 5, "needs": ["icu"]},
    {"eta_minutes": 12, "needs": ["emergency_bed"]}
  ]
}

### 3. Demand Forecasting
Based on incoming flow:
{
  "hospital_id": "...",
  "next_hour_forecast": {
    "expected_arrivals": 8,
    "icu_demand": 2,
    "blood_demand": {"O+": 3, "A-": 1},
    "ventilator_demand": 1
  },
  "alerts": [
    {"type": "capacity_warning", "resource": "icu_beds", "message": "ICU at 80% - consider diversion"}
  ]
}

### 4. Load Balancing Recommendations
When hospital is at capacity:
{
  "action": "recommend_diversion",
  "from_hospital": "...",
  "reason": "ICU full",
  "alternative_hospitals": [
    {"name": "...", "distance_km": 3.2, "icu_available": 4}
  ]
}

## Integration Points:
- Receives patient routing from HOSPITAL_SEARCH_AGENT
- Updates capacity based on confirmed arrivals
- Provides capacity data back to search for better routing
- Alerts staff via dashboard/notifications

## Estimation Logic (When Real Data Unavailable):
Since you may not have real-time hospital data, use heuristics:
- Larger hospitals (more doctors) = more capacity
- Teaching hospitals = better emergency resources
- Time of day affects availability (night = fewer elective, more emergency capacity)
- Weekend/holiday patterns
```

---

## Part 5: Implementation Code

### 5.1 Hospital Search Tool Implementation

```python
import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2

class HospitalSearchTool:
    def __init__(self, csv_path: str):
        self.df = pd.read_csv(csv_path)
        self.df.columns = self.df.columns.str.strip()
        # Clean coordinates
        self.df['Lat'] = pd.to_numeric(self.df['Lat'], errors='coerce')
        self.df['Long'] = pd.to_numeric(self.df['Long'], errors='coerce')
        # Pre-compute city index for fast filtering
        self.city_index = self.df.groupby('CITY').indices
        
    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance in km between two points."""
        R = 6371  # Earth's radius in km
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    def search_nearby(
        self, 
        user_lat: float, 
        user_long: float, 
        city: str = None,
        max_distance_km: float = 10,
        limit: int = 5,
        capability_keywords: list = None
    ) -> list:
        """Search for hospitals near user location."""
        
        # Start with full dataset or city subset
        if city and city in self.city_index:
            working_df = self.df.iloc[self.city_index[city]].copy()
        else:
            working_df = self.df.copy()
        
        # Filter by capability keywords if provided
        if capability_keywords:
            pattern = '|'.join(capability_keywords)
            working_df = working_df[
                working_df['HOSPITAL NAME'].str.lower().str.contains(pattern, na=False)
            ]
        
        # Calculate distances
        working_df['distance_km'] = working_df.apply(
            lambda row: self.haversine_distance(
                user_lat, user_long, row['Lat'], row['Long']
            ) if pd.notna(row['Lat']) and pd.notna(row['Long']) else float('inf'),
            axis=1
        )
        
        # Filter by max distance and sort
        nearby = working_df[working_df['distance_km'] <= max_distance_km]
        nearby = nearby.nsmallest(limit, 'distance_km')
        
        # Format results
        results = []
        for idx, row in nearby.iterrows():
            results.append({
                'hospital_name': row['HOSPITAL NAME'],
                'city': row['CITY'],
                'area': row['AREA'],
                'address': row['ADDRESS'],
                'contact': row['CONTACT'],
                'distance_km': round(row['distance_km'], 2),
                'doctors_count': row['DOCTORS'],
                'google_maps_link': row['Google Map Link'],
                'lat': row['Lat'],
                'long': row['Long']
            })
        
        return results
    
    def infer_capability(self, hospital_name: str) -> dict:
        """Infer hospital capabilities from name."""
        name_lower = hospital_name.lower()
        
        capabilities = {
            'emergency': any(kw in name_lower for kw in ['hospital', 'medical center', 'teaching']),
            'icu_likely': any(kw in name_lower for kw in ['teaching', 'general hospital', 'medical center', 'icu']),
            'cardiac': any(kw in name_lower for kw in ['heart', 'cardiac', 'cardio', 'cardiovascular', 'chest']),
            'pediatric': any(kw in name_lower for kw in ['children', 'child', 'pediatric', 'kids']),
            'maternity': any(kw in name_lower for kw in ['maternity', 'mother', 'women', 'gynae', 'obstetric']),
            'trauma': any(kw in name_lower for kw in ['trauma', 'accident', 'emergency']),
            'eye': any(kw in name_lower for kw in ['eye', 'ophthalmic', 'vision']),
            'is_clinic': 'clinic' in name_lower and 'hospital' not in name_lower
        }
        
        return capabilities
```

### 5.2 Location Resolver Implementation

```python
class LocationResolver:
    """Resolve Pakistani location references to coordinates."""
    
    # Known area coordinates (expand this significantly)
    KNOWN_AREAS = {
        # Karachi
        ('gulistan-e-jauhar', 'karachi'): (24.9165, 67.1255),
        ('gulistan e jauhar', 'karachi'): (24.9165, 67.1255),
        ('dha phase 5', 'karachi'): (24.7937, 67.0513),
        ('dha phase 6', 'karachi'): (24.7850, 67.0610),
        ('clifton', 'karachi'): (24.8138, 67.0300),
        ('saddar', 'karachi'): (24.8607, 67.0104),
        ('north nazimabad', 'karachi'): (24.9420, 67.0512),
        ('korangi', 'karachi'): (24.8340, 67.1285),
        ('malir', 'karachi'): (24.8933, 67.1970),
        ('nazimabad', 'karachi'): (24.9214, 67.0334),
        ('fb area', 'karachi'): (24.9263, 67.0563),
        ('pechs', 'karachi'): (24.8700, 67.0670),
        ('tariq road', 'karachi'): (24.8760, 67.0640),
        
        # Lahore
        ('dha', 'lahore'): (31.4744, 74.3587),
        ('gulberg', 'lahore'): (31.5150, 74.3514),
        ('model town', 'lahore'): (31.4836, 74.3164),
        ('johar town', 'lahore'): (31.4692, 74.2721),
        ('bahria town', 'lahore'): (31.3625, 74.1820),
        ('cantt', 'lahore'): (31.5350, 74.3610),
        
        # Islamabad
        ('f-6', 'islamabad'): (33.7294, 73.0931),
        ('f-7', 'islamabad'): (33.7195, 73.0711),
        ('f-8', 'islamabad'): (33.7085, 73.0494),
        ('f-10', 'islamabad'): (33.6956, 73.0159),
        ('g-9', 'islamabad'): (33.6889, 73.0283),
        ('i-8', 'islamabad'): (33.6678, 73.0780),
        ('i-10', 'islamabad'): (33.6450, 73.0120),
        ('blue area', 'islamabad'): (33.7100, 73.0577),
    }
    
    # City center coordinates (fallback)
    CITY_CENTERS = {
        'karachi': (24.8607, 67.0011),
        'lahore': (31.5204, 74.3587),
        'islamabad': (33.6844, 73.0479),
        'rawalpindi': (33.5651, 73.0169),
        'faisalabad': (31.4504, 73.1350),
        'multan': (30.1575, 71.5249),
        'peshawar': (34.0151, 71.5249),
        'quetta': (30.1798, 66.9750),
        'hyderabad': (25.3960, 68.3578),
    }
    
    def resolve(self, location_text: str, city_hint: str = None) -> dict:
        """Resolve location text to coordinates."""
        
        text_lower = location_text.lower().strip()
        
        # Extract city from text if not provided
        city = city_hint.lower() if city_hint else None
        if not city:
            for city_name in self.CITY_CENTERS.keys():
                if city_name in text_lower:
                    city = city_name
                    break
        
        # Try to match known areas
        for (area, area_city), coords in self.KNOWN_AREAS.items():
            if area in text_lower:
                if not city or city == area_city:
                    return {
                        'resolved_lat': coords[0],
                        'resolved_long': coords[1],
                        'confidence': 'high',
                        'resolved_city': area_city.title(),
                        'resolved_area': area.replace('-', ' ').title(),
                        'search_radius_km': 5
                    }
        
        # Fallback to city center
        if city and city in self.CITY_CENTERS:
            coords = self.CITY_CENTERS[city]
            return {
                'resolved_lat': coords[0],
                'resolved_long': coords[1],
                'confidence': 'low',
                'resolved_city': city.title(),
                'resolved_area': None,
                'search_radius_km': 15,  # Wider radius for low confidence
                'clarification_needed': f"Could you specify which area in {city.title()}?"
            }
        
        # Unable to resolve
        return {
            'resolved_lat': None,
            'resolved_long': None,
            'confidence': 'none',
            'clarification_needed': "Please provide your location with city name (e.g., 'Gulistan-e-Jauhar, Karachi')"
        }
```

### 5.3 Integrated Agent Tool Handler

```python
import json

class SehatSaathiToolHandler:
    """Handle all tools for the Sehat Saathi multi-agent system."""
    
    def __init__(self, hospital_csv_path: str):
        self.hospital_search = HospitalSearchTool(hospital_csv_path)
        self.location_resolver = LocationResolver()
        self.patient_arrivals = {}  # In-memory tracking
        self.hospital_capacity = {}  # Estimated capacity
    
    def handle_tool_call(self, tool_name: str, parameters: dict) -> dict:
        """Route tool calls to appropriate handlers."""
        
        handlers = {
            'search_hospitals_by_location': self._search_hospitals,
            'geocode_location': self._geocode_location,
            'assess_emergency': self._assess_emergency,
            'register_patient_arrival': self._register_arrival,
            'get_hospital_capacity': self._get_capacity,
            'update_hospital_capacity': self._update_capacity,
        }
        
        handler = handlers.get(tool_name)
        if handler:
            return handler(parameters)
        else:
            return {'error': f'Unknown tool: {tool_name}'}
    
    def _search_hospitals(self, params: dict) -> dict:
        """Search hospitals near location."""
        
        # Map emergency type to capability keywords
        capability_map = {
            'cardiac': ['heart', 'cardiac', 'cardio', 'cardiovascular', 'chest'],
            'trauma': ['trauma', 'accident', 'emergency', 'orthopedic'],
            'pediatric': ['children', 'child', 'pediatric'],
            'maternity': ['maternity', 'mother', 'women', 'gynae'],
            'respiratory': ['chest', 'pulmonary', 'respiratory', 'lung'],
        }
        
        keywords = capability_map.get(params.get('emergency_type'))
        
        results = self.hospital_search.search_nearby(
            user_lat=params['user_lat'],
            user_long=params['user_long'],
            city=params.get('city'),
            max_distance_km=params.get('max_distance_km', 10),
            limit=params.get('limit', 5),
            capability_keywords=keywords
        )
        
        return {
            'success': True,
            'results': results,
            'total_found': len(results),
            'search_params': params
        }
    
    def _geocode_location(self, params: dict) -> dict:
        """Resolve location to coordinates."""
        return self.location_resolver.resolve(
            params['location_text'],
            params.get('city_hint')
        )
    
    def _assess_emergency(self, params: dict) -> dict:
        """Assess emergency severity (simplified - real implementation needs more logic)."""
        
        symptoms = params.get('symptoms', '').lower()
        
        # Critical patterns
        critical_patterns = [
            'chest pain', 'heart attack', 'can\'t breathe', 'unconscious',
            'severe bleeding', 'accident', 'stroke', 'seizure', 'not responding'
        ]
        
        urgent_patterns = [
            'high fever', 'severe pain', 'broken', 'fracture', 'burn',
            'pregnancy complication', 'heavy bleeding'
        ]
        
        if any(pattern in symptoms for pattern in critical_patterns):
            severity = 'CRITICAL'
            time_sensitivity = 'minutes'
            transport = 'ambulance_emergency'
        elif any(pattern in symptoms for pattern in urgent_patterns):
            severity = 'URGENT'
            time_sensitivity = 'hours'
            transport = 'ambulance_standard'
        else:
            severity = 'STANDARD'
            time_sensitivity = 'day'
            transport = 'private_vehicle'
        
        return {
            'severity': severity,
            'time_sensitivity': time_sensitivity,
            'recommended_transport': transport,
            'requires_icu': severity == 'CRITICAL',
            'requires_emergency': severity in ['CRITICAL', 'URGENT']
        }
    
    def _register_arrival(self, params: dict) -> dict:
        """Register expected patient arrival."""
        hospital_id = params['hospital_id']
        
        if hospital_id not in self.patient_arrivals:
            self.patient_arrivals[hospital_id] = []
        
        arrival = {
            'patient_id': params.get('patient_id', 'anonymous'),
            'eta_minutes': params['eta_minutes'],
            'emergency_type': params.get('emergency_type'),
            'resources_needed': params.get('resources_needed', []),
            'registered_at': pd.Timestamp.now().isoformat()
        }
        
        self.patient_arrivals[hospital_id].append(arrival)
        
        return {
            'success': True,
            'message': f'Patient arrival registered at {hospital_id}',
            'arrival': arrival
        }
    
    def _get_capacity(self, params: dict) -> dict:
        """Get estimated hospital capacity."""
        hospital_id = params['hospital_id']
        
        # Return stored capacity or default estimates
        if hospital_id in self.hospital_capacity:
            return self.hospital_capacity[hospital_id]
        
        # Default estimates based on hospital type
        return {
            'hospital_id': hospital_id,
            'estimated': True,
            'emergency_beds': {'total': 20, 'available': 10},
            'icu_beds': {'total': 10, 'available': 5},
            'ventilators': {'total': 5, 'available': 3},
            'incoming_patients': self.patient_arrivals.get(hospital_id, [])
        }
    
    def _update_capacity(self, params: dict) -> dict:
        """Update hospital capacity (for provider interface)."""
        hospital_id = params['hospital_id']
        self.hospital_capacity[hospital_id] = params['capacity_data']
        return {'success': True, 'message': 'Capacity updated'}
```

---

## Part 6: Data Enrichment Strategy

Your current CSV lacks critical emergency data. Here's how to enrich it:

### Option 1: Rule-Based Inference (Immediate)
```python
HOSPITAL_TIERS = {
    'tier_1': {  # Full emergency capabilities
        'patterns': ['teaching hospital', 'medical college', 'general hospital', 
                     'civil hospital', 'jinnah hospital', 'aga khan'],
        'assumed_capabilities': ['emergency', 'icu', 'ventilator', 'blood_bank', 'surgery']
    },
    'tier_2': {  # Good emergency capabilities
        'patterns': ['hospital', 'medical center', 'healthcare'],
        'assumed_capabilities': ['emergency', 'icu']
    },
    'tier_3': {  # Basic care
        'patterns': ['clinic', 'dispensary', 'diagnostic'],
        'assumed_capabilities': ['outpatient']
    }
}
```

### Option 2: Web Scraping Enrichment
- Scrape hospital websites for services
- Use Google Maps API for reviews mentioning "emergency", "ICU"

### Option 3: Crowdsourced Updates
- Build provider interface for hospitals to update their own data
- Verify through partnerships with health departments

---

## Part 7: WhatsApp Integration Pattern

```python
# WhatsApp message handler pseudo-code

async def handle_whatsapp_message(message):
    """Process incoming WhatsApp message."""
    
    # Check for location share
    if message.has_location:
        user_location = {
            'lat': message.location.latitude,
            'long': message.location.longitude,
            'confidence': 'high'
        }
    else:
        # Try to extract location from text
        user_location = location_resolver.resolve(message.text)
    
    # If location still unknown, ask for it
    if user_location['confidence'] == 'none':
        return await reply(
            "🏥 Sehat Saathi Emergency\n\n"
            "Please share your location:\n"
            "📍 Tap the + button → Location → Share Live Location\n\n"
            "Or type your area name (e.g., 'Gulistan-e-Jauhar Karachi')"
        )
    
    # Assess emergency from message
    emergency = assess_emergency(message.text)
    
    # Search hospitals
    hospitals = search_hospitals(
        user_lat=user_location['lat'],
        user_long=user_location['long'],
        city=user_location.get('city'),
        emergency_type=emergency.get('emergency_type')
    )
    
    # Format response
    response = format_emergency_response(hospitals, emergency)
    
    return await reply(response)
```

---

## Part 8: Sample Conversation Flows

### Flow 1: Critical Emergency (Urdu/Roman Urdu)

```
User: meri ammi ko chest pain ho rahi hai aur saans bhi nahi aa rahi

Agent: 🚨 EMERGENCY ALERT

Ye CRITICAL emergency hai. Abhi ke liye:
1. Ammi ko bithao, lita nahi
2. Tight kapde dhele karo
3. Ambulance ke liye 1122 dial karo

📍 Aap kahan hain? Location share karein ya area batayein.

User: Defence Phase 5 Karachi

Agent: 🏥 NEAREST HOSPITALS (DHA Phase 5):

1. SOUTH CITY HOSPITAL
   📞 021-111-744-744
   📍 2.1 km door
   🗺️ [Google Maps Link]
   ✅ Cardiac Emergency Available

2. AGA KHAN HOSPITAL (Stadium Road)
   📞 021-111-911-911  
   📍 4.8 km door
   🗺️ [Google Maps Link]
   ✅ Full Cardiac ICU

⏱️ Ambulance ETA: 8-12 minutes
📞 Emergency: 1122

Kya ambulance bulani hai ya apni gaari se ja rahe hain?
```

### Flow 2: Standard Query (English)

```
User: I need a children's hospital near Gulberg Lahore

Agent: 🏥 Children's Hospitals near Gulberg, Lahore:

1. CHILDREN'S HOSPITAL LAHORE
   📞 042-99231651
   📍 3.2 km away
   🗺️ [Google Maps Link]
   
2. SHAUKAT KHANUM MEMORIAL
   📞 042-35905000
   📍 5.1 km away  
   🗺️ [Google Maps Link]

3. HAMEED LATIF HOSPITAL (Pediatric Wing)
   📞 042-35761999
   📍 2.8 km away
   🗺️ [Google Maps Link]

Is this an emergency? I can help prioritize based on urgency.
```

---

## Part 9: Testing & Validation Queries

Use these to test your agent:

```python
test_cases = [
    # Location resolution tests
    {"input": "gulistan e jauhar karachi", "expected_city": "Karachi"},
    {"input": "F-8 Islamabad", "expected_city": "Islamabad"},
    {"input": "near airport lahore", "expected_city": "Lahore"},
    
    # Emergency triage tests
    {"input": "chest pain can't breathe", "expected_severity": "CRITICAL"},
    {"input": "broken leg accident", "expected_severity": "URGENT"},
    {"input": "mild fever cough", "expected_severity": "STANDARD"},
    
    # Hospital search tests
    {"location": (24.9165, 67.1255), "city": "Karachi", "expected_count": ">0"},
    {"location": (31.5150, 74.3514), "city": "Lahore", "capability": "cardiac"},
]
```

---

## Part 10: Recommended Tech Stack

| Component | Recommendation | Reason |
|-----------|---------------|--------|
| Agent Framework | LangGraph or CrewAI | Multi-agent orchestration with tool calling |
| Data Layer | Pandas in-memory | Fast for 8.6k records, no infra needed |
| Geocoding | Google Maps API (paid) or local lookup table | Accuracy for Pakistani addresses |
| Vector Search (optional) | FAISS or Chroma | If adding semantic hospital matching |
| WhatsApp Integration | Twilio or Meta Business API | Production-ready |
| Hosting | AWS Lambda + API Gateway | Serverless, scalable |

---

## Quick Start Checklist

1. ☐ Load CSV into pandas DataFrame
2. ☐ Build location lookup table for Pakistani areas
3. ☐ Implement Haversine distance calculation
4. ☐ Create capability inference from hospital names
5. ☐ Set up tool definitions in your agent framework
6. ☐ Write orchestrator prompt with routing logic
7. ☐ Test with sample emergency scenarios
8. ☐ Integrate WhatsApp (location share handling)
9. ☐ Add provider dashboard for capacity updates
10. ☐ Deploy and monitor

