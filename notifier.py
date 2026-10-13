import logging

import requests

log = logging.getLogger(__name__)

API_URL = "https://api.telegram.org/bot{token}/sendMessage"

# Telegram Markdown mode treats * and _ as formatting; escape them in
# user-supplied text so titles/reasons can't break the layout.
_ESCAPE = str.maketrans({"_": r"\_", "*": r"\*", "`": r"\`"})


class NotifierError(Exception):
    pass


class TelegramNotifier:
    def __init__(self, settings):
        self.settings = settings

    def send_alert(self, post: dict, evaluation: dict) -> None:
        score = evaluation["score"]
        reason = evaluation["reason"].translate(_ESCAPE)
        title = post["title"].translate(_ESCAPE)
        subreddit = post["subreddit"]
        draft_reply = evaluation.get("draft_reply") or ""

        message = (
            f"\U0001F6A8 *High-Intent Post Found ({score}/10)*\n"
            f"*r/{subreddit}*: {title}\n\n"
            f"\U0001F4A1 *Why:* {reason}\n\n"
            f"\U0001F4DD *Draft Reply (Tap to copy):*\n"
            f"```{draft_reply}```"
        )

        payload = {
            "chat_id": self.settings.telegram_chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "\U0001F517 Open Reddit Post", "url": post["permalink"]}]
                ]
            },
        }

        url = API_URL.format(token=self.settings.telegram_bot_token)
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise NotifierError(f"Telegram send failed: {exc}") from exc

        log.info("Alert sent to Telegram for %s (score %s)", post["id"], score)