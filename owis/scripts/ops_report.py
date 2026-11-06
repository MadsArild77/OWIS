"""Print the operational report from a read-only database copy."""
import argparse
import sqlite3

from owis.modules.news.processing.ops_report import markdown, read_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--days', type=int, default=30)
    args = parser.parse_args()
    try:
        print(markdown(read_report(args.db, args.days)), end='')
    except (ValueError, sqlite3.Error) as exc:
        parser.exit(2, f'Cannot read report: {exc}\n')


if __name__ == '__main__':
    main()
