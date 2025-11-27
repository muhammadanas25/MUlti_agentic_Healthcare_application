# WhatsApp Integration Setup Guide

## Prerequisites

Your `.env` file already has the required Twilio credentials:
```


## Quick Start

### Step 1: Start the WhatsApp Server

```bash
python whatsapp_server.py
```

Or with uvicorn directly:
```bash
uvicorn whatsapp_server:app --reload --port 8000
```

### Step 2: Expose Local Server with ngrok

Since Twilio needs to reach your server, use ngrok to create a public URL:

```bash
# Install ngrok (if not installed)
# Ubuntu: sudo snap install ngrok
# Mac: brew install ngrok

# Start ngrok tunnel
ngrok http 8000
```

You'll see output like:
```
Forwarding    https://abc123.ngrok.io -> http://localhost:8000
```

Copy the **HTTPS** URL (e.g., `https://abc123.ngrok.io`)

### Step 3: Configure Twilio Webhook

1. Go to [Twilio Console](https://console.twilio.com/)
2. Navigate to **Messaging** → **Try it out** → **Send a WhatsApp message**
3. Or go to **Messaging** → **Settings** → **WhatsApp Sandbox Settings**
4. Set the webhook URL:
   - **When a message comes in**: `https://abc123.ngrok.io/webhook/whatsapp`
   - **Status callback URL**: `https://abc123.ngrok.io/webhook/status`
5. Click **Save**

### Step 4: Join the Sandbox

Send this message from your WhatsApp to **+1 415 523 8886**:
```
join <your-sandbox-code>
```

(Find your sandbox code in the Twilio Console under WhatsApp Sandbox)

### Step 5: Test It!

Send a message to the WhatsApp Sandbox number:
- "Hi" - Get welcome message
- "I have fever and headache" - Get symptom assessment
- "Find hospital in Karachi" - Get hospital recommendations
- "medicine Panadol" - Search for medicine
- "sehat card" - Check insurance eligibility

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    USER'S WHATSAPP                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    TWILIO SERVERS                           │
│              (WhatsApp Business API)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ Webhook POST
┌─────────────────────────────────────────────────────────────┐
│              NGROK TUNNEL (for local dev)                   │
│           https://abc123.ngrok.io                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│             FASTAPI SERVER (whatsapp_server.py)             │
│                  /webhook/whatsapp                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              MESSAGE ROUTER (message_router.py)             │
│           Detects intent, routes to agents                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    AI AGENTS                                │
│  Dr. Sameer | Guide | Haqdar | Yaadgar | Khandan | Muhafiz │
│             (Using Gemini AI for reasoning)                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               WHATSAPP INTERFACE                            │
│          Formats response, sends via Twilio                 │
└─────────────────────────────────────────────────────────────┘
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/health` | GET | Detailed health status |
| `/webhook/whatsapp` | POST | Twilio webhook (incoming messages) |
| `/webhook/status` | POST | Twilio status callbacks |
| `/sessions` | GET | List active sessions |
| `/sessions/{phone}` | GET | Get session details |
| `/send?phone=X&message=Y` | POST | Send message manually |
| `/agents` | GET | List active agents |

## Testing Without Twilio

You can test the API directly:

```bash
# Health check
curl http://localhost:8000/

# List agents
curl http://localhost:8000/agents

# Send a test message (simulates webhook)
curl -X POST http://localhost:8000/webhook/whatsapp \
  -d "Body=I have fever" \
  -d "From=whatsapp:+923001234567" \
  -d "To=whatsapp:+14155238886"
```

## Message Flow Examples

### Symptom Assessment
```
User: "mujhe bukhar hai aur sar dard"
→ Router detects: symptoms intent
→ Routes to: Dr. Sameer
→ Dr. Sameer: Assesses symptoms using Gemini AI
→ Response: Triage result with recommendations
```

### Hospital Search
```
User: "hospital near Gulberg Karachi"
→ Router detects: hospital intent, extracts "Gulberg, Karachi"
→ Routes to: Guide
→ Guide: Searches database, ranks by relevance
→ Response: Top hospitals with details
```

### Medicine Search
```
User: "dawa Panadol kahan milegi"
→ Router detects: medicine intent, extracts "Panadol"
→ Routes to: Yaadgar
→ Yaadgar: Searches pharmacies, compares prices
→ Response: Pharmacy options with prices
```

### Emergency
```
User: "chest pain breathing problem emergency"
→ Router detects: emergency keywords
→ Priority handling
→ Dr. Sameer: Critical assessment
→ Response: Emergency template with 1122, nearest hospital
→ Muhafiz: Logs for community monitoring
```

## Session Management

Sessions track:
- User's phone number
- Conversation history
- Current state (greeting, awaiting info, etc.)
- Patient information collected
- Last assessment results

Sessions persist in memory (use Redis for production).

## Troubleshooting

### "Webhook not receiving messages"
1. Check ngrok is running and URL is correct
2. Verify Twilio webhook URL is set
3. Check ngrok logs for incoming requests

### "Agent initialization failed"
1. Check Gemini API key in `.env`
2. Verify internet connection
3. Check for Python errors in console

### "Message not sending"
1. Verify Twilio credentials
2. Check phone number format (include country code)
3. Ensure sandbox is joined

### "Timeout errors"
1. Gemini API can be slow - increase timeouts
2. Check for rate limiting
3. Consider caching responses

## Production Deployment

For production:
1. Use a proper server (not ngrok)
2. Set up Redis for sessions
3. Use Twilio WhatsApp Business API (not sandbox)
4. Implement rate limiting
5. Add proper logging
6. Set up SSL/TLS
7. Configure CORS properly

## Example Conversation

```
User: Assalam o alaikum
Bot: 🏥 *Sehat Saathi - آپ کا صحت ساتھی*

     Assalam-o-Alaikum! Welcome to Sehat Saathi.

     I can help you with:
     1️⃣ Check symptoms & get advice
     2️⃣ Find nearby hospitals & doctors
     ...

User: mujhe 2 din se bukhar hai aur khansi bhi
Bot: 🏥 *Dr. Sameer - Assessment*

     ⚠️ Urgency: *MODERATE*

     📋 Possible conditions:
       • Viral fever
       • Common cold/flu
       • Respiratory infection

     ✅ *Recommendation:*
     Visit a general physician within 24-48 hours...

     🚨 *Watch for:*
       • Temperature above 103°F
       • Difficulty breathing
       • Persistent chest pain

User: koi hospital batao Karachi mein
Bot: 🏥 *Hospital Recommendation*

     *Jinnah Postgraduate Medical Centre*
     _Large hospital with all specialties_

     📍 *Other options:*
       • Civil Hospital Karachi
       • Aga Khan University Hospital
```
