# Batch 7 Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish Batch 7 with plain-language documentation, one durable end-to-end local workflow test, and a complete local QA pass.

**Architecture:** Keep the existing local-first Python services and static localhost UI intact. Add documentation for manual and mock analytics, strengthen deterministic tests around formulas and the cross-service workflow, then verify that the local bridge still exposes no real publishing, reply sending, or analytics fetch behavior.

**Tech Stack:** Python standard library, SQLite, `unittest`, static HTML/CSS/JavaScript, localhost SQLite bridge.

---

### Task 1: Close Documentation Gaps

**Files:**
- Create: `docs/manual-analytics-entry.md`
- Create: `docs/mock-analytics.md`
- Modify: `README.md`
- Test: `tests/test_batch7_closeout_docs.py`

- [ ] Add a failing documentation contract test that requires both guides and their core safety language.
- [ ] Run `python -m unittest tests.test_batch7_closeout_docs` and confirm it fails because the files do not exist.
- [ ] Write both plain-language guides and link them from `README.md`.
- [ ] Run `python -m unittest tests.test_batch7_closeout_docs` and confirm it passes.

### Task 2: Add Batch 7 Workflow Verification

**Files:**
- Create: `tests/test_batch7_full_workflow.py`
- Modify: `tests/test_analytics_service.py`

- [ ] Add exact regression assertions for engagement rate, click-through rate, lead rate, and performance score formulas.
- [ ] Add one SQLite workflow test that marks a queue item manually exported, records manual analytics, generates insights, ingests mock engagement, generates and locally approves a reply suggestion, refreshes learning memory, generates a weekly report, reopens SQLite, and verifies persisted records.
- [ ] Assert the workflow uses `manual` and `mock` source labels and has no external reply-send capability.
- [ ] Run `python -m unittest tests.test_analytics_service tests.test_batch7_full_workflow`.

### Task 3: Complete Local QA

**Files:**
- Verify only.

- [ ] Run `python -m unittest discover tests`.
- [ ] Run `python -m compileall -q scripts apps tests`.
- [ ] Run `node --check` for every JavaScript file under `apps/web`.
- [ ] Run `git diff --check`.
- [ ] Initialize and seed an isolated SQLite database.
- [ ] Run the Batch 7 local services against the isolated database.
- [ ] Run the repository security scan and confirm no suspicious secret-like literals are present.
- [ ] Verify `http://127.0.0.1:8000/api/health` reports real publishing and real reply sending disabled.
- [ ] Verify Analytics and Engagement through the rendered local app.
