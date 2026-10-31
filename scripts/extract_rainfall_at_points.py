"""
Extract IMD gridded rainfall features at landslide point locations.

Source
  IMD 0.25 deg daily rainfall, RF25_ind{YYYY}_rfp25.nc, 35 files 1991-2025.
  Grid 129 x 135, lat 6.5..38.5, lon 66.5..100.0, units mm.
  TIME is "days since 1900-12-31". Ocean/outside-India cells carry fill (-999).

Method
  Pass 1 - read each year once and reduce it to four per-cell maps:
      annual total, monsoon total, monsoon max 1-day, monsoon max 5-day
  Pass 2 - look up each point's grid cell in its own event year.
  Climatology is the 35-year mean at that cell, used to express the event year
  as a ratio (anomaly), i.e. "was that year unusually wet".

Monsoon is defined as 1 June - 30 September (JJAS), the standard Indian
monsoon window.

Honest limits
  GSI records give the YEAR, not the month or day, so no true antecedent
  rainfall (3-day / 7-day pre-event) is possible from this source. Those need
  event dates and belong to a later version.

Output
  04_RAINFALL/derived/rainfall_at_points.csv
"""

import os
import re
import sys
import glob
import warnings
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from scipy.io import netcdf_file

ROOT = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\TERRAPULSE_DATA"
NC_DIR = os.path.join(ROOT, "04_RAINFALL", "IMD_RF25", "rainfall")
IN_CSV = os.path.join(ROOT, "05_TERRAIN", "Copernicus_DEM", "GLO30", "derived", "terrain_at_points.csv")
OUT_DIR = os.path.join(ROOT, "04_RAINFALL", "derived")
OUT_CSV = os.path.join(OUT_DIR, "rainfall_at_points.csv")

warnings.filterwarnings('ignore', message='All-NaN slice')

FILL = -999.0
MONSOON_MONTHS = (6, 7, 8, 9)
EPOCH = datetime(1900, 12, 31)


def year_files():
    out = {}
    for p in sorted(glob.glob(os.path.join(NC_DIR, "RF25_ind*_rfp25.nc"))):
        base = os.path.basename(p)
        try:
            yr = int(base.replace("RF25_ind", "").replace("_rfp25.nc", ""))
        except ValueError:
            continue
        out[yr] = p
    return out


def summarise(path):
    """Read one year -> (annual, monsoon_total, max1d, max5d, lon, lat, year_ok)."""
    nc = netcdf_file(path, "r", mmap=False)
    try:
        lon = np.array(nc.variables["LONGITUDE"][:], dtype="float64")
        lat = np.array(nc.variables["LATITUDE"][:], dtype="float64")
        t = np.array(nc.variables["TIME"][:], dtype="float64")
        r = np.array(nc.variables["RAINFALL"][:], dtype="float32")
    finally:
        nc.close()

    r = np.where(r <= FILL, np.nan, r)
    valid_cell = ~np.all(np.isnan(r), axis=0)

    annual = np.nansum(r, axis=0)
    annual[~valid_cell] = np.nan

    dates = [EPOCH + timedelta(days=int(d)) for d in t]
    yr = dates[0].year if dates else -1
    mask = np.array([d.month in MONSOON_MONTHS for d in dates])
    mons = r[mask]

    if mons.shape[0] == 0:
        shape = annual.shape
        nan = np.full(shape, np.nan)
        return annual, nan.copy(), nan.copy(), nan.copy(), lon, lat, yr

    with np.errstate(invalid="ignore"):
        m_total = np.nansum(mons, axis=0)
        m_max1 = np.nanmax(mons, axis=0)
    for a in (m_total, m_max1):
        a[~valid_cell] = np.nan

    filled = np.nan_to_num(mons, nan=0.0)
    cs = np.cumsum(filled, axis=0)
    if cs.shape[0] >= 5:
        s5 = cs[4:] - np.concatenate([np.zeros((1,) + cs.shape[1:], dtype=cs.dtype), cs[:-5]], axis=0)
        m_max5 = s5.max(axis=0)
    else:
        m_max5 = cs[-1]
    m_max5 = m_max5.astype("float64")
    m_max5[~valid_cell] = np.nan

    return annual, m_total, m_max1, m_max5, lon, lat, yr


def main():
    in_csv = sys.argv[1] if len(sys.argv) > 1 else IN_CSV
    out_csv = sys.argv[2] if len(sys.argv) > 2 else OUT_CSV
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)

    pts = pd.read_csv(in_csv)
    print("points: %d   (%s)" % (len(pts), os.path.basename(in_csv)))

    def year_from_slide_no(s):
        m = re.findall(r"(?:^|/)((?:19|20)\d{2})(?=/|$)", str(s))
        return int(m[-1]) if m else None

    def parse_year(v):
        try:
            y = int(float(str(v).strip()[:4]))
        except (TypeError, ValueError):
            return None
        return y if 1900 <= y <= 2100 else None

    # INITIATION is the true event year but is populated for only ~20% of records.
    # The SLIDE_NO pattern STATE/DISTRICT/TOPOSHEET/YEAR/SERIAL carries a year for
    # ~99%, but where both exist SLIDE_NO is usually LATER (by up to 75 years), so
    # it behaves like the survey/catalogue year rather than the event year.
    # Prefer INITIATION; fall back to SLIDE_NO; always record which was used.
    pts["year_initiation"] = pts["INITIATION"].map(parse_year)
    pts["year_slide_id"] = pts["SLIDE_NO"].map(year_from_slide_no)
    pts["event_year"] = pts["year_initiation"].fillna(pts["year_slide_id"])
    pts["year_source"] = np.where(
        pts["year_initiation"].notna(), "initiation",
        np.where(pts["year_slide_id"].notna(), "slide_id", ""))

    print("year from INITIATION : %d" % pts["year_initiation"].notna().sum())
    print("year from SLIDE_NO   : %d" % pts["year_slide_id"].notna().sum())
    print("usable event year    : %d" % pts["event_year"].notna().sum())
    print("no year at all       : %d" % pts["event_year"].isna().sum())

    files = year_files()
    print("IMD year files: %d  (%d..%d)" % (len(files), min(files), max(files)))

    annual_sum = mons_sum = None
    n_years = None
    lon = lat = None
    per_year = {}

    for yr in sorted(files):
        a, mt, m1, m5, lon, lat, file_year = summarise(files[yr])
        if file_year != yr:
            print("  NOTE: %s spans %d..%d (labelled %d)"
                  % (os.path.basename(files[yr]), file_year, file_year, yr))
        per_year[yr] = (a, mt, m1, m5)
        if annual_sum is None:
            annual_sum = np.where(np.isnan(a), 0.0, a)
            mons_sum = np.where(np.isnan(mt), 0.0, mt)
            m1_sum = np.where(np.isnan(m1), 0.0, m1)
            m5_sum = np.where(np.isnan(m5), 0.0, m5)
            n_years = (~np.isnan(a)).astype("float64")
        else:
            annual_sum += np.where(np.isnan(a), 0.0, a)
            mons_sum += np.where(np.isnan(mt), 0.0, mt)
            m1_sum += np.where(np.isnan(m1), 0.0, m1)
            m5_sum += np.where(np.isnan(m5), 0.0, m5)
            n_years += (~np.isnan(a)).astype("float64")

    nz = np.maximum(n_years, 1)
    clim_annual = np.where(n_years > 0, annual_sum / nz, np.nan)
    clim_mons = np.where(n_years > 0, mons_sum / nz, np.nan)
    clim_m1 = np.where(n_years > 0, m1_sum / nz, np.nan)
    clim_m5 = np.where(n_years > 0, m5_sum / nz, np.nan)
    print("climatology built over %d years" % len(files))

    nlat, nlon = clim_annual.shape
    print("grid: %d lat x %d lon" % (nlat, nlon))

    def cell_of(lo, la):
        c = int(round((lo - lon[0]) / (lon[1] - lon[0])))
        r = int(round((la - lat[0]) / (lat[1] - lat[0])))
        if 0 <= r < nlat and 0 <= c < nlon:
            return r, c
        return None, None

    out = []
    no_year = no_file = fill_cell = gap_year = 0

    for _, p in pts.iterrows():
        r, c = cell_of(p["lon"], p["lat"])
        rec = {
            "SLIDE_NO": p["SLIDE_NO"], "STATE": p["STATE"],
            "lon": p["lon"], "lat": p["lat"],
            "event_year": p["event_year"],
            "year_source": p["year_source"],
            "rain_cell_lon": lon[c] if r is not None else np.nan,
            "rain_cell_lat": lat[r] if r is not None else np.nan,
            "rain_clim_annual_mm": np.nan, "rain_clim_monsoon_mm": np.nan,
            "rain_clim_max1d_mm": np.nan, "rain_clim_max5d_mm": np.nan,
            "rain_annual_mm": np.nan, "rain_monsoon_mm": np.nan,
            "rain_monsoon_max1d_mm": np.nan, "rain_monsoon_max5d_mm": np.nan,
            "rain_anomaly": np.nan, "rain_monsoon_anomaly": np.nan,
            "rain_data_gap": 0,
        }

        if r is None:
            out.append(rec); continue

        if np.isfinite(clim_annual[r, c]):
            rec["rain_clim_annual_mm"] = round(float(clim_annual[r, c]), 1)
            rec["rain_clim_monsoon_mm"] = round(float(clim_mons[r, c]), 1)
            rec["rain_clim_max1d_mm"] = round(float(clim_m1[r, c]), 2)
            rec["rain_clim_max5d_mm"] = round(float(clim_m5[r, c]), 2)
        else:
            fill_cell += 1

        yr = p["event_year"]
        if yr is None or pd.isna(yr):
            no_year += 1
            out.append(rec); continue
        yr = int(yr)
        if yr not in per_year:
            no_file += 1
            out.append(rec); continue

        a, mt, m1, m5 = per_year[yr]
        av = float(a[r, c])
        if not np.isfinite(av):
            out.append(rec); continue

        ca = rec["rain_clim_annual_mm"]
        cm = rec["rain_clim_monsoon_mm"]

        # IMD carries blocks of all-zero cells in some years. Measured case:
        # lon 92.5-93.0 / lat 22.0-22.75 reads 0 mm for 2004 and 2005, then
        # 1893 mm in 2006, against a 2584 mm climatology. That is a source gap,
        # not drought. A year far below the cell's own climatology is treated as
        # missing and flagged, never fed to the model as a real value.
        if np.isfinite(ca) and ca > 0 and av < 0.20 * ca:
            rec["rain_data_gap"] = 1
            out.append(rec)
            gap_year += 1
            continue

        rec["rain_annual_mm"] = round(av, 1)
        rec["rain_monsoon_mm"] = round(float(mt[r, c]), 1)
        rec["rain_monsoon_max1d_mm"] = round(float(m1[r, c]), 1)
        rec["rain_monsoon_max5d_mm"] = round(float(m5[r, c]), 1)
        if np.isfinite(ca) and ca > 0:
            rec["rain_anomaly"] = round(av / ca, 3)
        if np.isfinite(cm) and cm > 0:
            rec["rain_monsoon_anomaly"] = round(float(mt[r, c]) / cm, 3)
        out.append(rec)

    df = pd.DataFrame(out)
    df.to_csv(out_csv, index=False)
    print("\nwrote %s" % out_csv)

    print("\n--- coverage ---")
    print("rows                       : %d" % len(df))
    print("annual rainfall present    : %d" % df.rain_annual_mm.notna().sum())
    print("  missing: no event year   : %d" % no_year)
    print("  missing: year not in IMD : %d" % no_file)
    print("  missing: fill/ocean cell : %d" % fill_cell)
    print("  missing: IMD zero-block  : %d" % gap_year)

    print("\n--- published sanity check (wettest place on Earth) ---")
    for st in ["Meghalaya", "Mizoram", "Sikkim", "Assam", "Arunachal Pradesh"]:
        s = df[df.STATE == st]["rain_clim_annual_mm"].dropna()
        if len(s):
            print("  %-20s n=%4d  mean clim annual = %7.0f mm   max = %7.0f mm"
                  % (st, len(s), s.mean(), s.max()))

    print("\n--- event-year feature stats ---")
    cols = ["rain_clim_annual_mm", "rain_clim_monsoon_mm", "rain_clim_max1d_mm",
            "rain_clim_max5d_mm", "rain_annual_mm", "rain_monsoon_mm",
            "rain_anomaly", "rain_monsoon_anomaly"]
    print(df[cols].describe().round(1).to_string())


if __name__ == "__main__":
    main()