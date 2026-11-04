"""Download the public NHANES 1999-2002 (DNA methylation), 2003-2006, 2011-2014 and 2015-2018 files used in research/

    python3 research/fetch_nhanes.py            # into research/data/

Sources (US CDC / NCHS public-use data):
- NHANES: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/<year>/DataFiles/
- Linked mortality (follow-up to 31 Dec 2019):
  https://ftp.cdc.gov/pub/Health_Statistics/NCHS/datalinkage/linked_mortality/

Files already downloaded with the right size are skipped.
"""

import os
import sys
import urllib.parse
import urllib.request

NHANES = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/%s/DataFiles/%s"
MORT = ("https://ftp.cdc.gov/pub/Health_Statistics/NCHS/datalinkage/"
        "linked_mortality/%s")
DNAM = "https://wwwn.cdc.gov/Nchs/data/nhanes/dnam/%s"

FILES = [
    # 2003-2004 (cycle C)
    NHANES % ("2003", "DEMO_C.xpt"),
    NHANES % ("2003", "L40_C.xpt"),       # biochemistry: albumin, creatinine, glucose, ALP
    NHANES % ("2003", "L11_C.xpt"),       # CRP
    NHANES % ("2003", "L25_C.xpt"),       # complete blood count
    NHANES % ("2003", "PAXRAW_C.ZIP"),    # hip accelerometer, minute by minute
    NHANES % ("2003", "BPX_C.xpt"),       # exam blood pressure and pulse
    MORT % "NHANES_2003_2004_MORT_2019_PUBLIC.dat",
    # 2005-2006 (cycle D)
    NHANES % ("2005", "DEMO_D.xpt"),
    NHANES % ("2005", "BIOPRO_D.xpt"),
    NHANES % ("2005", "CRP_D.xpt"),
    NHANES % ("2005", "CBC_D.xpt"),
    NHANES % ("2005", "PAXRAW_D.ZIP"),
    NHANES % ("2005", "BPX_D.xpt"),
    MORT % "NHANES_2005_2006_MORT_2019_PUBLIC.dat",
    # 2011-2012 (G) and 2013-2014 (H): wrist accelerometry as daily (PAXDAY)
    # and hourly (PAXHR, ~130-145 MB each) summaries. No CRP or hs-CRP was
    # measured in these cycles.
    NHANES % ("2011", "DEMO_G.xpt"),
    NHANES % ("2011", "BIOPRO_G.xpt"),
    NHANES % ("2011", "CBC_G.xpt"),
    NHANES % ("2011", "BPX_G.xpt"),
    NHANES % ("2011", "PAXDAY_G.xpt"),    # daily MIMS, wear/sleep/non-wear minutes
    NHANES % ("2011", "PAXHD_G.xpt"),     # monitor header: start time, data quality
    NHANES % ("2011", "PAXHR_G.xpt"),     # hourly MIMS and wake/sleep/non-wear minutes
    MORT % "NHANES_2011_2012_MORT_2019_PUBLIC.dat",
    NHANES % ("2013", "DEMO_H.xpt"),
    NHANES % ("2013", "BIOPRO_H.xpt"),
    NHANES % ("2013", "CBC_H.xpt"),
    NHANES % ("2013", "BPX_H.xpt"),
    NHANES % ("2013", "PAXDAY_H.xpt"),
    NHANES % ("2013", "PAXHD_H.xpt"),
    NHANES % ("2013", "PAXHR_H.xpt"),
    MORT % "NHANES_2013_2014_MORT_2019_PUBLIC.dat",
    # 2015-2016 (I) and 2017-2018 (J): confirmatory test set, labs + hs-CRP only
    NHANES % ("2015", "DEMO_I.xpt"),
    NHANES % ("2015", "BIOPRO_I.xpt"),
    NHANES % ("2015", "CBC_I.xpt"),
    NHANES % ("2015", "HSCRP_I.xpt"),     # LBXHSCRP, mg/L
    MORT % "NHANES_2015_2016_MORT_2019_PUBLIC.dat",
    NHANES % ("2017", "DEMO_J.xpt"),
    NHANES % ("2017", "BIOPRO_J.xpt"),
    NHANES % ("2017", "CBC_J.xpt"),
    NHANES % ("2017", "HSCRP_J.xpt"),
    MORT % "NHANES_2017_2018_MORT_2019_PUBLIC.dat",
    # 1999-2000 and 2001-2002: DNA methylation clocks (adults 50+) with labs
    DNAM % "dnmepi.sas7bdat",
    DNAM % "NHANES%20DNAm%20Epigenetic%20Biomarkers%20Data%20Documentation.pdf",
    NHANES % ("1999", "DEMO.xpt"),
    NHANES % ("1999", "LAB18.xpt"),       # biochemistry
    NHANES % ("1999", "LAB11.xpt"),       # CRP
    NHANES % ("1999", "LAB25.xpt"),       # complete blood count
    NHANES % ("1999", "BPX.xpt"),
    NHANES % ("2001", "DEMO_B.xpt"),
    NHANES % ("2001", "L40_B.xpt"),
    NHANES % ("2001", "L11_B.xpt"),
    NHANES % ("2001", "L25_B.xpt"),
    NHANES % ("2001", "BPX_B.xpt"),
]


def fetch(url, folder):
    name = urllib.parse.unquote(url.rsplit("/", 1)[1])
    path = os.path.join(folder, name)
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD")) as r:
        size = int(r.headers.get("Content-Length", 0))
    if os.path.exists(path) and os.path.getsize(path) == size:
        print("have  %s" % name)
        return path
    print("get   %s (%.1f MB)" % (name, size / 1e6), flush=True)
    tmp = path + ".part"
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    if size and os.path.getsize(tmp) != size:
        raise IOError("%s: expected %d bytes, got %d" % (name, size, os.path.getsize(tmp)))
    os.replace(tmp, path)
    return path


def main():
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(folder, exist_ok=True)
    for url in FILES:
        fetch(url, folder)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
