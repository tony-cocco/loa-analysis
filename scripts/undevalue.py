# Minimal devalue parser (SvelteKit's serialization format).
import json
def parse(text):
    vals = json.loads(text) if isinstance(text, str) else text
    memo = {}
    def h(i):
        if i == -1: return None
        if i in (-2, -3, -4, -5, -6): return {-2: None, -3: float('nan'), -4: float('inf'), -5: float('-inf'), -6: -0.0}[i]
        if i in memo: return memo[i]
        v = vals[i]
        if isinstance(v, list):
            if v and isinstance(v[0], str) and v[0] in ('Date', 'Set', 'Map', 'BigInt', 'RegExp', 'Object', 'null'):
                out = v[1] if v[0] in ('Date', 'BigInt') else [h(x) for x in v[1:]]
            else:
                out = []; memo[i] = out; out.extend(h(x) for x in v)
        elif isinstance(v, dict):
            out = {}; memo[i] = out
            for k, x in v.items(): out[k] = h(x)
        else:
            out = v
        memo[i] = out
        return out
    return h(0)
