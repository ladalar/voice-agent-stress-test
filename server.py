"""
Flask webhook server that handles Twilio voice call events.

Flow per call:
1. Twilio dials the target number and POSTs to /voice when it connects.
2. /voice returns TwiML that plays the patient's opening line, then
   listens for the agent's response via <Gather>.
3. Each agent utterance is sent to /respond, which uses GPT-4 to generate
   the next patient line and loops back to <Gather>.
4. When the patient decides to end the call (GPT says goodbye), we hang up.
5. On status callbacks (/status) we save the transcript to disk.
"""

import os
import logging
from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from dotenv import load_dotenv

import conversation as conv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# TTS voice used for patient — "Polly.Joanna" is a Twilio/Amazon Polly neural voice
PATIENT_VOICE = "Polly.Joanna"
LANGUAGE = "en-US"

# How long Twilio waits for speech before considering it done (seconds)
SPEECH_TIMEOUT = "3"

# Maximum call length guard (seconds); Twilio will end the call if reached
MAX_CALL_DURATION = 300  # 5 minutes


# ---------------------------------------------------------------------------
# /voice  — initial handler when call connects
# ---------------------------------------------------------------------------

@app.route("/voice", methods=["POST"])
def voice():
    """
    Called by Twilio when the outbound call is answered.
    Reads the scenario from the URL query string, starts a session,
    and plays the patient's opening line while setting up a <Gather>
    to capture the agent's reply.
    """
    call_sid = request.form.get("CallSid", "unknown")
    scenario_id = request.args.get("scenario", "appointment_scheduling")

    from scenarios import SCENARIO_MAP
    scenario = SCENARIO_MAP.get(scenario_id)
    if scenario is None:
        logger.error("Unknown scenario '%s' for call %s", scenario_id, call_sid)
        resp = VoiceResponse()
        resp.say("Configuration error. Goodbye.")
        resp.hangup()
        return Response(str(resp), mimetype="text/xml")

    # Start GPT session
    conv.start_session(call_sid, scenario)
    opening = conv.get_initial_message(call_sid)

    resp = _build_gather_response(call_sid, opening)
    return Response(str(resp), mimetype="text/xml")


# ---------------------------------------------------------------------------
# /respond  — handles each agent utterance and returns next patient line
# ---------------------------------------------------------------------------

@app.route("/respond", methods=["POST"])
def respond():
    """
    Called by Twilio after <Gather> captures the agent's speech.
    Generates the next patient response via GPT-4 and loops.
    """
    call_sid = request.form.get("CallSid", "unknown")
    agent_speech = request.form.get("SpeechResult", "").strip()

    if not agent_speech:
        # Nothing heard — ask agent to repeat
        agent_speech = "(silence)"

    patient_reply = conv.generate_response(call_sid, agent_speech)

    if conv.is_call_ending(patient_reply):
        # Patient decided to hang up
        resp = VoiceResponse()
        resp.say(patient_reply, voice=PATIENT_VOICE, language=LANGUAGE)
        resp.pause(length=1)
        resp.hangup()
        return Response(str(resp), mimetype="text/xml")

    resp = _build_gather_response(call_sid, patient_reply)
    return Response(str(resp), mimetype="text/xml")


# ---------------------------------------------------------------------------
# /status  — Twilio status callback (called when call ends)
# ---------------------------------------------------------------------------

@app.route("/status", methods=["POST"])
def status():
    """
    Receives call status updates from Twilio.
    Saves the transcript when the call is completed.
    """
    call_sid = request.form.get("CallSid", "unknown")
    call_status = request.form.get("CallStatus", "unknown")
    logger.info("Call %s status: %s", call_sid, call_status)

    if call_status in ("completed", "failed", "busy", "no-answer", "canceled"):
        conv.end_session(call_sid)
        path = conv.save_transcript(call_sid)
        if path:
            logger.info("Transcript saved to %s", path)

    return Response("", status=204)


# ---------------------------------------------------------------------------
# /health  — simple liveness check
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _build_gather_response(call_sid: str, patient_text: str) -> VoiceResponse:
    """
    Build a TwiML VoiceResponse that:
    1. Says the patient_text
    2. Listens for agent speech (Gather)
    3. Falls through to a hangup if no speech is detected after the timeout
    """
    webhook_base = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
    resp = VoiceResponse()

    gather = Gather(
        input="speech",
        action=f"{webhook_base}/respond",
        method="POST",
        speechTimeout=SPEECH_TIMEOUT,
        language=LANGUAGE,
    )
    gather.say(patient_text, voice=PATIENT_VOICE, language=LANGUAGE)
    resp.append(gather)

    # If gather times out without hearing anything, say goodbye and hang up
    resp.say("I'm sorry, I didn't hear anything. Goodbye.", voice=PATIENT_VOICE, language=LANGUAGE)
    resp.hangup()
    return resp


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info("Starting webhook server on port %d", port)
    app.run(host="0.0.0.0", port=port, debug=False)
