"""Sequential evaluation-only budget guard. Prices checked 2026-09-23.
Conservative byte-based reservation; actual usage priced without cache discounts.
Not a provider billing cap or a production-wide budget.
"""
import json
import math
from urllib.parse import urlparse

RATES = {"gpt-4o-mini": (0.15, 0.60), "text-embedding-3-small": (0.02, 0.0)}

class EvaluationBudget:
    def __init__(self, limit):
        if not math.isfinite(limit) or limit <= 0: raise ValueError("Budget must be positive and finite")
        self.limit=limit
        self.charged=0.0
        self.calls=[]

    def post(self, original, client, url, **kwargs):
        payload=kwargs["json"]
        model=payload["model"]
        if urlparse(str(url)).hostname != "api.openai.com" or model not in RATES:
            raise ValueError("No verified evaluation pricing for this endpoint/model")
        in_rate,out_rate=RATES[model]
        # One UTF-8 byte per token plus generous protocol overhead.
        max_input=len(json.dumps(payload,ensure_ascii=False).encode())+1024
        max_output=int(payload.get("max_tokens",0))
        reserve=(max_input*in_rate+max_output*out_rate)/1e6
        if self.charged+reserve>self.limit:
            raise RuntimeError("Evaluation budget exhausted before request")
        self.charged+=reserve
        record=dict(model=model, input_tokens=None, output_tokens=None, estimated_usd=reserve, status="reserved")
        self.calls.append(record)
        response=original(client,url,**kwargs)
        response.raise_for_status()
        usage=response.json().get("usage") or {}
        if "prompt_tokens" in usage:
            prompt=int(usage["prompt_tokens"]); completion=int(usage.get("completion_tokens",0))
            cost=(prompt*in_rate+completion*out_rate)/1e6
            self.charged+=cost-reserve
            record.update(input_tokens=prompt,output_tokens=completion,estimated_usd=cost,status="measured")
        return response
