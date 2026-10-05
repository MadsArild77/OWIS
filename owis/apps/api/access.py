"""Optional shared-password protection for the whole app.

Set OWI_ACCESS_PASSWORD to require HTTP Basic login on every route except the
health check. Without it the app stays open, as before, and logs a warning on
hosted environments so an unprotected deployment is visible in the logs.
"""
import base64
import logging
import os
import secrets

from starlette.responses import PlainTextResponse

logger = logging.getLogger(__name__)

OPEN_PATHS = {'/health'}


def credentials():
    password = os.getenv('OWI_ACCESS_PASSWORD', '')
    if not password:
        return None
    return os.getenv('OWI_ACCESS_USER', 'owis'), password


def warn_if_open():
    if credentials() is None and os.getenv('RAILWAY_ENVIRONMENT_ID'):
        logger.warning('OWI_ACCESS_PASSWORD is not set: OWIS is publicly accessible without login.')


def _authorised(header, expected):
    scheme, _, value = (header or '').partition(' ')
    if scheme.lower() != 'basic':
        return False
    try:
        user, _, password = base64.b64decode(value).decode('utf-8').partition(':')
    except (ValueError, UnicodeDecodeError):
        return False
    return (secrets.compare_digest(user.encode(), expected[0].encode())
            & secrets.compare_digest(password.encode(), expected[1].encode()))


async def require_login(request, call_next):
    expected = credentials()
    if expected is None or request.url.path in OPEN_PATHS or _authorised(request.headers.get('authorization'), expected):
        return await call_next(request)
    return PlainTextResponse('Login required', status_code=401,
                             headers={'WWW-Authenticate': 'Basic realm="OWIS", charset="UTF-8"'})
