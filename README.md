# yt-playlist-import

JSON設定ファイルからYouTubeプレイリストを一括作成するスクリプト。
YouTube Music の視聴履歴(Google Takeout)などから選定した曲(videoId)を
`playlists-config.json` にまとめておき、実行すると設定通りのプレイリストが作成される。

## 運用方針

- **作成専用**。同じ `title` のプレイリストがチャンネル内に既に存在する場合は
  スキップする(既存プレイリストへの曲の追加・同期は行わない)
- 既存判定は毎回 `playlists.list` でチャンネル内を検索して `title` を照合する
  (状態ファイルなどは使わない。同名プレイリストが手動で存在する場合はスキップされる点に注意)

## セットアップ

1. `npm install`
2. Google Cloud Console で OAuthクライアントID(デスクトップアプリ)を発行し
   YouTube Data API v3 を有効化
3. 環境変数を設定:
   ```
   export YT_CLIENT_ID="xxxxx.apps.googleusercontent.com"
   export YT_CLIENT_SECRET="xxxxx"
   ```
4. `playlists-config.example.json` を参考に `playlists-config.json` を作成

## 設定ファイルの形式

```json
{
  "playlists": [
    {
      "title": "Chill Night Drive",
      "description": "夜のドライブ用に選定",
      "privacyStatus": "private",
      "tracks": [
        { "videoId": "dQw4w9WgXcQ", "title": "曲名", "artist": "アーティスト名" },
        { "videoId": "xxxxxxxxxxx" }
      ]
    }
  ]
}
```

- `description` / `privacyStatus` は省略可。`privacyStatus` のデフォルトは `private`
- `tracks[].title` / `tracks[].artist` は省略可(ログ表示・失敗レポート用の任意項目)
- `tracks` の配列順がそのままプレイリストへの追加順(再生順)になる

## 実行

```
npx tsx create-playlists-from-config.ts ./playlists-config.json
```

初回はブラウザで認可画面が開く。認可後は `token.json` にリフレッシュトークンが
保存されるので、2回目以降はブラウザ操作なしで実行できる。

## ログ

- 実行ごとに `logs/run-<ISO日時>.log` が生成される
- **標準出力**にはフェーズ見出し・作成/スキップ結果・完了サマリのみを表示(曲単位のログは出さない)
- **ログファイル**には標準出力の内容に加え、曲ごとのOK/NG結果も全て記録される
- 失敗した曲は `failed.json` にも別途まとめて出力される(プレイリスト単位で失敗した曲のリスト)

## 注意点

- `playlistItems.insert` は書き込みAPIで1回あたり50ユニット消費(10,000ユニット/日の
  共有プール)。合計200曲を超える追加は1日の上限に達する可能性がある
- 削除済み・非公開化された動画は追加に失敗する。失敗した曲があった場合は
  `failed.json` に詳細(videoId・title・artist・失敗理由)が出力される
- `search.list`(曲名からのvideoId検索)は使用していないため、YouTube検索クオータの
  制約(2026年6月以降 1日100回)は影響しない
