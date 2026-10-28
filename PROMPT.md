# Lost Ark parse comparison: prompt for Claude Code

Paste everything below the line into Claude Code, after filling in the bracketed fields. It works for any class and build.
If you also have the `scripts/` folder from this project, put it in your working directory: Claude can adapt it instead of starting from scratch.

---

I want to understand why my lostark.bible percentile is what it is, and where I can improve, by comparing my logs against other players running the same build. Gather and present the data first. Don't prescribe fixes until I ask.

**Me**
- Character: `[NAME]` on `[REGION, e.g. NA]`. Character page: `https://lostark.bible/character/[REGION]/[NAME]/logs`
- Class / build: `[CLASS]` running `[SPEC, as lostark.bible names it, e.g. Mayhem]`
- Logs to analyze (one per gate). Call them gate 1, gate 2, and so on:
  - Gate 1: `https://lostark.bible/logs/[ID]` ([BOSS], [DIFFICULTY])
  - Gate 2: `https://lostark.bible/logs/[ID]` ([BOSS], [DIFFICULTY])
- Comparison bracket: the 500-wide combat power range my CP falls in on each log (e.g. 7000–7500), patch `[e.g. sep26]`. Check my CP on each log; it can differ between gates.

**How to get the data** (lostark.bible is a SvelteKit app, and a plain fetch summary misses most of it)
1. **Log pages** (`/logs/<id>`) embed the full encounter in the page's `kit.start(app, element, { data: [...] })` call as a JavaScript object literal, not JSON. Download the HTML with curl, slice out that `data: [...]` array by bracket matching, and evaluate it in Node's `vm.runInNewContext` with an empty context to get JSON. `data[1].data.encounterInfo.encounter.entityList` has every player with `damageStats`, `skillStats`, per-skill `skills`, `engravingData`, `arkPassiveData`, `spec` and `combatPower`.
2. **Raid stats** (`/stats/raids?...`) load on the client through SvelteKit remote query functions. These are called as `GET https://lostark.bible/_app/remote/<hash>/<name>?payload=<base64url(devalue.stringify(arg))>`. The response is `{type:"result", data:"<devalue string>"}`, and the result is under the `_` key.
   - `raidStatsSearch` takes `{boss, difficulty, isSupport:false, filterBy:"combat_power", dpsType:"ndps", minCombatPower, maxCombatPower, includeBus:false, includeWeird:false, patch}`. It returns per-spec `q1/median/q3/max/upperWhisker/count`.
   - `raidSamplesSearch` takes the same filters plus `spec` and that spec's exact `ceiling` (=upperWhisker), `q3` and `median` from raidStatsSearch, and `statType:"ndps"`. It returns sample runs grouped as ceiling, q3 and median: these are the runs the site lists in its lower-right panel.
   - The `<hash>` prefix changes when the site redeploys. To find the current one, grep the stats page's route chunk under `/_app/immutable/nodes/` for `raidStatsSearch` (it appears as something like `Z("abc123/raidStatsSearch")`).
   - devalue objects are flat arrays: index 0 is the root, values reference other indices, and -1 means undefined. Sort object keys before encoding.
3. Download every sample log for my spec in each bracket, plus my own logs. **The site rate-limits (HTTP 429)**: wait at least 2 seconds between requests and back off on 429. Cache everything under `data/<gate>/` so reruns skip what's already downloaded.

**Analysis.** Use nDPS as the main metric: it removes external buffs, so support uptime doesn't affect it. Compare me against everyone on my spec inside the CP bracket, against the top 10 by nDPS, and against peers within ±100 CP of me.
- Where I sit: the bracket quartiles, plus my rank among the sampled runs.
- Headline metrics: nDPS, fight duration, crit rate, back-attack (or front-attack, if that's my build) damage share, casts per minute, time dead (`deathInfo`) and time knocked down or stunned (`incapacitations`).
- Skill by skill for my main skills: damage share, casts per minute, hits per cast, damage per hit, **damage per cast**, and crit/back-attack rate. When hits per cast differ sharply from the top runs (a different tripod, or hits connecting differently), compare by damage per cast instead of per hit. Exclude once-a-fight skills from casts-per-minute conclusions.
- Build choices: group peers by engravings and by Ark Passive nodes (Evolution tier 2, the Enlightenment tiers) and show the median nDPS for each choice, with mine highlighted. Get Ark Passive node names from the site's JS chunks, not from memory. Say that these groups are small and correlational.
- Write the takeaways from the computed numbers rather than hard-coding them, so they stay correct when I swap in new logs.
- Say plainly what the logs can't show: gems, tripods and individual gear pieces.

**Output.** One simple, self-contained HTML page per gate (`report-gate1.html`, `report-gate2.html`, ...) with tabs linking the gates. Include summary tiles, a dot chart of the bracket with my run highlighted, the tables above with red/green deltas against the top 10, a takeaways list, and an "all runs" table linking each log. Support light and dark mode, and don't use external dependencies. Keep the gate definitions in a `gates.json` (boss, difficulty, my log id, CP range, patch), plus a fetch script and a build script, so I can rerun with new logs.
