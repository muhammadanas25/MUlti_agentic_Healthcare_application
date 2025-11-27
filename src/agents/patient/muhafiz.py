"""Muhafiz - Community Health Monitoring Agent"""
from typing import Dict, Any, List, Optional
from ...core.agent import Agent, AgentMessage, AgentResponse
from datetime import datetime, timedelta


class MuhafizAgent(Agent):
    """
    Muhafiz - Community Health Monitoring & Public Health Agent

    Responsibilities:
    - Monitor disease outbreaks in communities
    - Track health trends and patterns
    - Alert communities about health risks
    - Coordinate with public health authorities
    - Organize health awareness campaigns
    - Support Lady Health Workers (LHWs)
    - Facilitate community health initiatives
    """

    def __init__(self):
        super().__init__(
            agent_id="agent-006-muhafiz",
            name="Muhafiz",
            role="community",
            organization="sehat-saathi-patient-side",
            system_prompt="""You are Muhafiz, a community health monitoring specialist for Sehat Saathi.

Your mission is to protect community health through surveillance, awareness, and coordination.

KEY RESPONSIBILITIES:
1. Monitor disease outbreaks (dengue, malaria, COVID, etc.)
2. Detect health trends in communities
3. Alert communities about health risks
4. Coordinate with District Health Officers
5. Organize awareness campaigns
6. Support Lady Health Workers (LHWs)
7. Facilitate community health initiatives

COMMUNITY HEALTH CHALLENGES IN PAKISTAN:
- Outbreak-prone diseases (dengue, malaria, typhoid, hepatitis)
- Seasonal disease patterns (dengue in monsoon, flu in winter)
- Water-borne diseases
- Vector-borne diseases (mosquitoes)
- Vaccine hesitancy in some areas
- Limited health literacy
- Sanitation issues

PUBLIC HEALTH SYSTEM:
- District Health Officers (DHOs)
- Lady Health Workers (LHWs) - frontline workers
- Basic Health Units (BHUs)
- Rural Health Centers (RHCs)
- Disease surveillance systems

YOUR APPROACH:
1. Aggregate anonymized health data from patients
2. Detect patterns and clusters of disease
3. Alert appropriate authorities when thresholds exceeded
4. Broadcast health warnings to communities
5. Provide prevention advice
6. Coordinate with LHWs for ground-level action
7. Track effectiveness of interventions

OUTBREAK DETECTION THRESHOLDS:
- Dengue: 3+ cases in same area within 7 days → alert
- Food poisoning: 5+ cases from same source → immediate alert
- Measles: 1 case → alert (vaccine-preventable)
- COVID/Flu: 10+ cases in area → alert

PRIVACY & ETHICS:
- Always anonymize patient data
- Report aggregate statistics, not individual cases
- Balance public health benefit with privacy
- Get appropriate consent
- Follow public health laws

COMMUNICATION STYLE:
- Clear, authoritative but not alarming
- Provide actionable prevention advice
- Use simple language everyone can understand
- Culturally appropriate messaging
- Engage community leaders and influencers
""",
            tools=["disease_surveillance", "outbreak_detection", "community_alerts", "health_campaigns"],
        )

        # Community health data (in-memory, would be in database in production)
        self.disease_reports: List[Dict[str, Any]] = []
        self.outbreaks: List[Dict[str, Any]] = []

        # Register message handlers
        self.register_message_handler("report_disease", self.handle_disease_report)
        self.register_message_handler("check_outbreak", self.handle_check_outbreak)

    def report_disease_case(
        self,
        disease: str,
        location: str,
        severity: str,
        patient_id: str,  # Will be anonymized
        timestamp: Optional[datetime] = None
    ) -> AgentResponse:
        """
        Report disease case for surveillance

        Args:
            disease: Disease name
            location: Patient location (area/neighborhood)
            severity: low/moderate/high/critical
            patient_id: Patient ID (will be anonymized)
            timestamp: When case occurred

        Returns:
            AgentResponse with surveillance status
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Anonymize patient ID
        anonymous_id = f"ANON-{hash(patient_id) % 100000:05d}"

        # Store report
        report = {
            "disease": disease,
            "location": location,
            "severity": severity,
            "anonymous_id": anonymous_id,
            "timestamp": timestamp.isoformat(),
            "reported_at": datetime.now().isoformat()
        }
        self.disease_reports.append(report)

        # Check for outbreak
        outbreak_detected = self._check_for_outbreak(disease, location)

        prompt = f"""Disease case reported:

DISEASE: {disease}
LOCATION: {location}
SEVERITY: {severity}

Recent cases of {disease} in {location}: {self._count_recent_cases(disease, location, days=7)}
Cases in last 24 hours: {self._count_recent_cases(disease, location, days=1)}

OUTBREAK DETECTED: {outbreak_detected}

Analyze and provide response in JSON format:
{{
    "case_logged": true,
    "outbreak_risk": "low/medium/high",
    "outbreak_detected": {outbreak_detected},
    "recent_cases_in_area": "number",
    "trend": "increasing/stable/decreasing",
    "action_required": [
        "action 1",
        "action 2"
    ],
    "alert_community": true/false,
    "alert_authorities": true/false,
    "prevention_message": "message for community"
}}
"""

        response = self.reason(
            prompt,
            context={
                "disease": disease,
                "location": location,
                "recent_reports": self._get_recent_reports(disease, location, days=7)
            }
        )

        # If outbreak detected, create outbreak record
        if outbreak_detected and response.data.get("outbreak_detected"):
            self._create_outbreak_record(disease, location, response.data)

        return response

    def _count_recent_cases(self, disease: str, location: str, days: int) -> int:
        """Count recent cases of disease in location"""
        cutoff = datetime.now() - timedelta(days=days)
        count = 0

        for report in self.disease_reports:
            report_time = datetime.fromisoformat(report["timestamp"])
            if (report["disease"].lower() == disease.lower() and
                location.lower() in report["location"].lower() and
                report_time >= cutoff):
                count += 1

        return count

    def _get_recent_reports(self, disease: str, location: str, days: int) -> List[Dict]:
        """Get recent reports for disease in location"""
        cutoff = datetime.now() - timedelta(days=days)
        reports = []

        for report in self.disease_reports:
            report_time = datetime.fromisoformat(report["timestamp"])
            if (report["disease"].lower() == disease.lower() and
                location.lower() in report["location"].lower() and
                report_time >= cutoff):
                reports.append(report)

        return reports

    def _check_for_outbreak(self, disease: str, location: str) -> bool:
        """Check if outbreak threshold exceeded"""
        # Simple outbreak detection logic
        cases_7days = self._count_recent_cases(disease, location, days=7)
        cases_24hrs = self._count_recent_cases(disease, location, days=1)

        # Outbreak thresholds
        thresholds = {
            "dengue": 3,
            "malaria": 3,
            "typhoid": 5,
            "hepatitis": 2,
            "covid": 10,
            "measles": 1,
            "food poisoning": 5,
        }

        threshold = thresholds.get(disease.lower(), 5)

        return cases_7days >= threshold or cases_24hrs >= (threshold // 2)

    def _create_outbreak_record(self, disease: str, location: str, analysis: Dict):
        """Create outbreak record"""
        outbreak = {
            "outbreak_id": f"OUT-{len(self.outbreaks) + 1:04d}",
            "disease": disease,
            "location": location,
            "detected_at": datetime.now().isoformat(),
            "case_count": self._count_recent_cases(disease, location, days=7),
            "status": "active",
            "analysis": analysis
        }
        self.outbreaks.append(outbreak)

        print(f"🚨 Muhafiz: OUTBREAK DETECTED - {disease} in {location} ({outbreak['case_count']} cases)")

    def generate_community_alert(
        self,
        disease: str,
        location: str,
        severity: str,
        case_count: int
    ) -> AgentResponse:
        """
        Generate community health alert

        Args:
            disease: Disease causing outbreak
            location: Affected area
            severity: Severity level
            case_count: Number of cases

        Returns:
            AgentResponse with alert message
        """
        prompt = f"""Generate community health alert:

DISEASE: {disease}
LOCATION: {location}
SEVERITY: {severity}
CASES: {case_count}

Create alert message in JSON format:
{{
    "alert_level": "low/medium/high/critical",
    "headline": {{
        "urdu": "headline in Urdu",
        "english": "headline in English"
    }},
    "message": {{
        "urdu": "detailed message in Urdu",
        "english": "detailed message in English"
    }},
    "prevention_tips": [
        "tip 1 - how to prevent",
        "tip 2",
        "tip 3"
    ],
    "symptoms_to_watch": ["symptom 1", "symptom 2"],
    "when_to_seek_care": "when to go to hospital",
    "what_community_should_do": [
        "action 1",
        "action 2"
    ],
    "contact_info": {{
        "health_department": "phone number",
        "nearest_hospital": "hospital name and phone"
    }},
    "dissemination_channels": ["WhatsApp", "SMS", "Community leaders", "Mosques/Churches", "Schools"]
}}

Make message clear but not panic-inducing. Provide actionable prevention steps.
Use culturally appropriate language and channels.
"""

        response = self.reason(
            prompt,
            context={
                "disease": disease,
                "location": location,
                "severity": severity,
                "cases": case_count
            }
        )

        return response

    def coordinate_with_lhws(
        self,
        outbreak_id: str,
        affected_areas: List[str],
        required_actions: List[str]
    ) -> AgentResponse:
        """
        Coordinate with Lady Health Workers for ground-level response

        Args:
            outbreak_id: Outbreak identifier
            affected_areas: List of affected areas
            required_actions: Actions LHWs should take

        Returns:
            AgentResponse with coordination plan
        """
        prompt = f"""Coordinate with Lady Health Workers (LHWs):

OUTBREAK: {outbreak_id}
AFFECTED AREAS: {', '.join(affected_areas)}
REQUIRED ACTIONS: {', '.join(required_actions)}

LHWs are community health workers who:
- Cover 1000 households each
- Provide basic health education
- Conduct door-to-door surveys
- Vaccinate children
- Detect disease cases early
- Link communities to health facilities

Create coordination plan in JSON format:
{{
    "priority_areas": ["area 1", "area 2"],
    "lhw_tasks": [
        {{
            "task": "task description",
            "area": "which area",
            "priority": "high/medium/low",
            "estimated_time": "days",
            "resources_needed": ["resource 1", "resource 2"]
        }}
    ],
    "door_to_door_survey": {{
        "questions_to_ask": ["question 1", "question 2"],
        "screening_criteria": "who to refer to hospital",
        "education_message": "message for households"
    }},
    "reporting_requirements": {{
        "frequency": "daily/weekly",
        "report_format": "what to report",
        "escalation_criteria": "when to escalate"
    }},
    "support_needed": ["training", "supplies", "transport"],
    "coordination_message": "message for LHWs with clear instructions"
}}
"""

        response = self.reason(
            prompt,
            context={
                "outbreak": outbreak_id,
                "areas": affected_areas,
                "actions": required_actions
            }
        )

        return response

    def analyze_health_trends(
        self,
        location: str,
        time_period_days: int = 30
    ) -> AgentResponse:
        """
        Analyze health trends in a location

        Args:
            location: Location to analyze
            time_period_days: Time period for analysis

        Returns:
            AgentResponse with trend analysis
        """
        # Aggregate data
        cutoff = datetime.now() - timedelta(days=time_period_days)
        location_reports = [
            r for r in self.disease_reports
            if location.lower() in r["location"].lower() and
            datetime.fromisoformat(r["timestamp"]) >= cutoff
        ]

        # Count by disease
        disease_counts = {}
        for report in location_reports:
            disease = report["disease"]
            disease_counts[disease] = disease_counts.get(disease, 0) + 1

        prompt = f"""Analyze health trends for {location} over last {time_period_days} days:

TOTAL CASES: {len(location_reports)}

CASES BY DISEASE:
{chr(10).join(f"- {disease}: {count} cases" for disease, count in disease_counts.items())}

Analyze trends in JSON format:
{{
    "total_cases": {len(location_reports)},
    "top_diseases": [
        {{
            "disease": "disease name",
            "case_count": "number",
            "trend": "increasing/stable/decreasing",
            "concern_level": "low/medium/high"
        }}
    ],
    "seasonal_patterns": "any seasonal patterns observed",
    "risk_assessment": "overall health risk level for area",
    "recommendations": [
        "recommendation 1",
        "recommendation 2"
    ],
    "interventions_suggested": [
        "intervention 1",
        "intervention 2"
    ],
    "community_message": "health status summary for community"
}}
"""

        response = self.reason(
            prompt,
            context={
                "location": location,
                "reports": location_reports,
                "disease_counts": disease_counts,
                "time_period": time_period_days
            }
        )

        return response

    def organize_health_campaign(
        self,
        campaign_type: str,
        target_locations: List[str],
        target_population: str
    ) -> AgentResponse:
        """
        Organize community health awareness campaign

        Args:
            campaign_type: Type of campaign (vaccination, dengue prevention, etc.)
            target_locations: Where to conduct campaign
            target_population: Who to target

        Returns:
            AgentResponse with campaign plan
        """
        prompt = f"""Organize health awareness campaign:

CAMPAIGN TYPE: {campaign_type}
LOCATIONS: {', '.join(target_locations)}
TARGET POPULATION: {target_population}

Create campaign plan in JSON format:
{{
    "campaign_name": "catchy name in Urdu/English",
    "objectives": ["objective 1", "objective 2"],
    "key_messages": [
        {{
            "message": "key message",
            "target": "who it's for",
            "channel": "how to deliver"
        }}
    ],
    "activities": [
        {{
            "activity": "activity name",
            "location": "where",
            "date": "when",
            "resources_needed": ["resource 1", "resource 2"],
            "responsible": "who will lead"
        }}
    ],
    "materials_needed": [
        "posters in Urdu",
        "pamphlets",
        "audio announcements for mosques"
    ],
    "partnerships": [
        "local government",
        "religious leaders",
        "schools",
        "community organizations"
    ],
    "success_metrics": ["how to measure success"],
    "budget_estimate": "rough cost",
    "implementation_timeline": "timeline"
}}
"""

        response = self.reason(
            prompt,
            context={
                "campaign": campaign_type,
                "locations": target_locations,
                "population": target_population
            }
        )

        return response

    def handle_disease_report(self, message: AgentMessage) -> AgentResponse:
        """Handle disease case report"""
        return self.report_disease_case(
            disease=message.payload.get("disease"),
            location=message.payload.get("location"),
            severity=message.payload.get("severity", "moderate"),
            patient_id=message.payload.get("patient_id"),
        )

    def handle_check_outbreak(self, message: AgentMessage) -> AgentResponse:
        """Handle outbreak check request"""
        disease = message.payload.get("disease")
        location = message.payload.get("location")

        outbreak_detected = self._check_for_outbreak(disease, location)
        case_count = self._count_recent_cases(disease, location, days=7)

        return AgentResponse(
            success=True,
            data={
                "outbreak_detected": outbreak_detected,
                "case_count": case_count,
                "location": location,
                "disease": disease
            },
            reasoning=f"{'Outbreak detected' if outbreak_detected else 'No outbreak'} - {case_count} cases in last 7 days",
            confidence=0.9
        )
