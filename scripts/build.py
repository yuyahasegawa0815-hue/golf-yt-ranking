"""data/ から静的サイトを dist/ に生成する。"""
import html
import json
import shutil
from datetime import date, datetime, timedelta, timezone

from common import DATA, ROOT, SNAP, config, load_json

DIST = ROOT / "dist"
CFG = config()
NAME = CFG["site_name"]
BASE = CFG["base_url"].rstrip("/")
e = html.escape


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
        return '<span class="muted">-</span>'
    if n == 0:
        return "±0"
    cls = "up" if n > 0 else "down"
    return f'<span class="{cls}">{"+" if n > 0 else "−"}{num(abs(n))}</span>'


def dur(sec):
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


def ago(iso, now):
    d = now - datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if d.days >= 1:
        return f"{d.days}日前"
    return f"{max(1, d.seconds // 3600)}時間前"


# ---------- データ読み込み ----------
def load():
    chans = {k: v for k, v in load_json(DATA / "channels.json")["channels"].items()
             if not v.get("inactive")}
    files = sorted(SNAP.glob("*.json"))
    snaps = {f.stem: load_json(f) for f in files}
    latest_day = files[-1].stem
    latest = snaps[latest_day]
    # 7日前（なければ最古）のスナップショットと比較
    target = (date.fromisoformat(latest_day) - timedelta(days=7)).isoformat()
    older = [d for d in snaps if d <= target] or [d for d in snaps if d < latest_day]
    base_day = (max(older) if [d for d in snaps if d <= target] else min(older)) if older else None
    base = snaps.get(base_day, {}) if base_day else {}
    rows = []
    for cid, meta in chans.items():
        if cid not in latest:
            continue
        subs, views, vids = latest[cid]
        b = base.get(cid)
        rows.append({
            "id": cid, **meta, "subs": subs, "views": views, "videos": vids,
            "d_subs": subs - b[0] if b else None,
            "d_views": views - b[1] if b else None,
        })
    videos = load_json(DATA / "videos.json")["videos"]
    return rows, snaps, latest_day, base_day, videos


# ---------- レイアウト ----------
def page(path, title, desc, body, depth, jsonld=None):
    root = "../" * depth
    ga = ""
    if CFG.get("ga4_id"):
        g = e(CFG["ga4_id"])
        ga = (f'<script async src="https://www.googletagmanager.com/gtag/js?id={g}"></script>'
              f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}"
              f"gtag('js',new Date());gtag('config','{g}');</script>")
    url = f"{BASE}/{path}".replace("index.html", "")
    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ""
    full_title = title if title == NAME else f"{title}｜{NAME}"
    doc = f"""<!doctype html>
<html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(full_title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:title" content="{e(full_title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:type" content="website"><meta property="og:url" content="{e(url)}">
<meta name="twitter:card" content="summary">
<link rel="stylesheet" href="{root}style.css">{ga}{ld}
</head><body>
<header class="site"><div class="wrap">
<a class="logo" href="{root}">⛳ ゴルフ<span>YouTube</span>ランキング</a>
<nav><a href="{root}ranking/growth/">急上昇</a><a href="{root}ranking/subscribers/">登録者数</a><a href="{root}videos/">人気動画</a><a href="{root}about/">このサイトについて</a></nav>
</div></header>
<main class="wrap">{body}</main>
<footer><div class="wrap">
<a href="{root}about/">運営者情報・データについて</a><a href="{root}about/#privacy">プライバシーポリシー</a>
<p>データ出典: YouTube Data API（YouTube は Google LLC の商標です）。当サイトはYouTubeの公式サイトではありません。<br>&copy; {date.today().year} {e(NAME)}</p>
</div></footer>
</body></html>
"""
    out = DIST / path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    return path


def crumb(depth, *items):
    root = "../" * depth
    parts = [f'<a href="{root}">ホーム</a>'] + list(items)
    return f'<div class="crumb">{" › ".join(parts)}</div>'


def ch_cell(r, root):
    return (f'<a class="ch" href="{root}channel/{r["id"]}/"><img src="{e(r["thumb"])}" alt="" '
            f'loading="lazy" width="36" height="36"><b>{e(r["title"])}</b></a>')


def rank_table(rows, root, mode, limit=None, period=""):
    rows = rows[:limit] if limit else rows
    if mode == "growth":
        head = (f'<th>#</th><th class="name">チャンネル</th><th>再生数増加{period}</th>'
                f'<th>登録者増加{period}</th><th class="opt">登録者数</th>')
        body = "".join(
            f'<tr><td class="no">{i}</td><td class="name">{ch_cell(r, root)}</td>'
            f'<td>{delta(r["d_views"])}</td><td>{delta(r["d_subs"])}</td>'
            f'<td class="opt">{num(r["subs"])}</td></tr>'
            for i, r in enumerate(rows, 1))
    else:
        head = ('<th>#</th><th class="name">チャンネル</th><th>登録者数</th>'
                '<th class="opt">総再生数</th><th class="opt">動画数</th>')
        body = "".join(
            f'<tr data-q="{e(r["title"].lower())}"><td class="no">{i}</td><td class="name">{ch_cell(r, root)}</td>'
            f'<td>{num(r["subs"])}</td><td class="opt">{num(r["views"])}</td>'
            f'<td class="opt">{r["videos"]:,}</td></tr>'
            for i, r in enumerate(rows, 1))
    return f'<div class="scroll"><table class="rank"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def video_grid(vs, chans, now, root=""):
    cards = []
    for v in vs:
        ch = chans.get(v["channel"], {})
        cards.append(
            f'<a class="vid" href="https://www.youtube.com/watch?v={e(v["id"])}" target="_blank" rel="noopener">'
            f'<img src="{e(v["thumb"])}" alt="" loading="lazy">'
            f'<div class="t">{e(v["title"])}</div>'
            f'<div class="m">{e(ch.get("title", ""))}<br>{num(v["views"])}回再生・{ago(v["published_at"], now)}・{dur(v["duration"])}</div></a>')
    return f'<div class="grid">{"".join(cards)}</div>'


def itemlist(rows, root_url):
    return {"@context": "https://schema.org", "@type": "ItemList",
            "itemListElement": [{"@type": "ListItem", "position": i, "name": r["title"],
                                 "url": f"{root_url}/channel/{r['id']}/"}
                                for i, r in enumerate(rows[:50], 1)]}


# ---------- ビルド ----------
def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copy(ROOT / "site_src" / "style.css", DIST / "style.css")

    rows, snaps, latest_day, base_day, videos = load()
    chans = {r["id"]: r for r in rows}
    now = datetime.now(timezone.utc)
    updated = f"{latest_day.replace('-', '/')} 更新"
    by_subs = sorted(rows, key=lambda r: -r["subs"])
    has_growth = base_day is not None
    days = (date.fromisoformat(latest_day) - date.fromisoformat(base_day)).days if has_growth else 0
    period = f"（{days}日）" if has_growth else ""
    by_growth = sorted([r for r in rows if r["d_views"] is not None], key=lambda r: -r["d_views"])
    week_ago = now - timedelta(days=7)
    week_videos = sorted([v for v in videos if v["channel"] in chans and
                          datetime.fromisoformat(v["published_at"].replace("Z", "+00:00")) >= week_ago],
                         key=lambda v: -v["views"])
    pages = []
    collecting = ('<p class="note">急上昇ランキングはデータ蓄積中です。毎日自動で集計しており、'
                  '数日後から表示されます。</p>')

    # トップ
    body = (f'<h1>ゴルフYouTubeランキング</h1><p class="lead">国内のゴルフ系YouTubeチャンネル'
            f'{len(rows)}件を毎日自動集計。{updated}</p>'
            f'<h2>今週の急上昇チャンネル</h2>'
            + (rank_table(by_growth, "", "growth", 10, period) + '<a class="more" href="ranking/growth/">急上昇ランキングをすべて見る →</a>'
               if has_growth else collecting)
            + '<h2>今週の人気ゴルフ動画</h2>' + video_grid(week_videos[:8], chans, now)
            + '<a class="more" href="videos/">人気動画をもっと見る →</a>'
            + '<h2>登録者数ランキング TOP20</h2>' + rank_table(by_subs, "", "subs", 20)
            + '<a class="more" href="ranking/subscribers/">全チャンネルを見る →</a>')
    pages.append(page("index.html", NAME,
                      f"ゴルフYouTuberの登録者数ランキング・急上昇・人気動画を毎日自動更新。国内{len(rows)}チャンネルを集計。",
                      body, 0, itemlist(by_subs, BASE)))

    # 登録者数ランキング
    body = (crumb(2, "登録者数ランキング") + f'<h1>ゴルフYouTuber 登録者数ランキング</h1>'
            f'<p class="lead">国内ゴルフ系YouTubeチャンネル{len(rows)}件の登録者数順。{updated}</p>'
            '<input class="filter" type="search" placeholder="チャンネル名で絞り込み" '
            'oninput="var q=this.value.toLowerCase();document.querySelectorAll(\'tbody tr\').forEach(function(t){t.style.display=t.dataset.q.indexOf(q)<0?\'none\':\'\'})">'
            + rank_table(by_subs, "../../", "subs"))
    pages.append(page("ranking/subscribers/index.html", "ゴルフYouTuber 登録者数ランキング",
                      f"ゴルフ系YouTubeチャンネルの登録者数ランキング（{latest_day}時点・全{len(rows)}件）。毎日自動更新。",
                      body, 2, itemlist(by_subs, BASE)))

    # 急上昇
    body = (crumb(2, "急上昇ランキング") + '<h1>ゴルフYouTube 急上昇ランキング</h1>'
            f'<p class="lead">直近{days or 7}日間の総再生数の増加が大きい順。{updated}</p>'
            '<p class="note">※YouTubeの登録者数は概数（上位3桁）で公開されるため、再生数の増加を主指標にしています。</p>'
            + (rank_table(by_growth, "../../", "growth", 100, period) if has_growth else collecting))
    pages.append(page("ranking/growth/index.html", "ゴルフYouTube 急上昇ランキング",
                      "今週伸びているゴルフYouTubeチャンネルを再生数・登録者数の増加で毎日ランキング。",
                      body, 2, itemlist(by_growth, BASE) if has_growth else None))

    # 人気動画
    month_videos = sorted([v for v in videos if v["channel"] in chans], key=lambda v: -v["views"])
    body = (crumb(1, "人気動画") + '<h1>今週の人気ゴルフ動画</h1>'
            f'<p class="lead">直近7日間に公開されたゴルフ動画の再生数順。{updated}</p>'
            + video_grid(week_videos[:60], chans, now)
            + '<h2>過去30日の人気ゴルフ動画</h2>' + video_grid(month_videos[:40], chans, now))
    pages.append(page("videos/index.html", "今週の人気ゴルフ動画ランキング",
                      "今週公開されたゴルフYouTube動画を再生数順に紹介。レッスン・ラウンド・試打動画の話題作がわかる。",
                      body, 1))

    # チャンネル個別
    rank_of = {r["id"]: i for i, r in enumerate(by_subs, 1)}
    vids_by_ch = {}
    for v in sorted(videos, key=lambda v: v["published_at"], reverse=True):
        vids_by_ch.setdefault(v["channel"], []).append(v)
    days_sorted = sorted(snaps)
    for r in rows:
        hist = [(d, snaps[d][r["id"]]) for d in days_sorted if r["id"] in snaps[d]][-30:]
        hist_rows = "".join(f'<tr><td class="name">{d}</td><td>{num(s[0])}</td><td>{num(s[1])}</td><td>{s[2]:,}</td></tr>'
                            for d, s in reversed(hist))
        yt_url = f'https://www.youtube.com/{r["custom_url"]}' if r.get("custom_url") else f'https://www.youtube.com/channel/{r["id"]}'
        body = (crumb(2, '<a href="../../ranking/subscribers/">登録者数ランキング</a>', e(r["title"]))
                + f'<div class="prof"><img src="{e(r["thumb"])}" alt="{e(r["title"])}"><div>'
                f'<h1>{e(r["title"])}</h1><div class="lead">ゴルフYouTube登録者数ランキング {rank_of[r["id"]]}位 / {len(rows)}</div></div></div>'
                '<div class="stats">'
                f'<div class="stat"><div class="k">登録者数</div><div class="v">{num(r["subs"])}</div><div class="d">{delta(r["d_subs"])} {period}</div></div>'
                f'<div class="stat"><div class="k">総再生数</div><div class="v">{num(r["views"])}</div><div class="d">{delta(r["d_views"])} {period}</div></div>'
                f'<div class="stat"><div class="k">動画数</div><div class="v">{r["videos"]:,}</div></div>'
                f'<div class="stat"><div class="k">開設日</div><div class="v" style="font-size:1.1rem">{e(r.get("published_at", ""))}</div></div>'
                '</div>'
                f'<a class="btn" href="{e(yt_url)}" target="_blank" rel="noopener">YouTubeでチャンネルを見る</a>'
                + ('<h2>最近の動画</h2>' + video_grid(vids_by_ch[r["id"]][:8], chans, now) if r["id"] in vids_by_ch else "")
                + '<h2>登録者数・再生数の推移（直近30日）</h2>'
                '<div class="scroll"><table class="rank"><thead><tr><th class="name">日付</th><th>登録者数</th><th>総再生数</th><th>動画数</th></tr></thead>'
                f'<tbody>{hist_rows}</tbody></table></div>'
                + (f'<h2>チャンネル紹介</h2><div class="desc">{e(r["description"])}</div>' if r.get("description") else ""))
        pages.append(page(f"channel/{r['id']}/index.html", f"{r['title']}の登録者数・再生数推移",
                          f"ゴルフYouTubeチャンネル「{r['title']}」の登録者数{num(r['subs'])}人・総再生数・最近の動画・推移データ。",
                          body, 2))

    # about
    body = (crumb(1, "このサイトについて") + '<h1>このサイトについて</h1>'
            f'<p>{e(NAME)}は、国内のゴルフ系YouTubeチャンネルの公開データをYouTube Data APIで毎日取得し、'
            '登録者数・再生数・急上昇・人気動画をランキング形式で紹介するサイトです。</p>'
            '<h2>データについて</h2><ul>'
            '<li>集計対象は、ゴルフに関する発信をしている日本語のチャンネル（登録者3,000人以上）です。対象は自動で随時追加しています。</li>'
            '<li>登録者数はYouTubeの公開仕様により概数です。</li>'
            '<li>掲載データはYouTube API サービスの利用規約に従い、取得から30日を超えたものは削除しています。</li>'
            '<li>掲載の追加・削除のご希望はお問い合わせください。</li></ul>'
            '<h2 id="privacy">プライバシーポリシー</h2>'
            '<p>当サイトはアクセス解析のためにGoogle アナリティクスを利用することがあり、Cookieを使用してデータを収集します。'
            'データは匿名で収集され、個人を特定するものではありません。また、当サイトはアフィリエイトプログラムに参加しており、'
            '商品紹介リンクを含む場合があります。</p>'
            '<p>当サイトはYouTube API サービスを利用しています。'
            '<a href="https://www.youtube.com/t/terms" target="_blank" rel="noopener">YouTube 利用規約</a>・'
            '<a href="https://policies.google.com/privacy" target="_blank" rel="noopener">Google プライバシーポリシー</a></p>'
            '<h2>お問い合わせ</h2><p>（お問い合わせ先を設定してください）</p>')
    pages.append(page("about/index.html", "このサイトについて", f"{NAME}の運営者情報・データの取得方法・プライバシーポリシー。", body, 1))

    # 404 / sitemap / robots
    page("404.html", "ページが見つかりません", "", f'<h1>ページが見つかりません</h1><p><a href="{BASE}/">トップへ</a></p>', 0)
    urls = "".join(f"<url><loc>{e(BASE + '/' + p.replace('index.html', ''))}</loc><lastmod>{latest_day}</lastmod></url>"
                   for p in pages)
    (DIST / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
        encoding="utf-8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")
    (DIST / ".nojekyll").write_text("")
    print(f"built {len(pages)} pages -> {DIST}")


if __name__ == "__main__":
    main()
