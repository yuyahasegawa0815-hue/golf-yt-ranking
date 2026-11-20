import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))


class Site:
    """sites/<name>/ 配下の設定・データへのパスをまとめたもの。"""

    def __init__(self, name):
        self.name = name
        self.dir = ROOT / "sites" / name
        if not self.dir.is_dir():
            sys.exit(f"unknown site: {name}")
        self.data = self.dir / "data"
        self.snap = self.data / "snapshots"
        self.cfg = load_json(self.dir / "config.json")
        self.dist = ROOT / "dist" / name


def site_from_argv(pos=1):
    if len(sys.argv) <= pos:
        sys.exit("usage: python scripts/<script>.py <site> [...]  (site: golf / poker)")
    return Site(sys.argv[pos])


def load_json(path, default=None):
    path = pathlib.Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, obj, compact=False):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    else:
        text = json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")


def today_jst():
    return datetime.now(JST).date()
