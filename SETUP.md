# Sehat Saathi - Setup & Installation Guide

## 🚀 Quick Start

### Prerequisites
- Python 3.9 or higher
- pip (Python package manager)
- Git

### Installation Steps

1. **Clone/Navigate to the repository:**
```bash
cd /home/anas/agentic
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Verify installation:**
```bash
python quick_test.py
```

This will:
- Initialize all 11 agents (6 patient-side + 5 provider-side)
- Test agent communication via MCP server
- Verify database access to real Pakistan healthcare data
- Show agent statistics

Expected output:
```
✓ Loaded 5000+ hospitals
✓ Loaded 10000+ doctors
✓ Loaded 15000+ medicines
✓ 11+ agents registered
✅ ALL TESTS PASSED!
```

## 🎬 Running Demos

### Interactive Demo (Recommended)
```bash
python main_demo.py
```

This launches an interactive menu where you can select from:
1. **Appointment Booking with Negotiation** - Watch patient agents negotiate with hospital schedulers
2. **Emergency Response** - See hospitals coordinate on critical cases
3. **Medicine Coordination** - Observe pharmacy agents finding best medicine options
4. **Run All Demos** - Complete showcase

### Individual Demo Scripts

Run specific scenarios directly:

```bash
# Demo 1: Appointment Booking
python -c "import asyncio; from src.demo.orchestrator import get_orchestrator; asyncio.run(get_orchestrator().scenario_appointment_booking('PAT-001', ['fever', 'cough'], 'Karachi'))"

# Demo 2: Emergency Response
python -c "import asyncio; from src.demo.orchestrator import get_orchestrator; asyncio.run(get_orchestrator().scenario_emergency_response('PAT-002', ['chest pain'], (24.8607, 67.0011)))"

# Demo 3: Medicine Search
python -c "import asyncio; from src.demo.orchestrator import get_orchestrator; asyncio.run(get_orchestrator().scenario_medicine_coordination('PAT-003', 'Insulin', 'Karachi'))"
```

## 📊 What You'll See

### Agent Communication Logs
The demos show real-time agent interactions:

```
📨 Guide → Scheduler (BHU Gulberg): request_appointment_slot
📨 Scheduler (BHU Gulberg) → Guide: available_slots (2 options)
🚨 Emergency (Jinnah Hospital): ACCEPTING emergency case - cardiac_emergency
   → ICU bed reserved, emergency team alerted
💊 Yaadgar: Found Insulin at 3 pharmacies, cheapest: Rs. 2,800
```

### Communication Trace Files
After each demo, a JSON trace file is exported to `logs/` containing:
- All agent-to-agent messages
- Decision reasoning
- Negotiation outcomes
- Timing information

These can be visualized or analyzed for research purposes.

## 🔧 Configuration

### Environment Variables
The system uses `.env` file for configuration:

```bash


### Adjusting Agent Behavior

Edit agent parameters in their respective files:
- `src/agents/patient/` - Patient-side agents
- `src/agents/provider/` - Provider-side agents

Example: Change Dr. Sameer's triage sensitivity:
```python
# src/agents/patient/dr_sameer.py
self.temperature = 0.5  # More conservative (default: 0.7)
```

## 🗄️ Data Sources

### Real Pakistan Healthcare Data
- **Hospitals**: 5,000+ facilities from across Pakistan
- **Doctors**: 10,000+ physicians with specializations, fees, ratings
- **Medicines**: 15,000+ medicines with prices from Pakistani pharmacies

Data files:
- `data/hospitals.csv` - Hospital information
- `data/doctors.csv` - Doctor profiles
- `data/medicines.csv` - Medicine catalog

### Mock Provider Data
For demo purposes, the following are simulated:
- Bed availability (ICU, general, emergency)
- Equipment status (ventilators, oxygen, monitors)
- Real-time appointment slots

In production, these would connect to actual Hospital Management Systems (HMS).

## 🏥 Provider-Side Integration

### For Hospitals: Integrating with Real HMS

To connect a real hospital system:

1. **Create provider config file:**
```python
# config/hospital_config.py
HOSPITAL_CONFIG = {
    "hospital_id": 1,
    "name": "Jinnah Hospital",
    "hms_api_url": "https://hospital-hms.example.com/api",
    "hms_api_key": "your-api-key"
}
```

2. **Update Resource Agent to use real data:**
```python
# src/agents/provider/resource.py
def check_resource_availability(self):
    # Instead of mock data:
    response = requests.get(
        f"{HMS_API_URL}/resources/beds",
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    return response.json()
```

3. **Register your hospital's agents:**
```python
orchestrator = get_orchestrator()
orchestrator.initialize_provider_agents(num_hospitals=1)
# Your hospital agents are now online and can receive patient requests
```

## 🔐 Security & Privacy

### Patient Data Anonymization
- All patient IDs are hashed before community health monitoring
- No PHI (Personal Health Information) is logged
- Agent communication logs contain only metadata

### HIPAA Compliance
- End-to-end encryption for sensitive data (configured in production)
- Audit trails for all agent interactions
- Role-based access control

## 📈 Monitoring & Logging

### View Agent Statistics
```python
from src.demo.orchestrator import get_orchestrator

orchestrator = get_orchestrator()
orchestrator.print_agent_statistics()
```

Output:
```
📊 AGENT COMMUNICATION STATISTICS
Total Agents Registered: 16
Active Agents: 16
Messages Sent: 45
Broadcasts: 3
Negotiations: 2
```

### Export Communication Trace
```python
orchestrator.export_communication_trace("logs/trace.json")
```

## 🧪 Testing

### Run Quick Test
```bash
python quick_test.py
```

### Run Full Test Suite (when implemented)
```bash
pytest tests/
```

## 🐛 Troubleshooting

### Issue: "No module named 'google.generativeai'"
```bash
pip install google-generativeai
```

### Issue: "Database file not found"
Check that CSV files exist:
```bash
ls -lh data/
```

### Issue: "Gemini API error"
Verify your API key is valid:
```bash
python -c "import google.generativeai as genai; genai.configure(api_key='YOUR_KEY'); print(genai.list_models())"
```

### Issue: Slow agent responses
- Reduce `gemini_temperature` in .env
- Use fewer hospitals: `orchestrator.initialize_all_agents(num_hospitals=1)`
- Increase `gemini_max_tokens` if responses are truncated

## 📚 Next Steps

1. **Run the quick test**: `python quick_test.py`
2. **Try interactive demo**: `python main_demo.py`
3. **Explore agent code**: Start with `src/agents/patient/dr_sameer.py`
4. **Read the architecture**: See `ARCHITECTURE.md` (if created)
5. **Integrate with WhatsApp**: See WhatsApp integration guide (next phase)

## 🤝 Contributing

This is a research prototype. To extend:

1. Add new agents by extending `Agent` base class
2. Add new capabilities by updating agent `system_prompt`
3. Add new scenarios in `src/demo/orchestrator.py`
4. Connect real hospital systems via provider interface

## 📧 Support

For issues or questions:
- Check logs in `logs/` directory
- Review agent decision logs via `agent.get_decision_log()`
- Examine MCP communication traces

---

**Built with ❤️ for Pakistan's healthcare**
