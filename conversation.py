"""
Conversation manager: uses GPT-4 to generate realistic patient responses
and maintains per-call conversation history.
"""

import os
import json
import logging
from datetime import datetime, timezone
from openai import OpenAI

logger = logging.getLogger(__name__)

# In-memory store of active call sessions keyed by Twilio CallSid
_sessions: dict[str, dict] = {}

_openai_client: OpenAI | None = None


def _get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _openai_client

# GPT-4 model to use for generating responses
MODEL = "gpt-4o"

# System-level meta-instructions added to every scenario
META_INSTRUCTIONS = (
    "\n\nIMPORTANT BEHAVIORAL RULES:\n"
    "- You are on a PHONE CALL. Keep responses concise (1-3 sentences max) and natural.\n"
    "- Do NOT use markdown, bullet points, or lists in your responses.\n"
    "- Do NOT narrate actions (e.g. 'hangs up phone'). Just speak naturally.\n"
    "- When you want to end the call say exactly: 'Thank you, goodbye.' and nothing else after that.\n"
    "- If the agent seems confused or repeats itself, politely point that out.\n"
    "- If the agent says something incorrect or contradictory, gently note it.\n"
)


def start_session(call_sid: str, scenario: dict) -> None:
    """Initialize a new conversation session for the given call."""
    _sessions[call_sid] = {
        "scenario": scenario,
        "messages": [],  # full OpenAI message history
        "transcript": [],  # human-readable log [{role, text, timestamp}]
        "start_time": datetime.now(timezone.utc).isoformat(),
        "end_time": None,
    }
    logger.info("Started session %s for scenario '%s'", call_sid, scenario["id"])


def get_initial_message(call_sid: str) -> str:
    """Return the scenario's opening line (what the patient says first)."""
    session = _sessions.get(call_sid)
    if not session:
        return "Hello, I need some help please."
    initial = session["scenario"]["initial_message"]
    _record_turn(call_sid, "patient", initial)
    return initial


def generate_response(call_sid: str, agent_text: str) -> str:
    """
    Given what the agent just said, generate the patient's next response using GPT-4.
    Returns the response text. Returns empty string if the session is unknown.
    """
    session = _sessions.get(call_sid)
    if not session:
        logger.warning("generate_response called for unknown session %s", call_sid)
        return "Thank you, goodbye."

    # Record agent turn
    _record_turn(call_sid, "agent", agent_text)

    # Build system prompt
    system_prompt = session["scenario"]["system_prompt"] + META_INSTRUCTIONS

    # Build message list for OpenAI
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history (agent = assistant, patient = user)
    for turn in session["transcript"]:
        if turn["role"] == "agent":
            messages.append({"role": "assistant", "content": turn["text"]})
        else:
            messages.append({"role": "user", "content": turn["text"]})

    # The last message should be the agent's most recent line → ask GPT for patient reply
    # (transcript already has agent turn recorded above so last entry is agent)
    try:
        completion = _get_openai_client().chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=150,
            temperature=0.7,
        )
        response_text = completion.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("OpenAI error for session %s: %s", call_sid, exc)
        response_text = "I'm sorry, could you repeat that?"

    # Record patient turn
    _record_turn(call_sid, "patient", response_text)
    logger.info("[%s] Patient: %s", call_sid, response_text)
    return response_text


def is_call_ending(response_text: str) -> bool:
    """Heuristic: did GPT decide to end the call?"""
    endings = [
        "thank you, goodbye",
        "goodbye",
        "bye bye",
        "have a great day",
        "take care, bye",
    ]
    # Strip trailing punctuation before matching
    lower = response_text.lower().strip().rstrip(".!?,")
    return any(lower.endswith(e) or lower == e for e in endings)


def end_session(call_sid: str) -> dict | None:
    """Mark the session as ended and return the session data."""
    session = _sessions.get(call_sid)
    if session:
        session["end_time"] = datetime.now(timezone.utc).isoformat()
        logger.info("Ended session %s", call_sid)
    return session


def save_transcript(call_sid: str, transcripts_dir: str = "transcripts") -> str | None:
    """
    Save the session transcript to disk.
    Returns the filepath if saved, None otherwise.
    """
    session = _sessions.get(call_sid)
    if not session:
        return None

    os.makedirs(transcripts_dir, exist_ok=True)

    scenario_id = session["scenario"]["id"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{scenario_id}_{timestamp}_{call_sid[-8:]}"

    # Save JSON
    json_path = os.path.join(transcripts_dir, f"{base_name}.json")
    with open(json_path, "w") as f:
        json.dump(session, f, indent=2, default=str)

    # Save human-readable text transcript
    txt_path = os.path.join(transcripts_dir, f"{base_name}.txt")
    with open(txt_path, "w") as f:
        f.write(f"Call Transcript\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"Scenario: {session['scenario']['name']}\n")
        f.write(f"Call SID: {call_sid}\n")
        f.write(f"Start:    {session['start_time']}\n")
        f.write(f"End:      {session.get('end_time', 'N/A')}\n")
        f.write(f"{'=' * 60}\n\n")
        for turn in session["transcript"]:
            label = "AGENT  " if turn["role"] == "agent" else "PATIENT"
            f.write(f"[{turn['timestamp']}] {label}: {turn['text']}\n\n")

    logger.info("Saved transcript to %s", txt_path)
    return txt_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _record_turn(call_sid: str, role: str, text: str) -> None:
    session = _sessions.get(call_sid)
    if not session:
        return
    entry = {
        "role": role,
        "text": text,
        "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
    }
    session["transcript"].append(entry)
    logger.info("[%s] %s: %s", call_sid, role.upper(), text)
