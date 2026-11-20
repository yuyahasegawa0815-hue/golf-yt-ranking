# YouTubeランキング＆ポーカートレーニング（2サイト運営）

同じ仕組みで2つの静的サイトを毎日自動更新する。

| サイト | フォルダ | 内容 | 公開先（Cloudflare Pages） |
|---|---|---|---|
| ゴルフYouTubeランキング | `sites/golf/` | ゴルフ系YouTubeの登録者数・急上昇・人気動画 | `golf-yt-ranking` |
| ポーカートレーニングラボ | `sites/poker/` | 練習ツール（クイズ・勝率計算・レンジ表・オッズ・用語集）＋ポーカー動画のジャンル別ランキング | `poker-training-lab` |

## 仕組み
| ファイル | 役割 |
|---|---|
| `scripts/discover.py <site>` | 検索APIでチャンネルを発見し `sites/<site>/data/channels.json` に追加（毎週月曜） |
| `scripts/snapshot.py <site>` | 全チャンネルの統計・直近30日の動画を取得（毎日） |
| `scripts/build.py <site>` | `sites/<site>/` から `dist/<site>/` に静的サイトを生成（毎日） |
| `sites/<site>/pages/**.html` | 手書きページ（ツール・解説）。先頭に `<!--{"title":..,"description":..}-->`、本文の `{{root}}` はルートへの相対パス |
| `sites/<site>/assets/` | JS等。ポーカーの役判定・勝率計算・レンジは `sites/poker/assets/poker.js` |
| `.github/workflows/daily.yml` | 上記を毎日 JST 5:47 に実行して公開 |

依存ライブラリなし（Python 3.10+ 標準ライブラリのみ）。

## 設定 (`sites/<site>/config.json`)
- `site_name` / `base_url`：公開URLが変わったら `base_url` を変更
- `cf_project`：Cloudflare Pages のプロジェクト名
- `ga4_id` / `gsc_verification`：GA4測定ID・Search Console確認コード
- `core_pattern` / `relevance_keywords` / `discover_queries`：チャンネル発見の条件
- `video_pattern`：ジャンル外チャンネルの動画を残す条件（ポーカー）
- `genres`：動画のジャンル分類（上から順にタイトルで判定。pattern が空のものが受け皿）

## ローカル実行
```bash
export YT_API_KEY=...
python3 scripts/snapshot.py poker && python3 scripts/build.py poker
```

## YouTube API ポリシーへの配慮
- 取得データは30日以内に更新・削除（`keep_days`）
- サムネイルはYouTubeのURLをそのまま表示し、加工しない
- 出典表記・YouTube利用規約/Googleプライバシーポリシーへのリンクを掲載
