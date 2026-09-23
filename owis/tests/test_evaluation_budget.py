import httpx
import pytest
from owis.scripts.evaluation_budget import EvaluationBudget


def test_budget_uses_returned_usage():
    budget = EvaluationBudget(0.1)
    def post(*args, **kwargs):
        return httpx.Response(200, request=httpx.Request('POST', args[1]),
                              json={'usage': {'prompt_tokens': 100, 'completion_tokens': 50}})
    budget.post(post, None, 'https://api.openai.com/v1/chat/completions',
                json={'model': 'gpt-4o-mini', 'max_tokens': 400})
    assert budget.charged == pytest.approx(0.000045)
    assert budget.calls[0]['status'] == 'measured'


@pytest.mark.parametrize('limit', [0, -1, float('nan'), float('inf')])
def test_invalid_limits(limit):
    with pytest.raises(ValueError):
        EvaluationBudget(limit)


def test_budget_stops_before_network():
    budget = EvaluationBudget(0.000001)
    def forbidden(*args, **kwargs):
        pytest.fail('Network called after budget exhausted')
    with pytest.raises(RuntimeError):
        budget.post(forbidden, None, 'https://api.openai.com/v1/chat/completions',
                    json={'model': 'gpt-4o-mini', 'max_tokens': 400})
    assert not budget.calls


def test_failed_request_keeps_reservation():
    budget = EvaluationBudget(0.1)
    def failed(*args, **kwargs):
        raise httpx.TimeoutException('timeout')
    with pytest.raises(httpx.TimeoutException):
        budget.post(failed, None, 'https://api.openai.com/v1/chat/completions',
                    json={'model': 'gpt-4o-mini', 'max_tokens': 400})
    assert budget.charged > 0
    assert budget.calls[0]['status'] == 'reserved'


@pytest.mark.parametrize('url,model', [('https://example.com', 'gpt-4o-mini'),
                                      ('https://api.openai.com', 'unknown')])
def test_unknown_pricing_rejected(url, model):
    with pytest.raises(ValueError):
        EvaluationBudget(0.1).post(None, None, url, json={'model': model})
