import logging
import os

import uvicorn


def _safe_port(raw: str | None) -> int:
    if not raw:
        return 8080
    try:
        return int(raw)
    except ValueError:
        return 8080


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = _safe_port(os.getenv("PORT"))
    # OWIS's own progress lines (fetch timings, scheduled runs) next to uvicorn's request log.
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    owis_logger = logging.getLogger("owis")
    owis_logger.setLevel(logging.INFO)
    owis_logger.addHandler(handler)
    uvicorn.run("owis.apps.api.main:app", host=host, port=port)


if __name__ == "__main__":
    main()
