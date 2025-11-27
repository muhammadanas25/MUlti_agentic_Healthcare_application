"""
Voice Call Interface using Twilio Voice

Handles incoming phone calls, speech recognition, and voice responses.
Integrates with the multi-agent system for conversational AI over phone.

Flow:
1. User calls Twilio number
2. Twilio sends webhook to /webhook/voice
3. Server greets user, asks for input
4. User speaks -> Twilio STT -> Text
5. Text -> Agent -> Response text
6. Response text -> Uplift AI TTS -> Audio URL
7. Twilio plays audio to user
8. Loop continues until hangup
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio

from twilio.twiml.voice_response import VoiceResponse, Gather, Say, Play
from twilio.rest import Client

from ..core.config import settings


class CallState(Enum):
    """States for a voice call session"""
    GREETING = "greeting"
    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"
    ENDED = "ended"


class CallLanguage(Enum):
    """Supported languages for voice calls"""
    URDU = "ur-PK"      # Urdu Pakistan
    ENGLISH = "en-US"   # English US
    ENGLISH_IN = "en-IN"  # English India (closer accent)
    HINDI = "hi-IN"     # Hindi India


@dataclass
class CallSession:
    """Represents an active phone call session"""
    call_sid: str
    from_number: str
    to_number: str
    state: CallState = CallState.GREETING
    language: CallLanguage = CallLanguage.URDU
    started_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    current_agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, agent: Optional[str] = None):
        """Add message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "agent": agent,
            "timestamp": datetime.now().isoformat()
        })
        self.last_activity = datetime.now()


class VoiceCallInterface:
    """
    Voice Call interface for Sehat Saathi.

    Handles:
    - Incoming call webhooks from Twilio
    - Speech-to-text via Twilio's built-in recognition
    - Text-to-speech via Uplift AI
    - Call session management
    - Integration with multi-agent system
    """

    # Greeting messages in different languages
    GREETINGS = {
        CallLanguage.URDU: "السلام علیکم! سہت ساتھی میں خوش آمدید۔ میں آپ کی صحت سے متعلق کیسے مدد کر سکتا ہوں؟",
        CallLanguage.ENGLISH: "Hello! Welcome to Sehat Saathi. How can I help you with your health concerns today?",
        CallLanguage.HINDI: "नमस्ते! सेहत साथी में आपका स्वागत है। मैं आपकी स्वास्थ्य संबंधी कैसे मदद कर सकता हूं?",
    }

    # Prompts for gathering speech
    LISTEN_PROMPTS = {
        CallLanguage.URDU: "براہ کرم اپنا سوال بولیں۔",
        CallLanguage.ENGLISH: "Please speak your question.",
        CallLanguage.HINDI: "कृपया अपना सवाल बोलें।",
    }

    # Processing messages
    PROCESSING_MESSAGES = {
        CallLanguage.URDU: "ایک لمحہ، میں آپ کی مدد کر رہا ہوں۔",
        CallLanguage.ENGLISH: "One moment, I'm processing your request.",
        CallLanguage.HINDI: "एक पल, मैं आपकी मदद कर रहा हूं।",
    }

    # Error messages
    ERROR_MESSAGES = {
        CallLanguage.URDU: "معذرت، میں سمجھ نہیں سکا۔ براہ کرم دوبارہ کوشش کریں۔",
        CallLanguage.ENGLISH: "Sorry, I couldn't understand. Please try again.",
        CallLanguage.HINDI: "क्षमा करें, मैं समझ नहीं पाया। कृपया फिर से कोशिश करें।",
    }

    # Goodbye messages
    GOODBYE_MESSAGES = {
        CallLanguage.URDU: "آپ کا شکریہ۔ اللہ حافظ!",
        CallLanguage.ENGLISH: "Thank you for calling. Goodbye!",
        CallLanguage.HINDI: "कॉल करने के लिए धन्यवाद। अलविदा!",
    }

    def __init__(self, voice_interface: Optional["VoiceInterface"] = None):
        """
        Initialize voice call interface.

        Args:
            voice_interface: VoiceInterface instance for TTS (optional)
        """
        self.client = Client(
            settings.twilio_account_sid,
            settings.twilio_auth_token
        )
        self.phone_number = settings.twilio_phone_number
        self.voice_interface = voice_interface

        # Active call sessions (call_sid -> CallSession)
        self.sessions: Dict[str, CallSession] = {}

        # Default settings
        self.default_language = CallLanguage.URDU
        self.speech_timeout = 3  # seconds of silence before processing
        self.max_speech_time = 30  # max seconds of speech input

        print(f"VoiceCallInterface initialized")
        print(f"  Phone Number: {self.phone_number}")

    def get_or_create_session(
        self,
        call_sid: str,
        from_number: str,
        to_number: str
    ) -> CallSession:
        """Get existing session or create new one"""
        if call_sid not in self.sessions:
            self.sessions[call_sid] = CallSession(
                call_sid=call_sid,
                from_number=from_number,
                to_number=to_number,
                language=self.default_language
            )
        return self.sessions[call_sid]

    def get_session(self, call_sid: str) -> Optional[CallSession]:
        """Get session by call SID"""
        return self.sessions.get(call_sid)

    def end_session(self, call_sid: str):
        """End and cleanup a call session"""
        if call_sid in self.sessions:
            self.sessions[call_sid].state = CallState.ENDED
            # Keep for history, cleanup in background

    def cleanup_old_sessions(self, max_age_minutes: int = 60):
        """Remove sessions older than max_age_minutes"""
        cutoff = datetime.now()
        to_remove = []
        for sid, session in self.sessions.items():
            age = (cutoff - session.last_activity).total_seconds() / 60
            if age > max_age_minutes:
                to_remove.append(sid)
        for sid in to_remove:
            del self.sessions[sid]

    def create_greeting_response(
        self,
        call_sid: str,
        from_number: str,
        to_number: str,
        webhook_base_url: str
    ) -> str:
        """
        Create TwiML response for incoming call greeting.

        Args:
            call_sid: Twilio call SID
            from_number: Caller's phone number
            to_number: Called number
            webhook_base_url: Base URL for webhooks (e.g., https://xxx.ngrok.io)

        Returns:
            TwiML XML string
        """
        session = self.get_or_create_session(call_sid, from_number, to_number)
        session.state = CallState.GREETING

        response = VoiceResponse()

        # Add greeting
        greeting = self.GREETINGS.get(session.language, self.GREETINGS[CallLanguage.URDU])

        # Use Gather to collect speech after greeting
        gather = Gather(
            input='speech',
            action=f"{webhook_base_url}/webhook/voice/gather",
            method='POST',
            language=session.language.value,
            speech_timeout=str(self.speech_timeout),
            timeout=10,
            speech_model='phone_call'
        )

        # Say the greeting (using Twilio's TTS for now, can be replaced with Uplift)
        gather.say(
            greeting,
            language=session.language.value,
            voice='Polly.Aditi' if session.language == CallLanguage.URDU else 'Polly.Joanna'
        )

        response.append(gather)

        # If no input, prompt again
        response.say(
            self.ERROR_MESSAGES.get(session.language, self.ERROR_MESSAGES[CallLanguage.URDU]),
            language=session.language.value
        )
        response.redirect(f"{webhook_base_url}/webhook/voice")

        session.add_message("assistant", greeting)
        session.state = CallState.LISTENING

        return str(response)

    def create_listening_response(
        self,
        call_sid: str,
        webhook_base_url: str,
        prompt: Optional[str] = None
    ) -> str:
        """
        Create TwiML to listen for user speech.

        Args:
            call_sid: Twilio call SID
            webhook_base_url: Base URL for webhooks
            prompt: Optional prompt to say before listening

        Returns:
            TwiML XML string
        """
        session = self.get_session(call_sid)
        if not session:
            return self._create_error_response("Session not found")

        response = VoiceResponse()

        gather = Gather(
            input='speech',
            action=f"{webhook_base_url}/webhook/voice/gather",
            method='POST',
            language=session.language.value,
            speech_timeout=str(self.speech_timeout),
            timeout=15,
            speech_model='phone_call'
        )

        if prompt:
            gather.say(prompt, language=session.language.value)

        response.append(gather)

        # If no input
        response.say(
            self.LISTEN_PROMPTS.get(session.language, self.LISTEN_PROMPTS[CallLanguage.URDU]),
            language=session.language.value
        )
        response.redirect(f"{webhook_base_url}/webhook/voice/continue")

        session.state = CallState.LISTENING
        return str(response)

    async def create_agent_response(
        self,
        call_sid: str,
        user_speech: str,
        webhook_base_url: str,
        message_router: "MessageRouter"
    ) -> str:
        """
        Process user speech through agent and create voice response.

        Args:
            call_sid: Twilio call SID
            user_speech: Transcribed user speech
            webhook_base_url: Base URL for webhooks
            message_router: MessageRouter instance for agent routing

        Returns:
            TwiML XML string
        """
        session = self.get_session(call_sid)
        if not session:
            return self._create_error_response("Session not found")

        session.state = CallState.PROCESSING
        session.add_message("user", user_speech)

        response = VoiceResponse()

        try:
            # Create a simple session dict for the router
            router_session = {
                "phone": session.from_number,
                "conversation_state": "voice_call",
                "patient_info": session.metadata.get("patient_info", {}),
                "message_history": session.conversation_history
            }

            # Route to agent
            agent_response, agent_name = await message_router.route_message(
                user_speech,
                router_session
            )

            session.current_agent = agent_name

            # Extract response text
            if agent_response.success and agent_response.data:
                if isinstance(agent_response.data, dict):
                    response_text = agent_response.data.get(
                        "patient_message",
                        agent_response.data.get("response", str(agent_response.data))
                    )
                else:
                    response_text = str(agent_response.data)
            else:
                response_text = agent_response.reasoning or "I couldn't process that request."

            # Clean response for speech (remove emojis, markdown)
            response_text = self._clean_for_speech(response_text)

            session.add_message("assistant", response_text, agent_name)
            session.state = CallState.RESPONDING

            # Generate voice response
            if self.voice_interface:
                # Use Uplift AI TTS
                voice_msg = await self.voice_interface.text_to_voice_async(
                    text=response_text,
                    user_id=session.from_number
                )

                if voice_msg.audio_url:
                    # Play the generated audio
                    response.play(voice_msg.audio_url)
                else:
                    # Fallback to Twilio TTS
                    response.say(response_text, language=session.language.value)
            else:
                # Use Twilio's built-in TTS
                response.say(response_text, language=session.language.value)

            # Continue listening
            gather = Gather(
                input='speech',
                action=f"{webhook_base_url}/webhook/voice/gather",
                method='POST',
                language=session.language.value,
                speech_timeout=str(self.speech_timeout),
                timeout=15,
                speech_model='phone_call'
            )
            gather.say(
                self.LISTEN_PROMPTS.get(session.language, ""),
                language=session.language.value
            )
            response.append(gather)

            # If no response, end call politely
            response.say(
                self.GOODBYE_MESSAGES.get(session.language, self.GOODBYE_MESSAGES[CallLanguage.URDU]),
                language=session.language.value
            )
            response.hangup()

        except Exception as e:
            print(f"Error processing voice call: {e}")
            response.say(
                self.ERROR_MESSAGES.get(session.language, self.ERROR_MESSAGES[CallLanguage.URDU]),
                language=session.language.value
            )
            response.redirect(f"{webhook_base_url}/webhook/voice/continue")

        return str(response)

    def create_goodbye_response(self, call_sid: str) -> str:
        """Create TwiML for ending the call"""
        session = self.get_session(call_sid)
        language = session.language if session else self.default_language

        response = VoiceResponse()
        response.say(
            self.GOODBYE_MESSAGES.get(language, self.GOODBYE_MESSAGES[CallLanguage.URDU]),
            language=language.value
        )
        response.hangup()

        if session:
            self.end_session(call_sid)

        return str(response)

    def _create_error_response(self, error: str) -> str:
        """Create error TwiML response"""
        response = VoiceResponse()
        response.say(
            "Sorry, an error occurred. Please try again later.",
            language="en-US"
        )
        response.hangup()
        return str(response)

    def _clean_for_speech(self, text: str) -> str:
        """Clean text for speech synthesis (remove emojis, markdown, etc.)"""
        import re

        # Remove emojis
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        text = emoji_pattern.sub('', text)

        # Remove markdown formatting
        text = re.sub(r'\*+', '', text)  # Bold/italic
        text = re.sub(r'_+', '', text)   # Italic/underline
        text = re.sub(r'`+', '', text)   # Code
        text = re.sub(r'#+\s*', '', text)  # Headers
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # Links

        # Remove bullet points
        text = re.sub(r'^\s*[-•]\s*', '', text, flags=re.MULTILINE)

        # Clean up whitespace
        text = re.sub(r'\n+', '. ', text)
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def set_language(self, call_sid: str, language: CallLanguage):
        """Set language for a call session"""
        session = self.get_session(call_sid)
        if session:
            session.language = language


# Global instance
_voice_call: Optional[VoiceCallInterface] = None


def get_voice_call_interface(
    voice_interface: Optional["VoiceInterface"] = None
) -> VoiceCallInterface:
    """Get or create voice call interface instance"""
    global _voice_call
    if _voice_call is None:
        _voice_call = VoiceCallInterface(voice_interface=voice_interface)
    return _voice_call
