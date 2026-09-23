"""Small synthetic Norwegian/English evaluation. --live explicitly enables API calls."""
import argparse
import json
import tempfile
import httpx
from unittest.mock import patch
from owis.scripts.evaluation_budget import EvaluationBudget
from pathlib import Path
from owis.core.config import settings
from owis.core.storage import db
from owis.core.llm.client import AIClient
from owis.modules.news.matching.semantic import embed_articles
from owis.modules.news.matching.service import build_candidate_pairs, judge_pair

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--max-usd",type=float,default=0.10)
    parser.add_argument("--output",default="work/matching-evaluation.json")
    args = parser.parse_args()
    budget=EvaluationBudget(args.max_usd)
    if not args.live:
        parser.error("Pass --live to run the OpenAI evaluation.")
    if not (settings.AI_ENABLED and settings.AI_API_KEY):
        parser.error("Configure OPENAI_API_KEY and OWI_AI_ENABLED=true in the process environment first.")
    cases=json.loads((Path(__file__).parents[1]/"tests/fixtures/news_match_cases.json").read_text(encoding="utf-8"))
    original_post=httpx.Client.post
    def guarded(client,url,**kwargs):return budget.post(original_post,client,url,**kwargs)
    with tempfile.TemporaryDirectory() as tmp, patch.object(httpx.Client,"post",guarded):
        db.DB_PATH=str(Path(tmp)/"evaluation.db")
        db.init_db()
        vectors=embed_articles([item for case in cases for item in (case["a"],case["b"])])
        rows=[]
        ai=AIClient()
        for index, case in enumerate(cases, 1):
            a,b=case["a"],case["b"]
            candidates=build_candidate_pairs([a,b],days_window=30,embeddings=vectors)
            judged=judge_pair(ai,a,b,0)
            expected=case["expected"]
            retrieval_ok=bool(candidates) if expected in {"same_event","update"} else True
            rows.append(dict(name=case["name"], expected=expected, actual=judged["relationship"],
                             candidate=bool(candidates), reason=judged.get("reason_short"), passed=retrieval_ok and judged["relationship"]==expected and not judged["fallback"]))
            print(f"Assessed {index}/{len(cases)}", flush=True)
        report=dict(model=settings.AI_MODEL, cases=rows, passed=sum(r["passed"] for r in rows),
                    total=len(rows), false_same_event=sum(r["actual"]=="same_event" and r["expected"]!="same_event" for r in rows),
                    estimated_usd=budget.charged, max_usd=budget.limit, usage=budget.calls)
        destination=Path(args.output); destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({k:v for k,v in report.items() if k not in {"cases","usage"}},indent=2))
        for row in rows:
            if not row["passed"]: print(json.dumps(row,ensure_ascii=False))
        raise SystemExit(0 if all(r["passed"] for r in rows) else 1)

if __name__ == "__main__": main()
