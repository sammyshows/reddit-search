import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

load_dotenv()

DEFAULT_SUBREDDITS = "+".join(
    ["Journaling", "ADHD", "mindfulness", "productivity", "DecidingToBeBetter"]
)

_REQUIRED = (
    "REDDIT_CLIENT_ID",
    "REDDIT_CLIENT_SECRET",
    "REDDIT_USERNAME",
    "DEEPSEEK_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)


def _env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


class Settings(BaseModel):
    reddit_client_id: str = Field(min_length=1)
    reddit_client_secret: str = Field(min_length=1)
    reddit_username: str = Field(min_length=1)
    deepseek_api_key: str = Field(min_length=1)
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    telegram_bot_token: str = Field(min_length=1)
    telegram_chat_id: str = Field(min_length=1)
    poll_interval_seconds: int = 900
    target_subreddits: str = DEFAULT_SUBREDDITS
    min_intent_score: int = 7
    db_path: str = "radar_cache.db"

    @field_validator("poll_interval_seconds")
    @classmethod
    def _interval_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("POLL_INTERVAL_SECONDS must be >= 0")
        return v

    @field_validator("min_intent_score")
    @classmethod
    def _score_range(cls, v: int) -> int:
        if not 1 <= v <= 10:
            raise ValueError("MIN_INTENT_SCORE must be between 1 and 10")
        return v

    @classmethod
    def from_env(cls) -> "Settings":
        missing = [key for key in _REQUIRED if not _env(key)]
        if missing:
            raise RuntimeError(
                "Missing required env vars: "
                + ", ".join(missing)
                + ". Copy .env.example to .env and fill in values."
            )
        return cls(
            reddit_client_id=_env("REDDIT_CLIENT_ID"),
            reddit_client_secret=_env("REDDIT_CLIENT_SECRET"),
            reddit_username=_env("REDDIT_USERNAME"),
            deepseek_api_key=_env("DEEPSEEK_API_KEY"),
            deepseek_base_url=_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            deepseek_model=_env("DEEPSEEK_MODEL", "deepseek-flash"),
            telegram_bot_token=_env("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_env("TELEGRAM_CHAT_ID"),
            poll_interval_seconds=int(_env("POLL_INTERVAL_SECONDS", "900")),
            target_subreddits=_env("TARGET_SUBREDDITS", DEFAULT_SUBREDDITS),
            min_intent_score=int(_env("MIN_INTENT_SCORE", "7")),
            db_path=_env("DB_PATH", "radar_cache.db"),
        )

    @property
    def reddit_user_agent(self) -> str:
        return f"macos:reddit-intent-radar:v1.0 (by /u/{self.reddit_username})"