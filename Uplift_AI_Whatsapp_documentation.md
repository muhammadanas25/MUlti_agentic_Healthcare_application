Build with Uplift AI
WhatsApp Voice Bot Tutorial

Build a voice-enabled WhatsApp bot with Uplift AI TTS
Prerequisites: WhatsApp Business API access and an Uplift AI API key
​
Overview
This tutorial shows you how to build a WhatsApp bot that can send voice messages using Uplift AI’s text-to-speech API. Perfect for customer support, notifications, or interactive voice responses.
​
Architecture

WhatsApp User

WhatsApp Cloud API

Your Webhook Server

Uplift AI TTS API

Audio URL
​
Step 1: Setup WhatsApp Business API
1

Create Meta App
Visit developers.facebook.com and create a new app with WhatsApp product
2

Get Credentials
Note down your:

    WhatsApp Business Account ID
    Phone Number ID
    Access Token
    Webhook Verify Token

3

Configure Webhook
Set your webhook URL and subscribe to messages events
​
Step 2: Build the Webhook Server
​
Node.js Implementation
Copy

// server.js
const express = require('express');
const axios = require('axios');
const app = express();

app.use(express.json());

// WhatsApp webhook verification
app.get('/webhook', (req, res) => {
  const verify_token = process.env.WEBHOOK_VERIFY_TOKEN;
  
  if (req.query['hub.verify_token'] === verify_token) {
    res.send(req.query['hub.challenge']);
  } else {
    res.sendStatus(403);
  }
});

// Handle incoming messages
app.post('/webhook', async (req, res) => {
  const { entry } = req.body;
  
  if (entry?.[0]?.changes?.[0]?.value?.messages) {
    const message = entry[0].changes[0].value.messages[0];
    const from = message.from;
    const text = message.text?.body;
    
    if (text) {
      // Process message and send voice response
      await handleMessage(from, text);
    }
  }
  
  res.sendStatus(200);
});

async function handleMessage(phoneNumber, userMessage) {
  // Generate response text (you can use AI here)
  const responseText = generateResponse(userMessage);
  
  // Convert to speech using Uplift AI
  const audioUrl = await generateVoiceMessage(responseText);
  
  // Send audio to WhatsApp
  await sendWhatsAppAudio(phoneNumber, audioUrl);
}

async function generateVoiceMessage(text) {
  const response = await axios.post(
    'https://api.upliftai.org/v1/synthesis/text-to-speech-async',
    {
      voiceId: 'v_8eelc901',
      text: text,
      outputFormat: 'MP3_22050_64' // Optimized for WhatsApp
    },
    {
      headers: {
        'Authorization': `Bearer ${process.env.UPLIFT_API_KEY}`,
        'Content-Type': 'application/json'
      }
    }
  );
  
  const { mediaId, token } = response.data;
  return `https://api.upliftai.org/v1/synthesis/stream-audio/${mediaId}?token=${token}`;
}

async function sendWhatsAppAudio(to, audioUrl) {
  await axios.post(
    `https://graph.facebook.com/v17.0/${process.env.PHONE_NUMBER_ID}/messages`,
    {
      messaging_product: 'whatsapp',
      to: to,
      type: 'audio',
      audio: {
        link: audioUrl
      }
    },
    {
      headers: {
        'Authorization': `Bearer ${process.env.WHATSAPP_ACCESS_TOKEN}`,
        'Content-Type': 'application/json'
      }
    }
  );
}

function generateResponse(userMessage) {
  // Simple response logic (replace with AI)
  const responses = {
    'hello': 'السلام علیکم! میں آپ کی کیسے مدد کر سکتی ہوں؟',
    'help': 'میں یہاں آپ کی مدد کے لیے ہوں۔ آپ کوئی بھی سوال پوچھ سکتے ہیں۔',
    'default': 'آپ کا پیغام موصول ہوا۔ جلد ہی جواب دیا جائے گا۔'
  };
  
  const key = userMessage.toLowerCase();
  return responses[key] || responses.default;
}

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Webhook server running on port ${PORT}`);
});

​
Step 3: Environment Configuration
Create a .env file:
Copy

# WhatsApp Configuration
WHATSAPP_ACCESS_TOKEN=your_whatsapp_token
PHONE_NUMBER_ID=your_phone_number_id
WEBHOOK_VERIFY_TOKEN=your_custom_verify_token

# Uplift AI Configuration
UPLIFT_API_KEY=sk_api_your_uplift_key

# Server Configuration
PORT=3000

​
Step 4: Deploy Your Bot
​
Using ngrok (Development)
Copy

# Install ngrok
npm install -g ngrok

# Start your server
node server.js

# In another terminal, expose it
ngrok http 3000

# Use the HTTPS URL for WhatsApp webhook

​
Production Deployment
Deploy to any cloud platform that supports Node.js:

    Vercel
    Railway
    Heroku
    AWS Lambda

​
Best Practices
Audio Optimization

    Use MP3_22050_64 for WhatsApp (smaller files)
    Keep messages under 30 seconds
    Test audio quality on different devices

Error Handling

    Implement retry logic for TTS API
    Queue messages during high load
    Log all webhook events for debugging

​
Next Steps
Add AI Intelligence
Integrate with ChatGPT or Claude for dynamic responses
Multi-Language Support
Support English, Urdu, and regional languages