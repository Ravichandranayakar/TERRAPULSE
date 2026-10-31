import json, urllib.parse, urllib.request, math

WMS = "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms?"

def gfi(layer, lon, lat, box, px, buf, fc=300):
    bbox = "%.6f,%.6f,%.6f,%.6f" % (lon-box/2, lat-box/2, lon+box/2, lat+box/2)
    q = urllib.parse.urlencode({
        "service":"WMS","version":"1.1.1","request":"GetFeatureInfo",
        "layers":layer,"query_layers":layer,"srs":"EPSG:4326",
        "bbox":bbox,"width":px,"height":px,"x":px//2,"y":px//2,
        "info_format":"application/json","feature_count":fc,"buffer":buf})
    with urllib.request.urlopen(WMS+q, timeout=90) as r:
        raw = r.read().decode("utf-8","replace")
    if not raw.strip().startswith("{"):
        raise ValueError("non-JSON")
    return json.loads(raw)

def dist_m(lon1,lat1,lon2,lat2):
    R=6371000.0
    p1,p2=math.radians(lat1),math.radians(lat2)
    dp=math.radians(lat2-lat1); dl=math.radians(lon2-lon1)
    a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(a))

pts = [("Arunachal",94.309444,28.527944),("Sikkim",88.542972,27.749111),
       ("Nagaland",95.19475,26.678833),("Assam",90.595,26.006)]

print("Layer: lineament:*_LN50K_0506")
print("%-11s %-8s %-9s %-8s %-9s %s" % ("pt","box","px","buf","n_feat","nearest_km"))
for name, lon, lat in pts:
    code = {"Arunachal":"AR","Sikkim":"SK","Nagaland":"NL","Assam":"AS"}[name]
    L = "lineament:%s_LN50K_0506" % code
    for box, px, buf in [(0.10,1024,50),(0.50,1024,500)]:
        try:
            g = gfi(L, lon, lat, box, px, buf)
            f = g.get("features", [])
            best = None
            for feat in f:
                geom = feat.get("geometry") or {}
                cs = []
                if geom.get("type")=="MultiLineString": cs = [c for line in geom["coordinates"] for c in line]
                elif geom.get("type")=="LineString": cs = geom["coordinates"]
                for c in cs:
                    d = dist_m(lon,lat,c[0],c[1])
                    if best is None or d < best: best = d
            print("%-11s %-8s %-9d %-8d %-9d %s" % (name, box, px, buf, len(f),
                  ("%.2f" % (best/1000)) if best is not None else "-"))
        except Exception as e:
            print("%-11s %-8s %-9d %-8d ERR %s" % (name, box, px, buf, str(e)[:40]))