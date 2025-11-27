"""
Voice Interface for Sehat Saathi

Orchestrates voice message generation and delivery.
Provides a unified interface for converting agent responses to voice
and handling incoming voice messages.

This interface is:
- Platform-agnostic (works with WhatsApp, Telegram, Web, etc.)
- Provider-agnostic (can use Uplift AI, ElevenLabs, etc.)
- Agent-agnostic (receives text, outputs voice)
"""
import os
import asyncio
import tempfile
from typing import Dict, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum

from ..providers.voice import (
    BaseTTSProvider,
    BaseSTTProvider,
    VoiceConfig,
    VoiceProviderFactory,
    AudioFormat,
    VoiceLanguage,
    SynthesisResult,
    TranscriptionResult
)
# Re-export VoiceLanguage for convenience
__all__ = ["VoiceInterface", "get_voice_interface", "ResponseMode", "VoiceMessage", "VoiceLanguage"]


class ResponseMode(Enum):
    """How voice responses should be delivered"""
    TEXT_ONLY = "text_only"           # Text response only
    VOICE_ONLY = "voice_only"         # Voice response only
    TEXT_AND_VOICE = "text_and_voice"  # Both text and voice


@dataclass
class VoiceMessage:
    """Represents a voice message to be sent"""
    text: str
    audio_data: Optional[bytes] = None
    audio_url: Optional[str] = None
    audio_path: Optional[str] = None
    duration_ms: Optional[int] = None
    format: AudioFormat = AudioFormat.MP3_22050_64
    language: VoiceLanguage = VoiceLanguage.URDU
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserPreferences:
    """User's voice interaction preferences"""
    response_mode: ResponseMode = ResponseMode.TEXT_AND_VOICE
    preferred_language: VoiceLanguage = VoiceLanguage.URDU
    voice_id: Optional[str] = None
    speaking_rate: float = 1.0


class VoiceInterface:
    """
    Voice interface for Sehat Saathi.

    Handles:
    - Converting text responses to voice (TTS)
    - Transcribing voice messages to text (STT)
    - Managing user voice preferences
    - Caching generated audio

    The interface is designed to work alongside existing text interfaces,
    not replace them. Agents continue to produce text responses, and this
    interface converts them to voice when needed.
    """

    # Default voice IDs for different languages
    DEFAULT_VOICES = {
        VoiceLanguage.URDU: "v_8eelc901",
        VoiceLanguage.ENGLISH: "v_en_pk_m1",
        VoiceLanguage.PUNJABI: "v_8eelc901",  # Fallback to Urdu
    }

    def __init__(
        self,
        tts_provider: str = "uplift",
        stt_provider: Optional[str] = None,
        api_key: Optional[str] = None,
        cache_dir: Optional[str] = None,
        default_language: VoiceLanguage = VoiceLanguage.URDU,
        default_format: AudioFormat = AudioFormat.MP3_22050_64
    ):
        """
        Initialize voice interface.

        Args:
            tts_provider: TTS provider name ("uplift", "elevenlabs", etc.)
            stt_provider: STT provider name (optional)
            api_key: API key for providers
            cache_dir: Directory to cache audio files
            default_language: Default language for synthesis
            default_format: Default audio format
        """
        self.default_language = default_language
        self.default_format = default_format

        # Initialize TTS provider
        self.tts: BaseTTSProvider = VoiceProviderFactory.get_tts(
            tts_provider,
            api_key=api_key
        )

        # Initialize STT provider (optional)
        self.stt: Optional[BaseSTTProvider] = None
        if stt_provider:
            self.stt = VoiceProviderFactory.get_stt(stt_provider, api_key=api_key)

        # Cache directory for audio files
        self.cache_dir = Path(cache_dir) if cache_dir else Path(tempfile.gettempdir()) / "sehat_voice_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # User preferences storage (in production, use Redis/DB)
        self.user_preferences: Dict[str, UserPreferences] = {}

        # Audio cache (text hash -> file path)
        self._audio_cache: Dict[str, str] = {}

        print(f"VoiceInterface initialized")
        print(f"  TTS Provider: {self.tts.provider_name}")
        print(f"  Default Language: {default_language.value}")
        print(f"  Cache Dir: {self.cache_dir}")

    def get_user_preferences(self, user_id: str) -> UserPreferences:
        """Get or create user voice preferences"""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = UserPreferences()
        return self.user_preferences[user_id]

    def set_user_preferences(
        self,
        user_id: str,
        response_mode: Optional[ResponseMode] = None,
        language: Optional[VoiceLanguage] = None,
        voice_id: Optional[str] = None,
        speaking_rate: Optional[float] = None
    ):
        """Update user voice preferences"""
        prefs = self.get_user_preferences(user_id)
        if response_mode is not None:
            prefs.response_mode = response_mode
        if language is not None:
            prefs.preferred_language = language
        if voice_id is not None:
            prefs.voice_id = voice_id
        if speaking_rate is not None:
            prefs.speaking_rate = max(0.5, min(2.0, speaking_rate))

    def _get_voice_config(
        self,
        user_id: Optional[str] = None,
        language: Optional[VoiceLanguage] = None,
        voice_id: Optional[str] = None,
        format: Optional[AudioFormat] = None
    ) -> VoiceConfig:
        """Build voice config from user preferences or defaults"""
        prefs = self.get_user_preferences(user_id) if user_id else UserPreferences()

        # Determine language
        lang = language or prefs.preferred_language or self.default_language

        # Determine voice ID
        vid = voice_id or prefs.voice_id or self.DEFAULT_VOICES.get(lang, "v_8eelc901")

        # Determine format
        fmt = format or self.default_format

        return VoiceConfig(
            voice_id=vid,
            language=lang,
            output_format=fmt,
            speaking_rate=prefs.speaking_rate
        )

    def _get_cache_key(self, text: str, config: VoiceConfig) -> str:
        """Generate cache key for audio"""
        import hashlib
        content = f"{text}:{config.voice_id}:{config.output_format.value}"
        return hashlib.md5(content.encode()).hexdigest()

    def _get_cached_audio(self, cache_key: str) -> Optional[str]:
        """Get cached audio file path if exists"""
        if cache_key in self._audio_cache:
            path = self._audio_cache[cache_key]
            if os.path.exists(path):
                return path
        return None

    def _cache_audio(self, cache_key: str, audio_data: bytes, format: AudioFormat) -> str:
        """Cache audio data and return file path"""
        ext = "mp3" if "MP3" in format.value else "wav"
        file_path = self.cache_dir / f"{cache_key}.{ext}"

        with open(file_path, "wb") as f:
            f.write(audio_data)

        self._audio_cache[cache_key] = str(file_path)
        return str(file_path)

    def text_to_voice(
        self,
        text: str,
        user_id: Optional[str] = None,
        language: Optional[VoiceLanguage] = None,
        voice_id: Optional[str] = None,
        use_cache: bool = True
    ) -> VoiceMessage:
        """
        Convert text to voice message (synchronous).

        Args:
            text: Text to convert
            user_id: User ID for preferences lookup
            language: Override language
            voice_id: Override voice
            use_cache: Whether to use cached audio

        Returns:
            VoiceMessage with audio data
        """
        config = self._get_voice_config(user_id, language, voice_id)
        cache_key = self._get_cache_key(text, config)

        # Check cache
        if use_cache:
            cached_path = self._get_cached_audio(cache_key)
            if cached_path:
                return VoiceMessage(
                    text=text,
                    audio_path=cached_path,
                    format=config.output_format,
                    language=config.language,
                    metadata={"cached": True}
                )

        # Synthesize
        result = self.tts.synthesize(text, config)

        if not result.success:
            return VoiceMessage(
                text=text,
                metadata={"error": result.error}
            )

        # Cache the audio
        audio_path = self._cache_audio(cache_key, result.audio_data, config.output_format)

        return VoiceMessage(
            text=text,
            audio_data=result.audio_data,
            audio_path=audio_path,
            duration_ms=result.duration_ms,
            format=config.output_format,
            language=config.language,
            metadata=result.metadata
        )

    async def text_to_voice_async(
        self,
        text: str,
        user_id: Optional[str] = None,
        language: Optional[VoiceLanguage] = None,
        voice_id: Optional[str] = None,
        return_url: bool = True
    ) -> VoiceMessage:
        """
        Convert text to voice message (asynchronous).

        Args:
            text: Text to convert
            user_id: User ID for preferences lookup
            language: Override language
            voice_id: Override voice
            return_url: If True, return streaming URL instead of downloading

        Returns:
            VoiceMessage with audio URL or data
        """
        config = self._get_voice_config(user_id, language, voice_id)

        # Use async synthesis which returns URL
        result = await self.tts.synthesize_async(text, config)

        if not result.success:
            return VoiceMessage(
                text=text,
                metadata={"error": result.error}
            )

        return VoiceMessage(
            text=text,
            audio_url=result.audio_url,
            format=config.output_format,
            language=config.language,
            metadata=result.metadata
        )

    async def voice_to_text(
        self,
        audio: Union[bytes, str],
        user_id: Optional[str] = None,
        language: Optional[VoiceLanguage] = None
    ) -> TranscriptionResult:
        """
        Convert voice message to text (STT).

        Args:
            audio: Audio bytes or file path
            user_id: User ID for preferences lookup
            language: Expected language hint

        Returns:
            TranscriptionResult with transcribed text
        """
        if not self.stt:
            return TranscriptionResult(
                success=False,
                error="STT provider not configured"
            )

        prefs = self.get_user_preferences(user_id) if user_id else UserPreferences()
        lang = language or prefs.preferred_language

        return await self.stt.transcribe_async(audio, lang)

    def should_send_voice(self, user_id: str) -> bool:
        """Check if user should receive voice responses"""
        prefs = self.get_user_preferences(user_id)
        return prefs.response_mode in [ResponseMode.VOICE_ONLY, ResponseMode.TEXT_AND_VOICE]

    def should_send_text(self, user_id: str) -> bool:
        """Check if user should receive text responses"""
        prefs = self.get_user_preferences(user_id)
        return prefs.response_mode in [ResponseMode.TEXT_ONLY, ResponseMode.TEXT_AND_VOICE]

    def cleanup_cache(self, max_age_hours: int = 24):
        """Remove old cached audio files"""
        import time
        cutoff = time.time() - (max_age_hours * 3600)

        for cache_key, file_path in list(self._audio_cache.items()):
            if os.path.exists(file_path):
                if os.path.getmtime(file_path) < cutoff:
                    os.remove(file_path)
                    del self._audio_cache[cache_key]

    async def close(self):
        """Cleanup resources"""
        if hasattr(self.tts, 'close'):
            await self.tts.close()
        if self.stt and hasattr(self.stt, 'close'):
            await self.stt.close()


# Global instance
_voice_interface: Optional[VoiceInterface] = None


def get_voice_interface(
    tts_provider: str = "uplift",
    **kwargs
) -> VoiceInterface:
    """Get or create voice interface instance"""
    global _voice_interface
    if _voice_interface is None:
        _voice_interface = VoiceInterface(tts_provider=tts_provider, **kwargs)
    return _voice_interface
