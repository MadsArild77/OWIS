"""Small synthetic Norwegian/English evaluation. --live explicitly enables API calls."""
import argparse
import json
import tempfile
from pathlib import Path
from owis.core.config import settings
from owis.core.storage import db
from owis.core.llm.client import AIClient
from owis.modules.news.matching.semantic import embed_articles
from owis.modules.news.matching.service import build_candidate_pairs, judge_pair

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if not args.live:
        parser.error("Pass --live to run the OpenAI evaluation (12 texts and 6 pair assessments).")
    if not (settings.AI_ENABLED and settings.AI_API_KEY):
        parser.error("Configure OPENAI_API_KEY and OWI_AI_ENABLED=true in the process environment first.")
    cases=json.loads((Path(__file__).parents[1]/"tests/fixtures/news_match_cases.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        db.DB_PATH=str(Path(tmp)/"evaluation.db")
        db.init_db()
        vectors=embed_articles([item for case in cases for item in (case["a"],case["b"])])
        rows=[]
        ai=AIClient()
        for case in cases:
            a,b=case["a"],case["b"]
            candidates=build_candidate_pairs([a,b],days_window=30,embeddings=vectors)
            judged=judge_pair(ai,a,b,0)
            expected=case["expected"]
            retrieval_ok=bool(candidates) if expected in {"same_event","update"} else True
            rows.append(dict(name=case["name"], expected=expected, actual=judged["relationship"],
                             candidate=bool(candidates), passed=retrieval_ok and judged["relationship"]==expected and not judged["fallback"]))
        print(json.dumps(rows,ensure_ascii=False,indent=2))
        raise SystemExit(0 if all(r["passed"] for r in rows) else 1)

if __name__ == "__main__": main()
