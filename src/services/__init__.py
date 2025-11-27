"""Sehat Saathi Services"""
from .hospital_resources import HospitalResourceService, get_hospital_resource_service
from .doctor_availability import DoctorAvailabilityService, get_doctor_availability_service
from .a2a_messaging import A2AMessagingService, get_a2a_messaging_service
from .dashboards import DashboardService, get_dashboard_service

__all__ = [
    "HospitalResourceService",
    "get_hospital_resource_service",
    "DoctorAvailabilityService",
    "get_doctor_availability_service",
    "A2AMessagingService",
    "get_a2a_messaging_service",
    "DashboardService",
    "get_dashboard_service",
]
