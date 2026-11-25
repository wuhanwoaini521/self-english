"""Download source word lists and sentence pairs into data/raw."""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

FILES = [
    (
        "cefrj-vocabulary-profile-1.5.csv",
        "https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/cefrj-vocabulary-profile-1.5.csv",
        True,
    ),
    (
        "cefrj-grammar-profile-20180315.csv",
        "https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/cefrj-grammar-profile-20180315.csv",
        False,
    ),
    (
        "NGSL-Spoken_1.2.txt",
        "https://raw.githubusercontent.com/koba-ninkigumi/ngsl/master/NGSL-Spoken_1.2.txt",
        True,
    ),
    (
        "NGSL-1.01.csv",
        "https://raw.githubusercontent.com/koba-ninkigumi/ngsl/master/NGSL-1.01.csv",
        False,
    ),
    (
        "ecdict.csv",
        "https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv",
        True,
    ),
    (
        "cmn-eng.zip",
        "https://www.manythings.org/anki/cmn-eng.zip",
        True,
    ),
    (
        "cmudict.dict",
        "https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict",
        False,
    ),
]


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"skip {dest.name} ({dest.stat().st_size} bytes)")
        return
    tmp = dest.with_suffix(dest.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "self-english/0.1"})
    print(f"get {url}")
    with urllib.request.urlopen(request, timeout=600) as response, tmp.open("wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        next_report = 0
        while True:
            chunk = response.read(256 * 1024)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total and done >= next_report:
                print(f"  {dest.name} {done / total:.0%} ({done // 1024} KB)")
                next_report = done + max(total // 10, 1)
    tmp.replace(dest)
    print(f"saved {dest.name} ({dest.stat().st_size} bytes)")


def main() -> None:
    failed = False
    for name, url, required in FILES:
        try:
            download(url, RAW / name)
        except urllib.error.HTTPError as exc:
            print(f"fail {name}: HTTP {exc.code}")
            failed = failed or required
        except Exception as exc:
            print(f"fail {name}: {exc}")
            failed = failed or required
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
