# Voice Agent Stress Tester

An automated voice bot that calls a medical AI agent, simulates realistic patient scenarios,
records the conversations, and identifies bugs or quality issues.

---

## Quick Start (single command after setup)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and fill in credentials
cp .env.example .env
# Edit .env with your Twilio credentials, HuggingFace token, and WEBHOOK_BASE_URL

# 3. In terminal 1 — start the webhook server
python server.py

# 4. In terminal 2 — expose the server publicly (requires ngrok)
ngrok http 5000
# Copy the https URL from ngrok output into WEBHOOK_BASE_URL in .env

# 5. In terminal 3 — run all test scenarios
python run.py --all
```

---

## Prerequisites

| Service | What you need |
|---------|---------------|
| **Twilio** | Account SID, Auth Token, a voice-capable phone number |
| **HuggingFace** | API token (free at https://huggingface.co/settings/tokens) |
| **ngrok** | [Install ngrok](https://ngrok.com/download) — free tier works fine |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```
TWILIO_ACCOUNT_SID=ACxxx...
TWILIO_AUTH_TOKEN=xxx...
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX   # Your Twilio number
HF_API_TOKEN=hf_xxx...             # HuggingFace token (for Mistral 7B)
WEBHOOK_BASE_URL=https://xxxx.ngrok.io   # From ngrok
TARGET_PHONE_NUMBER=+18054398008         # Test line (default)
PORT=5000                                 # Flask server port
```

---

## Running Individual Scenarios

```bash
# List all available scenarios
python run.py --list

# Run a specific scenario
python run.py --scenario appointment_scheduling

# Run the same scenario multiple times
python run.py --scenario medication_refill --count 3

# Run all scenarios with a 30-second gap between calls
python run.py --all --delay 30
```

### Available Scenarios

| ID | Description |
|----|-------------|
| `appointment_scheduling` | Simple checkup scheduling |
| `medication_refill` | Urgent prescription refill |
| `appointment_reschedule` | Move an existing appointment |
| `appointment_cancel` | Cancel without rescheduling |
| `office_hours_insurance` | New patient info gathering |
| `urgent_symptoms` | Chest tightness / triage |
| `lab_results` | Blood work result inquiry |
| `sunday_appointment_edge_case` | Weekend scheduling (closed) |
| `unclear_request` | Vague back pain complaint |
| `multiple_requests` | Three tasks in one call |
| `wrong_number_confusion` | Hard-of-hearing confused caller |
| `insurance_change` | Insurance update notification |

---

## How It Works

1. `run.py` uses the Twilio REST API to place an outbound call to the test number.
2. Twilio calls back our webhook server (`server.py`) with the scenario ID in the URL.
3. The server returns TwiML — the patient's opening line is played via `<Say>`,
   then `<Gather input="speech">` listens for the agent's reply.
4. Each agent utterance is sent to `/respond`, which calls Mistral 7B (via
   HuggingFace Inference API) to generate the next patient line in character, then loops back.
5. When Mistral 7B decides to end the call, a hangup is issued.
6. On call completion, Twilio POSTs to `/status` and the transcript is saved to `transcripts/`.

---

## Transcripts

Transcripts are saved to `transcripts/` in both `.json` and `.txt` formats
as each call completes.

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for design rationale.
