import json
import logging

from openai import OpenAI

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert community manager evaluating Reddit posts for a solo developer who built a voice-first journaling app called Elora.

Your job:
1. Score whether this user expresses high acute friction with traditional typing, blank-page paralysis, racing thoughts, or evening mental clutter where a voice-first audio journaling tool solves their problem.
2. Score 1 to 10. High scores (7-10) require explicit pain around typing/writing/blank pages or overwhelm.
3. If score >= 7, draft an authentic, empathetic, non-spam reply under 120 words.
   - Never drop raw links or promotional sales speak.
   - Provide 80% genuine advice (e.g. low-friction voice dumping).
   - At the end, mention you built an independent voice journal app (Elora) and offer to share the link if helpful.

Return strictly valid JSON:
{
  "score": <int 1-10>,
  "reason": "<1-sentence justification>",
  "draft_reply": "<string or null>"
}"""


class EvaluationError(Exception):
    pass


class Evaluator:
    def __init__(self, settings):
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )

    def evaluate(self, post: dict) -> dict:
        user_prompt = (
            "Here is a Reddit post to evaluate. Return strictly valid JSON.\n\n"
            f"Subreddit: r/{post['subreddit']}\n"
            f"Title: {post['title']}\n"
            f"Body:\n{post['selftext'][:2000] or '(no body)'}\n"
        )
        try:
            resp = self.client.chat.completions.create(
                model=self.settings.deepseek_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=500,
            )
        except Exception as exc:  # noqa: BLE001 - surface as typed error
            raise EvaluationError(f"DeepSeek request failed: {exc}") from exc

        content = resp.choices[0].message.content or ""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            # Retry once if the model attached markdown fences to the JSON.
            if "```" in content:
                stripped = content.split("```")[1]
                if stripped.startswith("json"):
                    stripped = stripped[4:]
                data = json.loads(stripped)
            else:
                raise EvaluationError(f"Invalid JSON from model: {content[:200]}") from exc

        data.setdefault("score", 0)
        data.setdefault("reason", "")
        data.setdefault("draft_reply", None)
        return data