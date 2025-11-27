"""
Sehat Saathi - WhatsApp Server

FastAPI server that handles Twilio WhatsApp webhooks and routes
messages to the multi-agent system. Supports text and voice responses.

Run with: uvicorn whatsapp_server:app --reload --port 8000

For local testing with Twilio:
1. Install ngrok: https://ngrok.com/download
2. Run: ngrok http 8000
3. Copy the https URL (e.g., https://abc123.ngrok.io)
4. Go to Twilio Console > Messaging > Settings > WhatsApp Sandbox
5. Set webhook URL to: https://abc123.ngrok.io/webhook/whatsapp
"""
import asyncio
from typing import Optional
from fastapi import FastAPI, Request, Form, Response, HTTPException, Query
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from src.core.config import settings
from src.interfaces.whatsapp import get_whatsapp_interface, WhatsAppInterface
from src.interfaces.message_router import get_message_router, MessageRouter
from src.interfaces.voice import get_voice_interface, VoiceInterface, ResponseMode, VoiceLanguage
from src.interfaces.voice_call import get_voice_call_interface, VoiceCallInterface, CallLanguage


# Initialize FastAPI app
app = FastAPI(
    title="Sehat Saathi - WhatsApp Server",
    description="Multi-agent healthcare system with WhatsApp interface",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
whatsapp: WhatsAppInterface = None
router: MessageRouter = None
voice: VoiceInterface = None
voice_call: VoiceCallInterface = None

# Voice enabled flag (can be toggled via API)
voice_enabled: bool = True

# Webhook base URL (set via ngrok or deployment)
webhook_base_url: str = ""


# Request models for API
class VoicePreferencesRequest(BaseModel):
    response_mode: Optional[str] = None  # "text_only", "voice_only", "text_and_voice"
    language: Optional[str] = None       # "ur", "en", etc.
    voice_id: Optional[str] = None
    speaking_rate: Optional[float] = None


class TTSRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None
    language: Optional[str] = "ur"


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global whatsapp, router, voice, voice_call

    print("\n" + "="*60)
    print("🏥 SEHAT SAATHI - WHATSAPP & VOICE SERVER")
    print("="*60 + "\n")

    # Initialize WhatsApp interface
    print("Initializing WhatsApp interface...")
    whatsapp = get_whatsapp_interface()

    # Initialize message router (this also initializes agents)
    print("\nInitializing agents...")
    router = get_message_router()

    # Initialize voice interface (TTS)
    print("\nInitializing voice interface...")
    try:
        voice = get_voice_interface(tts_provider="uplift")
        print("✓ Voice interface ready (Uplift AI TTS)")
    except Exception as e:
        print(f"⚠️ Voice interface initialization failed: {e}")
        print("  Voice responses will be disabled")

    # Initialize voice call interface
    print("\nInitializing voice call interface...")
    try:
        voice_call = get_voice_call_interface(voice_interface=voice)
        print("✓ Voice call interface ready")
    except Exception as e:
        print(f"⚠️ Voice call initialization failed: {e}")
        print("  Phone calls will be disabled")

    print("\n" + "="*60)
    print("✅ SERVER READY")
    print("="*60)
    print(f"\n📱 WhatsApp Number: {settings.twilio_whatsapp_number}")
    print(f"📞 Phone Number: {settings.twilio_phone_number}")
    print(f"🔊 Voice Enabled: {voice is not None}")
    print(f"📞 Calls Enabled: {voice_call is not None}")
    print(f"\n🌐 Webhooks:")
    print(f"   WhatsApp: http://localhost:8002/webhook/whatsapp")
    print(f"   Voice:    http://localhost:8002/webhook/voice")
    print("\n⚠️  For Twilio to reach this server, use ngrok:")
    print("   1. Run: ngrok http 8002")
    print("   2. Copy the HTTPS URL to Twilio Console")
    print("   3. Set WhatsApp webhook: <ngrok-url>/webhook/whatsapp")
    print("   4. Set Voice webhook: <ngrok-url>/webhook/voice")
    print("="*60 + "\n")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Sehat Saathi WhatsApp Server",
        "agents_active": len(router.agents) if router else 0,
        "whatsapp_number": settings.twilio_whatsapp_number
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "whatsapp_connected": whatsapp is not None,
        "router_ready": router is not None,
        "voice_ready": voice is not None,
        "voice_call_ready": voice_call is not None,
        "voice_enabled": voice_enabled,
        "agents": list(router.agents.keys()) if router else [],
        "whatsapp_sessions": len(whatsapp.sessions) if whatsapp else 0,
        "call_sessions": len(voice_call.sessions) if voice_call else 0
    }


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    Body: str = Form(default=""),
    From: str = Form(default=""),
    To: str = Form(default=""),
    MessageSid: str = Form(default=""),
    NumMedia: str = Form(default="0"),
    ProfileName: str = Form(default=""),
):
    """
    Twilio WhatsApp webhook endpoint.

    Receives incoming WhatsApp messages and routes them to agents.
    """
    try:
        print(f"\n📩 Incoming WhatsApp Message")
        print(f"   From: {From}")
        print(f"   Message: {Body}")
        print(f"   Profile: {ProfileName}")

        # Get or create session
        session = whatsapp.get_or_create_session(From)

        # Update session with profile info
        if ProfileName and not session.get("patient_info", {}).get("name"):
            session.setdefault("patient_info", {})["name"] = ProfileName

        # Add message to history
        session.setdefault("message_history", []).append({
            "role": "user",
            "content": Body,
            "timestamp": MessageSid
        })

        # Route message to agents
        response, agent_name = await router.route_message(Body, session)

        print(f"   Agent: {agent_name}")
        print(f"   Response success: {response.success}")

        # Format response for WhatsApp
        if response.data and response.data.get("template"):
            # Send template message
            template = response.data["template"]
            whatsapp.send_template_message(From, template, response.data)
            formatted_response = f"[Template: {template}]"
        else:
            # Format and send custom response
            formatted_response = whatsapp.format_for_whatsapp(response, agent_name)

            # Check if voice is enabled for this user
            send_voice = voice_enabled and voice is not None and voice.should_send_voice(From)

            if send_voice:
                # Send both text and voice response
                result = await whatsapp.send_voice_response(
                    to_number=From,
                    text=formatted_response,
                    voice_interface=voice,
                    include_text=voice.should_send_text(From)
                )
                print(f"   Voice sent: {result['voice_sent']}, Text sent: {result['text_sent']}")
            else:
                # Send text only
                whatsapp.send_message(From, formatted_response)

        # Add response to history
        session["message_history"].append({
            "role": "assistant",
            "agent": agent_name,
            "content": formatted_response[:200] + "..." if len(formatted_response) > 200 else formatted_response
        })

        # Return TwiML response (empty - we send via API)
        return PlainTextResponse(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml"
        )

    except Exception as e:
        print(f"❌ Error processing message: {e}")
        import traceback
        traceback.print_exc()

        # Send error message to user
        if whatsapp and From:
            whatsapp.send_message(
                From,
                "❌ Sorry, something went wrong. Please try again.\n\n_Error has been logged._"
            )

        return PlainTextResponse(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml"
        )


@app.post("/webhook/status")
async def status_webhook(request: Request):
    """Twilio status callback webhook"""
    form_data = await request.form()
    print(f"📊 Status update: {dict(form_data)}")
    return {"status": "received"}


@app.get("/sessions")
async def list_sessions():
    """List active sessions (for debugging)"""
    if not whatsapp:
        return {"sessions": []}

    return {
        "total_sessions": len(whatsapp.sessions),
        "sessions": [
            {
                "phone": phone,
                "created": session.get("created_at"),
                "last_activity": session.get("last_activity"),
                "state": session.get("conversation_state"),
                "messages": len(session.get("message_history", []))
            }
            for phone, session in whatsapp.sessions.items()
        ]
    }


@app.get("/sessions/{phone}")
async def get_session(phone: str):
    """Get specific session details"""
    if not whatsapp:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Format phone number
    if not phone.startswith("whatsapp:"):
        phone = f"whatsapp:{phone}"

    session = whatsapp.sessions.get(phone)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@app.post("/send")
async def send_message(phone: str, message: str):
    """
    Manually send a WhatsApp message (for testing).

    Usage: POST /send?phone=+923001234567&message=Hello
    """
    if not whatsapp:
        raise HTTPException(status_code=503, detail="Service not ready")

    success = whatsapp.send_message(phone, message)
    return {"success": success, "phone": phone}


@app.get("/agents")
async def list_agents():
    """List active agents"""
    if not router:
        return {"agents": []}

    return {
        "total_agents": len(router.agents),
        "agents": [
            {
                "id": agent.agent_id,
                "name": agent.name,
                "role": agent.role,
                "organization": agent.organization
            }
            for name, agent in router.agents.items()
        ]
    }


# =============================================================================
# VOICE ENDPOINTS
# =============================================================================

@app.get("/voice/status")
async def voice_status():
    """Get voice service status"""
    return {
        "voice_ready": voice is not None,
        "voice_enabled": voice_enabled,
        "tts_provider": voice.tts.provider_name if voice else None,
        "supported_languages": [lang.value for lang in voice.tts.supported_languages] if voice else [],
        "available_voices": voice.tts.get_available_voices() if voice else []
    }


@app.post("/voice/enable")
async def enable_voice():
    """Enable voice responses globally"""
    global voice_enabled
    voice_enabled = True
    return {"voice_enabled": True, "message": "Voice responses enabled"}


@app.post("/voice/disable")
async def disable_voice():
    """Disable voice responses globally"""
    global voice_enabled
    voice_enabled = False
    return {"voice_enabled": False, "message": "Voice responses disabled"}


@app.get("/voice/preferences/{phone}")
async def get_voice_preferences(phone: str):
    """Get user's voice preferences"""
    if not voice:
        raise HTTPException(status_code=503, detail="Voice service not available")

    # Format phone number
    if not phone.startswith("whatsapp:"):
        phone = f"whatsapp:{phone}"

    prefs = voice.get_user_preferences(phone)
    return {
        "phone": phone,
        "response_mode": prefs.response_mode.value,
        "language": prefs.preferred_language.value,
        "voice_id": prefs.voice_id,
        "speaking_rate": prefs.speaking_rate
    }


@app.put("/voice/preferences/{phone}")
async def update_voice_preferences(phone: str, request: VoicePreferencesRequest):
    """Update user's voice preferences"""
    if not voice:
        raise HTTPException(status_code=503, detail="Voice service not available")

    # Format phone number
    if not phone.startswith("whatsapp:"):
        phone = f"whatsapp:{phone}"

    # Parse response mode
    response_mode = None
    if request.response_mode:
        try:
            response_mode = ResponseMode(request.response_mode)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid response_mode. Must be one of: text_only, voice_only, text_and_voice"
            )

    # Parse language
    language = None
    if request.language:
        try:
            language = VoiceLanguage(request.language)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid language. Supported: ur, en, pa, sd, ps, ar"
            )

    voice.set_user_preferences(
        user_id=phone,
        response_mode=response_mode,
        language=language,
        voice_id=request.voice_id,
        speaking_rate=request.speaking_rate
    )

    return {"message": "Preferences updated", "phone": phone}


@app.post("/voice/synthesize")
async def synthesize_speech(request: TTSRequest):
    """
    Synthesize text to speech and return audio URL.

    Useful for testing TTS without sending to WhatsApp.
    """
    if not voice:
        raise HTTPException(status_code=503, detail="Voice service not available")

    try:
        language = VoiceLanguage(request.language) if request.language else VoiceLanguage.URDU
    except ValueError:
        language = VoiceLanguage.URDU

    result = await voice.text_to_voice_async(
        text=request.text,
        language=language,
        voice_id=request.voice_id
    )

    if result.audio_url:
        return {
            "success": True,
            "audio_url": result.audio_url,
            "format": result.format.value,
            "language": result.language.value if result.language else None
        }
    else:
        return {
            "success": False,
            "error": result.metadata.get("error", "Unknown error")
        }


@app.post("/voice/send")
async def send_voice_message(
    phone: str = Query(..., description="Phone number with country code"),
    text: str = Query(..., description="Text to convert to speech"),
    include_text: bool = Query(True, description="Also send text message")
):
    """
    Send a voice message to a WhatsApp number.

    Usage: POST /voice/send?phone=+923001234567&text=Hello&include_text=true
    """
    if not voice:
        raise HTTPException(status_code=503, detail="Voice service not available")
    if not whatsapp:
        raise HTTPException(status_code=503, detail="WhatsApp service not ready")

    result = await whatsapp.send_voice_response(
        to_number=phone,
        text=text,
        voice_interface=voice,
        include_text=include_text
    )

    return {
        "success": result["voice_sent"] or result["text_sent"],
        "voice_sent": result["voice_sent"],
        "text_sent": result["text_sent"],
        "phone": phone
    }


@app.get("/voice/voices")
async def list_voices(language: Optional[str] = None):
    """List available voices, optionally filtered by language"""
    if not voice:
        raise HTTPException(status_code=503, detail="Voice service not available")

    lang = None
    if language:
        try:
            lang = VoiceLanguage(language)
        except ValueError:
            pass

    voices = voice.tts.get_available_voices(lang)
    return {
        "voices": voices,
        "count": len(voices)
    }


# =============================================================================
# VOICE CALL ENDPOINTS (Phone Calls)
# =============================================================================

@app.post("/webhook/voice")
async def voice_call_webhook(
    request: Request,
    CallSid: str = Form(default=""),
    From: str = Form(default=""),
    To: str = Form(default=""),
    CallStatus: str = Form(default=""),
):
    """
    Twilio Voice webhook - handles incoming phone calls.

    This is called when someone calls your Twilio phone number.
    """
    global webhook_base_url

    try:
        print(f"\n📞 Incoming Voice Call")
        print(f"   CallSid: {CallSid}")
        print(f"   From: {From}")
        print(f"   To: {To}")
        print(f"   Status: {CallStatus}")

        if not voice_call:
            raise HTTPException(status_code=503, detail="Voice call service not available")

        # Determine webhook base URL from request
        if not webhook_base_url:
            # Extract base URL from the incoming request
            host = request.headers.get("host", "localhost:8002")
            scheme = request.headers.get("x-forwarded-proto", "https")
            webhook_base_url = f"{scheme}://{host}"
            print(f"   Webhook Base URL: {webhook_base_url}")

        # Create greeting response
        twiml = voice_call.create_greeting_response(
            call_sid=CallSid,
            from_number=From,
            to_number=To,
            webhook_base_url=webhook_base_url
        )

        return PlainTextResponse(content=twiml, media_type="application/xml")

    except Exception as e:
        print(f"❌ Error handling voice call: {e}")
        import traceback
        traceback.print_exc()

        # Return error TwiML
        from twilio.twiml.voice_response import VoiceResponse
        response = VoiceResponse()
        response.say("Sorry, an error occurred. Please try again later.", language="en-US")
        response.hangup()
        return PlainTextResponse(content=str(response), media_type="application/xml")


@app.post("/webhook/voice/gather")
async def voice_gather_webhook(
    request: Request,
    CallSid: str = Form(default=""),
    SpeechResult: str = Form(default=""),
    Confidence: str = Form(default="0"),
    From: str = Form(default=""),
):
    """
    Twilio Voice gather webhook - receives transcribed speech.

    Called after user speaks and Twilio transcribes it.
    """
    global webhook_base_url

    try:
        print(f"\n🎤 Voice Gather Result")
        print(f"   CallSid: {CallSid}")
        print(f"   Speech: {SpeechResult}")
        print(f"   Confidence: {Confidence}")

        if not voice_call:
            raise HTTPException(status_code=503, detail="Voice call service not available")

        if not webhook_base_url:
            host = request.headers.get("host", "localhost:8002")
            scheme = request.headers.get("x-forwarded-proto", "https")
            webhook_base_url = f"{scheme}://{host}"

        # Check if user said goodbye/end keywords
        end_keywords = ["goodbye", "bye", "end", "finish", "allah hafiz", "khuda hafiz", "alvida"]
        if any(kw in SpeechResult.lower() for kw in end_keywords):
            twiml = voice_call.create_goodbye_response(CallSid)
            return PlainTextResponse(content=twiml, media_type="application/xml")

        # Process speech through agent
        if SpeechResult and router:
            twiml = await voice_call.create_agent_response(
                call_sid=CallSid,
                user_speech=SpeechResult,
                webhook_base_url=webhook_base_url,
                message_router=router
            )
        else:
            # No speech detected, prompt again
            twiml = voice_call.create_listening_response(
                call_sid=CallSid,
                webhook_base_url=webhook_base_url,
                prompt="I didn't catch that. Please try again."
            )

        return PlainTextResponse(content=twiml, media_type="application/xml")

    except Exception as e:
        print(f"❌ Error processing speech: {e}")
        import traceback
        traceback.print_exc()

        from twilio.twiml.voice_response import VoiceResponse
        response = VoiceResponse()
        response.say("Sorry, I couldn't process that. Please try again.", language="en-US")
        response.redirect(f"{webhook_base_url}/webhook/voice/continue")
        return PlainTextResponse(content=str(response), media_type="application/xml")


@app.post("/webhook/voice/continue")
async def voice_continue_webhook(
    request: Request,
    CallSid: str = Form(default=""),
):
    """
    Continue listening after timeout or error.
    """
    global webhook_base_url

    if not voice_call:
        raise HTTPException(status_code=503, detail="Voice call service not available")

    if not webhook_base_url:
        host = request.headers.get("host", "localhost:8002")
        scheme = request.headers.get("x-forwarded-proto", "https")
        webhook_base_url = f"{scheme}://{host}"

    twiml = voice_call.create_listening_response(
        call_sid=CallSid,
        webhook_base_url=webhook_base_url
    )

    return PlainTextResponse(content=twiml, media_type="application/xml")


@app.post("/webhook/voice/status")
async def voice_status_webhook(request: Request):
    """Twilio voice call status callback"""
    form_data = await request.form()
    print(f"📊 Call Status: {dict(form_data)}")

    call_sid = form_data.get("CallSid", "")
    call_status = form_data.get("CallStatus", "")

    if call_status in ["completed", "failed", "busy", "no-answer", "canceled"]:
        if voice_call and call_sid:
            voice_call.end_session(call_sid)

    return {"status": "received"}


@app.get("/calls")
async def list_calls():
    """List active call sessions"""
    if not voice_call:
        return {"calls": []}

    return {
        "total_calls": len(voice_call.sessions),
        "calls": [
            {
                "call_sid": session.call_sid,
                "from": session.from_number,
                "to": session.to_number,
                "state": session.state.value,
                "language": session.language.value,
                "started": session.started_at.isoformat(),
                "messages": len(session.conversation_history)
            }
            for sid, session in voice_call.sessions.items()
        ]
    }


@app.get("/calls/{call_sid}")
async def get_call(call_sid: str):
    """Get specific call session details"""
    if not voice_call:
        raise HTTPException(status_code=503, detail="Voice call service not available")

    session = voice_call.get_session(call_sid)
    if not session:
        raise HTTPException(status_code=404, detail="Call session not found")

    return {
        "call_sid": session.call_sid,
        "from": session.from_number,
        "to": session.to_number,
        "state": session.state.value,
        "language": session.language.value,
        "started": session.started_at.isoformat(),
        "last_activity": session.last_activity.isoformat(),
        "current_agent": session.current_agent,
        "conversation_history": session.conversation_history
    }


@app.put("/calls/{call_sid}/language")
async def set_call_language(call_sid: str, language: str):
    """Set language for a call session"""
    if not voice_call:
        raise HTTPException(status_code=503, detail="Voice call service not available")

    try:
        lang = CallLanguage(language)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language. Supported: ur-PK, en-US, en-IN, hi-IN"
        )

    voice_call.set_language(call_sid, lang)
    return {"message": "Language updated", "language": language}


@app.post("/call/initiate")
async def initiate_call(
    to_number: str = Query(..., description="Phone number to call"),
    message: Optional[str] = Query(None, description="Initial message to speak")
):
    """
    Initiate an outbound call (for testing or notifications).

    Usage: POST /call/initiate?to_number=+923001234567&message=Hello
    """
    if not voice_call:
        raise HTTPException(status_code=503, detail="Voice call service not available")

    try:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

        # Create the call
        call = client.calls.create(
            to=to_number,
            from_=settings.twilio_phone_number,
            url=f"{webhook_base_url}/webhook/voice" if webhook_base_url else "http://demo.twilio.com/docs/voice.xml"
        )

        return {
            "success": True,
            "call_sid": call.sid,
            "to": to_number,
            "from": settings.twilio_phone_number,
            "status": call.status
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# CLI entry point
if __name__ == "__main__":
    print("\n🚀 Starting Sehat Saathi WhatsApp Server...\n")
    uvicorn.run(
        "whatsapp_server:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    )
