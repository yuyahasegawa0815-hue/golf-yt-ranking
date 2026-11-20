# このリポジトリについて
副業用のゴルフYouTubeランキングサイト。詳細は README.md。

## 方針
- Python標準ライブラリのみで書く（Actionsでの依存インストールを不要にするため）
- データ取得とサイト生成は分離（snapshot.py / build.py）
- YouTube API のクォータは 10,000ユニット/日。search は1回100ユニットなので discover 以外では使わない
- YouTube API Services Developer Policies を守る（30日保持、サムネイル無加工、出典表記）
- 生成ページは SEO を意識：title/description/canonical/JSON-LD/sitemap を必ず出す
- 収益化（アフィリエイト）リンクには rel="sponsored" を付け、PR表記を入れる
- サイトは `sites/<site>/` ごとに分かれている。スクリプトは必ずサイト名を引数に取る
- ポーカーサイトでは、リアルマネーのオンラインポーカー・オンラインカジノへの誘導や紹介は一切しない（日本では賭博罪のリスク）。収益化は広告・書籍・学習ツール・アミューズメントポーカーに限る
- ポーカーのツールを変更したら、役判定と勝率が既知の値（AA vs KK ≒ 82%、AKs vs QQ ≒ 46%）と合うか確認する
