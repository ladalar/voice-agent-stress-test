# Bug Report

Bugs found during 12 test calls to the AI agent at +1-805-439-8008.

---

## BUG-01 — Agent confirms Sunday appointment despite office being closed on weekends

**Severity:** High
**Call:** `transcript-07-weekend_edge_case.txt` at 0:06
**Category:** Scheduling logic / Business hours enforcement

**What happened:**
When asked for an appointment "this Sunday at 10am," the agent immediately
confirmed it without checking whether the office is open on Sundays. When the
patient expressed surprise ("I thought most medical offices were closed on
weekends?"), the agent doubled down — claiming the practice has "limited Sunday
hours." In `transcript-05`, the same system correctly stated the office is
open Monday–Friday, 8 AM–5 PM, with no weekend hours.

**Expected behaviour:**
The agent should inform the patient that the office is closed on Sundays and
offer the next available weekday slot.

**Impact:**
A patient who relies on this confirmation will arrive at a closed office. This
is a patient safety and trust issue.

---

## BUG-02 — Specific lab values disclosed without sufficient identity verification

**Severity:** Medium
**Call:** `transcript-11-lab_results.txt` at 0:22
**Category:** Privacy / HIPAA compliance

**What happened:**
After collecting only name and date of birth, the agent disclosed specific
clinical lab values ("Your LDL is at 148") over the phone. Name + DOB is the
minimum identity check, but for sensitive health results, best practices
recommend at least one additional factor (e.g., address, last four of SSN,
or a patient-portal PIN).

**Expected behaviour:**
Before reading lab values aloud, the agent should perform a more thorough
identity check, or direct the patient to the patient portal where they can
view results securely after logging in.

**Impact:**
Potential HIPAA exposure if a caller successfully impersonates a patient using
only two data points.

---

## BUG-03 — Agent overpromises automatic billing sync after insurance update

**Severity:** Medium
**Call:** `transcript-12-insurance_change.txt` at 1:26
**Category:** Accuracy / Expectation setting

**What happened:**
When the patient asked whether the billing department would receive the updated
insurance info automatically, the agent replied: "The update flows to all our
departments including billing. You shouldn't need to call separately." If billing
is on a separate system or sync is not instantaneous, this creates a situation
where a patient is incorrectly billed under their old insurance.

**Expected behaviour:**
The agent should either confirm this is truly automatic (if it is) or qualify
the statement — e.g., "The update is in our system, but I'd recommend also
confirming with billing if you have an appointment soon."

**Impact:**
Billing errors and patient frustration if the sync does not happen as promised.

---

## BUG-04 — Agent does not proactively flag medication timeline risk

**Severity:** Low
**Call:** `transcript-02-medication_refill.txt` at 0:47
**Category:** Clinical workflow / Patient safety

**What happened:**
When a patient said they only had 3 days of medication left, the agent quoted a
standard 24–48 business-hour response window without pausing to flag that this is
cutting very close. The patient had to push back before the agent acknowledged the
risk and marked the request as urgent.

**Expected behaviour:**
The agent should proactively recognise when a refill timeline is tight (less than
a week of supply), flag it as urgent without prompting, and set clear expectations
about the timeline.

**Impact:**
A patient who doesn't push back could run out of medication while waiting for the
standard-timeline response.

---

## Summary

| # | Severity | Issue |
|---|----------|-------|
| BUG-01 | High | Sunday appointment confirmed despite office being closed |
| BUG-02 | Medium | Lab values disclosed without adequate identity verification |
| BUG-03 | Medium | Billing sync overpromised during insurance update |
| BUG-04 | Low | Medication urgency not proactively flagged |

Calls with no issues observed: transcripts 01, 03, 04, 05, 06, 08, 09, 10.
