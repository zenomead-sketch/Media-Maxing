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

The easiest Windows path is to double-click `start-media-maxing.bat` in the
project folder.

If you are using a terminal, run:

```powershell
python -m scripts.local_beta_launcher
```

This starts the local database/API bridge and the web app together, then opens
Control Center at `http://127.0.0.1:8044/#home`.

To practice with safe fake data, seed demo data by running
`python -m scripts.local_beta_launcher --seed-demo`.

Advanced/manual startup is still available for troubleshooting:

```powershell
python -m scripts.db.init_db --database data/app.sqlite
python -m scripts.db.seed_demo --database data/app.sqlite
python -m apps.api.local_server --database data/app.sqlite --port 8000
```

When the launcher is running, start from Control Center. It points you to the
next useful daily action and keeps setup/admin screens available in the sidebar.

## Demo-day QA

When you want to check the full local workflow, run `python -m scripts.demo_day_check`.

The demo-day check walks through onboarding, media, Generate, Drafts, Calendar,
Publish Queue, Manual Export, Analytics, Engagement Inbox, reply approval, AI
memory, weekly reports, Backup & Data, and Diagnostics. It does not call real
APIs, publish posts, or send replies.

## Use mock mode

Mock mode is the default. It lets you generate draft examples, mock analytics,
mock engagement items, and mock social account connections. Mock data is fake
and should not be treated as real business performance.

## Use local Ollama generation, optional

If your computer can run a local model, you can use Ollama for draft generation
without sending prompts to a cloud AI provider.

1. Install and start Ollama outside this app.
2. Pull the model named in `.env`, for example `ollama pull llama3.1:8b`.
3. In `.env`, set `ENABLE_LOCAL_AI_CALLS=true`.
4. Keep `LOCAL_AI_BASE_URL=http://127.0.0.1:11434`.
5. In Settings, choose `Local AI runtime, Ollama`.
6. Generate drafts normally.

If Ollama is not running or the model is missing, generation will show a local
AI error. Switch Settings back to mock mode to keep testing without Ollama.
Cloud AI APIs are still optional later configuration; do not paste API keys into
the browser UI.

## Add enough real media for better drafts

You can test the app with demo media, but real generation improves when the app
has enough of your own job photos and videos. Use 5 real media items as the
starter minimum, and aim for 20 before serious content planning. Strong local
libraries usually have 50 or more items; 100 or more gives the app excellent
content memory.

For the first 20, try to include before/after examples, finished job photos,
behind-the-scenes process, team/process shots, customer problem examples, and
seasonal or location-specific examples. The app will not block generation under
20 items; it will show guidance so you know why a draft may feel less specific.

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
