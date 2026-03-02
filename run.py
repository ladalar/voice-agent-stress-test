"""
Entry point: make outbound calls from our voice bot to the test line.

Usage:
    # Run all scenarios (one call each)
    python run.py --all

    # Run a specific scenario
    python run.py --scenario appointment_scheduling

    # List available scenarios
    python run.py --list

    # Run multiple times (e.g., call the same scenario 3 times)
    python run.py --scenario medication_refill --count 3

Prerequisites:
    1. Copy .env.example to .env and fill in credentials.
    2. Start the webhook server: python server.py
    3. Expose it publicly: ngrok http 5000
    4. Update WEBHOOK_BASE_URL in .env with the ngrok URL.
    5. Run this script.
"""

import argparse
import os
import sys
import time
import logging
from dotenv import load_dotenv
from twilio.rest import Client

from scenarios import SCENARIOS, SCENARIO_MAP

load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s – %(message)s",
)
logger = logging.getLogger(__name__)


def make_call(scenario_id: str) -> str | None:
    """Initiate a single outbound call for the given scenario. Returns CallSid."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_PHONE_NUMBER")
    to_number = os.getenv("TARGET_PHONE_NUMBER")
    webhook_base = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")

    if not all([account_sid, auth_token, from_number, webhook_base]):
        logger.error(
            "Missing required environment variables. "
            "Check TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
            "TWILIO_PHONE_NUMBER, and WEBHOOK_BASE_URL in your .env file."
        )
        return None

    if scenario_id not in SCENARIO_MAP:
        logger.error("Unknown scenario: '%s'. Run --list to see available scenarios.", scenario_id)
        return None

    client = Client(account_sid, auth_token)

    voice_url = f"{webhook_base}/voice?scenario={scenario_id}"
    status_url = f"{webhook_base}/status"

    logger.info("Dialing %s with scenario '%s' ...", to_number, scenario_id)
    try:
        call = client.calls.create(
            url=voice_url,
            to=to_number,
            from_=from_number,
            status_callback=status_url,
            status_callback_method="POST",
            status_callback_event=["completed", "failed", "busy", "no-answer"],
            timeout=60,  # ring timeout in seconds
        )
        logger.info("Call initiated. SID: %s", call.sid)
        return call.sid
    except Exception as exc:
        logger.error("Failed to initiate call: %s", exc)
        return None


def list_scenarios() -> None:
    print("\nAvailable scenarios:")
    print("-" * 60)
    for s in SCENARIOS:
        print(f"  {s['id']:<35}  {s['name']}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Voice bot stress tester — makes outbound calls to the test line."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Run all scenarios (one call each)")
    group.add_argument("--scenario", metavar="SCENARIO_ID", help="Run a specific scenario")
    group.add_argument("--list", action="store_true", help="List available scenarios")
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        metavar="N",
        help="Number of times to call the same scenario (default: 1)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=30.0,
        metavar="SECONDS",
        help="Seconds to wait between calls when running multiple (default: 30)",
    )

    args = parser.parse_args()

    if args.list:
        list_scenarios()
        return

    scenarios_to_run: list[str] = []
    if args.all:
        scenarios_to_run = [s["id"] for s in SCENARIOS]
    else:
        scenarios_to_run = [args.scenario] * args.count

    if not scenarios_to_run:
        parser.print_help()
        sys.exit(1)

    call_sids = []
    for i, scenario_id in enumerate(scenarios_to_run):
        if i > 0:
            logger.info("Waiting %.0f seconds before next call ...", args.delay)
            time.sleep(args.delay)

        sid = make_call(scenario_id)
        if sid:
            call_sids.append({"scenario": scenario_id, "sid": sid})
    
    print(f"\n{'=' * 60}")
    print(f"Initiated {len(call_sids)} / {len(scenarios_to_run)} calls.")
    for entry in call_sids:
        print(f"  {entry['scenario']:<35}  {entry['sid']}")
    print(f"{'=' * 60}")
    print("\nTranscripts will be saved to the transcripts/ directory")
    print("as each call completes (via the /status webhook).\n")


if __name__ == "__main__":
    main()
