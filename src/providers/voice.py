"""
Abstract Voice Provider Interface

Base interfaces for Text-to-Speech (TTS) and Speech-to-Text (STT) providers.
Follows Open/Closed Principle - extend for new providers without modifying existing code.

Supported providers can include:
- Uplift AI (implemented)
- ElevenLabs
- AWS Polly
- Google Cloud TTS
- Azure Cognitive Services
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, AsyncIterator, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class AudioFormat(Enum):
    """Supported audio output formats"""
    MP3_22050_64 = "MP3_22050_64"    # Optimized for WhatsApp (smaller)
    MP3_22050_128 = "MP3_22050_128"  # Better quality
    MP3_44100_128 = "MP3_44100_128"  # High quality
    WAV_22050 = "WAV_22050"
    OGG_OPUS = "OGG_OPUS"


class VoiceLanguage(Enum):
    """Supported languages"""
    URDU = "ur"
    ENGLISH = "en"
    PUNJABI = "pa"
    SINDHI = "sd"
    PASHTO = "ps"
    ARABIC = "ar"


@dataclass
class VoiceConfig:
    """Configuration for voice synthesis"""
    voice_id: str
    language: VoiceLanguage = VoiceLanguage.URDU
    output_format: AudioFormat = AudioFormat.MP3_22050_64
    speaking_rate: float = 1.0  # 0.5 to 2.0
    pitch: float = 0.0          # -10 to 10
    volume_gain_db: float = 0.0  # -6 to 6


@dataclass
class SynthesisResult:
    """Result of text-to-speech synthesis"""
    success: bool
    audio_data: Optional[bytes] = None
    audio_url: Optional[str] = None
    duration_ms: Optional[int] = None
    format: AudioFormat = AudioFormat.MP3_22050_64
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class TranscriptionResult:
    """Result of speech-to-text transcription"""
    success: bool
    text: Optional[str] = None
    language: Optional[VoiceLanguage] = None
    confidence: float = 0.0
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTTSProvider(ABC):
    """
    Abstract base class for Text-to-Speech providers.

    To add a new TTS provider:
    1. Create a new class inheriting from BaseTTSProvider
    2. Implement all abstract methods
    3. Register in VoiceProviderFactory

    Example:
        class ElevenLabsTTS(BaseTTSProvider):
            def synthesize(self, text, config):
                # Implementation
                pass
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier"""
        pass

    @property
    @abstractmethod
    def supported_languages(self) -> list[VoiceLanguage]:
        """Return list of supported languages"""
        pass

    @abstractmethod
    def get_available_voices(self, language: Optional[VoiceLanguage] = None) -> list[Dict[str, Any]]:
        """
        Get available voices for the provider.

        Args:
            language: Filter by language (optional)

        Returns:
            List of voice dictionaries with id, name, language, gender
        """
        pass

    @abstractmethod
    def synthesize(self, text: str, config: VoiceConfig) -> SynthesisResult:
        """
        Synchronous text-to-speech synthesis.

        Args:
            text: Text to convert to speech
            config: Voice configuration

        Returns:
            SynthesisResult with audio data or URL
        """
        pass

    @abstractmethod
    async def synthesize_async(self, text: str, config: VoiceConfig) -> SynthesisResult:
        """
        Asynchronous text-to-speech synthesis.

        Args:
            text: Text to convert to speech
            config: Voice configuration

        Returns:
            SynthesisResult with audio data or URL
        """
        pass

    @abstractmethod
    async def synthesize_stream(self, text: str, config: VoiceConfig) -> AsyncIterator[bytes]:
        """
        Stream audio chunks as they're generated.

        Args:
            text: Text to convert to speech
            config: Voice configuration

        Yields:
            Audio data chunks
        """
        pass

    def validate_text(self, text: str, max_length: int = 5000) -> tuple[bool, Optional[str]]:
        """
        Validate text before synthesis.

        Args:
            text: Text to validate
            max_length: Maximum allowed length

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not text or not text.strip():
            return False, "Text cannot be empty"

        if len(text) > max_length:
            return False, f"Text exceeds maximum length of {max_length} characters"

        return True, None


class BaseSTTProvider(ABC):
    """
    Abstract base class for Speech-to-Text providers.

    To add a new STT provider:
    1. Create a new class inheriting from BaseSTTProvider
    2. Implement all abstract methods
    3. Register in VoiceProviderFactory
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier"""
        pass

    @property
    @abstractmethod
    def supported_languages(self) -> list[VoiceLanguage]:
        """Return list of supported languages"""
        pass

    @abstractmethod
    def transcribe(
        self,
        audio_data: Union[bytes, str],
        language: Optional[VoiceLanguage] = None
    ) -> TranscriptionResult:
        """
        Synchronous speech-to-text transcription.

        Args:
            audio_data: Audio bytes or file path
            language: Expected language (optional, for better accuracy)

        Returns:
            TranscriptionResult with transcribed text
        """
        pass

    @abstractmethod
    async def transcribe_async(
        self,
        audio_data: Union[bytes, str],
        language: Optional[VoiceLanguage] = None
    ) -> TranscriptionResult:
        """
        Asynchronous speech-to-text transcription.

        Args:
            audio_data: Audio bytes or file path
            language: Expected language (optional)

        Returns:
            TranscriptionResult with transcribed text
        """
        pass


class VoiceProviderFactory:
    """
    Factory for creating voice provider instances.

    Usage:
        factory = VoiceProviderFactory()
        factory.register_tts("uplift", UpliftTTS)
        tts = factory.get_tts("uplift", api_key="...")
    """

    _tts_providers: Dict[str, type[BaseTTSProvider]] = {}
    _stt_providers: Dict[str, type[BaseSTTProvider]] = {}

    @classmethod
    def register_tts(cls, name: str, provider_class: type[BaseTTSProvider]):
        """Register a TTS provider class"""
        cls._tts_providers[name.lower()] = provider_class

    @classmethod
    def register_stt(cls, name: str, provider_class: type[BaseSTTProvider]):
        """Register an STT provider class"""
        cls._stt_providers[name.lower()] = provider_class

    @classmethod
    def get_tts(cls, name: str, **kwargs) -> BaseTTSProvider:
        """
        Get a TTS provider instance.

        Args:
            name: Provider name (e.g., "uplift", "elevenlabs")
            **kwargs: Provider-specific configuration

        Returns:
            Configured TTS provider instance

        Raises:
            ValueError: If provider not found
        """
        provider_class = cls._tts_providers.get(name.lower())
        if not provider_class:
            available = list(cls._tts_providers.keys())
            raise ValueError(f"TTS provider '{name}' not found. Available: {available}")
        return provider_class(**kwargs)

    @classmethod
    def get_stt(cls, name: str, **kwargs) -> BaseSTTProvider:
        """
        Get an STT provider instance.

        Args:
            name: Provider name
            **kwargs: Provider-specific configuration

        Returns:
            Configured STT provider instance

        Raises:
            ValueError: If provider not found
        """
        provider_class = cls._stt_providers.get(name.lower())
        if not provider_class:
            available = list(cls._stt_providers.keys())
            raise ValueError(f"STT provider '{name}' not found. Available: {available}")
        return provider_class(**kwargs)

    @classmethod
    def list_tts_providers(cls) -> list[str]:
        """List registered TTS providers"""
        return list(cls._tts_providers.keys())

    @classmethod
    def list_stt_providers(cls) -> list[str]:
        """List registered STT providers"""
        return list(cls._stt_providers.keys())
