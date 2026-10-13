# reddit-intent-radar

A lightweight 24/7 background monitor that polls target subreddits, filters for
high-intent pain points (keyword match + DeepSeek V4 Flash evaluation), tracks
seen posts in SQLite, and routes high-scoring opportunities with draft replies
straight to a Telegram bot.

Built for **Elora**, a voice-first journaling app.

## Features

- **Reddit polling** via `praw` (OAuth, strict user-agent) — subreddits joined with `+`.
- **Two-stage filter**: cheap broad keyword matching first (no LLM token spend on noise), then DeepSeek scoring on matches only.
- **LLM evaluation**: DeepSeek V4 Flash via the OpenAI-compatible SDK. Returns a strict JSON `{"score", "reason", "draft_reply"}`.
- **SQLite dedupe**: every post is recorded once; unmatched posts are stored with score 0 so they're never re-scored or re-fetched.
- **Telegram alerts**: Markdown message with the score, reason, a tap-to-copy draft reply, and an inline button linking to the post.
- **Resilient loop**: configurable interval, exponential backoff (60s base, capped at 1h) on failures, graceful SIGINT/SIGTERM shutdown.

## Requirements

- Python 3.11+
- A Reddit **script** app: https://www.reddit.com/prefs/apps
- A DeepSeek API key (https://platform.deepseek.com) **or** OpenRouter key with model `deepseek/deepseek-v4-flash`
- A Telegram bot token (via @BotFather) and your chat ID (via @userinfobot)

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with your credentials
```

## Usage

```bash
python main.py                 # run the 24/7 monitor
python main.py --dry-run       # one live poll iteration, then exit
python main.py --test-eval     # send a sample post to DeepSeek, print parsed JSON
python main.py --test-telegram # send a dummy Telegram alert
```

The monitor is safe to run under a supervisor that restarts it on crash, e.g.:

```bash
while true; do python main.py; sleep 5; done
```

## Configuration (`.env`)

| Variable | Required | Default |
|---|---|---|
| `REDDIT_CLIENT_ID` | ✅ | — |
| `REDDIT_CLIENT_SECRET` | ✅ | — |
| `REDDIT_USERNAME` | ✅ | — |
| `DEEPSEEK_API_KEY` | ✅ | — |
| `DEEPSEEK_BASE_URL` | ❌ | `https://api.deepseek.com` (or `https://openrouter.ai/api/v1`) |
| `DEEPSEEK_MODEL` | ❌ | `deepseek-flash` (or `deepseek/deepseek-v4-flash`) |
| `TELEGRAM_BOT_TOKEN` | ✅ | — |
| `TELEGRAM_CHAT_ID` | ✅ | — |
| `POLL_INTERVAL_SECONDS` | ❌ | `900` (15 min; `0` runs one shot) |
| `TARGET_SUBREDDITS` | ❌ | `Journaling+ADHD+mindfulness+productivity+DecidingToBeBetter` |
| `MIN_INTENT_SCORE` | ❌ | `7` |
| `DB_PATH` | ❌ | `radar_cache.db` |

## How it works

1. Every poll cycle, grab the newest `25` posts across the target subreddits.
2. Skip anything already in the SQLite `processed_posts` table.
3. Match titles/body against the broad keyword list. No match → record with score 0, move on.
4. Keyword hits are sent to DeepSeek with a strict-JSON prompt. Score `>= MIN_INTENT_SCORE` → send Telegram alert with a drafted reply.
5. Every post is recorded so nothing is re-evaluated across restarts.

## Project layout

```
reddit-intent-radar/
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── config.py        # .env loading + strict validation
├── db.py            # SQLite dedupe store
├── reddit_client.py # praw + keyword filter
├── evaluator.py     # DeepSeek V4 Flash scoring + drafting
├── notifier.py      # Telegram alerts with inline keyboard
└── main.py          # orchestration, signals, backoff
```

## Verification checklist

```bash
python main.py --test-eval        # 1. DeepSeek key + model string verified, valid JSON printed
python main.py --test-telegram    # 2. bot token + chat id verified, dummy alert received
python main.py --dry-run          # 3. PRAW creds + DB persistence verified over live posts
```

## Notes

- Reddit API usage limits apply; keep `POLL_INTERVAL_SECONDS` at 300+ for most accounts.
- The LLM prompt explicitly forbids raw links and promotional spam; the draft reply is ~80% genuine advice, with Elora mentioned only at the end as an offer.