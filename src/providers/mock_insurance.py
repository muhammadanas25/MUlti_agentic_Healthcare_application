"""
Mock Insurance/Sehat Sahulat API

Simulates Pakistan's Sehat Sahulat Program API.
Replace with actual NADRA/Sehat Sahulat API when available.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import hashlib
from .base import BaseInsuranceAPI


class MockInsuranceSystem(BaseInsuranceAPI):
    """
    Mock Sehat Sahulat Insurance System.

    Simulates:
    - CNIC-based eligibility verification
    - Coverage checking
    - Pre-authorization
    """

    # Covered treatments under Sehat Sahulat
    COVERED_TREATMENTS = {
        "hospitalization": {"coverage": 100, "max_amount": 1000000},
        "surgery": {"coverage": 100, "max_amount": 1000000},
        "cardiac_procedure": {"coverage": 100, "max_amount": 1000000},
        "cancer_treatment": {"coverage": 100, "max_amount": 1000000},
        "dialysis": {"coverage": 100, "max_amount": 500000},
        "maternity": {"coverage": 100, "max_amount": 300000},
        "icu_care": {"coverage": 100, "max_amount": 500000},
        "diagnostic_tests": {"coverage": 80, "max_amount": 50000},
        "emergency_care": {"coverage": 100, "max_amount": 200000},
    }

    # NOT covered
    NOT_COVERED = ["outpatient", "dental", "cosmetic", "experimental", "routine_checkup"]

    def __init__(self):
        self._authorizations: Dict[str, Dict] = {}
        self._used_coverage: Dict[str, float] = {}  # CNIC -> used amount

    def _get_seed(self, key: str) -> int:
        """Generate deterministic seed"""
        return int(hashlib.md5(key.encode()).hexdigest()[:8], 16)

    def verify_eligibility(self, cnic: str) -> Dict[str, Any]:
        """
        Verify patient's Sehat Sahulat eligibility.

        In production: GET /api/v1/sehat-sahulat/verify?cnic={cnic}
        """
        # Validate CNIC format (XXXXX-XXXXXXX-X)
        clean_cnic = cnic.replace("-", "")
        if len(clean_cnic) != 13:
            return {
                "verified": False,
                "error": "INVALID_CNIC_FORMAT",
                "message": "CNIC must be 13 digits"
            }

        seed = self._get_seed(cnic)

        # 70% of population eligible (based on poverty score)
        is_eligible = (seed % 10) < 7

        if not is_eligible:
            return {
                "verified": True,
                "eligible": False,
                "cnic": cnic,
                "reason": "POVERTY_SCORE_ABOVE_THRESHOLD",
                "message": "Not eligible for Sehat Sahulat based on poverty score",
                "alternative_options": [
                    "Government hospital (free/subsidized)",
                    "Zakat funds",
                    "NGO assistance programs"
                ]
            }

        # Generate card details
        card_number = f"SS-{clean_cnic[:5]}-{seed % 10000:04d}"
        family_size = 2 + (seed % 6)  # 2-7 family members

        # Calculate remaining coverage
        total_coverage = 1000000  # Rs. 10 lakh per family
        used = self._used_coverage.get(cnic, 0)
        remaining = total_coverage - used

        # Expiry (1 year from "issuance")
        issue_date = datetime(2024, 1, 1) + timedelta(days=seed % 365)
        expiry_date = issue_date + timedelta(days=365)

        return {
            "verified": True,
            "eligible": True,
            "cnic": cnic,
            "card_number": card_number,
            "card_status": "active" if expiry_date > datetime.now() else "expired",
            "family_head": f"Family Head ({cnic[:5]}***)",
            "family_members_covered": family_size,
            "coverage": {
                "total_limit": total_coverage,
                "used": used,
                "remaining": remaining,
                "period": "annual",
                "renewal_date": expiry_date.strftime("%Y-%m-%d")
            },
            "empaneled_hospitals": 500 + (seed % 200),  # Number of hospitals
            "issue_date": issue_date.strftime("%Y-%m-%d"),
            "expiry_date": expiry_date.strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat()
        }

    def check_coverage(self, cnic: str, treatment_code: str) -> Dict[str, Any]:
        """
        Check if specific treatment is covered.

        In production: GET /api/v1/sehat-sahulat/coverage?cnic={cnic}&treatment={code}
        """
        # First verify eligibility
        eligibility = self.verify_eligibility(cnic)

        if not eligibility.get("eligible"):
            return {
                "covered": False,
                "reason": "NOT_ELIGIBLE",
                "eligibility": eligibility
            }

        # Check if treatment is covered
        treatment_lower = treatment_code.lower().replace(" ", "_")

        if treatment_lower in self.NOT_COVERED:
            return {
                "covered": False,
                "treatment": treatment_code,
                "reason": "TREATMENT_NOT_COVERED",
                "message": f"{treatment_code} is not covered under Sehat Sahulat",
                "covered_alternatives": list(self.COVERED_TREATMENTS.keys())
            }

        # Find matching coverage
        coverage_info = None
        for key, value in self.COVERED_TREATMENTS.items():
            if key in treatment_lower or treatment_lower in key:
                coverage_info = value
                break

        if not coverage_info:
            # Default to hospitalization if treatment type unclear
            coverage_info = self.COVERED_TREATMENTS["hospitalization"]

        remaining = eligibility["coverage"]["remaining"]
        max_for_treatment = min(coverage_info["max_amount"], remaining)

        return {
            "covered": True,
            "treatment": treatment_code,
            "coverage_percentage": coverage_info["coverage"],
            "max_coverage_amount": max_for_treatment,
            "patient_copay_percentage": 100 - coverage_info["coverage"],
            "remaining_annual_limit": remaining,
            "requires_pre_authorization": coverage_info["max_amount"] > 100000,
            "eligibility": eligibility
        }

    def pre_authorize(self, cnic: str, treatment_code: str, estimated_cost: float) -> Dict[str, Any]:
        """
        Pre-authorize treatment.

        In production: POST /api/v1/sehat-sahulat/pre-authorize
        """
        # Check coverage first
        coverage = self.check_coverage(cnic, treatment_code)

        if not coverage.get("covered"):
            return {
                "authorized": False,
                "reason": coverage.get("reason", "NOT_COVERED"),
                "message": coverage.get("message", "Treatment not covered"),
                "coverage_check": coverage
            }

        max_coverage = coverage["max_coverage_amount"]
        coverage_pct = coverage["coverage_percentage"]

        # Calculate amounts
        covered_amount = min(estimated_cost * (coverage_pct / 100), max_coverage)
        patient_pays = estimated_cost - covered_amount

        # Generate authorization
        auth_id = f"AUTH-{hashlib.md5(f'{cnic}{treatment_code}{datetime.now()}'.encode()).hexdigest()[:8].upper()}"

        authorization = {
            "authorization_id": auth_id,
            "cnic": cnic,
            "treatment": treatment_code,
            "estimated_cost": estimated_cost,
            "covered_amount": round(covered_amount, 2),
            "patient_responsibility": round(patient_pays, 2),
            "status": "approved",
            "valid_from": datetime.now().isoformat(),
            "valid_until": (datetime.now() + timedelta(days=30)).isoformat(),
            "conditions": [
                "Treatment must be at empaneled hospital",
                "Pre-authorization valid for 30 days",
                "Actual coverage based on final bill"
            ]
        }

        self._authorizations[auth_id] = authorization

        return {
            "authorized": True,
            "authorization": authorization,
            "message": f"Treatment pre-authorized. Patient pays Rs. {patient_pays:,.0f}"
        }

    def get_empaneled_hospitals(self, city: str) -> Dict[str, Any]:
        """
        Get list of empaneled hospitals in a city.

        In production: GET /api/v1/sehat-sahulat/hospitals?city={city}
        """
        seed = self._get_seed(city)
        num_hospitals = 20 + (seed % 80)  # 20-100 hospitals per city

        return {
            "city": city,
            "total_empaneled": num_hospitals,
            "includes_government": True,
            "includes_private": True,
            "message": f"{num_hospitals} hospitals accept Sehat Sahulat in {city}",
            "verification_helpline": "0800-00786"
        }


# Global instance
_mock_insurance: Optional[MockInsuranceSystem] = None


def get_insurance_system() -> MockInsuranceSystem:
    """Get or create insurance system instance"""
    global _mock_insurance
    if _mock_insurance is None:
        _mock_insurance = MockInsuranceSystem()
    return _mock_insurance
