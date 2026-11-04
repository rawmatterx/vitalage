"""Download the public NHANES 2003-2006 files used to refit the model.

    python3 research/fetch_nhanes.py            # into research/data/

Sources (US CDC / NCHS public-use data):
- NHANES: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/<year>/DataFiles/
- Linked mortality (follow-up to 31 Dec 2019):
  https://ftp.cdc.gov/pub/Health_Statistics/NCHS/datalinkage/linked_mortality/

Files already downloaded with the right size are skipped.
"""

import os
import sys
import urllib.request

NHANES = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/%s/DataFiles/%s"
MORT = ("https://ftp.cdc.gov/pub/Health_Statistics/NCHS/datalinkage/"
        "linked_mortality/%s")

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
]


def fetch(url, folder):
    name = url.rsplit("/", 1)[1]
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
