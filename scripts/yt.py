"""YouTube Data API v3 の最小ラッパー（標準ライブラリのみ）。

APIキーは環境変数 YT_API_KEY から読む。未設定の場合はキーなしでリクエストする
（キーを自動付与するプロキシ環境向け）。
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://www.googleapis.com/youtube/v3/"


def get(endpoint, **params):
    key = os.environ.get("YT_API_KEY")
    if key:
        params["key"] = key
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (500, 503) and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            body = e.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"YouTube API error {e.code} on {endpoint}: {body}") from e


def chunks(seq, n=50):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def channels(ids, part="snippet,statistics,contentDetails"):
    out = []
    for batch in chunks(ids):
        out += get("channels", part=part, id=",".join(batch), maxResults=50).get("items", [])
    return out


def videos(ids, part="snippet,statistics,contentDetails"):
    out = []
    for batch in chunks(ids):
        out += get("videos", part=part, id=",".join(batch), maxResults=50).get("items", [])
    return out


def best_thumb(thumbs):
    for k in ("medium", "high", "default"):
        if k in thumbs:
            return thumbs[k]["url"]
    return ""
