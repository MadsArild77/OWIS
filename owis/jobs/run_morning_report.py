"""Run a durable morning report from an external scheduler."""
import argparse
from owis.core.storage.db import init_db
from owis.modules.news.processing.morning import start


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh', action='store_true', help='Replace today\'s saved report (five-minute cooldown).')
    args = parser.parse_args()
    init_db()
    state = start(refresh=args.refresh, synchronous=True)
    print(f"Morning report {state.get('report_date', '')}: {state['status']}")
    if state['status'] == 'failed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
