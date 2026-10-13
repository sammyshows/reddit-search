import argparse
import json
import logging
import signal
import sys
import time

from config import Settings
from db import Database
from evaluator import EvaluationError, Evaluator
from notifier import NotifierError, TelegramNotifier
from reddit_client import RedditClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("radar")

SHUTDOWN = False
MAX_BACKOFF_SECONDS = 3600
BASE_BACKOFF_SECONDS = 60


def _handle_signal(signum, frame):  # noqa: ARG001
    global SHUTDOWN
    log.info("Received signal %s, shutting down gracefully...", signum)
    SHUTDOWN = True


def _sleep(seconds: float) -> None:
    """Sleep in small slices so SIGINT/SIGTERM are handled promptly."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not SHUTDOWN:
        time.sleep(min(1.0, deadline - time.monotonic()))


def run_poll_cycle(reddit: RedditClient, evaluator: Evaluator, notifier: TelegramNotifier, settings: Settings, db: Database) -> None:
    for post in reddit.fetch_new_candidate_posts(limit=25):
        if SHUTDOWN:
            return
        log.info("Evaluating %s with DeepSeek...", post["id"])
        evaluation = evaluator.evaluate(post)
        log.info("Post %s scored %s/10: %s", post["id"], evaluation["score"], evaluation["reason"])
        score = int(evaluation.get("score", 0))
        db.record_post(post["id"], post["title"], post["subreddit"], score)
        if score >= settings.min_intent_score:
            notifier.send_alert(post, evaluation)


def run(settings: Settings, one_shot: bool = False) -> None:
    global SHUTDOWN

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    db = Database(settings.db_path)
    db.prune_old_records(days=30)

    reddit = RedditClient(settings, db)
    evaluator = Evaluator(settings)
    notifier = TelegramNotifier(settings)

    log.info(
        "reddit-intent-radar v1.0 | subreddits=%s | interval=%ss | min_score=%s | model=%s",
        settings.target_subreddits,
        settings.poll_interval_seconds,
        settings.min_intent_score,
        settings.deepseek_model,
    )

    consecutive_failures = 0
    try:
        while not SHUTDOWN:
            try:
                run_poll_cycle(reddit, evaluator, notifier, settings, db)
                consecutive_failures = 0
            except Exception as exc:  # noqa: BLE001
                consecutive_failures += 1
                backoff = min(BASE_BACKOFF_SECONDS * (2 ** (consecutive_failures - 1)), MAX_BACKOFF_SECONDS)
                log.error("Error during poll cycle: %s", exc, exc_info=True)
                log.error("Retrying in %ss...", backoff)
                _sleep(backoff)
                continue

            if one_shot or settings.poll_interval_seconds == 0:
                log.info("One-shot run complete.")
                break
            _sleep(settings.poll_interval_seconds)
    finally:
        db.close()
        log.info("radar stopped.")


def test_eval(settings: Settings) -> None:
    sample = {
        "id": "test_post_1",
        "title": "I hate typing out everything and staring at a blank page every night",
        "selftext": "My brain is a mess of racing thoughts by the evening. I can't journal because writing takes forever and I get stuck on the blank page. Wish I could just talk it out.",
        "subreddit": "Journaling",
        "score": 42,
        "created_utc": int(time.time()),
        "permalink": "https://reddit.com/r/Journaling/comments/test/test",
        "url": "",
    }
    evaluator = Evaluator(settings)
    result = evaluator.evaluate(sample)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if 1 <= int(result.get("score", 0)) <= 10:
        print("\nPASS: received valid scored JSON from DeepSeek.")
    else:
        print("\nWARNING: score out of range or unexpected.")


def test_telegram(settings: Settings) -> None:
    notifier = TelegramNotifier(settings)
    dummy = {
        "id": "test_telegram",
        "title": "Test alert — verify your bot is wired up",
        "subreddit": "Journaling",
        "score": 8,
        "created_utc": int(time.time()),
        "permalink": "https://reddit.com/r/Journaling/comments/test/test",
        "url": "",
        "selftext": "",
    }
    evaluation = {
        "score": 8,
        "reason": "This is a dummy message sent via --test-telegram.",
        "draft_reply": "Looks like a perfect storm for a voice journal. If you want, I built one (Elora) — happy to share the link.",
    }
    notifier.send_alert(dummy, evaluation)
    print("PASS: dummy alert sent to Telegram.")


def main() -> None:
    parser = argparse.ArgumentParser(description="24/7 Reddit high-intent monitor for Elora")
    parser.add_argument("--test-eval", action="store_true", help="Send a hardcoded sample post to DeepSeek and print parsed JSON")
    parser.add_argument("--test-telegram", action="store_true", help="Send a dummy Telegram notification")
    parser.add_argument("--dry-run", action="store_true", help="Run one poll iteration over live Reddit and exit")
    args = parser.parse_args()

    try:
        settings = Settings.from_env()
    except (RuntimeError, ValueError) as exc:
        log.error("Configuration error: %s", exc)
        sys.exit(1)

    if args.test_eval:
        test_eval(settings)
    elif args.test_telegram:
        test_telegram(settings)
    elif args.dry_run:
        run(settings, one_shot=True)
    else:
        run(settings)


if __name__ == "__main__":
    main()