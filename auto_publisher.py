"""
Auto-publisher for InkDrive.

Runs as a background job (via APScheduler) or standalone cron script.
Each run:
  1. Loads AutoPublishConfig from DB — skips if disabled or not yet due.
  2. For each selected category, asks Gemini (with Google Search grounding)
     for the top trending topic.
  3. Researches that topic with a grounded Gemini call.
  4. Generates a full article using the existing prompt pipeline.
  5. Saves and immediately publishes the article under the first superadmin
     user so it appears on the public feed.
"""

import logging
import uuid
import re
import json
import time
import os
import random
import markdown
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

ALL_CATEGORIES = [
    "Technology & AI",
    "Business & Finance",
    "Health & Wellness",
    "Science & Discovery",
    "Environment & Climate",
    "Culture & Society",
    "Startup & Innovation",
]


# ---------------------------------------------------------------------------
# Gemini helpers
# ---------------------------------------------------------------------------

def _make_research_model(base_model_name: str):
    """Return a Gemini model instance with Google Search grounding enabled."""
    try:
        from vertexai.generative_models import GenerativeModel, Tool, grounding
        google_search_tool = Tool.from_google_search_retrieval(
            grounding.GoogleSearchRetrieval()
        )
        return GenerativeModel(base_model_name, tools=[google_search_tool])
    except Exception as exc:
        logger.warning("Could not create grounded model (%s); falling back to base.", exc)
        from vertexai.generative_models import GenerativeModel
        return GenerativeModel(base_model_name)


def fetch_trending_topics(category: str, model) -> list:
    """Return up to 3 trending topic strings for *category* using Gemini search."""
    month_year = datetime.now().strftime("%B %Y")
    prompt = (
        f'Search the web for the 3 most newsworthy, trending topics right now '
        f'in the category "{category}" as of {month_year}.\n\n'
        f'Return ONLY a JSON array of 3 short topic titles, e.g.:\n'
        f'["Topic one", "Topic two", "Topic three"]\n\n'
        f'No other text.'
    )
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if match:
            topics = json.loads(match.group(0))
            return [t for t in topics if isinstance(t, str)][:3]
    except Exception as exc:
        logger.error("fetch_trending_topics failed for '%s': %s", category, exc)
    return []


def research_topic(topic: str, model) -> str:
    """Return a 300-400 word research summary for *topic* using Gemini search."""
    prompt = (
        f'Search the web and research this topic thoroughly: "{topic}"\n\n'
        f'Provide a structured research summary covering:\n'
        f'1. Key recent developments and facts\n'
        f'2. Relevant statistics or data points\n'
        f'3. Expert perspectives where available\n'
        f'4. Background context\n\n'
        f'Keep it concise (300-400 words), accurate, and current.'
    )
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as exc:
        logger.error("research_topic failed for '%s': %s", topic, exc)
    return ""


def generate_article(topic: str, research: str, settings: dict, base_client) -> tuple:
    """Generate article HTML + raw markdown. Returns (raw_text, html) or ('', '')."""
    from app import construct_initial_prompt, format_article_content

    base_prompt = construct_initial_prompt(topic, settings)
    if research:
        base_prompt += (
            "\n\n**Research Context (incorporate these verified facts):**\n" + research
        )

    try:
        response = base_client.generate_content(contents=base_prompt)
        raw_text = response.text
        content_html = format_article_content(raw_text, topic)
        return raw_text, content_html
    except Exception as exc:
        logger.error("generate_article failed for '%s': %s", topic, exc)
        return "", ""


def _extract_title(raw_text: str, fallback: str) -> str:
    match = re.search(r'^#\s+(.+)$', raw_text, re.MULTILINE)
    return match.group(1).strip() if match else fallback


# ---------------------------------------------------------------------------
# Main job
# ---------------------------------------------------------------------------

def run_auto_publish_job(app):
    """Entry point called by APScheduler or the standalone CLI."""
    with app.app_context():
        from models import db, User, GeneratedContent, AutoPublishConfig
        from app import CLIENT

        # ── Load config ────────────────────────────────────────────────────
        config = AutoPublishConfig.get_or_create()

        if not config.is_enabled:
            logger.info("Auto-publish disabled — skipping.")
            return

        if config.last_run_at:
            next_due = config.last_run_at + timedelta(hours=config.frequency_hours)
            if datetime.now(timezone.utc) < next_due:
                logger.info("Auto-publish not due until %s — skipping.", next_due)
                return

        if not CLIENT:
            _fail(config, "AI client not initialized")
            return

        # ── System user ────────────────────────────────────────────────────
        system_user = (
            User.query.filter_by(is_superadmin=True).first()
            or User.query.filter_by(is_active=True).first()
        )
        if not system_user:
            _fail(config, "No active user found to attribute articles")
            return

        # ── Grounded research model ────────────────────────────────────────
        model_name = os.getenv("MODEL_NAME", "gemini-2.5-flash-lite")
        research_model = _make_research_model(model_name)

        # ── Category selection ─────────────────────────────────────────────
        enabled_categories = config.get_categories() or ALL_CATEGORIES
        n = min(config.articles_per_run, len(enabled_categories))
        selected = random.sample(enabled_categories, n)

        settings = {
            "wordCount": str(config.word_count),
            "tone": config.tone,
            "enable_images": True,
            "audience": "general readers",
        }

        published, errors = 0, []

        for category in selected:
            try:
                logger.info("[auto-publish] category='%s' — fetching trending topics", category)
                topics = fetch_trending_topics(category, research_model)
                if not topics:
                    errors.append(f"{category}: no trending topics found")
                    continue

                topic = topics[0]
                logger.info("[auto-publish] topic='%s' — researching", topic)
                research = research_topic(topic, research_model)

                logger.info("[auto-publish] topic='%s' — generating article", topic)
                raw_text, content_html = generate_article(topic, research, settings, CLIENT)
                if not raw_text:
                    errors.append(f"{category}: generation returned empty")
                    continue

                title = _extract_title(raw_text, topic)
                word_count = len(raw_text.split())

                content = GeneratedContent(
                    user_id=system_user.id,
                    title=title[:500],
                    content_html=content_html,
                    content_raw=raw_text,
                    topic=topic,
                    word_count=word_count,
                    category=category,
                    is_auto_published=True,
                    # Publish immediately
                    is_public=True,
                    public_id=str(uuid.uuid4())[:12],
                    published_at=datetime.now(timezone.utc),
                )
                db.session.add(content)
                db.session.flush()
                content.extract_seo_data()

                system_user.articles_generated = (system_user.articles_generated or 0) + 1
                system_user.total_words_generated = (system_user.total_words_generated or 0) + word_count

                db.session.commit()
                published += 1
                logger.info("[auto-publish] published '%s' (id=%s)", title, content.id)

                time.sleep(2)  # brief pause between articles

            except Exception as exc:
                logger.error("[auto-publish] error for category '%s': %s", category, exc)
                errors.append(f"{category}: {str(exc)[:120]}")
                db.session.rollback()

        # ── Update run status ──────────────────────────────────────────────
        config.last_run_at = datetime.now(timezone.utc)
        config.last_run_status = (
            f"Published {published} article(s)"
            + (f". Errors: {'; '.join(errors)}" if errors else "")
        )
        db.session.commit()
        logger.info("[auto-publish] job complete — %d published", published)


def _fail(config, reason: str):
    from models import db
    logger.error("[auto-publish] %s", reason)
    config.last_run_status = f"Failed: {reason}"
    try:
        db.session.commit()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Standalone CLI  (python auto_publisher.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from app import app
    run_auto_publish_job(app)
