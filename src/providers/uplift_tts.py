"""
Uplift AI Text-to-Speech Provider

Implementation of BaseTTSProvider for Uplift AI's TTS API.
Supports synchronous, asynchronous, and streaming synthesis.

Documentation: https://docs.upliftai.org/text-to-speech
"""
import os
import asyncio
from typing import Dict, Any, Optional, AsyncIterator, List
import requests
import aiohttp

from .voice import (
    BaseTTSProvider,
    VoiceConfig,
    SynthesisResult,
    AudioFormat,
    VoiceLanguage,
    VoiceProviderFactory
)


class UpliftTTS(BaseTTSProvider):
    """
    Uplift AI Text-to-Speech provider.

    Supports Urdu and regional Pakistani languages with natural-sounding voices.

    Usage:
        tts = UpliftTTS(api_key="sk_api_...")
        result = tts.synthesize("السلام علیکم", config)
    """

    BASE_URL = "https://api.upliftai.org/v1/synthesis"

    # Predefined voices for Uplift AI
    VOICES = [
        {"id": "v_8eelc901", "name": "Amina", "language": "ur", "gender": "female", "accent": "Pakistani Urdu"},
        {"id": "v_urdu_m1", "name": "Ahmed", "language": "ur", "gender": "male", "accent": "Pakistani Urdu"},
        {"id": "v_urdu_f2", "name": "Fatima", "language": "ur", "gender": "female", "accent": "Pakistani Urdu"},
        {"id": "v_en_pk_m1", "name": "Ali", "language": "en", "gender": "male", "accent": "Pakistani English"},
        {"id": "v_en_pk_f1", "name": "Sara", "language": "en", "gender": "female", "accent": "Pakistani English"},
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize Uplift AI TTS provider.

        Args:
            api_key: Uplift AI API key (or set UPLIFT_API_KEY env var)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.api_key = api_key or os.getenv("UPLIFT_API_KEY")
        if not self.api_key:
            raise ValueError("Uplift API key required. Set UPLIFT_API_KEY env var or pass api_key parameter.")

        self.timeout = timeout
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def provider_name(self) -> str:
        return "uplift_ai"

    @property
    def supported_languages(self) -> List[VoiceLanguage]:
        return [VoiceLanguage.URDU, VoiceLanguage.ENGLISH, VoiceLanguage.PUNJABI]

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _format_to_api(self, format: AudioFormat) -> str:
        """Convert AudioFormat enum to API format string"""
        return format.value

    def get_available_voices(self, language: Optional[VoiceLanguage] = None) -> List[Dict[str, Any]]:
        """Get available voices, optionally filtered by language"""
        voices = self.VOICES.copy()
        if language:
            voices = [v for v in voices if v["language"] == language.value]
        return voices

    def synthesize(self, text: str, config: VoiceConfig) -> SynthesisResult:
        """
        Synchronous text-to-speech synthesis.

        Returns audio bytes directly (not streaming).
        """
        # Validate text
        is_valid, error = self.validate_text(text)
        if not is_valid:
            return SynthesisResult(success=False, error=error)

        url = f"{self.BASE_URL}/text-to-speech"
        payload = {
            "voiceId": config.voice_id,
            "text": text,
            "outputFormat": self._format_to_api(config.output_format)
        }

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=self.timeout
                )
                response.raise_for_status()

                # Get duration from headers
                duration_ms = response.headers.get("x-uplift-ai-audio-duration")
                if duration_ms:
                    duration_ms = int(duration_ms)

                return SynthesisResult(
                    success=True,
                    audio_data=response.content,
                    duration_ms=duration_ms,
                    format=config.output_format,
                    metadata={
                        "voice_id": config.voice_id,
                        "text_length": len(text),
                        "provider": self.provider_name
                    }
                )

            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries - 1:
                    return SynthesisResult(
                        success=False,
                        error=f"API request failed after {self.max_retries} attempts: {str(e)}"
                    )
                # Exponential backoff
                asyncio.sleep(2 ** attempt)

        return SynthesisResult(success=False, error="Unknown error during synthesis")

    async def synthesize_async(self, text: str, config: VoiceConfig) -> SynthesisResult:
        """
        Asynchronous text-to-speech synthesis.

        Uses the async API endpoint that returns a URL for streaming.
        """
        # Validate text
        is_valid, error = self.validate_text(text)
        if not is_valid:
            return SynthesisResult(success=False, error=error)

        url = f"{self.BASE_URL}/text-to-speech-async"
        payload = {
            "voiceId": config.voice_id,
            "text": text,
            "outputFormat": self._format_to_api(config.output_format)
        }

        session = await self._get_session()

        for attempt in range(self.max_retries):
            try:
                async with session.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    response.raise_for_status()
                    data = await response.json()

                    # Construct streaming URL
                    media_id = data.get("mediaId")
                    token = data.get("token")
                    audio_url = f"{self.BASE_URL}/stream-audio/{media_id}?token={token}"

                    return SynthesisResult(
                        success=True,
                        audio_url=audio_url,
                        format=config.output_format,
                        metadata={
                            "voice_id": config.voice_id,
                            "text_length": len(text),
                            "media_id": media_id,
                            "provider": self.provider_name
                        }
                    )

            except aiohttp.ClientError as e:
                if attempt == self.max_retries - 1:
                    return SynthesisResult(
                        success=False,
                        error=f"Async API request failed: {str(e)}"
                    )
                await asyncio.sleep(2 ** attempt)

        return SynthesisResult(success=False, error="Unknown error during async synthesis")

    async def synthesize_stream(self, text: str, config: VoiceConfig) -> AsyncIterator[bytes]:
        """
        Stream audio chunks as they're generated.

        Useful for real-time playback or large text inputs.
        """
        # Validate text
        is_valid, error = self.validate_text(text)
        if not is_valid:
            raise ValueError(error)

        url = f"{self.BASE_URL}/text-to-speech-stream"
        payload = {
            "voiceId": config.voice_id,
            "text": text,
            "outputFormat": self._format_to_api(config.output_format)
        }

        session = await self._get_session()

        async with session.post(
            url,
            json=payload,
            headers=self._get_headers(),
            timeout=aiohttp.ClientTimeout(total=self.timeout * 2)
        ) as response:
            response.raise_for_status()
            async for chunk in response.content.iter_chunked(8192):
                yield chunk

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the aiohttp session"""
        if self._session and not self._session.closed:
            await self._session.close()

    def __del__(self):
        """Cleanup on deletion"""
        if self._session and not self._session.closed:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._session.close())
                else:
                    loop.run_until_complete(self._session.close())
            except Exception:
                pass


# Register with factory
VoiceProviderFactory.register_tts("uplift", UpliftTTS)
VoiceProviderFactory.register_tts("uplift_ai", UpliftTTS)
