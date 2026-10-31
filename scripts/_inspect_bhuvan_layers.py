import re
xml = open(r"C:\Users\Ravichandran\Downloads\TERRAPULSE\TERRAPULSE_DATA\07_GEOLOGY\bhuvan_wms_capabilities.xml",
           encoding="utf-8", errors="replace").read()
print("capabilities length:", len(xml))
print()
for lay in ["lineament:AR_LN50K_0506", "lineament:SK_LN50K_0506",
            "geomorphology:AR_GM50K_0506", "geomorphology:SK_GM50K_0506"]:
    i = xml.find("<Name>" + lay + "</Name>")
    if i < 0:
        print(lay, "-> NOT FOUND")
        continue
    seg = xml[max(0, i - 2000): i + 500]
    q = re.search(r'queryable="(\d)"', seg)
    print(lay)
    print("   queryable :", q.group(1) if q else "not found")
    for m in re.finditer(r"<(MinScaleDenominator|MaxScaleDenominator)>([^<]+)<", seg):
        print("   ", m.group(1), "=", m.group(2))
    print("   context:", re.sub(r"\s+", " ", seg[-260:]))
    print()