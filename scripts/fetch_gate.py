# Fetch bracket stats, sample runs for your spec and every sample log for one gate defined in gates.json.
# Usage: python3 -I scripts/fetch_gate.py gate2   (run from ~/dev/mayhem)
import json, os, subprocess, sys, time, urllib.error, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import remote, undevalue

ROOT = os.path.dirname(HERE)


def main(gate):
    config = json.load(open(os.path.join(ROOT, 'gates.json')))
    g, SPEC = config['gates'][gate], config['spec']
    out = os.path.join(ROOT, 'data', gate)
    os.makedirs(os.path.join(out, 'logs'), exist_ok=True)
    common = {'boss': g['boss'], 'difficulty': g['difficulty'], 'minCombatPower': g['minCP'], 'maxCombatPower': g['maxCP'],
              'includeBus': False, 'includeWeird': False, 'patch': g['patch']}

    stats = undevalue.parse(remote.call('1ranzqj/raidStatsSearch', {**common, 'isSupport': False, 'filterBy': 'combat_power',
                                                                    'dpsType': 'ndps'})['data'])
    json.dump(stats, open(os.path.join(out, 'bracket_stats.json'), 'w'))
    q = next(s for s in stats['_']['stats'] if s['spec'] == SPEC)
    print(f"bracket: {q['count']} {SPEC} runs, median {q['median'] / 1e6:.0f}M")

    samples = undevalue.parse(remote.call('1ranzqj/raidSamplesSearch', {**common, 'spec': SPEC, 'ceiling': q['upperWhisker'],
                                                                         'q3': q['q3'], 'median': q['median'], 'statType': 'ndps'})['data'])['_']
    json.dump(samples, open(os.path.join(out, 'samples.json'), 'w'))

    ids = sorted({e['id'] for v in samples.values() for e in v} | {g['log']})
    for i in ids:
        dest = os.path.join(out, 'logs', i + '.json')
        if os.path.exists(dest):
            continue
        tmp = dest[:-5] + '.html'
        req = urllib.request.Request(f'https://lostark.bible/logs/{i}', headers={'User-Agent': remote.UA})
        for attempt in range(6):
            try:
                body = urllib.request.urlopen(req, timeout=30).read()
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == 5:
                    raise
                wait = int(e.headers.get('Retry-After') or 0) or 15 * (attempt + 1)
                print(f'429 on {i}, waiting {wait}s', flush=True)
                time.sleep(wait)
        open(tmp, 'wb').write(body)
        subprocess.run(['node', os.path.join(HERE, 'extract.js'), tmp, dest], check=True, capture_output=True)
        os.remove(tmp)
        time.sleep(2)
    print(f'{len(ids)} logs in {out}/logs')


if __name__ == '__main__':
    main(sys.argv[1])
