"""Provider APIs - Mock implementations that can be swapped with real APIs"""
from .mock_hms import MockHospitalManagementSystem
from .mock_pharmacy import MockPharmacySystem
from .mock_insurance import MockInsuranceSystem

# Voice providers
from .voice import (
    BaseTTSProvider,
    BaseSTTProvider,
    VoiceProviderFactory,
    VoiceConfig,
    AudioFormat,
    VoiceLanguage,
    SynthesisResult,
    TranscriptionResult
)
from .uplift_tts import UpliftTTS

__all__ = [
    # Mock providers
    "MockHospitalManagementSystem",
    "MockPharmacySystem",
    "MockInsuranceSystem",
    # Voice providers
    "BaseTTSProvider",
    "BaseSTTProvider",
    "VoiceProviderFactory",
    "VoiceConfig",
    "AudioFormat",
    "VoiceLanguage",
    "SynthesisResult",
    "TranscriptionResult",
    "UpliftTTS",
]
