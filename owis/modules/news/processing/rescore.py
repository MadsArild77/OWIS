"""Re-apply the current taxonomy and scoring to stored stories.

Runs at startup only when SCORING_VERSION changes. It is rule-based (no AI calls),
keeps summaries and editorial decisions, and keeps an earlier AI domain decision
when the rules are unsure.
"""
from datetime import datetime, timezone
import logging
import re

from owis.core.storage.db import get_conn
from owis.modules.news.collectors.scrape_fetcher import is_junk_link, is_subscriber_title
from owis.modules.news.processing import signal, taxonomy

logger = logging.getLogger(__name__)
_VERSION_KEY = "news_scoring_version"


def _split(value):
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def rescore_existing(force: bool = False) -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM news_registry_meta WHERE key=?", (_VERSION_KEY,)).fetchone()
        if row and row["value"] == signal.SCORING_VERSION and not force:
            return 0
        items = conn.execute('''SELECT p.id, p.title, p.cleaned_text, p.theme_tags, p.geography_tags, p.actors,
                r.id AS raw_id, r.source_name FROM news_processed_items p
                JOIN news_raw_items r ON r.id = p.raw_item_id''').fetchall()
        bases = {r["raw_id"]: dict(r) for r in conn.execute("SELECT * FROM news_content_basis")}
        domains = {r["processed_id"]: dict(r) for r in conn.execute("SELECT * FROM news_domain_classification")}
        now = datetime.now(timezone.utc).isoformat()
        for item in items:
            title, text = item["title"] or "", item["cleaned_text"] or ""
            if is_subscriber_title(title):
                # Subscriber stories from Norwegian trade press: clean title, record the paywall for open-source lookup.
                title = ("" if title.startswith("[Paywalled]") else "[Paywalled] ") + re.sub(r"\s*\(\+\)\s*$", "", title).strip()
                conn.execute("UPDATE news_processed_items SET title=? WHERE id=?", (title, item["id"]))
                conn.execute("UPDATE news_content_basis SET access='restricted' WHERE raw_id=? AND access='unknown'", (item["raw_id"],))
            themes = taxonomy.normalize_themes(_split(item["theme_tags"])) or ["general_news"]
            geos = taxonomy.geographies_for(title, text, _split(item["geography_tags"]))
            actors = taxonomy.normalize_actors(_split(item["actors"]) + taxonomy.extract_actors(f"{title} {text[:2000]}"))
            score, focus, _ = signal.score_signal(title, text, geos, actors, item["source_name"], bases.get(item["raw_id"]))
            if is_junk_link("", title):
                score, focus = 0, signal.Focus("other_energy", 1.0)
            conn.execute('''UPDATE news_processed_items SET theme_tags=?, geography_tags=?, actors=?, signal_score=?,
                    linkedin_candidate=? WHERE id=?''',
                         (",".join(themes), ",".join(geos), ",".join(actors), score,
                          int(signal.is_linkedin_candidate(score, focus)), item["id"]))
            previous = domains.get(item["id"])
            if previous and focus.confidence < 0.7:
                continue
            conn.execute('''INSERT INTO news_domain_classification(processed_id, domain_bucket, domain_confidence, classified_at)
                    VALUES(?,?,?,?) ON CONFLICT(processed_id) DO UPDATE SET domain_bucket=excluded.domain_bucket,
                    domain_confidence=excluded.domain_confidence, classified_at=excluded.classified_at''',
                         (item["id"], focus.bucket, focus.confidence, now))
        for master in conn.execute("SELECT collection_key, geography_tags, actors, theme_tags FROM news_collection_masters").fetchall():
            conn.execute("UPDATE news_collection_masters SET geography_tags=?, actors=?, theme_tags=? WHERE collection_key=?",
                         (",".join(taxonomy.normalize_geographies(_split(master["geography_tags"]))),
                          ",".join(taxonomy.normalize_actors(_split(master["actors"]))),
                          ",".join(taxonomy.normalize_themes(_split(master["theme_tags"]))), master["collection_key"]))
        conn.execute("INSERT OR REPLACE INTO news_registry_meta(key, value) VALUES(?, ?)", (_VERSION_KEY, signal.SCORING_VERSION))
    logger.info("Rescored %s stored news items with scoring version %s", len(items), signal.SCORING_VERSION)
    return len(items)
