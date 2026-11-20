"""検索APIでジャンルに合うチャンネルを発見し sites/<site>/data/channels.json に追加する（週1回想定）。

使い方: python scripts/discover.py <site> [ページ数]

クォータ: 1検索 = 100ユニット。クエリ数 x ページ数 x 100 を消費する。
"""
import re
import sys

import yt
from common import load_json, save_json, site_from_argv, today_jst

JP = re.compile(r"[぀-ヿ一-鿿]")


def is_relevant(snippet, cfg):
    title = snippet.get("title", "")
    desc = snippet.get("description", "")
    text = (title + "\n" + desc).lower()
    if not JP.search(title + desc):
        return False
    core = re.compile(cfg["core_pattern"], re.I)
    if core.search(title):
        return True
    hits = sum(text.count(k.lower()) for k in cfg["relevance_keywords"])
    return len(core.findall(text)) >= 2 and hits >= 3


def main(site, pages=2):
    cfg = site.cfg
    path = site.data / "channels.json"
    db = load_json(path, {"channels": {}, "rejected": []})
    known = set(db["channels"]) | set(db["rejected"]) | set(cfg["exclude_channel_ids"])

    found = set()
    for q in cfg["discover_queries"]:
        token = None
        for _ in range(pages):
            params = dict(part="snippet", type="channel", q=q, regionCode="JP",
                          relevanceLanguage="ja", maxResults=50)
            if token:
                params["pageToken"] = token
            r = yt.get("search", **params)
            found |= {i["id"]["channelId"] for i in r.get("items", [])}
            token = r.get("nextPageToken")
            if not token:
                break

    new_ids = [c for c in found if c not in known]
    added = 0
    for c in yt.channels(new_ids, part="snippet,statistics"):
        sn, st = c["snippet"], c["statistics"]
        subs = int(st.get("subscriberCount", 0))
        if st.get("hiddenSubscriberCount") or subs < cfg["min_subscribers"] \
                or not is_relevant(sn, cfg):
            db["rejected"].append(c["id"])
            continue
        db["channels"][c["id"]] = {
            "title": sn["title"],
            "description": sn.get("description", "")[:400],
            "thumb": yt.best_thumb(sn.get("thumbnails", {})),
            "custom_url": sn.get("customUrl", ""),
            "published_at": sn.get("publishedAt", "")[:10],
            "country": sn.get("country", ""),
            "added": today_jst().isoformat(),
        }
        added += 1
    db["rejected"] = sorted(set(db["rejected"]))
    save_json(path, db)
    print(f"searched={len(found)} new_candidates={len(new_ids)} added={added} "
          f"total={len(db['channels'])}")


if __name__ == "__main__":
    main(site_from_argv(), int(sys.argv[2]) if len(sys.argv) > 2 else 2)
