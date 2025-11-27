# Sehat Saathi - System Architecture

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PATIENT INTERFACE                        │
│              (WhatsApp, Voice, Web - Future)                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  PATIENT-SIDE AGENTS (6)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Dr.Sameer │  │  Guide   │  │ Haqdar   │  │ Yaadgar  │   │
│  │(Triage)  │  │(Navigate)│  │(Eligible)│  │(Medicine)│   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│  ┌──────────┐  ┌──────────┐                                │
│  │ Khandan  │  │ Muhafiz  │                                │
│  │(Family)  │  │(Community│                                │
│  └──────────┘  └──────────┘                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│             MCP SERVER (Communication Hub)                  │
│  • Agent Registry & Discovery                               │
│  • Message Routing                                          │
│  • Broadcast & Negotiation                                  │
│  • Authentication & Logging                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 PROVIDER-SIDE AGENTS (5 per hospital)       │
│                                                             │
│  Hospital 1          Hospital 2          Hospital 3        │
│  ┌────────────┐      ┌────────────┐      ┌────────────┐   │
│  │ Scheduler  │      │ Scheduler  │      │ Scheduler  │   │
│  │ Resource   │      │ Resource   │      │ Resource   │   │
│  │ Billing    │      │ Billing    │      │ Billing    │   │
│  │ Clinical   │      │ Clinical   │      │ Clinical   │   │
│  │ Emergency  │      │ Emergency  │      │ Emergency  │   │
│  └────────────┘      └────────────┘      └────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA LAYER                               │
│  • Hospital Database (5000+ hospitals)                      │
│  • Doctor Database (10000+ doctors)                         │
│  • Medicine Database (15000+ medicines)                     │
│  • Appointments, Emergency Cases (Runtime)                  │
└─────────────────────────────────────────────────────────────┘
```

## 🤖 Agent Architecture

### Base Agent Class
All agents inherit from `Agent` base class:

```python
class Agent:
    - agent_id: Unique identifier
    - name: Human-readable name
    - role: Agent role (triage, scheduler, etc.)
    - organization: patient-side or provider-side
    - system_prompt: Detailed instructions for behavior
    - tools: List of capabilities

    Methods:
    - reason(): Core AI reasoning using Gemini
    - process_message(): Handle incoming messages
    - send_message(): Create outgoing messages
    - negotiate(): Multi-agent negotiation
    - explain_decision(): Human-readable explanation
```

### Agent Reasoning Flow

```
1. Receive Input/Message
         ↓
2. Build Context (add relevant data)
         ↓
3. Send to Gemini AI
         ↓
4. Parse Response (extract JSON if present)
         ↓
5. Log Decision (audit trail)
         ↓
6. Return AgentResponse
```

## 🔄 MCP (Model Context Protocol) Server

### Key Components

1. **Agent Registry**
   - Maintains list of all active agents
   - Stores agent metadata (role, organization, capabilities)
   - Enables agent discovery by role/organization

2. **Message Router**
   - Routes point-to-point messages between agents
   - Handles broadcasts to multiple agents
   - Validates agent permissions
   - Logs all communications

3. **Negotiation Facilitator**
   - Coordinates multi-agent negotiations
   - Collects proposals and counter-proposals
   - Determines consensus or best option

### Message Structure

```json
{
  "message_id": "msg-uuid",
  "timestamp": "ISO-8601",
  "from_agent": {
    "id": "agent-002-guide",
    "name": "Guide",
    "role": "navigation",
    "organization": "patient-side"
  },
  "to_agent": {
    "id": "agent-101-scheduler-1",
    "name": "Scheduler (Hospital A)",
    "role": "scheduler",
    "organization": "provider-side"
  },
  "action": "request_appointment_slot",
  "payload": {
    "patient_id": "PAT-001",
    "urgency": "moderate",
    "preferred_time": "today_afternoon"
  },
  "priority": "normal",
  "requires_response": true
}
```

## 📊 Agent Communication Patterns

### Pattern 1: Point-to-Point
```
Guide Agent → Scheduler Agent: "Book appointment"
Scheduler Agent → Guide Agent: "Slot confirmed"
```

### Pattern 2: Broadcast
```
Emergency Agent → ALL Hospital Emergency Agents: "Critical case"
Hospital A: "Can accept"
Hospital B: "Cannot accept (at capacity)"
Hospital C: "Can accept as backup"
```

### Pattern 3: Negotiation
```
Yaadgar Agent → Multiple Pharmacy Resource Agents:
  "Need insulin, budget Rs. 3000"

Pharmacy A: "Available, Rs. 4200"
Pharmacy B: "Available, Rs. 2800 (generic)" ✓ SELECTED
Pharmacy C: "Out of stock"

Yaadgar → Patient: "Found at Pharmacy B, cheapest option"
```

### Pattern 4: Cascade
```
1. Dr. Sameer detects critical emergency
2. Triggers Guide Agent to broadcast to hospitals
3. Guide receives responses, selects best
4. Haqdar verifies insurance
5. Billing Agent pre-authorizes
6. Resource Agent reserves bed
7. Khandan notifies family
8. Muhafiz logs for community monitoring

All happens autonomously in <30 seconds
```

## 🗄️ Data Layer

### Database Manager
```python
class DatabaseManager:
    - hospitals_df: DataFrame of hospitals
    - doctors_df: DataFrame of doctors
    - medicines_df: DataFrame of medicines
    - appointments: Dict of active appointments
    - emergency_cases: Dict of emergency cases

    Methods:
    - search_hospitals(city, specialty, ...)
    - search_doctors(city, specialization, ...)
    - search_medicines(name, max_price, ...)
    - create_appointment()
    - create_emergency_case()
```

### Data Models
- **Hospital**: Name, location, beds, ICU, specialties, contact
- **Doctor**: Name, specialty, experience, fees, satisfaction, availability
- **Medicine**: Name, company, price, stock, generic alternatives
- **Appointment**: Patient, doctor, time, status, slot_id
- **EmergencyCase**: Patient, symptoms, severity, assigned hospital

## 🧠 AI Reasoning Engine

### Gemini Integration
- Model: gemini-2.0-flash-exp (configurable)
- Temperature: 0.7 (balanced creativity and consistency)
- Max Tokens: 2048

### Reasoning Process
1. Agent receives query/message
2. Builds comprehensive prompt with:
   - Agent's role and system instructions
   - Current context (patient data, options, etc.)
   - Specific task to perform
3. Sends to Gemini API
4. Parses structured response (JSON preferred)
5. Extracts decision + reasoning
6. Logs for audit trail

### Example Reasoning Prompt
```
You are Guide, a navigation specialist.

TASK: Find best hospital for patient

CONTEXT:
- Patient location: Karachi, Gulberg
- Urgency: High
- Specialty needed: Cardiology
- Insurance: Sehat Card verified

AVAILABLE HOSPITALS:
1. Jinnah Hospital: 4.2 km, ICU available, cardiology team on duty
2. Aga Khan: 6.8 km, ICU available, cardiology team on duty
3. Liaquat: 3.1 km, no ICU beds, cardiology available

Analyze and recommend in JSON format:
{
  "recommended_hospital": "...",
  "reasoning": "...",
  "alternatives": [...]
}
```

## 🔐 Security Architecture

### Authentication
- Each agent has unique agent_id
- Public key infrastructure (in production)
- MCP server validates all messages

### Authorization
- Agents can only perform actions in their capability list
- Cross-organizational communication requires MCP routing
- Emergency overrides for critical cases

### Privacy
- Patient data encrypted end-to-end
- Anonymization for community health monitoring
- No PHI in logs (only metadata)
- Audit trail for compliance

### Data Flow Security
```
Patient Data (PII) → Encrypted → Agent Reasoning (Local)
                                         ↓
Agent Decision → Anonymized → MCP Communication
                                         ↓
Community Health Data → Aggregated → No Individual Info
```

## ⚡ Performance Considerations

### Scalability
- Stateless agents (can be replicated)
- Async message processing
- In-memory caching for frequent queries
- Database connection pooling

### Latency Optimization
- Parallel agent queries (broadcast)
- Local reasoning (no external API calls except Gemini)
- Cached hospital/doctor/medicine data

### Resource Management
- Agent lifecycle management
- Connection pooling for database
- Rate limiting for Gemini API
- Graceful degradation on failures

## 🔮 Future Enhancements

### Phase 2: Real-time Interfaces
- WhatsApp integration (Twilio)
- Voice calls (speech-to-text/text-to-speech)
- Web dashboard

### Phase 3: Advanced AI
- Multi-modal inputs (medical images)
- Predictive analytics (outbreak prediction)
- Personalized health recommendations

### Phase 4: Ecosystem Integration
- Integration with NADRA for Sehat Card verification
- Integration with 1122 ambulance service
- Integration with DRAP medicine database
- Integration with lab systems for real results

### Phase 5: Research & Optimization
- Reinforcement learning for better negotiations
- Federated learning across hospitals
- Automated agent policy optimization
- A/B testing for agent strategies

---

**Architecture designed for:**
- ✅ Maximum autonomy
- ✅ Cross-organizational coordination
- ✅ Scalability to national level
- ✅ Privacy and security
- ✅ Real-world deployability in Pakistan's healthcare system
