import json, urllib.request, urllib.parse

BASE = "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms?"

def gfi(layer, bbox, x, y, w, h, buf=None, fc=50):
    d = {"service":"WMS","version":"1.1.1","request":"GetFeatureInfo",
         "layers":layer,"query_layers":layer,"srs":"EPSG:4326",
         "bbox":bbox,"width":w,"height":h,"x":x,"y":y,
         "info_format":"application/json","feature_count":fc}
    if buf is not None:
        d["buffer"] = buf
    with urllib.request.urlopen(BASE + urllib.parse.urlencode(d), timeout=120) as r:
        return json.loads(r.read().decode("utf-8","replace"))

print("=== AR lineament, bbox 92.0-93.0 / 27.0-28.0, with buffer ===")
for buf in [0, 10, 50, 200, 1000]:
    try:
        g = gfi("lineament:AR_LN50K_0506", "92.0,27.0,93.0,28.0", 512, 512, 1024, 1024, buf=buf)
        n = len(g.get("features", []))
        print("  buffer=%-5s -> %d features" % (buf, n))
        if n:
            f = g["features"][0]
            print("     geom:", f["geometry"]["type"])
            print("     props:", json.dumps(f["properties"])[:300])
            break
    except Exception as e:
        print("  buffer=%-5s -> ERR %s" % (buf, str(e)[:90]))

print()
print("=== Same test on geomorphology, for comparison ===")
g = gfi("geomorphology:AR_GM50K_0506", "92.0,27.0,93.0,28.0", 512, 512, 1024, 1024)
print("  geomorphology -> %d features" % len(g.get("features", [])))