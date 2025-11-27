# Sehat Saathi - Multi-Agent Healthcare System

## 🏥 Advanced Multi-Agent Autonomy & Cross-System Communication

A truly autonomous multi-agent ecosystem for healthcare in Pakistan, where agents communicate peer-to-peer, negotiate, and make decisions across organizational boundaries.

## 🤖 Agent Architecture

### Patient-Side Agents (6 agents)
1. **Dr. Sameer** - Triage & symptom assessment
2. **Guide** - Navigation & appointment booking
3. **Haqdar** - Eligibility & insurance verification
4. **Yaadgar** - Medication reminders & pharmacy coordination
5. **Khandan** - Family health tracking
6. **Muhafiz** - Community health monitoring

### Provider-Side Agents (5 agents)
7. **Scheduler Agent** - Appointment management & bed availability
8. **Resource Agent** - Equipment, medicine stock, staff tracking
9. **Billing Agent** - Insurance & payment processing
10. **Clinical Agent** - Test results & treatment coordination
11. **Emergency Agent** - Critical care & ambulance dispatch

## 🔄 Key Features

- **Autonomous Decision Making**: Agents reason and make decisions independently
- **Peer-to-Peer Negotiation**: Agents negotiate across organizational boundaries
- **Real-time Communication**: MCP (Model Context Protocol) for agent messaging
- **Multi-Interface Support**: WhatsApp, Voice calls, Web interface
- **Real Pakistan Data**: Uses actual hospital, doctor, and medicine data

## 🚀 Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Run quick system test
python quick_test.py

# Run interactive demos
python main_demo.py
```

### Quick Test Output
```
✓ Loaded 5000+ hospitals
✓ Loaded 10000+ doctors
✓ Loaded 15000+ medicines
✓ 11+ agents registered
✅ ALL TESTS PASSED!
```

### Demo Scenarios Available
1. **Appointment Booking** - Multi-agent negotiation for doctor appointments
2. **Emergency Response** - Hospital coordination for critical cases
3. **Medicine Search** - Pharmacy coordination and price comparison

## 📖 Documentation

- **[SETUP.md](SETUP.md)** - Complete setup and installation guide
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture and design details

## 📊 Project Structure

```
sehat-saathi/
├── src/
│   ├── agents/
│   │   ├── patient/          # Patient-side agents
│   │   └── provider/         # Provider-side agents
│   ├── core/                 # Core agent framework
│   ├── mcp/                  # Agent communication protocol
│   ├── database/             # Data layer
│   ├── interfaces/           # WhatsApp, Voice, Web
│   └── utils/                # Utilities
├── data/                     # Hospital, doctor, medicine data
├── tests/                    # Test suite
└── config/                   # Configuration files
```

## 🔐 Security

- End-to-end encryption for patient data
- Agent authentication and authorization
- HIPAA/compliance logging
- Secure multi-party communication

## 📝 License

MIT License - Built for innovation in healthcare
