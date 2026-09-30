"""Host-side, explicitly approved promotion/rollback. No unauthenticated HTTP mutation."""
import argparse
import json
from pathlib import Path

from .registry import promote, rollback


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', default='models/production', type=Path)
    parser.add_argument('--pointer', default='logs/model-active.json', type=Path)
    commands = parser.add_subparsers(dest='action', required=True)
    promotion = commands.add_parser('promote')
    promotion.add_argument('--candidate', required=True, type=Path)
    promotion.add_argument('--report', required=True, type=Path)
    promotion.add_argument('--approve-report-sha256', required=True)
    promotion.add_argument('--baseline', default='models/production/v1.0.0', type=Path)
    reversal = commands.add_parser('rollback')
    reversal.add_argument('--expected-generation', required=True)
    args = parser.parse_args()
    if args.action == 'promote':
        result = promote(args.candidate, args.report, args.approve_report_sha256, args.registry, args.pointer, args.baseline)
    else:
        result = rollback(args.registry, args.pointer, args.expected_generation)
    print(json.dumps(result, ensure_ascii=False, indent=2))
