# loa-analysis

Compare your Lost Ark raid logs from [lostark.bible](https://lostark.bible) against other players running the same build, and
see where the gap is: casts per minute, damage per cast, hits landed, uptime, deaths and time knocked down, plus build choices.
Each gate gets its own self-contained HTML report.

Currently set up for Mayhem Berserker on Belgardin (gate 1) and Phaetus An Kragma (gate 2).

## Requirements

- Python 3.10+ (standard library only)
- Node.js (used to evaluate the data embedded in log pages)

## Usage

```sh
cp gates.example.json gates.json         # then fill in your character name and log ids
python3 -I scripts/fetch_gate.py gate1   # download bracket stats, sample runs and every sample log
python3 -I scripts/fetch_gate.py gate2
python3 -I scripts/build_report.py       # writes report-gate1.html, report-gate2.html, ...
open report-gate1.html
```

To check a new run, put its log id in `gates.json`, make sure your CP on that log is inside `minCP`–`maxCP`, then fetch and
build again. The fetch refreshes the bracket data, so copy `data/<gate>` first if you want to keep the old baseline.

## gates.json

Copy `gates.example.json` to `gates.json`. It's gitignored, so your character name and log ids stay local.

```json
{
  "character": "YourCharacter",
  "spec": "Mayhem",
  "gates": {
    "gate1": {"label": "Gate 1", "boss": "Belgardin, Arbiter of Death", "difficulty": "Nightmare", "log": "LOG_ID",
              "minCP": 7000, "maxCP": 7500, "patch": "sep26"}
  }
}
```

`spec`, `boss` and `difficulty` must match lostark.bible's names. The CP range is the bracket you're compared against; use the
500-wide range your CP falls in on that log.

## Layout

| Path | What it does |
|---|---|
| `scripts/fetch_gate.py` | Pulls bracket stats and same-spec sample runs for a gate, then downloads each log into `data/<gate>/` |
| `scripts/build_report.py` | Builds `report-<gate>.html` from the downloaded data |
| `scripts/remote.py` | Calls lostark.bible's SvelteKit remote query functions (`raidStatsSearch`, `raidSamplesSearch`) |
| `scripts/undevalue.py` | Decodes SvelteKit's devalue format |
| `scripts/extract.js` | Pulls the encounter data embedded in a log page out as JSON |
| `PROMPT.md` | A prompt raid members can give Claude Code to run this analysis for their own class and build |

`gates.json`, `data/` and the generated reports are gitignored.

## Notes

- **nDPS is the main metric.** It strips external buffs, so how well your supports covered you doesn't change it.
- **The logs don't include gems or individual gear pieces**, so lower damage per cast can come from gear as well as play.
  Tripods are recorded per skill (`tripodIndex`).
- **Time sitting ready** comes from each skill's `timeAvailable`. Only some uploads record it, so it's compared against
  just the peers that have it.
- **Hard-coded for this build:** the Berserker skill and Ark Passive lists in `build_report.py`. Other builds need those
  changed, or can use `PROMPT.md`.
- **lostark.bible rate-limits downloads (HTTP 429).** `fetch_gate.py` waits between requests and backs off when limited.
- **The remote function hash (`1ranzqj/...`) changes when the site redeploys.** `PROMPT.md` explains how to find the new one.
- **This is an unofficial tool** and isn't affiliated with lostark.bible.
