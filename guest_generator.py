"""Bounded CLI for this project's direct Garena guest-generation flow."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time

import lssj
import jwt_protocol


def save_records(path, records):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         delete=False) as stream:
            temporary = stream.name
            json.dump(records, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Generate guests using your own OB55 implementation.')
    parser.add_argument('--region', required=True, type=str.upper, choices=sorted(lssj.REGNS))
    parser.add_argument('--count', type=int, default=1)
    parser.add_argument('--name-prefix', default='MEAN')
    parser.add_argument('--password-prefix', default='MEAN')
    parser.add_argument('--output', type=Path, default=Path('generated_guests.json'))
    args = parser.parse_args(argv)
    if args.count < 1:
        parser.error('--count must be positive')
    # Validate the output before creating any account.
    records = json.loads(args.output.read_text(encoding='utf-8')) if args.output.exists() else []
    if not isinstance(records, list) or not args.output.parent.is_dir():
        parser.error('Output must be a JSON list in an existing directory')
    print(f'Protocol {jwt_protocol.RELEASE_VERSION}; client {jwt_protocol.CLIENT_VERSION}')
    for index in range(args.count):
        result = lssj.create_guest_account(args.region, args.name_prefix, args.password_prefix)
        if result.get('guest_created'):
            records.append(result)
            save_records(args.output, records)
        if not result.get('success'):
            diagnostic = {key: result[key] for key in (
                'failed_stage', 'error', 'warning', 'http_status', 'upstream_error',
                'error_detail', 'retry_after_seconds', 'rate_limited') if key in result}
            print(json.dumps(diagnostic, ensure_ascii=False))
            print('Stopped. Created credentials, if any, are saved in the output file.')
            return 1
        print(f'Created {index + 1}/{args.count}; credentials saved to {args.output}')
        if index + 1 < args.count:
            time.sleep(5)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
