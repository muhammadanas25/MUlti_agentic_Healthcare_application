"""
WhatsApp Interface using Twilio

Handles incoming WhatsApp messages, routes to agents, and sends responses.
Supports both text and audio (voice) messages.
"""
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
import asyncio
import os
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from ..core.config import settings
from ..core.agent import AgentResponse


class WhatsAppInterface:
    """
    WhatsApp interface for Sehat Saathi.

    Handles:
    - Receiving messages via Twilio webhook
    - Formatting messages for WhatsApp (with emojis, structure)
    - Sending responses back via Twilio
    - Managing conversation sessions
    """

    def __init__(self):
        self.client = Client(
            settings.twilio_account_sid,
            settings.twilio_auth_token
        )
        self.whatsapp_number = settings.twilio_whatsapp_number

        # Session storage (in production, use Redis)
        self.sessions: Dict[str, Dict[str, Any]] = {}

        print(f"✓ WhatsApp interface initialized")
        print(f"  WhatsApp Number: {self.whatsapp_number}")

    def get_or_create_session(self, phone_number: str) -> Dict[str, Any]:
        """Get or create conversation session for user"""
        if phone_number not in self.sessions:
            self.sessions[phone_number] = {
                "phone": phone_number,
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "conversation_state": "greeting",
                "patient_info": {},
                "current_flow": None,
                "message_history": []
            }
        else:
            self.sessions[phone_number]["last_activity"] = datetime.now().isoformat()

        return self.sessions[phone_number]

    def update_session(self, phone_number: str, updates: Dict[str, Any]):
        """Update session data"""
        if phone_number in self.sessions:
            self.sessions[phone_number].update(updates)

    def format_for_whatsapp(self, response: AgentResponse, agent_name: str = "Sehat Saathi") -> str:
        """
        Format agent response for WhatsApp.

        WhatsApp supports:
        - Emojis
        - Bold: *text*
        - Italic: _text_
        - Strikethrough: ~text~
        - Monospace: ```text```
        - Line breaks
        """
        if not response.success:
            return f"❌ Sorry, I couldn't process that request. Please try again.\n\n_Error: {response.reasoning}_"

        data = response.data
        if not data:
            return response.reasoning or "I'm here to help! What would you like to know?"

        # Format based on response type
        if isinstance(data, dict):
            return self._format_dict_response(data, agent_name)
        elif isinstance(data, str):
            return data
        else:
            return str(data)

    def _format_dict_response(self, data: Dict[str, Any], agent_name: str) -> str:
        """Format dictionary response for WhatsApp"""
        lines = []

        # Check for patient_message first (used by conversational Dr. Sameer)
        if "patient_message" in data:
            return data["patient_message"]

        # Handle common response types
        if "urgency" in data:
            # Triage response
            lines.append(f"🏥 *{agent_name} - Assessment*\n")
            lines.append(f"⚠️ Urgency: *{data.get('urgency', 'Unknown')}*")

            if data.get("possible_conditions"):
                conditions = data["possible_conditions"]
                if isinstance(conditions, list):
                    lines.append(f"\n📋 Possible conditions:")
                    for c in conditions[:3]:
                        lines.append(f"  • {c}")

            if data.get("recommended_action"):
                lines.append(f"\n✅ *Recommendation:*\n{data['recommended_action']}")

            if data.get("red_flags"):
                flags = data["red_flags"]
                if isinstance(flags, list):
                    lines.append(f"\n🚨 *Watch for:*")
                    for f in flags[:3]:
                        lines.append(f"  • {f}")

        elif "recommended_hospital" in data:
            # Hospital recommendation
            lines.append(f"🏥 *Hospital Recommendation*\n")
            hospital = data["recommended_hospital"]
            if isinstance(hospital, dict):
                lines.append(f"*{hospital.get('name', 'Hospital')}*")
                if hospital.get('reason'):
                    lines.append(f"_{hospital['reason']}_")

            if data.get("alternatives"):
                lines.append(f"\n📍 *Other options:*")
                for alt in data["alternatives"][:2]:
                    if isinstance(alt, dict):
                        lines.append(f"  • {alt.get('name', 'Alternative')}")

        elif "recommended_doctor" in data:
            # Doctor recommendation
            lines.append(f"👨‍⚕️ *Doctor Recommendation*\n")
            doctor = data["recommended_doctor"]
            if isinstance(doctor, dict):
                lines.append(f"*{doctor.get('name', 'Doctor')}*")
                if doctor.get('estimated_cost'):
                    lines.append(f"💰 Fee: {doctor['estimated_cost']}")

        elif "appointment" in data:
            # Appointment confirmation
            lines.append(f"✅ *Appointment Confirmed!*\n")
            apt = data["appointment"]
            if isinstance(apt, dict):
                lines.append(f"📅 {apt.get('appointment_time', 'TBD')}")
                lines.append(f"🏥 {apt.get('hospital', 'Hospital')}")

        elif "is_eligible" in data or "eligible" in data:
            # Insurance verification
            eligible = data.get("is_eligible") or data.get("eligible")
            lines.append(f"💳 *Sehat Sahulat Status*\n")
            if eligible:
                lines.append(f"✅ Card is *ACTIVE*")
                if data.get("coverage_amount"):
                    lines.append(f"💰 Coverage: Rs. {data['coverage_amount']:,}")
            else:
                lines.append(f"❌ Not eligible for Sehat Sahulat")
                lines.append(f"\n_Alternative options available at government hospitals_")

        elif "medicine_details" in data or "pharmacies" in data:
            # Medicine search
            lines.append(f"💊 *Medicine Search Results*\n")
            if data.get("recommended_option"):
                opt = data["recommended_option"]
                if isinstance(opt, dict):
                    lines.append(f"✅ *Recommended:* {opt.get('medicine_name', 'Medicine')}")
                    lines.append(f"💰 Price: Rs. {opt.get('price', 'N/A')}")

            if data.get("generic_alternatives"):
                lines.append(f"\n💡 *Cheaper alternatives:*")
                for alt in data["generic_alternatives"][:2]:
                    if isinstance(alt, dict):
                        lines.append(f"  • {alt.get('name', 'Generic')}: Rs. {alt.get('price', 'N/A')}")

        elif "patient_message" in data:
            # Direct patient message
            lines.append(data["patient_message"])

        elif "response" in data:
            # Generic response
            lines.append(data["response"])

        else:
            # Fallback: format as key-value
            for key, value in list(data.items())[:5]:
                if not key.startswith("_"):
                    formatted_key = key.replace("_", " ").title()
                    lines.append(f"• *{formatted_key}:* {value}")

        return "\n".join(lines)

    def send_message(self, to_number: str, message: str) -> bool:
        """
        Send WhatsApp message via Twilio.

        Args:
            to_number: Recipient's phone number (with country code)
            message: Message text

        Returns:
            True if sent successfully
        """
        try:
            # Ensure WhatsApp format
            if not to_number.startswith("whatsapp:"):
                to_number = f"whatsapp:{to_number}"

            # Truncate if too long (WhatsApp limit is 4096)
            if len(message) > 4000:
                message = message[:3990] + "\n\n_[Message truncated]_"

            sent_message = self.client.messages.create(
                body=message,
                from_=self.whatsapp_number,
                to=to_number
            )

            print(f"📱 Message sent to {to_number}: {sent_message.sid}")
            return True

        except Exception as e:
            print(f"❌ Failed to send WhatsApp message: {e}")
            return False

    def send_audio_message(
        self,
        to_number: str,
        audio_url: Optional[str] = None,
        audio_path: Optional[str] = None,
        caption: Optional[str] = None
    ) -> bool:
        """
        Send WhatsApp audio/voice message via Twilio.

        Args:
            to_number: Recipient's phone number (with country code)
            audio_url: URL to publicly accessible audio file
            audio_path: Local path to audio file (will be uploaded)
            caption: Optional text caption with the audio

        Returns:
            True if sent successfully

        Note:
            Either audio_url or audio_path must be provided.
            For audio_path, the file must be uploaded to a public URL first.
        """
        try:
            # Ensure WhatsApp format
            if not to_number.startswith("whatsapp:"):
                to_number = f"whatsapp:{to_number}"

            if not audio_url and not audio_path:
                raise ValueError("Either audio_url or audio_path must be provided")

            # If local path provided, we need a URL
            # In production, upload to S3/GCS/etc. and get URL
            media_url = audio_url
            if audio_path and not audio_url:
                # For now, require URL - in production implement upload
                raise ValueError("Local audio files require upload to public URL first. Use audio_url instead.")

            # Send audio message
            message_params = {
                "from_": self.whatsapp_number,
                "to": to_number,
                "media_url": [media_url]
            }

            if caption:
                message_params["body"] = caption[:1000]  # WhatsApp caption limit

            sent_message = self.client.messages.create(**message_params)

            print(f"🔊 Audio sent to {to_number}: {sent_message.sid}")
            return True

        except Exception as e:
            print(f"❌ Failed to send WhatsApp audio: {e}")
            return False

    async def send_voice_response(
        self,
        to_number: str,
        text: str,
        voice_interface: "VoiceInterface",
        include_text: bool = True,
        language: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Send both text and voice response to user.

        Args:
            to_number: Recipient's phone number
            text: Text to convert to speech and/or send
            voice_interface: VoiceInterface instance for TTS
            include_text: Whether to also send text message
            language: Language for TTS (defaults to user preference)

        Returns:
            Dict with 'text_sent' and 'voice_sent' booleans
        """
        result = {"text_sent": False, "voice_sent": False}

        # Send text first if requested
        if include_text:
            result["text_sent"] = self.send_message(to_number, text)

        # Generate and send voice
        try:
            from .voice import VoiceLanguage

            lang = None
            if language:
                try:
                    lang = VoiceLanguage(language)
                except ValueError:
                    lang = None

            # Use async synthesis which returns URL (preferred for WhatsApp)
            voice_msg = await voice_interface.text_to_voice_async(
                text=text,
                user_id=to_number,
                language=lang
            )

            if voice_msg.audio_url:
                result["voice_sent"] = self.send_audio_message(
                    to_number=to_number,
                    audio_url=voice_msg.audio_url
                )
            elif voice_msg.metadata.get("error"):
                print(f"⚠️ Voice synthesis failed: {voice_msg.metadata['error']}")

        except Exception as e:
            print(f"❌ Failed to send voice response: {e}")

        return result

    def send_template_message(
        self,
        to_number: str,
        template_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """Send templated message for common scenarios"""

        templates = {
            "welcome": """🏥 *Sehat Saathi - آپ کا صحت ساتھی*

Assalam-o-Alaikum! Welcome to Sehat Saathi.

I can help you with:
1️⃣ Check symptoms & get advice
2️⃣ Find nearby hospitals & doctors
3️⃣ Book appointments
4️⃣ Find medicines & pharmacies
5️⃣ Check Sehat Card eligibility

_Type a number or describe your health concern._

مدد کے لیے "help" لکھیں""",

            "help": """📖 *How to use Sehat Saathi:*

• *For symptoms:* Type your symptoms
  Example: "bukhar aur sar dard"

• *For hospitals:* Type "hospital" + area
  Example: "hospital Gulberg Karachi"

• *For doctors:* Type "doctor" + specialty
  Example: "doctor heart Lahore"

• *For medicines:* Type "medicine" + name
  Example: "medicine Panadol"

• *For Sehat Card:* Type "sehat card"

_Need more help? Reply "agent" to talk to support._""",

            "emergency": f"""🚨 *EMERGENCY ALERT*

Based on your symptoms, this may be an emergency.

*Please do the following immediately:*
1. Call emergency: *1122*
2. Go to nearest hospital: {data.get('hospital', 'Emergency ward')}

🏥 Hospital: *{data.get('hospital_name', 'Nearest hospital')}*
📍 {data.get('address', '')}
📞 {data.get('phone', '')}

_An ambulance can save precious time. Don't delay!_""",

            "appointment_confirmed": f"""✅ *Appointment Confirmed!*

👨‍⚕️ *Doctor:* {data.get('doctor_name', 'Doctor')}
🏥 *Hospital:* {data.get('hospital_name', 'Hospital')}
📅 *Date:* {data.get('date', 'TBD')}
⏰ *Time:* {data.get('time', 'TBD')}
💰 *Fee:* {data.get('fee', 'Free')}

📍 *Address:*
{data.get('address', '')}

⚠️ Please arrive 15 minutes early.
Reply "cancel" to cancel appointment.""",

            "sehat_card_active": f"""💳 *Sehat Sahulat Card - ACTIVE ✅*

Card Number: {data.get('card_number', 'N/A')}
Coverage: Rs. {data.get('coverage', '10,00,000')}
Family Members: {data.get('family_size', 'N/A')}
Valid Until: {data.get('expiry', 'N/A')}

✅ Your treatment at empaneled hospitals will be FREE.

_Show this card at the hospital billing counter._""",

            "sehat_card_inactive": """💳 *Sehat Sahulat Card - NOT FOUND ❌*

Your CNIC is not registered in Sehat Sahulat program.

*Alternative options:*
• Government hospitals (free/low cost)
• Zakat funds at private hospitals
• NGO-run clinics (Edhi, SIUT, etc.)

_Reply "free hospitals" to find free healthcare near you._"""
        }

        message = templates.get(template_type, templates["help"])

        return self.send_message(to_number, message)

    def create_twiml_response(self, message: str) -> str:
        """Create TwiML response for Twilio webhook"""
        response = MessagingResponse()
        response.message(message)
        return str(response)


# Global instance
_whatsapp: Optional[WhatsAppInterface] = None


def get_whatsapp_interface() -> WhatsAppInterface:
    """Get or create WhatsApp interface instance"""
    global _whatsapp
    if _whatsapp is None:
        _whatsapp = WhatsAppInterface()
    return _whatsapp
