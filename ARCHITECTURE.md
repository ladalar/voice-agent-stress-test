# Architecture

## System Overview

The voice bot is built around three components: a **Twilio call orchestrator**,
a **Flask webhook server**, and a **Mistral 7B conversation engine** (served via
the HuggingFace Inference API).

When a test run is initiated via `run.py`, the Twilio REST API places an outbound
call to the target number (+1-805-439-8008). The `url` parameter in that API call
points to our webhook server, passing the selected patient scenario ID in the query
string. When the call is answered, Twilio hits `/voice` and we return TwiML
containing `<Gather input="speech">` — this plays the patient's opening line
(via Twilio's Polly neural TTS) and then listens for the agent's reply.

Every agent utterance is posted to `/respond`. We pass the transcribed speech
to `conversation.py`, which builds the full conversation history and calls
Mistral 7B (via the HuggingFace Inference API) with a persona-specific system
prompt. Mistral generates the next patient line in character, which we speak
back via a new `<Gather>` loop.
When the model chooses to end the call (it says "Thank you, goodbye."), we
play the farewell and issue a `<Hangup>`. On call completion, Twilio fires the
`/status` webhook and we persist the transcript to disk in both JSON and
human-readable text formats.

## Key Design Choices

**Twilio `<Gather input="speech">` instead of Media Streams.**
A WebSocket media-stream approach would give lower latency but requires
significantly more infrastructure (audio encoding/decoding, a streaming STT
pipeline, TTS audio generation served over HTTP, buffer management). For a
stress-testing tool where conversation quality matters more than sub-second
latency, the `<Gather>` round-trip (≈2–4 s per turn) is an acceptable trade-off
that keeps the codebase simple and debuggable.

**Twilio Polly TTS instead of a separate TTS API.**
Using Twilio's built-in Amazon Polly voices eliminates the need to generate,
host, and serve audio files. This reduces moving parts and cost while still
producing natural-sounding speech adequate for testing the agent.

**Mistral 7B (HuggingFace Inference API) for patient personas.**
Mistral 7B Instruct produces realistic, contextually appropriate patient
dialogue at no cost beyond the free HuggingFace Inference tier. The
system prompt per scenario captures personality, goals, and behavioural
guardrails (e.g., "be persistent about Sunday", "ask to repeat if confused").
A meta-instruction block enforces phone-appropriate brevity and a clear
end-call signal ("Thank you, goodbye.") so the bot terminates cleanly.
Using `InferenceClient.chat_completion()` from `huggingface-hub` keeps the
interface nearly identical to the OpenAI SDK, making the model easy to swap.

**In-memory session state.**
Active call state (conversation history, scenario, timestamps) is stored in a
Python dict keyed by Twilio's `CallSid`. This is sufficient for a single-process
stress-testing tool and avoids database complexity. If horizontal scaling were
needed, Redis would be a straightforward drop-in.

**Scenario-driven testing.**
Rather than random or scripted dialogue, each call is driven by a GPT persona
with a defined goal. This produces natural variation across runs (different
phrasing, follow-up questions) while keeping each call focused on a specific
test case (scheduling, refills, edge cases, etc.). New scenarios can be added
in `scenarios.py` with no code changes elsewhere.
