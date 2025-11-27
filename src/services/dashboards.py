"""
Dashboard Service

Provides dashboard data for:
1. Hospital Manager Dashboard - Resource stats, bookings, alerts
2. Doctor Appointment Dashboard - Schedule, appointments, patients
3. Admin Dashboard - System-wide stats
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from .hospital_resources import get_hospital_resource_service, HospitalResourceService
from .doctor_availability import get_doctor_availability_service, DoctorAvailabilityService
from .a2a_messaging import get_a2a_messaging_service, A2AMessagingService


@dataclass
class DashboardAlert:
    """Alert for dashboards"""
    alert_id: str
    alert_type: str  # critical, warning, info
    title: str
    message: str
    resource_type: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class DashboardService:
    """
    Unified dashboard service for hospital managers and doctors.

    Provides:
    - Real-time stats and metrics
    - Resource utilization
    - Booking/appointment summaries
    - Alerts and notifications
    - Activity logs
    """

    def __init__(self):
        self.resource_service = get_hospital_resource_service()
        self.doctor_service = get_doctor_availability_service()
        self.messaging_service = get_a2a_messaging_service()

        print("Dashboard Service initialized")

    # ==================== Hospital Manager Dashboard ====================

    def get_hospital_dashboard(self, hospital_id: int) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data for hospital manager.

        Includes:
        - Resource summary (beds, blood, equipment)
        - Booking statistics
        - Critical alerts
        - Staff status
        - Recent activity
        """
        # Get base stats from resource service
        stats = self.resource_service.get_dashboard_stats(hospital_id)

        if "error" in stats:
            return stats

        # Generate alerts
        alerts = self._generate_hospital_alerts(stats)

        # Add agent coordination activity
        agent_activity = self._get_agent_activity(hospital_id)

        return {
            **stats,
            "alerts": [asdict(a) if hasattr(a, '__dict__') else a for a in alerts],
            "agent_activity": agent_activity,
            "dashboard_type": "hospital_manager",
            "generated_at": datetime.now().isoformat()
        }

    def _generate_hospital_alerts(self, stats: Dict[str, Any]) -> List[DashboardAlert]:
        """Generate alerts based on resource status"""
        alerts = []

        # Critical resource alerts
        for resource in stats.get("critical_resources", []):
            alert = DashboardAlert(
                alert_id=f"alert-{resource['type']}-{resource['subtype']}",
                alert_type="critical",
                title=f"Low {resource['subtype'].upper()}",
                message=f"Only {resource['available']}/{resource['total']} {resource['subtype']} available",
                resource_type=resource['type']
            )
            alerts.append(alert)

        # High occupancy warning
        occupancy = stats.get("summary", {}).get("bed_occupancy_rate", 0)
        if occupancy > 85:
            alerts.append(DashboardAlert(
                alert_id="alert-high-occupancy",
                alert_type="warning",
                title="High Bed Occupancy",
                message=f"Bed occupancy at {occupancy}%. Consider diverting non-emergency cases.",
                resource_type="bed"
            ))

        # ICU alert
        icu_available = stats.get("summary", {}).get("icu_beds_available", 0)
        if icu_available <= 2:
            alerts.append(DashboardAlert(
                alert_id="alert-icu-critical",
                alert_type="critical",
                title="ICU Nearly Full",
                message=f"Only {icu_available} ICU beds available. Alert other hospitals.",
                resource_type="bed"
            ))

        # Pending bookings alert
        pending = stats.get("bookings", {}).get("pending", 0)
        if pending > 10:
            alerts.append(DashboardAlert(
                alert_id="alert-pending-bookings",
                alert_type="warning",
                title="Pending Bookings",
                message=f"{pending} bookings awaiting confirmation"
            ))

        return alerts

    def _get_agent_activity(self, hospital_id: int) -> List[Dict[str, Any]]:
        """Get recent agent activity for hospital"""
        # Get recent messages from A2A service
        history = self.messaging_service.get_message_history(limit=20)

        # Filter relevant activity
        activity = []
        for msg in history:
            if msg.get("message_type") in ["broadcast", "request", "negotiation"]:
                activity.append({
                    "timestamp": msg.get("timestamp"),
                    "from_agent": msg.get("from_agent_name"),
                    "action": msg.get("action"),
                    "type": msg.get("message_type"),
                    "summary": self._summarize_message(msg)
                })

        return activity[:10]  # Last 10 activities

    def _summarize_message(self, msg: Dict) -> str:
        """Create human-readable summary of message"""
        action = msg.get("action", "")
        from_agent = msg.get("from_agent_name", "Unknown")

        if action == "check_resource_availability":
            payload = msg.get("payload", {})
            return f"Resource query: {payload.get('resource_subtype', 'unknown')}"
        elif action == "emergency_alert":
            return f"Emergency alert from {from_agent}"
        elif action == "booking_created":
            return "New booking created"
        else:
            return f"{action} from {from_agent}"

    def get_hospital_resource_breakdown(self, hospital_id: int) -> Dict[str, Any]:
        """Get detailed resource breakdown for hospital"""
        resources = self.resource_service.get_hospital_resources(hospital_id)

        if not resources or "error" in resources:
            return {"error": "Hospital not found"}

        # Calculate utilization rates
        bed_utilization = {}
        for bed_type, status in resources.get("beds", {}).items():
            total = status.get("total", 0)
            in_use = status.get("in_use", 0)
            bed_utilization[bed_type] = {
                **status,
                "utilization_rate": round((in_use / total * 100), 1) if total > 0 else 0
            }

        return {
            "hospital_id": hospital_id,
            "hospital_name": resources.get("hospital_name"),
            "beds": bed_utilization,
            "blood_bank": resources.get("blood_bank", {}),
            "equipment": resources.get("equipment", {}),
            "staff": resources.get("staff", {}),
            "generated_at": datetime.now().isoformat()
        }

    def get_booking_analytics(self, hospital_id: int, days: int = 7) -> Dict[str, Any]:
        """Get booking analytics for hospital"""
        bookings = self.resource_service.get_hospital_bookings(hospital_id)

        # Group by status
        by_status = {}
        for booking in bookings:
            status = booking.get("status", "unknown")
            if status not in by_status:
                by_status[status] = []
            by_status[status].append(booking)

        # Group by resource type
        by_resource = {}
        for booking in bookings:
            resource = booking.get("resource_type", "unknown")
            if resource not in by_resource:
                by_resource[resource] = 0
            by_resource[resource] += 1

        return {
            "hospital_id": hospital_id,
            "total_bookings": len(bookings),
            "by_status": {k: len(v) for k, v in by_status.items()},
            "by_resource": by_resource,
            "recent_bookings": bookings[-10:],
            "generated_at": datetime.now().isoformat()
        }

    # ==================== Doctor Appointment Dashboard ====================

    def get_doctor_dashboard(self, doctor_id: int, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive dashboard for doctor.

        Includes:
        - Today's appointments
        - Upcoming appointments
        - Patient stats
        - Schedule overview
        """
        dashboard = self.doctor_service.get_doctor_dashboard(doctor_id, date)

        if "error" in dashboard:
            return dashboard

        # Add alerts
        alerts = self._generate_doctor_alerts(dashboard)

        return {
            **dashboard,
            "alerts": [asdict(a) if hasattr(a, '__dict__') else a for a in alerts],
            "dashboard_type": "doctor",
            "generated_at": datetime.now().isoformat()
        }

    def _generate_doctor_alerts(self, dashboard: Dict[str, Any]) -> List[DashboardAlert]:
        """Generate alerts for doctor dashboard"""
        alerts = []

        today = dashboard.get("today", {})

        # Fully booked alert
        if today.get("scheduled", 0) >= dashboard.get("schedule", {}).get("patients_per_day", 20):
            alerts.append(DashboardAlert(
                alert_id="alert-fully-booked",
                alert_type="info",
                title="Fully Booked Today",
                message="All appointment slots are booked for today"
            ))

        # High cancellation rate
        if today.get("cancelled", 0) > 3:
            alerts.append(DashboardAlert(
                alert_id="alert-cancellations",
                alert_type="warning",
                title="Multiple Cancellations",
                message=f"{today.get('cancelled')} appointments cancelled today"
            ))

        return alerts

    def get_doctor_schedule_overview(
        self,
        doctor_id: int,
        start_date: Optional[str] = None,
        weeks: int = 4
    ) -> Dict[str, Any]:
        """Get schedule overview for doctor (calendar view)"""
        schedule = self.doctor_service.get_doctor_schedule_view(doctor_id, start_date, weeks)

        if "error" in schedule:
            return schedule

        # Calculate summary stats
        working_days = sum(1 for d in schedule.get("schedule", {}).values() if d.get("working"))
        total_slots = sum(d.get("total_slots", 0) for d in schedule.get("schedule", {}).values())
        booked_slots = sum(d.get("booked", 0) for d in schedule.get("schedule", {}).values())

        return {
            **schedule,
            "summary": {
                "working_days": working_days,
                "total_slots": total_slots,
                "booked_slots": booked_slots,
                "available_slots": total_slots - booked_slots,
                "utilization_rate": round((booked_slots / total_slots * 100), 1) if total_slots > 0 else 0
            },
            "generated_at": datetime.now().isoformat()
        }

    def get_doctor_patient_list(
        self,
        doctor_id: int,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get patient list for doctor on a specific date"""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        dashboard = self.doctor_service.get_doctor_dashboard(doctor_id, date)

        if "error" in dashboard:
            return dashboard

        appointments = dashboard.get("today", {}).get("appointments", [])

        # Group by status
        waiting = [a for a in appointments if a.get("status") == "scheduled"]
        in_progress = [a for a in appointments if a.get("status") == "in_progress"]
        completed = [a for a in appointments if a.get("status") == "completed"]

        return {
            "doctor_id": doctor_id,
            "date": date,
            "total_patients": len(appointments),
            "waiting": waiting,
            "in_progress": in_progress,
            "completed": completed,
            "generated_at": datetime.now().isoformat()
        }

    # ==================== Admin Dashboard ====================

    def get_admin_dashboard(self, city: Optional[str] = None) -> Dict[str, Any]:
        """
        Get system-wide dashboard for administrators.

        Includes:
        - All hospitals summary
        - System-wide stats
        - A2A messaging stats
        """
        # Get all hospitals summary
        hospitals = self.resource_service.get_all_hospitals_summary(city)

        # Calculate totals
        total_beds = sum(h.get("total_beds", 0) for h in hospitals)
        available_beds = sum(h.get("available_beds", 0) for h in hospitals)
        icu_available = sum(h.get("icu_available", 0) for h in hospitals)
        ventilators = sum(h.get("ventilators_available", 0) for h in hospitals)

        # Hospitals with critical shortages
        critical_hospitals = [h for h in hospitals if h.get("has_critical_shortage")]

        # Get messaging stats
        messaging_stats = self.messaging_service.get_stats()

        # Get doctor stats
        doctors = self.doctor_service.doctors
        specializations = self.doctor_service.get_specializations()
        cities = self.doctor_service.get_cities()

        return {
            "dashboard_type": "admin",
            "city_filter": city,
            "hospitals": {
                "total": len(hospitals),
                "with_critical_shortage": len(critical_hospitals),
                "summary": hospitals[:20]  # Top 20 hospitals
            },
            "resources": {
                "total_beds": total_beds,
                "available_beds": available_beds,
                "bed_occupancy_rate": round(((total_beds - available_beds) / total_beds * 100), 1) if total_beds > 0 else 0,
                "icu_available": icu_available,
                "ventilators_available": ventilators
            },
            "doctors": {
                "total": len(doctors),
                "specializations": len(specializations),
                "cities": len(cities)
            },
            "messaging": messaging_stats,
            "critical_hospitals": critical_hospitals[:5],
            "generated_at": datetime.now().isoformat()
        }

    # ==================== Search and Query ====================

    def search_resources_across_hospitals(
        self,
        resource_type: str,
        resource_subtype: str,
        city: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search for resources across all hospitals"""
        results = self.resource_service.search_available_resources(
            resource_type=resource_type,
            resource_subtype=resource_subtype,
            city=city
        )

        return {
            "search": {
                "resource_type": resource_type,
                "resource_subtype": resource_subtype,
                "city": city
            },
            "results": results,
            "total_found": len(results),
            "generated_at": datetime.now().isoformat()
        }

    def search_doctors(
        self,
        specialization: Optional[str] = None,
        city: Optional[str] = None,
        day: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search for doctors"""
        results = self.doctor_service.search_doctors(
            specialization=specialization,
            city=city,
            day=day,
            limit=20
        )

        return {
            "search": {
                "specialization": specialization,
                "city": city,
                "day": day
            },
            "results": results,
            "total_found": len(results),
            "generated_at": datetime.now().isoformat()
        }


# Global instance
_dashboard_service: Optional[DashboardService] = None


def get_dashboard_service() -> DashboardService:
    """Get or create the dashboard service instance"""
    global _dashboard_service
    if _dashboard_service is None:
        _dashboard_service = DashboardService()
    return _dashboard_service
