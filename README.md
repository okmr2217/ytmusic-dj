# 🎵 YouTube Music DJ — セットアップ & 使い方

テキストベースのセットリストからYouTube Musicプレイリストを自動生成するPython CLIツール。フェーズ・ムード・ジャンル等のメタデータでフィルタリング可能。

## 1. インストール

```powershell
pip install ytmusicapi
```

## 2. 認証セットアップ（初回のみ）

### 方法A: コマンドで対話セットアップ

```powershell
cd ytmusic_dj
ytmusicapi browser
```

対話形式で以下を聞かれる：

1. **Chrome で music.youtube.com を開く**（ログイン済みであること）
2. **F12** → **Network** タブ → **F5でリロード**
3. リクエスト一覧から `music.youtube.com` 宛のリクエストを1つクリック
4. **Request Headers** から以下をコピペ：
   - `Cookie` ← 一番重要。とても長い文字列
   - その他聞かれたヘッダー

→ `browser.json` が生成される

### 方法B: Pythonで対話セットアップ

```python
from ytmusicapi import YTMusic
YTMusic.setup(filepath="browser.json")
```

同じく対話形式でヘッダーを聞かれる。

### 認証の確認

```python
from ytmusicapi import YTMusic
yt = YTMusic("browser.json")
print(yt.get_library_playlists())  # 自分のプレイリスト一覧が表示されればOK
```

---

## 3. 使い方

### 基本（全曲でプレイリスト作成）

```powershell
python ytmusic_dj.py playlist.json
```

### ドライラン（検索テストだけ、プレイリスト作成しない）

```powershell
python ytmusic_dj.py playlist.json --dry-run
```

**まずはドライランで正しい曲が見つかるか確認してから本番実行がおすすめ！**

### フェーズ指定

```powershell
# ウォームアップ曲だけ
python ytmusic_dj.py playlist.json --phase 1_warmup

# 設計フェーズの曲だけ
python ytmusic_dj.py playlist.json --phase 2_design

# 実装フェーズの曲だけ
python ytmusic_dj.py playlist.json --phase 3_implement

# クロージングだけ
python ytmusic_dj.py playlist.json --phase 4_closing
```

### ムード指定

```powershell
# エナジー系だけ
python ytmusic_dj.py playlist.json --mood energy

# チル系だけ
python ytmusic_dj.py playlist.json --mood chill

# 集中系だけ
python ytmusic_dj.py playlist.json --mood focus
```

### タグ（ジャンル）指定

```powershell
# 日本語ラップだけ
python ytmusic_dj.py playlist.json --tags 日本語ラップ

# 海外ラップだけ
python ytmusic_dj.py playlist.json --tags 海外ラップ

# 複数タグ（OR条件）
python ytmusic_dj.py playlist.json --tags 日本語ラップ 海外ラップ
```

### 優先度指定

```powershell
# ヘビロテだけの短めリスト
python ytmusic_dj.py playlist.json --priority high
```

### フィルタ組み合わせ

```powershell
# 実装フェーズ × エナジー系
python ytmusic_dj.py playlist.json --phase 3_implement --mood energy

# 日本語ラップ × チル
python ytmusic_dj.py playlist.json --tags 日本語ラップ --mood chill
```

---

## 4. JSONデータ形式

```json
{
  "playlist_name": "プレイリスト名",
  "description": "説明文",
  "tracks": [
    {
      "title": "曲名",          // 必須
      "artist": "アーティスト名",  // 必須
      "priority": "high",       // high / medium / low
      "tags": ["ジャンル"],      // フィルタ用
      "mood": "energy",         // energy / chill / focus
      "phase": "1_warmup",      // 作業フェーズ
      "play_count": 15,         // 再生回数（参考情報）
      "note": "メモ"            // 任意
    }
  ]
}
```

`title` と `artist` 以外は全てオプションです。

---

## 5. トラブルシューティング

### 認証エラーが出る
- `browser.json` の Cookie が期限切れの可能性あり
- → 再度 `ytmusicapi browser` でセットアップし直す

### 曲が見つからない
- 日本語の曲名が YouTube Music に登録されている表記と違う場合がある
- → playlist.json の曲名を YouTube Music の表記に合わせる
- → `--dry-run` で検索結果を確認して調整

### レート制限に引っかかる
- `ytmusic_dj.py` 内の `REQUEST_DELAY` を大きくする（デフォルト1秒）

---

## 6. 今後の拡張アイデア

- [ ] 再生回数順でソートするオプション (`--sort play_count`)
- [ ] 複数JSONを結合するバッチモード
- [ ] 既存プレイリストへの追記モード
- [ ] Claudeとの連携（好みデータから自動でJSON生成）
