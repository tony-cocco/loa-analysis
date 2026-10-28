# Call a lostark.bible SvelteKit remote query: devalue-encode a flat dict arg, base64url it, GET it.
import json, base64, sys, urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"

def devalue(obj):
    vals = [None]
    def add(v):
        if v is None: return -1
        if v is True or v is False or isinstance(v, (int, float, str)):
            vals.append(v); return len(vals) - 1
        raise TypeError(type(v))
    ref = {}
    for k in sorted(obj):  # SvelteKit sorts keys for cache stability
        if obj[k] is not None: ref[k] = None
    vals[0] = ref
    for k in ref: ref[k] = add(obj[k])
    return json.dumps(vals, separators=(',', ':'))

def call(fn, arg):
    p = base64.urlsafe_b64encode(devalue(arg).encode()).decode().rstrip('=')
    url = f"https://lostark.bible/_app/remote/{fn}?payload={p}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "x-sveltekit-pathname": "/stats/raids", "x-sveltekit-search": ""})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

if __name__ == "__main__":
    fn, arg, out = sys.argv[1], json.loads(sys.argv[2]), sys.argv[3]
    res = call(fn, arg)
    open(out, "w").write(json.dumps(res))
    print(json.dumps(res)[:1500])
