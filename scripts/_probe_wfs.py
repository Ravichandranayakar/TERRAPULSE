import urllib.request, urllib.parse
def try_url(label, url):
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            body = r.read(1200).decode("utf-8","replace")
        ok = "ExceptionReport" not in body
        print("%-46s %s  %s" % (label, r.status, "REAL DATA" if ok else "ExceptionReport"))
        if ok:
            print("     ", body[:300].replace("\n"," "))
        else:
            import re
            m = re.search(r"<ows:ExceptionText>([^<]+)", body)
            print("      ->", m.group(1)[:160] if m else body[:160])
    except Exception as e:
        print("%-46s ERR %s" % (label, str(e)[:110]))

L = "geomorphology:AR_GM50K_0506"
variants = [
    ("wfs  (workspace path)", "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wfs"),
    ("wfs  (root)",            "https://bhuvan-vec2.nrsc.gov.in/wfs"),
    ("wfs  (geoserver/wfs)",   "https://bhuvan-vec2.nrsc.gov.in/geoserver/wfs"),
    ("wms->GetFeature typenames", "https://bhuvan-vec2.nrsc.gov.in/bhuvan/ows"),
    ("wfs  (ows path)",        "https://bhuvan-vec2.nrsc.gov.in/bhuvan/ows?service=WFS"),
]
for label, base in variants:
    sep = "&" if "?" in base else "?"
    try_url(label + " GetCapabilities", base + sep + "service=WFS&request=GetCapabilities")

print()
print("=== try WFS GetFeature on the layer (whichever endpoint) ===")
for base in ["https://bhuvan-vec2.nrsc.gov.in/bhuvan/wfs",
             "https://bhuvan-vec2.nrsc.gov.in/bhuvan/ows"]:
    q = urllib.parse.urlencode({"service":"WFS","version":"1.0.0","request":"GetFeature",
                                "typeName":L,"maxFeatures":2,"outputFormat":"application/json"})
    try_url("GetFeature " + base.split("/")[-1], base + "?" + q)