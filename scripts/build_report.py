# Build report-<gate>.html comparing your log for a gate (see gates.json) against other players on the same spec.
# Usage: python3 -I scripts/build_report.py [gate1 gate2 ...]   (run from ~/dev/mayhem; no args = every gate)
import json, glob, os, html, statistics as st, datetime, sys, urllib.parse
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = json.load(open(os.path.join(ROOT, 'gates.json')))
GATES, ME, SPEC = CONFIG['gates'], CONFIG['character'], CONFIG['spec']
# Set per gate by configure()
GATE = DATA = MY_LOG = BOSS = DIFF = STATS_URL = None
CP_MIN = CP_MAX = 0


def configure(gate):
    global GATE, DATA, MY_LOG, BOSS, DIFF, STATS_URL, CP_MIN, CP_MAX
    g = GATES[gate]
    GATE, DATA, MY_LOG, BOSS, DIFF = gate, os.path.join(ROOT, 'data', gate), g['log'], g['boss'], g['difficulty']
    CP_MIN, CP_MAX = g['minCP'], g['maxCP']
    STATS_URL = 'https://lostark.bible/stats/raids?' + urllib.parse.urlencode({
        'boss': BOSS, 'difficulty': DIFF, 'patch': g['patch'], 'filterBy': 'combat_power', 'type': 'ndps',
        'minCombatPower': CP_MIN, 'maxCombatPower': CP_MAX})


KEY_SKILLS = ['Dark Rush', 'Blood Slash', 'Overdrive', 'Finish Strike', 'Hell Blade', 'Sword Storm',
              'Power Break', 'Mountain Crash', 'Red Dust', 'Berserk Fury', 'Bleed', 'Rage Deathblade', 'Basic Attack']
ARK = {1010100: 'Crit', 1010400: 'Swiftness', 1020200: 'Illicit Spell', 1020300: 'Keen Sense', 1020400: 'Limit Break',
       1020500: 'Optimized Training', 2160040: 'Physical Awakening', 2160070: 'Provocation', 2160110: 'Stampede'}


def load_players():
    rows = []
    for f in sorted(glob.glob(os.path.join(DATA, 'logs', '*.json'))):
        info = json.load(open(f))[1]['data']['encounterInfo']
        enc = info['encounter']
        dur = enc['duration'] / 1000
        for p in enc['entityList']:
            if p['entityType'] != 'PLAYER' or p.get('spec') != SPEC:
                continue
            ds, ss = p['damageStats'], p['skillStats']
            dmg = ds['damageDealt']
            skills = {}
            for s in p['skills'].values():
                skills[s['name']] = {
                    'share': s['totalDamage'] / dmg, 'casts': s['casts'], 'hits': s['hits'],
                    'cpm': s['casts'] / (dur / 60),
                    'hpc': s['hits'] / s['casts'] if s['casts'] else 0,
                    'dph': s['totalDamage'] / s['hits'] if s['hits'] else 0,
                    'dpc': s['totalDamage'] / s['casts'] if s['casts'] else 0,
                    # ms the skill was off cooldown but not pressed; only some uploads record it
                    'ready': (s.get('timeAvailable') or 0) / 1000,
                    'readyPct': (s.get('timeAvailable') or 0) / 1000 / dur,
                    'ba': s['backAttackDamage'] / s['totalDamage'] if s['totalDamage'] else 0,
                }
            ark = {x['id']: x['lv'] for t in ('evolution', 'enlightenment', 'leap') for x in p['arkPassiveData'][t]}
            rows.append({
                'log': info['id'], 'name': p['name'], 'me': p['name'] == ME and info['id'] == MY_LOG,
                'cp': p['combatPower'], 'ilvl': p['gearScore'], 'dur': dur,
                'date': datetime.datetime.fromtimestamp(enc['fightStart'] / 1000).strftime('%b %d'),
                'ndps': ds['ndps'], 'rdps': ds['rdps'], 'dps': ds['dps'],
                'crit': ss['crits'] / ss['hits'], 'ba': ds['backAttackDamage'] / dmg,
                'cpm': ss['casts'] / (dur / 60), 'deaths': ds['deaths'],
                'dead': sum(x['deadFor'] for x in ds.get('deathInfo', [])) / 1000,
                'incap': sum(i['duration'] for i in ds.get('incapacitations', [])) / 1000,
                'engr': sorted(p['engravingData']), 'ark': ark, 'skills': skills,
                'readyTracked': any(s.get('timeAvailable') for s in p['skills'].values()),
            })
    return rows


def med(vals):
    vals = list(vals)
    return st.median(vals) if vals else 0


# ---------- formatting ----------
def M(v): return f'{v / 1e6:,.0f}M'
def B(v): return f'{v / 1e9:.2f}B'
def pct(v, d=1): return f'{v * 100:.{d}f}%'
def mmss(v): return f'{int(v // 60)}:{int(v % 60):02d}'
def esc(s): return html.escape(str(s))


def delta(me, ref, higher_better=True, threshold=0.05):
    """Relative delta cell: red when you're behind by more than threshold, green when ahead."""
    if not ref:
        return '<td class="num muted">–</td>'
    d = (me - ref) / ref
    good = d >= 0 if higher_better else d <= 0
    cls = '' if abs(d) < threshold else ('good' if good else 'bad')
    return f'<td class="num {cls}">{d * 100:+.0f}%</td>'


def strip_svg(peers, me, q):
    """Dot strip of peer nDPS with bracket quartiles and your run highlighted."""
    W, H, pad = 760, 120, 30
    vals = [r['ndps'] for r in peers] + [me['ndps'], q['lowerWhisker'], q['max']]
    lo, hi = min(vals) * 0.98, max(vals) * 1.01
    x = lambda v: pad + (v - lo) / (hi - lo) * (W - 2 * pad)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="nDPS distribution">']
    out.append(f'<rect x="{x(q["q1"]):.1f}" y="30" width="{x(q["q3"]) - x(q["q1"]):.1f}" height="40" class="box"/>')
    out.append(f'<line x1="{x(q["median"]):.1f}" x2="{x(q["median"]):.1f}" y1="26" y2="74" class="medline"/>')
    for label, key in (('Q1', 'q1'), ('Median', 'median'), ('Q3', 'q3')):
        out.append(f'<text x="{x(q[key]):.1f}" y="20" class="lbl" text-anchor="middle">{label} {M(q[key])}</text>')
    for i, r in enumerate(sorted(peers, key=lambda r: r['ndps'])):
        out.append(f'<circle cx="{x(r["ndps"]):.1f}" cy="{44 + (i % 3) * 6}" r="4" class="dot"><title>{esc(r["name"])} {M(r["ndps"])}</title></circle>')
    out.append(f'<circle cx="{x(me["ndps"]):.1f}" cy="50" r="7" class="me"><title>You {M(me["ndps"])}</title></circle>')
    out.append(f'<text x="{x(me["ndps"]):.1f}" y="96" class="lbl me-lbl" text-anchor="middle">You {M(me["ndps"])}</text>')
    for v in (lo, hi):
        out.append(f'<text x="{x(v):.1f}" y="114" class="lbl" text-anchor="middle">{M(v)}</text>')
    out.append('</svg>')
    return ''.join(out)


def build(gate):
    configure(gate)
    label = GATES[gate]['label']
    rows = load_players()
    me = next(r for r in rows if r['me'])
    peers = sorted([r for r in rows if not r['me'] and CP_MIN <= r['cp'] <= CP_MAX], key=lambda r: -r['ndps'])
    top = peers[:10]
    cp_matched = [r for r in peers if abs(r['cp'] - me['cp']) <= 100]
    bracket = json.load(open(os.path.join(DATA, 'bracket_stats.json')))['_']
    q = next(s for s in bracket['stats'] if s['spec'] == SPEC)
    rank = sum(1 for r in peers if r['ndps'] > me['ndps']) + 1

    tiles = [
        ('Your nDPS', M(me['ndps']), f'CP {me["cp"]:.0f} · ilvl {me["ilvl"]}'),
        ('Bracket median', M(q['median']), f'{q["count"]} {SPEC} runs, {CP_MIN}–{CP_MAX} CP'),
        ('Gap to median', f'{(me["ndps"] / q["median"] - 1) * 100:+.1f}%', f'Q1 is {M(q["q1"])}'),
        ('CP-matched median', M(med(r['ndps'] for r in cp_matched)), f'{len(cp_matched)} peers within ±100 CP of you'),
        ('Rank in sample', f'{rank} / {len(peers) + 1}', 'sampled logs I downloaded'),
    ]

    headline = [
        ('nDPS', 'ndps', M, True), ('Fight duration', 'dur', mmss, False), ('Crit rate', 'crit', pct, True),
        ('Back-attack damage share', 'ba', pct, True), ('Casts / min (all skills)', 'cpm', lambda v: f'{v:.1f}', True),
        ('Time dead (s)', 'dead', lambda v: f'{v:.0f}', False), ('Time knocked down / stunned (s)', 'incap', lambda v: f'{v:.0f}', False),
    ]

    def sk(rs, n, k): return med(r['skills'].get(n, {}).get(k, 0) for r in rs if n in r['skills'])

    skill_rows = []
    for n in KEY_SKILLS:
        m = me['skills'].get(n)
        if not m:
            continue
        users = [r for r in top if n in r['skills'] and r['skills'][n]['casts']]
        skill_rows.append((n, m, users))

    # build groupings
    def ark_key(r, ids): return ' + '.join(f'{ARK[i]} {r["ark"][i]}' for i in ids if i in r['ark']) or '—'
    def slot(r): return 'Mass Increase' if 'Mass Increase' in r['engr'] else ('Cursed Doll' if 'Cursed Doll' in r['engr'] else 'other')
    groups = [
        ('Engraving: Mass Increase vs Cursed Doll', slot),
        ('Evolution tier 2', lambda r: ark_key(r, [1020200, 1020300, 1020400, 1020500])),
        ('Enlightenment tier 3/4', lambda r: ark_key(r, [2160040, 2160070, 2160110])),
        ('Evolution stats', lambda r: ark_key(r, [1010100, 1010400])),
    ]
    engr_use = Counter(e for r in peers for e in r['engr'])

    H = []
    a = H.append
    a(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(SPEC)} {label} Comparison</title><style>
:root{{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1f;--muted:#6b6b70;--line:#e3e3e0;--accent:#c0392b;--good:#1e8e3e;--bad:#c5221f;--box:#e8eef7;--dot:#7a8aa6}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#141416;--card:#1d1d20;--fg:#ececef;--muted:#9a9aa2;--line:#2e2e33;--accent:#ff6b5b;--good:#5cc77a;--bad:#ff7a70;--box:#26303f;--dot:#8796b3}}}}
:root[data-theme="dark"]{{--bg:#141416;--card:#1d1d20;--fg:#ececef;--muted:#9a9aa2;--line:#2e2e33;--accent:#ff6b5b;--good:#5cc77a;--bad:#ff7a70;--box:#26303f;--dot:#8796b3}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1000px;margin:0 auto;padding:24px 16px 64px}}h1{{font-size:24px;margin:0 0 4px}}h2{{font-size:18px;margin:36px 0 8px}}
p.sub,.muted{{color:var(--muted)}}a{{color:inherit}}.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:20px 0}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}}.tile .k{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
.tile .v{{font-size:24px;font-weight:600;font-variant-numeric:tabular-nums}}.tile .s{{font-size:12px;color:var(--muted)}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;overflow-x:auto}}
table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:6px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}}
th{{font-size:12px;color:var(--muted);font-weight:600}}td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}}
tr.me td{{background:color-mix(in srgb,var(--accent) 12%,transparent);font-weight:600}}.good{{color:var(--good)}}.bad{{color:var(--bad);font-weight:600}}
svg{{width:100%;height:auto}}svg .box{{fill:var(--box)}}svg .medline{{stroke:var(--fg);stroke-width:2}}svg .dot{{fill:var(--dot);opacity:.85}}
svg .me{{fill:var(--accent);stroke:var(--card);stroke-width:2}}svg .lbl{{fill:var(--muted);font-size:11px}}svg .me-lbl{{fill:var(--accent);font-weight:600}}
nav{{display:flex;gap:8px;margin-bottom:16px}}nav a{{padding:4px 12px;border:1px solid var(--line);border-radius:999px;text-decoration:none;font-size:13px}}
nav a.on{{background:var(--fg);color:var(--bg);border-color:var(--fg)}}ul{{padding-left:20px}}li{{margin:4px 0}}.grp{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}}.grp td:first-child{{white-space:normal}}.grp th,.grp td{{padding:6px 6px}}
</style></head><body><main>
<nav>{''.join(f'<a href="report-{k}.html"{" class=on" if k == gate else ""}>{esc(v["label"])}</a>' for k, v in GATES.items())}</nav>
<h1>{esc(SPEC)}: {label} · {esc(BOSS)} ({esc(DIFF)})</h1>
<p class="sub">{esc(ME)} · log <a href="https://lostark.bible/logs/{MY_LOG}">{MY_LOG}</a> · {me["date"]} · compared with {len(peers)} other {esc(SPEC)} players at {CP_MIN}–{CP_MAX} CP
from the <a href="{STATS_URL}">bracket's sample runs</a>. Bracket stats as of {esc(bracket["timestamp"][:10])}.</p>
<div class="tiles">''')
    for k, v, s in tiles:
        a(f'<div class="tile"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div><div class="s">{esc(s)}</div></div>')
    a('</div>')

    a('<h2>Where you sit</h2><p class="muted">Shaded box is the bracket\'s middle 50% (Q1 to Q3) across all '
      f'{q["count"]} runs. Dots are the {len(peers)} sampled peers. nDPS strips external buffs, so how well your supports '
      'covered you does not change this number.</p>')
    a(f'<div class="card">{strip_svg(peers, me, q)}</div>')

    a('<h2>Headline metrics</h2><div class="card"><table><tr><th>Metric</th><th class="num">You</th>'
      '<th class="num">Peer median</th><th class="num">Top 10 median</th><th class="num">You vs top 10</th></tr>')
    for label, k, f, hb in headline:
        a(f'<tr><td>{label}</td><td class="num">{f(me[k])}</td><td class="num">{f(med(r[k] for r in peers))}</td>'
          f'<td class="num">{f(med(r[k] for r in top))}</td>')
        a(delta(me[k], med(r[k] for r in top), hb) if k not in ('dead', 'incap') else '<td class="num muted">–</td>')
        a('</tr>')
    a('</table></div>')

    a('<h2>Skill by skill vs the top 10</h2><p class="muted">Hits per cast show whether hits land; damage per cast shows what each '
      'press is worth. When hits per cast differ a lot (often a different tripod), damage per hit is not comparable, so go by damage per cast. '
      'Red means you trail the top 10 median by more than 5%.</p>')
    a('<div class="card"><table><tr><th>Skill</th><th class="num">Dmg share<br>you / top</th><th class="num">Casts/min<br>you / top</th>'
      '<th class="num">Δ</th><th class="num">Hits/cast<br>you / top</th><th class="num">Dmg/hit<br>you / top</th>'
      '<th class="num">Dmg/cast<br>you / top</th><th class="num">Δ</th><th class="num">Back-attack<br>you / top</th></tr>')
    for n, m, users in skill_rows:
        t = lambda k: med(r['skills'][n][k] for r in users)
        hpc_off = t('hpc') and abs(m['hpc'] / t('hpc') - 1) > 0.25
        a(f'<tr><td>{esc(n)}</td><td class="num">{pct(m["share"])} / {pct(t("share"))}</td>'
          f'<td class="num">{m["cpm"]:.2f} / {t("cpm"):.2f}</td>{delta(m["cpm"], t("cpm"), n != "Basic Attack")}'
          f'<td class="num{" bad" if hpc_off else ""}">{m["hpc"]:.1f} / {t("hpc"):.1f}</td>'
          f'<td class="num{" muted" if hpc_off else ""}">{M(m["dph"])} / {M(t("dph"))}</td>'
          f'<td class="num">{B(m["dpc"])} / {B(t("dpc"))}</td>{delta(m["dpc"], t("dpc")) if n != "Bleed" else "<td class=num>–</td>"}'
          f'<td class="num">{pct(m["ba"], 0)} / {pct(t("ba"), 0)}</td></tr>')
    a('</table></div>')
    bleed_me, bleed_top = me['skills'].get('Bleed', {}).get('hits', 0), med(r['skills']['Bleed']['hits'] for r in top if 'Bleed' in r['skills'])

    # Time sitting ready: only compare against peers whose uploads recorded it.
    tracked = [r for r in peers if r['readyTracked']]
    ready_top = tracked[:10]
    ready_rows, ready_behind = [], []
    if me['readyTracked'] and tracked:
        for n, m, _ in skill_rows:
            if n in ('Basic Attack', 'Bleed') or m['casts'] < 5:
                continue
            # A 0 means the uploader didn't record this skill, not that it was never ready.
            vals = [r['skills'][n]['readyPct'] for r in tracked if r['skills'].get(n, {}).get('readyPct')]
            if len(vals) < 3 or not m['readyPct']:
                continue
            t = med(r['skills'][n]['readyPct'] for r in ready_top if r['skills'].get(n, {}).get('readyPct'))
            rank = sorted(vals + [m['readyPct']]).index(m['readyPct']) + 1
            ready_rows.append((n, m, t, med(vals), rank, len(vals) + 1))
            if m['readyPct'] - t > 0.05:
                ready_behind.append((n, m['readyPct'] - t))
    a('<h2>Time sitting ready</h2>')
    if ready_rows:
        a(f'<p class="muted">How long each skill was off cooldown but not pressed, as a share of the fight. Only {len(tracked)} of '
          f'{len(peers)} peers\' uploads record this, so the comparison uses just those; "top" is the best {len(ready_top)} of them by nDPS. '
          'Rank 1 means the least time sitting ready.</p>')
        a('<div class="card"><table><tr><th>Skill</th><th class="num">You</th><th class="num">Top</th><th class="num">Tracked median</th>'
          '<th class="num">You − top</th><th class="num">Seconds ready</th><th class="num">Rank</th></tr>')
        for n, m, t, md, rank, of in sorted(ready_rows, key=lambda x: x[2] - x[1]['readyPct']):
            d = m['readyPct'] - t
            cls = 'bad' if d > 0.05 else ('good' if d < -0.05 else '')
            a(f'<tr><td>{esc(n)}</td><td class="num">{pct(m["readyPct"], 0)}</td><td class="num">{pct(t, 0)}</td>'
              f'<td class="num">{pct(md, 0)}</td><td class="num {cls}">{d * 100:+.0f} pts</td>'
              f'<td class="num">{m["ready"]:.0f}s</td><td class="num">{rank} / {of}</td></tr>')
        a('</table></div>')
    else:
        a('<p class="muted">Your upload for this log doesn\'t record how long skills sat ready.</p>')

    # Takeaways are derived from the skill table so they hold for any gate.
    rotation = []
    for n, m, users in skill_rows:
        if n in ('Basic Attack', 'Bleed') or not users or m['share'] < 0.01:
            continue
        t = lambda k: med(r['skills'][n][k] for r in users)
        rel = lambda k: m[k] / t(k) - 1 if t(k) else 0
        rotation.append((n, rel('cpm'), rel('dpc'), rel('hpc')))
    def names(xs): return ', '.join(f'{n} ({d * 100:+.0f}%)' for n, d in xs) or 'none'
    low_dpc = sorted([(n, d) for n, _, d, _ in rotation if d < -0.05], key=lambda x: x[1])
    high_dpc = [(n, d) for n, _, d, _ in rotation if d > 0.05]
    # Skip once-a-fight skills (awakening, hyper) where casts/min mostly tracks fight length.
    low_cpm = sorted([(n, c) for n, c, _, _ in rotation if c < -0.05 and me['skills'][n]['casts'] >= 5], key=lambda x: x[1])
    diff_hpc = [(n, h) for n, _, _, h in rotation if abs(h) > 0.25]
    few_hpc = [(n, h) for n, _, _, h in rotation if -0.25 <= h < -0.10]
    ba_me = me['skills'].get('Basic Attack', {}).get('cpm', 0)
    ba_top = med(r['skills']['Basic Attack']['cpm'] for r in top if 'Basic Attack' in r['skills'])
    fine = [lbl for lbl, k, hb in (('crit rate', 'crit', True), ('back-attack share', 'ba', True),
                                  ('casts per minute', 'cpm', True), ('time knocked down', 'incap', False))
            if (me[k] >= med(r[k] for r in peers)) == hb or me[k] == med(r[k] for r in peers)]

    a('<h2>Takeaways from the data</h2><div class="card"><ul>')
    a('<li><b>Damage per cast:</b> behind the top 10 on ' + names(low_dpc) + '.' +
      (f' Ahead on {names(high_dpc)}.' if high_dpc else '') + '</li>')
    if diff_hpc:
        a(f'<li><b>Different hit pattern:</b> hits per cast differ sharply on {names(diff_hpc)}, possibly a different tripod or how the hits '
          'connect on this boss. Compare these by damage per cast, not per hit.</li>')
    a('<li><b>Hits landing:</b> ' + (f'fewer hits per cast on {names(few_hpc)}, so some hits are missing.' if few_hpc
                                     else 'hits per cast are otherwise in line with the top runs.') + '</li>')
    a(f'<li><b>Casts per minute:</b> behind on {names(low_cpm)}. Basic Attack {ba_me:.1f}/min vs {ba_top:.1f} for the top 10.</li>')
    a(f'<li><b>Bleed ticks:</b> {bleed_me} hits for you vs {bleed_top:.0f} median for the top 10.</li>')
    a(f'<li><b>Survival and length:</b> {me["deaths"]} death{"s" if me["deaths"] != 1 else ""} ({me["dead"]:.0f}s dead), '
      f'{me["incap"]:.0f}s knocked down or stunned vs {med(r["incap"] for r in top):.0f}s for the top 10, '
      f'fight length {mmss(me["dur"])} vs {mmss(med(r["dur"] for r in top))}.</li>')
    if fine:
        a(f'<li><b>At or better than the peer median:</b> {", ".join(fine)}.</li>')
    if ready_rows:
        a('<li><b>Time sitting ready:</b> ' + (f'more than the top tracked players on {", ".join(f"{n} ({d * 100:+.0f} pts)" for n, d in sorted(ready_behind, key=lambda x: -x[1]))}.'
                                               if ready_behind else 'in line with the top tracked players.') + '</li>')
    a('<li><b>Not in the logs:</b> gems and gear pieces. These could explain lower damage per cast as easily as play could.</li>')
    a('</ul></div>')

    a('<h2>Build choices vs nDPS</h2><p class="muted">Median nDPS of peers grouped by each choice. Groups are small, so read these as '
      'hints, not proof. Stronger players may simply pick the stronger option.</p><div class="grp">')
    for title, fn in groups:
        g = defaultdict(list)
        for r in peers:
            g[fn(r)].append(r['ndps'])
        mine = fn(me)
        a(f'<div class="card"><b>{esc(title)}</b><table><tr><th>Choice</th><th class="num">n</th><th class="num">Median nDPS</th></tr>')
        for k, v in sorted(g.items(), key=lambda kv: -len(kv[1])):
            a(f'<tr{" class=me" if k == mine else ""}><td>{esc(k)}</td><td class="num">{len(v)}</td><td class="num">{M(med(v))}</td></tr>')
        if mine not in g:
            a(f'<tr class="me"><td>{esc(mine)} (you)</td><td class="num">0</td><td class="num">–</td></tr>')
        a(f'</table><p class="muted">You: {esc(mine)}</p></div>')
    a('</div>')
    a('<p class="muted">Engraving usage across peers: ' + ', '.join(f'{esc(k)} {v}' for k, v in engr_use.most_common()) + '.</p>')

    a('<h2>All runs</h2><div class="card"><table><tr><th>#</th><th>Player</th><th>Log</th><th>Date</th><th class="num">nDPS</th>'
      '<th class="num">CP</th><th class="num">Duration</th><th class="num">Crit</th><th class="num">BA share</th><th class="num">Casts/min</th>'
      '<th class="num">Dead (s)</th><th>Mass Inc. / Cursed Doll</th></tr>')
    for i, r in enumerate(sorted(peers + [me], key=lambda r: -r['ndps']), 1):
        a(f'<tr{" class=me" if r["me"] else ""}><td>{i}</td><td>{esc(r["name"])}</td><td><a href="https://lostark.bible/logs/{r["log"]}">{r["log"]}</a></td>'
          f'<td>{r["date"]}</td><td class="num">{M(r["ndps"])}</td><td class="num">{r["cp"]:.0f}</td><td class="num">{mmss(r["dur"])}</td>'
          f'<td class="num">{pct(r["crit"])}</td><td class="num">{pct(r["ba"])}</td><td class="num">{r["cpm"]:.1f}</td>'
          f'<td class="num">{r["dead"]:.0f}</td><td>{slot(r)}</td></tr>')
    a('</table></div>')
    a('<p class="muted">Source: lostark.bible logs and raid stats. "Top 10" means the 10 highest-nDPS peers in this sample. '
      'Peers outside the CP bracket who appeared in the same logs are excluded.</p></main></body></html>')

    out = os.path.join(ROOT, f'report-{gate}.html')
    open(out, 'w').write(''.join(H))
    print('wrote', out)


if __name__ == '__main__':
    for gate in sys.argv[1:] or GATES:
        build(gate)
