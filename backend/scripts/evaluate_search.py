"""Owner-run retrieval evaluation; default judgments target psf/requests.

Pass --cases JSON containing [{query, intent, expected: [{symbol, path_suffix?}]}]
for another repository or a pinned corpus. No source is executed or printed.
"""
import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID


CASES = [
    ('implementation', 'How are HTTP errors handled?', 'Response.raise_for_status', None),
    ('implementation', 'How are cookies added to an outgoing request?', 'PreparedRequest.prepare_cookies', None),
    ('implementation', 'How does a session follow redirects?', 'SessionRedirectMixin.resolve_redirects', None),
    ('implementation', 'How is JSON response content decoded?', 'Response.json', None),
    ('implementation', 'How is HTTP Basic authentication attached?', 'HTTPBasicAuth.__call__', None),
    ('implementation', 'How is the request body prepared?', 'PreparedRequest.prepare_body', None),
    ('definition', 'What is HTTPError?', 'HTTPError', None),
    ('definition', 'What is a Session?', 'Session', None),
    ('definition', 'What is RequestException?', 'RequestException', None),
    ('definition', 'What is a PreparedRequest?', 'PreparedRequest', None),
    ('symbol', 'Response.iter_content', 'Response.iter_content', None),
    ('symbol', 'Session.merge_environment_settings', 'Session.merge_environment_settings', None),
    ('symbol', 'HTTPAdapter.send', 'HTTPAdapter.send', None),
    ('symbol', 'PreparedRequest.prepare_url', 'PreparedRequest.prepare_url', None),
    ('documentation', 'Where is installation documented?', '<file>', 'README.md'),
    ('documentation', 'What does the project README say about usage?', '<file>', 'README.md'),
    ('documentation', 'What changes are described in the release history?', '<file>', 'HISTORY.md'),
    ('documentation', 'Which bug fixes are listed in the changelog?', '<file>', 'HISTORY.md'),
]


def matches(hit, target):
    return hit.get('symbol_name') == target['symbol'] and (
        not target.get('path_suffix') or hit.get('file_path', '').endswith(target['path_suffix'])
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository-id', required=True, type=UUID)
    parser.add_argument('--base-url', default='http://localhost:8000')
    parser.add_argument('--cases', type=Path)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding='utf-8')) if args.cases else [
        dict(query=query, intent=intent, expected=[dict(symbol=symbol, path_suffix=path)])
        for intent, query, symbol, path in CASES
    ]
    if not isinstance(cases, list) or not cases:
        parser.error('Cases must be a nonempty JSON list')
    for case in cases:
        if not isinstance(case.get('query'), str) or not case.get('expected') or any(
            not isinstance(target.get('symbol'), str) for target in case['expected']
        ):
            parser.error('Each case requires query and nonempty expected symbol judgments')
    results = []
    for number, case in enumerate(cases, 1):
        request = Request(
            f'{args.base_url.rstrip("/")}/api/repositories/{args.repository_id}/search',
            data=json.dumps({'query': case['query'], 'top_k': 5}).encode(),
            headers={'Content-Type': 'application/json'}, method='POST',
        )
        error = None
        try:
            with urlopen(request, timeout=180) as response:
                hits = json.load(response)['chunks'][:5]
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as exc:
            hits, error = [], type(exc).__name__
        targets = case['expected']
        recall = sum(any(matches(hit, target) for hit in hits) for target in targets) / len(targets)
        reciprocal = next((1 / rank for rank, hit in enumerate(hits, 1)
                           if any(matches(hit, target) for target in targets)), 0.0)
        row = dict(case=number, intent=case.get('intent', 'unspecified'),
                   recall_at_5=recall, reciprocal_rank_at_5=reciprocal, error=error)
        results.append(row)
        print(json.dumps(row))
    print(json.dumps(dict(queries=len(results), failures=sum(row['error'] is not None for row in results),
                          recall_at_5=sum(row['recall_at_5'] for row in results) / len(results),
                          mrr_at_5=sum(row['reciprocal_rank_at_5'] for row in results) / len(results))))
    for intent in sorted({row['intent'] for row in results}):
        group = [row for row in results if row['intent'] == intent]
        print(json.dumps(dict(intent=intent, queries=len(group),
                              recall_at_5=sum(row['recall_at_5'] for row in group) / len(group),
                              mrr_at_5=sum(row['reciprocal_rank_at_5'] for row in group) / len(group))))


if __name__ == '__main__':
    main()
