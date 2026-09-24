"""Bounded retries for idempotent source GETs. Callers set HTTP timeouts."""
import time
import httpx
from owis.modules.news.storage.source_events import record_attempts, error_message

MAX_RETRIES = 3
RETRY_STATUS = {408, 429, 500, 502, 503, 504}


def get_with_retry(get, url, *, source='unknown', operation='fetch'):
    # One initial request plus at most three retries. Never retry parse/auth/404 errors.
    for attempt in range(1, MAX_RETRIES + 2):
        response = None
        try:
            response = get(url)
            if response.status_code not in RETRY_STATUS:
                return response
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in RETRY_STATUS:
                raise
            record_attempts([dict(source=source, url=url, status='error',
                error=f'Attempt {attempt}/{MAX_RETRIES + 1}: {error_message(exc)}')], operation + '_attempt')
            if attempt > MAX_RETRIES:
                raise
            delay = 2 ** (attempt - 1)
            if response is not None:
                try:
                    delay = max(delay, float(response.headers.get('Retry-After', '0')))
                except ValueError:
                    pass
                # A long server cooldown is not a reason to keep a job waiting.
                if delay > 10:
                    raise
            time.sleep(delay)
