"""登録チャンネルの統計と直近動画を取得して保存する（毎日実行）。

出力:
  sites/<site>/data/snapshots/YYYY-MM-DD.json  {channel_id: [登録者, 総再生, 動画数]}
  sites/<site>/data/videos.json                直近30日に公開された動画の最新統計
クォータ目安: チャンネル数 + 数十ユニット / 日
"""
import re
from datetime import datetime, timedelta, timezone

import yt
from common import load_json, save_json, site_from_argv, today_jst

DUR = re.compile(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def seconds(iso):
    m = DUR.fullmatch(iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def main(site):
    cfg = site.cfg
    path = site.data / "channels.json"
    db = load_json(path, {"channels": {}, "rejected": []})
    today = today_jst()
    snap, uploads = {}, {}

    alive = set()
    for c in yt.channels(db["channels"].keys()):
        cid, sn, st = c["id"], c["snippet"], c["statistics"]
        alive.add(cid)
        meta = db["channels"][cid]
        meta["title"] = sn["title"]
        meta["thumb"] = yt.best_thumb(sn.get("thumbnails", {})) or meta.get("thumb", "")
        meta["description"] = sn.get("description", "")[:400]
        meta["custom_url"] = sn.get("customUrl", meta.get("custom_url", ""))
        snap[cid] = [int(st.get("subscriberCount", 0)), int(st.get("viewCount", 0)),
                     int(st.get("videoCount", 0))]
        up = c.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        if up:
            uploads[cid] = up
    for cid in set(db["channels"]) - alive:  # 削除・非公開になったチャンネル
        db["channels"][cid]["inactive"] = True

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    vids = []
    for cid, pl in uploads.items():
        try:
            r = yt.get("playlistItems", part="contentDetails", playlistId=pl, maxResults=10)
        except RuntimeError:
            continue
        for it in r.get("items", []):
            pub = it["contentDetails"].get("videoPublishedAt")
            if pub and datetime.fromisoformat(pub.replace("Z", "+00:00")) >= cutoff:
                vids.append(it["contentDetails"]["videoId"])

    videos = []
    for v in yt.videos(vids):
        sn, st = v["snippet"], v.get("statistics", {})
        videos.append({
            "desc": sn.get("description", "")[:300],
            "id": v["id"],
            "channel": sn["channelId"],
            "title": sn["title"],
            "published_at": sn["publishedAt"],
            "thumb": yt.best_thumb(sn.get("thumbnails", {})),
            "duration": seconds(v.get("contentDetails", {}).get("duration")),
            "views": int(st.get("viewCount", 0)),
            "likes": int(st.get("likeCount", 0)),
            "comments": int(st.get("commentCount", 0)),
        })

    save_json(site.snap / f"{today.isoformat()}.json", snap, compact=True)
    save_json(site.data / "videos.json", {"date": today.isoformat(), "videos": videos})
    save_json(path, db)

    # YouTube API ポリシー（保存データは30日以内に更新/削除）に合わせて古い履歴を削除
    keep_from = today - timedelta(days=cfg["keep_days"])
    for f in site.snap.glob("*.json"):
        if f.stem < keep_from.isoformat():
            f.unlink()
    print(f"channels={len(snap)} videos={len(videos)}")


if __name__ == "__main__":
    main(site_from_argv())
