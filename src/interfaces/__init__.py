"""Interfaces - WhatsApp, Voice, Web, CLI"""
from .whatsapp import WhatsAppInterface, get_whatsapp_interface
from .voice import VoiceInterface, get_voice_interface, ResponseMode, VoiceMessage, VoiceLanguage
from .voice_call import VoiceCallInterface, get_voice_call_interface, CallLanguage, CallState
from .message_router import MessageRouter, get_message_router
from .cli_tester import CLITester

__all__ = [
    # WhatsApp
    "WhatsAppInterface",
    "get_whatsapp_interface",
    # Voice (TTS/WhatsApp audio)
    "VoiceInterface",
    "get_voice_interface",
    "ResponseMode",
    "VoiceMessage",
    "VoiceLanguage",
    # Voice Call (Phone)
    "VoiceCallInterface",
    "get_voice_call_interface",
    "CallLanguage",
    "CallState",
    # Message Router
    "MessageRouter",
    "get_message_router",
    # CLI Tester
    "CLITester",
]
