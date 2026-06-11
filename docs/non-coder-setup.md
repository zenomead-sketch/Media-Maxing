# Non-Coder Setup

This setup path is for someone who does not want to edit code. Real publishing
is disabled. Mock mode lets you use the app locally without API keys.

## Install dependencies

There is no package manager setup yet. The app currently uses Python standard
library services, static HTML, CSS, and JavaScript. You need Python available on
your machine. Node is only used for JavaScript syntax checks by builders.

## Copy the environment file

Copy `.env.example` to `.env` if you need local configuration. This is the only
copy step most users need. Keep `.env`
private. Do not commit it.

Values you may add later:

- `LOCAL_DATA_DIR` if you want app data somewhere other than `./data`.
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` only when real AI providers are
  intentionally enabled later.
- Social platform client IDs and secrets only when future real OAuth work is
  ready.

Do not add fake real credentials to docs, commits, issues, or screenshots.

## Run the app

Initialize the database: `python -m scripts.db.init_db --database data/app.sqlite`.

Seed demo data: use this to seed demo data for practice:
`python -m scripts.db.seed_demo --database data/app.sqlite`.

Start the local app: `python -m apps.api.local_server --database data/app.sqlite --port 8000`.

Open the app at `http://127.0.0.1:8000`.

## Use mock mode

Mock mode is the default. It lets you generate draft examples, mock analytics,
mock engagement items, and mock social account connections. Mock data is fake
and should not be treated as real business performance.

## What not to touch

Do not edit database files directly. Do not edit migration files unless a
builder tells you to. Do not commit `.env`, local media, exports, backups, logs,
or secret values. Do not turn on real publishing flags unless a future release
explicitly implements real publishing safety gates.

## Avoid committing secrets

Do not commit API keys, OAuth tokens, client secrets, authorization codes, or
provider responses. If you think a secret was committed, stop and ask Claude
Code or Codex for a secret cleanup plan before sharing the repo.

## How to ask Claude Code or Codex

Use plain requests like:

- "Read AGENTS.md first, run diagnostics, and tell me why the app will not start."
- "Read AGENTS.md first, run tests, and fix the draft scheduling error."
- "Read AGENTS.md first, check for secrets, and summarize any risky files."

Ask the builder to report commands run and failures honestly.
