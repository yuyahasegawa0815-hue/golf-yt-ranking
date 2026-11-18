"""検索APIでゴルフ系チャンネルを発見し data/channels.json に追加する（週1回想定）。

クォータ: 1検索 = 100ユニット。クエリ数 x ページ数 x 100 を消費する。
"""
import re
import sys

import yt
from common import DATA, config, load_json, save_json, today_jst

JP = re.compile(r"[぀-ヿ一-鿿]")


def is_golf(snippet, keywords):
    title = snippet.get("title", "")
    desc = snippet.get("description", "")
    text = (title + "\n" + desc).lower()
    if not JP.search(title + desc):
        return False
    if re.search(r"ゴルフ|golf|ゴルファー", title, re.I):
        return True
    hits = sum(text.count(k.lower()) for k in keywords)
    return text.count("ゴルフ") + text.count("golf") >= 2 and hits >= 3


def main(pages=2):
    cfg = config()
    path = DATA / "channels.json"
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
                or not is_golf(sn, cfg["relevance_keywords"]):
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
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2)
