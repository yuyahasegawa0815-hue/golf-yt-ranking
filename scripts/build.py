"""sites/<site>/ の設定・データから静的サイトを dist/<site>/ に生成する。

使い方: python scripts/build.py <site>
- YouTube集計ページ（ランキング・急上昇・動画・チャンネル個別）を自動生成
- sites/<site>/pages/**.html を共通レイアウトで包んで出力（ツール・解説ページ用）
  先頭行に <!--{"title": ..., "description": ...}--> を書く。本文中の {{root}} はサイトルートへの相対パスに置換
- sites/<site>/assets/ はそのまま dist/<site>/assets/ にコピー
"""
import html
import json
import re
import shutil
from datetime import date, datetime, timedelta, timezone

from common import ROOT, load_json, site_from_argv

e = html.escape
SITE = site_from_argv()
CFG = SITE.cfg
DIST = SITE.dist
NAME = CFG["site_name"]
BASE = CFG["base_url"].rstrip("/")
NOW = datetime.now(timezone.utc)
PAGES = []


# ---------- 表示ヘルパー ----------
def num(n):
    if n is None:
        return "-"
    if abs(n) >= 100_000_000:
        return f"{n / 100_000_000:.2f}億"
    if abs(n) >= 10_000:
        return f"{n / 10_000:.1f}万".replace(".0万", "万")
    return f"{n:,}"


def delta(n):
    if n is None:
        return "-"
    if n == 0:
        return "±0"
    cls = "up" if n > 0 else "down"
    return f'<span class="{cls}">{"+" if n > 0 else "−"}{num(abs(n))}</span>'


def dur(sec):
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


def parse_time(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def ago(iso):
    d = NOW - parse_time(iso)
    return f"{d.days}日前" if d.days >= 1 else f"{max(1, d.seconds // 3600)}時間前"


# ---------- データ ----------
def load():
    chans = {k: v for k, v in load_json(SITE.data / "channels.json")["channels"].items()
             if not v.get("inactive")}
    files = sorted(SITE.snap.glob("*.json"))
    snaps = {f.stem: load_json(f) for f in files}
    latest_day = files[-1].stem
    latest = snaps[latest_day]
    target = (date.fromisoformat(latest_day) - timedelta(days=7)).isoformat()
    on_or_before = [d for d in snaps if d <= target]
    earlier = [d for d in snaps if d < latest_day]
    base_day = max(on_or_before) if on_or_before else (min(earlier) if earlier else None)
    base = snaps.get(base_day, {}) if base_day else {}
    rows = []
    for cid, meta in chans.items():
        if cid not in latest:
            continue
        subs, views, vids = latest[cid]
        b = base.get(cid)
        rows.append({"id": cid, **meta, "subs": subs, "views": views, "videos": vids,
                     "d_subs": subs - b[0] if b else None,
                     "d_views": views - b[1] if b else None})
    by_id = {r["id"]: r for r in rows}

    # 動画: ジャンル外チャンネルの無関係な動画を除外し、ジャンル分類する
    core = re.compile(CFG.get("core_pattern", "."), re.I)
    vpat = re.compile(CFG["video_pattern"], re.I) if CFG.get("video_pattern") else None
    genres = CFG.get("genres", [])
    videos = []
    for v in load_json(SITE.data / "videos.json")["videos"]:
        ch = by_id.get(v["channel"])
        if not ch:
            continue
        if vpat and not core.search(ch["title"]) and not vpat.search(v["title"] + " " + v.get("desc", "")):
            continue
        v["genre"] = next((g["slug"] for g in genres
                           if not g["pattern"] or re.search(g["pattern"], v["title"], re.I)), None)
        videos.append(v)
    return rows, by_id, snaps, latest_day, base_day, videos


# ---------- レイアウト ----------
def theme_css():
    t = CFG.get("theme")
    if not t:
        return ""
    light = f'--accent:{t["accent"]};--accent-weak:{t["accent_weak"]};--up:{t["accent"]}'
    dark = f'--accent:{t["accent_dark"]};--accent-weak:{t["accent_weak_dark"]};--up:{t["accent_dark"]}'
    return (f"<style>:root{{{light}}}@media (prefers-color-scheme:dark){{:root{{{dark}}}}}</style>")


def page(path, title, desc, body, jsonld=None, extra_head=""):
    depth = path.count("/")
    root = "../" * depth
    head = ""
    if CFG.get("gsc_verification"):
        head += f'<meta name="google-site-verification" content="{e(CFG["gsc_verification"])}">'
    if CFG.get("ga4_id"):
        g = e(CFG["ga4_id"])
        head += (f'<script async src="https://www.googletagmanager.com/gtag/js?id={g}"></script>'
                 f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}"
                 f"gtag('js',new Date());gtag('config','{g}');</script>")
    if jsonld:
        head += f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>'
    url = f"{BASE}/{path}".replace("index.html", "")
    full_title = title if title == NAME else f"{title}｜{NAME}"
    nav = "".join(f'<a href="{root}{p}">{e(label)}</a>' for label, p in CFG["nav"])
    doc = f"""<!doctype html>
<html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(full_title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:title" content="{e(full_title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:type" content="website"><meta property="og:url" content="{e(url)}">
<meta name="twitter:card" content="summary">
<link rel="stylesheet" href="{root}style.css">{theme_css()}{head}{extra_head}
</head><body>
<header class="site"><div class="wrap">
<a class="logo" href="{root}">{CFG["logo_html"]}</a>
<nav>{nav}</nav>
</div></header>
<main class="wrap">{body.replace("{{root}}", root)}</main>
<footer><div class="wrap">
<a href="{root}about/">運営者情報・データについて</a><a href="{root}about/#privacy">プライバシーポリシー</a>
<p>動画データ出典: YouTube Data API（YouTube は Google LLC の商標です）。当サイトはYouTubeの公式サイトではありません。<br>&copy; {date.today().year} {e(NAME)}</p>
</div></footer>
</body></html>
"""
    out = DIST / path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    if path != "404.html":
        PAGES.append(path)


def crumb(*items):
    parts = ['<a href="{{root}}">ホーム</a>', *items]
    return '<div class="crumb">' + " › ".join(parts) + "</div>"


def ch_cell(r):
    return (f'<a class="ch" href="{{{{root}}}}channel/{r["id"]}/"><img src="{e(r["thumb"])}" alt="" '
            f'loading="lazy" width="36" height="36"><b>{e(r["title"])}</b></a>')


def rank_table(rows, mode, limit=None, period=""):
    rows = rows[:limit] if limit else rows
    if mode == "growth":
        head = (f'<th>#</th><th class="name">チャンネル</th><th>再生数増加{period}</th>'
                f'<th>登録者増加{period}</th><th class="opt">登録者数</th>')
        body = "".join(
            f'<tr><td class="no">{i}</td><td class="name">{ch_cell(r)}</td>'
            f'<td>{delta(r["d_views"])}</td><td>{delta(r["d_subs"])}</td>'
            f'<td class="opt">{num(r["subs"])}</td></tr>' for i, r in enumerate(rows, 1))
    else:
        head = ('<th>#</th><th class="name">チャンネル</th><th>登録者数</th>'
                '<th class="opt">総再生数</th><th class="opt">動画数</th>')
        body = "".join(
            f'<tr data-q="{e(r["title"].lower())}"><td class="no">{i}</td><td class="name">{ch_cell(r)}</td>'
            f'<td>{num(r["subs"])}</td><td class="opt">{num(r["views"])}</td>'
            f'<td class="opt">{r["videos"]:,}</td></tr>' for i, r in enumerate(rows, 1))
    return f'<div class="scroll"><table class="rank"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def video_grid(vs, chans, ranked=False):
    if not vs:
        return '<p class="note">該当する動画はまだありません。</p>'
    cards = []
    for i, v in enumerate(vs, 1):
        ch = chans.get(v["channel"], {})
        badge = f'<span class="badge">{i}</span>' if ranked else ""
        cards.append(
            f'<a class="vid" href="https://www.youtube.com/watch?v={e(v["id"])}" target="_blank" rel="noopener">'
            f'<div class="th">{badge}<img src="{e(v["thumb"])}" alt="" loading="lazy"></div>'
            f'<div class="t">{e(v["title"])}</div>'
            f'<div class="m">{e(ch.get("title", ""))}<br>{num(v["views"])}回再生・{ago(v["published_at"])}・{dur(v["duration"])}</div></a>')
    return f'<div class="grid">{"".join(cards)}</div>'


def itemlist(rows):
    return {"@context": "https://schema.org", "@type": "ItemList",
            "itemListElement": [{"@type": "ListItem", "position": i, "name": r["title"],
                                 "url": f"{BASE}/channel/{r['id']}/"} for i, r in enumerate(rows[:50], 1)]}


# ---------- 共通の集計ページ ----------
def build_common(rows, by_id, snaps, latest_day, base_day, videos, ctx):
    updated, period, days = ctx["updated"], ctx["period"], ctx["days"]
    by_subs, by_growth, has_growth = ctx["by_subs"], ctx["by_growth"], ctx["has_growth"]
    label = CFG.get("genre_label", "")

    page("ranking/subscribers/index.html", f"{label}YouTuber 登録者数ランキング",
         f"{label}系YouTubeチャンネルの登録者数ランキング（{latest_day}時点・全{len(rows)}件）。毎日自動更新。",
         crumb("登録者数ランキング") + f'<h1>{label}YouTuber 登録者数ランキング</h1>'
         f'<p class="lead">国内{label}系YouTubeチャンネル{len(rows)}件の登録者数順。{updated}</p>'
         '<input class="filter" type="search" placeholder="チャンネル名で絞り込み" '
         'oninput="var q=this.value.toLowerCase();document.querySelectorAll(\'tbody tr\').forEach(function(t){t.style.display=t.dataset.q.indexOf(q)<0?\'none\':\'\'})">'
         + rank_table(by_subs, "subs"), itemlist(by_subs))

    page("ranking/growth/index.html", f"{label}YouTube 急上昇ランキング",
         f"今週伸びている{label}YouTubeチャンネルを再生数・登録者数の増加で毎日ランキング。",
         crumb("急上昇ランキング") + f'<h1>{label}YouTube 急上昇ランキング</h1>'
         f'<p class="lead">直近{days or 7}日間の総再生数の増加が大きい順。{updated}</p>'
         '<p class="note">※YouTubeの登録者数は概数（上位3桁）で公開されるため、再生数の増加を主指標にしています。</p>'
         + (rank_table(by_growth, "growth", 100, period) if has_growth else ctx["collecting"]),
         itemlist(by_growth) if has_growth else None)

    rank_of = {r["id"]: i for i, r in enumerate(by_subs, 1)}
    vids_by_ch = {}
    for v in sorted(videos, key=lambda v: v["published_at"], reverse=True):
        vids_by_ch.setdefault(v["channel"], []).append(v)
    days_sorted = sorted(snaps)
    for r in rows:
        hist = [(d, snaps[d][r["id"]]) for d in days_sorted if r["id"] in snaps[d]][-30:]
        hist_rows = "".join(f'<tr><td class="name">{d}</td><td>{num(s[0])}</td><td>{num(s[1])}</td><td>{s[2]:,}</td></tr>'
                            for d, s in reversed(hist))
        yt_url = (f'https://www.youtube.com/{r["custom_url"]}' if r.get("custom_url")
                  else f'https://www.youtube.com/channel/{r["id"]}')
        body = (crumb('<a href="{{root}}ranking/subscribers/">登録者数ランキング</a>', e(r["title"]))
                + f'<div class="prof"><img src="{e(r["thumb"])}" alt="{e(r["title"])}"><div>'
                f'<h1>{e(r["title"])}</h1><div class="lead">{label}YouTube登録者数ランキング {rank_of[r["id"]]}位 / {len(rows)}</div></div></div>'
                '<div class="stats">'
                f'<div class="stat"><div class="k">登録者数</div><div class="v">{num(r["subs"])}</div><div class="d">{delta(r["d_subs"])} {period}</div></div>'
                f'<div class="stat"><div class="k">総再生数</div><div class="v">{num(r["views"])}</div><div class="d">{delta(r["d_views"])} {period}</div></div>'
                f'<div class="stat"><div class="k">動画数</div><div class="v">{r["videos"]:,}</div></div>'
                f'<div class="stat"><div class="k">開設日</div><div class="v" style="font-size:1.1rem">{e(r.get("published_at", ""))}</div></div>'
                '</div>'
                f'<a class="btn" href="{e(yt_url)}" target="_blank" rel="noopener">YouTubeでチャンネルを見る</a>'
                + ('<h2>最近の動画</h2>' + video_grid(vids_by_ch[r["id"]][:8], by_id) if r["id"] in vids_by_ch else "")
                + '<h2>登録者数・再生数の推移（直近30日）</h2>'
                '<div class="scroll"><table class="rank"><thead><tr><th class="name">日付</th><th>登録者数</th><th>総再生数</th><th>動画数</th></tr></thead>'
                f'<tbody>{hist_rows}</tbody></table></div>'
                + (f'<h2>チャンネル紹介</h2><div class="desc">{e(r["description"])}</div>' if r.get("description") else ""))
        page(f"channel/{r['id']}/index.html", f"{r['title']}の登録者数・再生数推移",
             f"{label}YouTubeチャンネル「{r['title']}」の登録者数{num(r['subs'])}人・総再生数・最近の動画・推移データ。", body)

    page("about/index.html", "このサイトについて", f"{NAME}の運営者情報・データの取得方法・プライバシーポリシー。",
         crumb("このサイトについて") + '<h1>このサイトについて</h1>'
         f'<p>{e(NAME)}は、{e(CFG["site_description"])}です。YouTubeのデータはYouTube Data APIで毎日自動取得しています。</p>'
         '<h2>データについて</h2><ul>'
         f'<li>集計対象は、{label}に関する発信をしている日本語のチャンネル（登録者{CFG["min_subscribers"]:,}人以上）です。対象は自動で随時追加しています。</li>'
         '<li>動画のジャンル分類はタイトルから自動判定しているため、実際の内容と異なる場合があります。</li>'
         '<li>登録者数はYouTubeの公開仕様により概数です。</li>'
         '<li>掲載データはYouTube API サービスの利用規約に従い、取得から30日を超えたものは削除しています。</li>'
         '<li>掲載の追加・削除のご希望はお問い合わせください。</li></ul>'
         + CFG.get("about_extra_html", "") +
         '<h2 id="privacy">プライバシーポリシー</h2>'
         '<p>当サイトはアクセス解析のためにGoogle アナリティクスを利用することがあり、Cookieを使用してデータを収集します。'
         'データは匿名で収集され、個人を特定するものではありません。また、当サイトはアフィリエイトプログラムに参加しており、'
         '商品紹介リンクを含む場合があります。</p>'
         '<p>当サイトはYouTube API サービスを利用しています。'
         '<a href="https://www.youtube.com/t/terms" target="_blank" rel="noopener">YouTube 利用規約</a>・'
         '<a href="https://policies.google.com/privacy" target="_blank" rel="noopener">Google プライバシーポリシー</a></p>'
         '<h2>お問い合わせ</h2><p>（お問い合わせ先を設定してください）</p>')


# ---------- ゴルフ版 ----------
def build_golf(rows, by_id, videos, ctx):
    week = sorted([v for v in videos if parse_time(v["published_at"]) >= NOW - timedelta(days=7)],
                  key=lambda v: -v["views"])
    month = sorted(videos, key=lambda v: -v["views"])
    body = (f'<h1>{e(NAME)}</h1><p class="lead">国内のゴルフ系YouTubeチャンネル{len(rows)}件を毎日自動集計。{ctx["updated"]}</p>'
            '<h2>今週の急上昇チャンネル</h2>'
            + (rank_table(ctx["by_growth"], "growth", 10, ctx["period"]) + '<a class="more" href="ranking/growth/">急上昇ランキングをすべて見る →</a>'
               if ctx["has_growth"] else ctx["collecting"])
            + '<h2>今週の人気ゴルフ動画</h2>' + video_grid(week[:8], by_id)
            + '<a class="more" href="videos/">人気動画をもっと見る →</a>'
            + '<h2>登録者数ランキング TOP20</h2>' + rank_table(ctx["by_subs"], "subs", 20)
            + '<a class="more" href="ranking/subscribers/">全チャンネルを見る →</a>')
    page("index.html", NAME, f"ゴルフYouTuberの登録者数ランキング・急上昇・人気動画を毎日自動更新。国内{len(rows)}チャンネルを集計。",
         body, itemlist(ctx["by_subs"]))
    page("videos/index.html", "今週の人気ゴルフ動画ランキング",
         "今週公開されたゴルフYouTube動画を再生数順に紹介。レッスン・ラウンド・試打動画の話題作がわかる。",
         crumb("人気動画") + '<h1>今週の人気ゴルフ動画</h1>'
         f'<p class="lead">直近7日間に公開されたゴルフ動画の再生数順。{ctx["updated"]}</p>'
         + video_grid(week[:60], by_id) + '<h2>過去30日の人気ゴルフ動画</h2>' + video_grid(month[:40], by_id))


# ---------- ポーカー版 ----------
def build_poker(rows, by_id, videos, ctx):
    genres = CFG["genres"]
    week = [v for v in videos if parse_time(v["published_at"]) >= NOW - timedelta(days=7)]
    top = lambda vs, n: sorted(vs, key=lambda v: -v["views"])[:n]  # noqa: E731
    tabs = ('<div class="tabs"><a href="{{root}}videos/">すべて</a>'
            + "".join(f'<a href="{{{{root}}}}videos/{g["slug"]}/">{e(g["name"])}</a>' for g in genres) + '</div>')

    # 動画ランキング（全体・ジャンル別）
    page("videos/index.html", "ポーカーYouTube動画ランキング（今週・30日）",
         "今週・過去30日に公開されたポーカーYouTube動画を再生数順にランキング。解説・トーナメント・キャッシュゲーム・エンタメのジャンル別も。",
         crumb("動画ランキング") + '<h1>ポーカーYouTube動画ランキング</h1>'
         f'<p class="lead">国内ポーカーYouTubeチャンネル{len(rows)}件の新着動画を再生数順に集計。{ctx["updated"]}</p>' + tabs
         + '<h2>今週の人気動画</h2>' + video_grid(top(week, 24), by_id, True)
         + '<h2>過去30日の人気動画</h2>' + video_grid(top(videos, 24), by_id, True))
    for g in genres:
        gv = [v for v in videos if v["genre"] == g["slug"]]
        gw = [v for v in gv if v in week]
        page(f"videos/{g['slug']}/index.html", f"ポーカー{g['name']}動画ランキング",
             f"{g['desc']}を再生数順にランキング。毎日自動更新。",
             crumb('<a href="{{root}}videos/">動画ランキング</a>', e(g["name"]))
             + f'<h1>ポーカー{e(g["name"])}動画ランキング</h1><p class="lead">{e(g["desc"])}。{ctx["updated"]}</p>' + tabs
             + '<h2>今週の人気動画</h2>' + video_grid(top(gw, 24), by_id, True)
             + '<h2>過去30日の人気動画</h2>' + video_grid(top(gv, 36), by_id, True))

    # トップ
    tools = [("tools/preflop-quiz/", "プリフロップ練習クイズ", "ポジションと手札から、レイズかフォールドかを即答。解説つきで何問でも。"),
             ("tools/equity/", "ポーカー勝率計算機", "手札とボードを選ぶだけで勝率（エクイティ）を計算。最大6人まで。"),
             ("tools/ranges/", "プリフロップレンジ表", "6人テーブルのポジション別オープンレンジを13×13表で確認。"),
             ("learn/odds/", "オッズ・アウツ早見表", "アウツ別の勝率とポットオッズを一覧で。必要勝率の計算ツール付き。"),
             ("learn/glossary/", "ポーカー用語集", "初心者がつまずく用語をやさしく解説。"),
             ("learn/hand-rankings/", "役の強さ一覧", "ロイヤルフラッシュからハイカードまで、カード例つきで。")]
    cards = "".join(f'<a class="tool" href="{p}"><b>{e(t)}</b><span>{e(d)}</span></a>' for p, t, d in tools)
    sections = "".join(
        f'<h2>{e(g["name"])}の人気動画</h2>'
        + video_grid(top([v for v in videos if v["genre"] == g["slug"]], 4), by_id, True)
        + f'<a class="more" href="videos/{g["slug"]}/">{e(g["name"])}のランキングを見る →</a>' for g in genres)
    body = (f'<h1>{e(NAME)}</h1><p class="lead">無料で使えるポーカー（テキサスホールデム）の練習ツールと、'
            f'ポーカーYouTube動画のジャンル別ランキング。{ctx["updated"]}</p>'
            f'<h2>練習ツール</h2><div class="tools">{cards}</div>'
            '<h2>今週の人気ポーカー動画</h2>' + video_grid(top(week, 8), by_id, True)
            + '<a class="more" href="videos/">動画ランキングをすべて見る →</a>' + sections
            + '<h2>ポーカーYouTuber 登録者数ランキング</h2>' + rank_table(ctx["by_subs"], "subs", 10)
            + '<a class="more" href="ranking/subscribers/">全チャンネルを見る →</a>'
            + ('<a class="more" style="margin-left:16px" href="ranking/growth/">急上昇ランキング →</a>' if ctx["has_growth"] else ""))
    page("index.html", NAME, CFG["site_description"] + "。毎日自動更新。", body,
         {"@context": "https://schema.org", "@type": "WebSite", "name": NAME, "url": BASE + "/"})


# ---------- 手書きページ ----------
def build_static_pages():
    src = SITE.dir / "pages"
    if not src.is_dir():
        return
    for f in sorted(src.rglob("*.html")):
        text = f.read_text(encoding="utf-8")
        m = re.match(r"<!--(\{.*?\})-->\s*", text, re.S)
        meta = json.loads(m.group(1)) if m else {}
        body = text[m.end():] if m else text
        rel = f.relative_to(src).with_suffix("")
        path = "index.html" if str(rel) == "index" else f"{rel.as_posix()}/index.html"
        page(path, meta.get("title", rel.name), meta.get("description", ""), body,
             meta.get("jsonld"), meta.get("head", ""))


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    shutil.copy(ROOT / "site_src" / "style.css", DIST / "style.css")
    if (SITE.dir / "assets").is_dir():
        shutil.copytree(SITE.dir / "assets", DIST / "assets")

    rows, by_id, snaps, latest_day, base_day, videos = load()
    has_growth = base_day is not None
    days = (date.fromisoformat(latest_day) - date.fromisoformat(base_day)).days if has_growth else 0
    ctx = {
        "updated": f"{latest_day.replace('-', '/')} 更新",
        "period": f"（{days}日）" if has_growth else "",
        "days": days,
        "has_growth": has_growth,
        "by_subs": sorted(rows, key=lambda r: -r["subs"]),
        "by_growth": sorted([r for r in rows if r["d_views"] is not None], key=lambda r: -r["d_views"]),
        "collecting": '<p class="note">急上昇ランキングはデータ蓄積中です。毎日自動で集計しており、数日後から表示されます。</p>',
    }
    build_common(rows, by_id, snaps, latest_day, base_day, videos, ctx)
    {"golf": build_golf, "poker": build_poker}[CFG["home"]](rows, by_id, videos, ctx)
    build_static_pages()

    page("404.html", "ページが見つかりません", "",
         f'<h1>ページが見つかりません</h1><p><a href="{BASE}/">トップへ</a></p>')
    urls = "".join(f"<url><loc>{e(BASE + '/' + p.replace('index.html', ''))}</loc><lastmod>{latest_day}</lastmod></url>"
                   for p in PAGES)
    (DIST / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
        encoding="utf-8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")
    (DIST / ".nojekyll").write_text("")
    print(f"[{SITE.name}] built {len(PAGES)} pages -> {DIST}")


if __name__ == "__main__":
    main()
