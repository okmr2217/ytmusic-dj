#!/usr/bin/env python3
"""
YouTube Music 認証セットアップ

ChromeのDevToolsからコピーしたcURLコマンドを解析して browser.json を生成する
"""

import json
import re
import sys


def parse_curl(curl_text):
    """cURLコマンドからヘッダーを抽出"""
    headers = {}

    # -H 'key: value' パターン
    h_pattern = re.findall(r"-H\s+'([^']+)'", curl_text)
    for h in h_pattern:
        if ": " in h:
            key, value = h.split(": ", 1)
            headers[key.lower()] = value

    # -b 'cookie' パターン（Cookie）
    b_pattern = re.findall(r"-b\s+'([^']+)'", curl_text)
    if b_pattern:
        headers["cookie"] = b_pattern[0]

    return headers


def main():
    print("=" * 60)
    print("🔐 YouTube Music 認証セットアップ")
    print("=" * 60)
    print()
    print("以下の手順で認証情報を取得してください：")
    print()
    print("1. Chromeで music.youtube.com を開く（ログイン済み）")
    print("2. F12 → Network タブ → 「Fetch/XHR」をクリック")
    print("3. ページ上で何かクリック（ホーム、ライブラリ等）")
    print("4. リクエストを右クリック → Copy → Copy as cURL (bash)")
    print()
    print("コピーしたcURLコマンドを貼り付けて、空行で確定:")
    print("(複数行になっても大丈夫です)")
    print()

    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "" and lines:
                break
            lines.append(line)
        except EOFError:
            break

    curl_text = " ".join(lines)

    if not curl_text.strip():
        print("入力がありません。終了します。")
        sys.exit(1)

    # ヘッダーを抽出
    headers = parse_curl(curl_text)

    if "cookie" not in headers:
        print("⚠ Cookieが見つかりません。")
        print("  music.youtube.com のリクエストからコピーしたか確認してください。")
        sys.exit(1)

    # 必要なヘッダーだけ抽出
    browser_json = {}
    important_keys = [
        "accept", "accept-language", "authorization", "content-type",
        "cookie", "referer", "user-agent",
        "x-goog-authuser", "x-goog-visitor-id", "x-origin",
        "x-youtube-bootstrap-logged-in", "x-youtube-client-name",
        "x-youtube-client-version",
    ]

    for key in important_keys:
        if key in headers:
            browser_json[key] = headers[key]

    # browser.json に保存
    with open("browser.json", "w", encoding="utf-8") as f:
        json.dump(browser_json, f, indent=2)

    print()
    print("✅ browser.json を作成しました！")
    print()

    # テスト
    print("🔍 接続テスト中...")
    try:
        from ytmusicapi import YTMusic
        yt = YTMusic("browser.json")

        # 検索テスト
        results = yt.search("Oasis Wonderwall", filter="songs", limit=1)
        if results:
            print(f"  検索: ✅ ({results[0]['title']})")
        else:
            print("  検索: ⚠ 結果なし（接続は成功）")

        # プレイリスト作成テスト
        pid = yt.create_playlist("_ytmusic_dj_test", "セットアップテスト")
        print(f"  プレイリスト作成: ✅")
        yt.delete_playlist(pid)
        print(f"  プレイリスト削除: ✅")

        print()
        print("🎉 セットアップ完了！ytmusic_dj.py が使えます。")

    except Exception as e:
        print(f"  テストエラー: {e}")
        print()
        print("認証情報に問題がある可能性があります。")
        print("music.youtube.com に正しくログインした状態で再度お試しください。")


if __name__ == "__main__":
    main()
