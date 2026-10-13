import logging
from typing import Iterator

import praw

from db import Database

log = logging.getLogger(__name__)

KEYWORDS = [
    "blank page",
    "hate writing",
    "hate typing",
    "can't journal",
    "racing thoughts",
    "brain dump",
    "audio",
    "voice",
    "speech to text",
    "overthinking",
    "paralysis",
]


def _normalize(text: str) -> str:
    return text.lower().replace("\u2019", "'").replace("-", " ")


def _matches_keywords(title: str, selftext: str) -> bool:
    body = _normalize(f"{title} {selftext}")
    return any(keyword in body for keyword in KEYWORDS)


class RedditClient:
    def __init__(self, settings, db: Database):
        self.settings = settings
        self.db = db
        self.reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            username=settings.reddit_username,
            user_agent=settings.reddit_user_agent,
        )

    def fetch_new_candidate_posts(self, limit: int = 25) -> Iterator[dict]:
        """Yield dicts for unprocessed posts that match the broad keyword filter.

        Posts that don't match keywords are recorded with score 0 and skipped
        so we never burn LLM tokens (or re-check them) again.
        """
        for submission in self.reddit.subreddit(self.settings.target_subreddits).new(limit=limit):
            if self.db.is_post_processed(submission.id):
                continue

            post = {
                "id": submission.id,
                "title": submission.title,
                "selftext": submission.selftext or "",
                "subreddit": submission.subreddit.display_name,
                "score": submission.score,
                "created_utc": int(submission.created_utc),
                "permalink": f"https://reddit.com{submission.permalink}",
                "url": submission.url,
            }

            if _matches_keywords(post["title"], post["selftext"]):
                log.info(
                    "Candidate %s r/%s: %r", post["id"], post["subreddit"], post["title"]
                )
                yield post
            else:
                self.db.record_post(
                    post["id"], post["title"], post["subreddit"], post["score"]
                )
                log.debug("No keyword match, recorded %s (score 0)", post["id"])