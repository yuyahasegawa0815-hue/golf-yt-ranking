# ゴルフYouTubeランキング

国内のゴルフ系YouTubeチャンネルを毎日自動で集計し、登録者数ランキング・急上昇・人気動画を静的サイトとして公開するプロジェクト。

## 仕組み
| ファイル | 役割 | 頻度 |
|---|---|---|
| `scripts/discover.py` | 検索APIでゴルフ系チャンネルを発見し `data/channels.json` に追加 | 毎週月曜（手動実行も可） |
| `scripts/snapshot.py` | 全チャンネルの統計・直近30日の動画を取得 | 毎日 |
| `scripts/build.py` | `data/` から `dist/` に静的サイトを生成 | 毎日 |
| `.github/workflows/daily.yml` | 上記を実行し GitHub Pages に公開 | 毎日 JST 5:47 |

依存ライブラリなし（Python 3.10+ 標準ライブラリのみ）。

## 設定 (`config.json`)
- `site_name` / `base_url`：独自ドメインに移行したら `base_url` を変更
- `ga4_id`：GA4の測定ID（例 `G-XXXXXXX`）を入れると計測タグが入る
- `min_subscribers`：掲載する最低登録者数
- `discover_queries`：チャンネル発見に使う検索語
- `exclude_channel_ids`：掲載したくないチャンネル

## ローカル実行
```bash
export YT_API_KEY=...   # YouTube Data API v3 のキー
cd scripts && python3 snapshot.py && python3 build.py
```

## YouTube API ポリシーへの配慮
- 取得データは30日以内に更新・削除（`keep_days`）
- サムネイルはYouTubeのURLをそのまま表示し、加工しない
- 出典表記・YouTube利用規約/Googleプライバシーポリシーへのリンクを掲載
