#!/usr/bin/env python3
"""
YouTube Music DJ — テキスト(JSON)からプレイリストを自動生成
Usage:
    python ytmusic_dj.py playlist.json
    python ytmusic_dj.py /path/to/dir/         # ディレクトリ内の全JSONを処理
    python ytmusic_dj.py playlist.json --phase 2_design
    python ytmusic_dj.py playlist.json --mood chill
    python ytmusic_dj.py playlist.json --tags 日本語ラップ
    python ytmusic_dj.py playlist.json --priority high
    python ytmusic_dj.py playlist.json --phase 3_implement --mood energy
    python ytmusic_dj.py playlist.json --dry-run  # 検索結果だけ確認、プレイリスト作成しない
"""

import json
import argparse
import sys
import time
from pathlib import Path

try:
    from ytmusicapi import YTMusic
except ImportError:
    print("❌ ytmusicapi がインストールされていません")
    print("   → pip install ytmusicapi")
    sys.exit(1)


# ─── 設定 ───────────────────────────────────────────────
AUTH_FILE = "browser.json"       # 認証ファイルのパス
SEARCH_LIMIT = 3                 # 検索結果の候補数（1曲目を採用）
REQUEST_DELAY = 1.0              # API連続リクエストの間隔（秒）。レート制限対策
# ────────────────────────────────────────────────────────


def load_playlist_json(filepath: str) -> dict:
    """JSONファイルを読み込む"""
    path = Path(filepath)
    if not path.exists():
        print(f"❌ ファイルが見つかりません: {filepath}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def filter_tracks(tracks: list, phase: str = None, mood: str = None,
                  tags: list = None, priority: str = None) -> list:
    """フィルタ条件に合う曲だけ抽出"""
    filtered = tracks

    if phase:
        filtered = [t for t in filtered if t.get("phase", "") == phase]

    if mood:
        filtered = [t for t in filtered if t.get("mood", "") == mood]

    if tags:
        filtered = [t for t in filtered
                    if any(tag in t.get("tags", []) for tag in tags)]

    if priority:
        filtered = [t for t in filtered if t.get("priority", "") == priority]

    return filtered


def deduplicate_tracks(tracks: list) -> list:
    """同じ曲名+アーティストの重複を除去（最初の出現を残す）"""
    seen = set()
    unique = []
    for t in tracks:
        key = (t["title"], t["artist"])
        if key not in seen:
            seen.add(key)
            unique.append(t)
    return unique


def search_track(ytmusic: YTMusic, title: str, artist: str) -> dict | None:
    """YouTube Musicで曲を検索し、最もマッチする結果を返す"""
    query = f"{title} {artist}"
    try:
        results = ytmusic.search(query, filter="songs", limit=SEARCH_LIMIT)
        if results:
            return results[0]

        # songs で見つからなければ videos でフォールバック
        results = ytmusic.search(query, filter="videos", limit=SEARCH_LIMIT)
        if results:
            return results[0]
    except Exception as e:
        print(f"  ⚠️  検索エラー: {query} → {e}")

    return None


def create_playlist_from_json(json_path: str, phase: str = None,
                               mood: str = None, tags: list = None,
                               priority: str = None, dry_run: bool = False):
    """メイン処理：JSONからプレイリストを生成"""

    # ── JSON読み込み ──
    data = load_playlist_json(json_path)
    playlist_name = data.get("playlist_name", "DJ Auto Playlist")
    description = data.get("description", "")
    tracks = data.get("tracks", [])

    print(f"\n🎵 プレイリスト: {playlist_name}")
    print(f"📝 説明: {description}")
    print(f"📀 全{len(tracks)}曲")

    # ── フィルタ適用 ──
    if any([phase, mood, tags, priority]):
        tracks = filter_tracks(tracks, phase, mood, tags, priority)
        filters = []
        if phase:    filters.append(f"phase={phase}")
        if mood:     filters.append(f"mood={mood}")
        if tags:     filters.append(f"tags={','.join(tags)}")
        if priority: filters.append(f"priority={priority}")
        print(f"🔍 フィルタ: {', '.join(filters)} → {len(tracks)}曲")

        # フィルタ適用時はプレイリスト名にサフィックス追加
        suffix_parts = []
        if phase:    suffix_parts.append(phase)
        if mood:     suffix_parts.append(mood)
        if tags:     suffix_parts.append("+".join(tags))
        playlist_name = f"{playlist_name} [{' / '.join(suffix_parts)}]"

    # ── 重複除去 ──
    tracks = deduplicate_tracks(tracks)
    print(f"📀 重複除去後: {len(tracks)}曲")

    if not tracks:
        print("❌ 条件に合う曲がありません")
        return

    # ── 曲リスト表示 ──
    print("\n── セットリスト ──")
    for i, t in enumerate(tracks, 1):
        phase_label = f" [{t.get('phase', '')}]" if t.get('phase') else ""
        mood_label = f" ({t.get('mood', '')})" if t.get('mood') else ""
        print(f"  {i:2d}. {t['artist']} - {t['title']}{phase_label}{mood_label}")

    if dry_run:
        print("\n🔍 ドライラン: 検索テストのみ実行します\n")

    # ── YTMusic認証 ──
    auth_path = Path(AUTH_FILE)
    if not auth_path.exists():
        print(f"\n❌ 認証ファイルが見つかりません: {AUTH_FILE}")
        print("   → 先にセットアップを実行してください:")
        print("     ytmusicapi browser")
        sys.exit(1)

    print(f"\n🔐 認証中... ({AUTH_FILE})")
    ytmusic = YTMusic(AUTH_FILE)
    print("✅ 認証OK\n")

    # ── 曲を検索 ──
    video_ids = []
    not_found = []

    for i, t in enumerate(tracks, 1):
        title = t["title"]
        artist = t["artist"]
        print(f"  🔎 [{i}/{len(tracks)}] {artist} - {title} ... ", end="", flush=True)

        result = search_track(ytmusic, title, artist)

        if result:
            vid = result.get("videoId")
            found_title = result.get("title", "?")
            found_artists = ", ".join(
                a.get("name", "?") for a in result.get("artists", [])
            ) or "?"
            video_ids.append(vid)
            print(f"✅ → {found_artists} - {found_title}")
        else:
            not_found.append(f"{artist} - {title}")
            print("❌ 見つからず")

        time.sleep(REQUEST_DELAY)

    # ── 結果サマリー ──
    print(f"\n── 検索結果 ──")
    print(f"  ✅ 見つかった: {len(video_ids)}曲")
    if not_found:
        print(f"  ❌ 見つからなかった: {len(not_found)}曲")
        for nf in not_found:
            print(f"     - {nf}")

    if dry_run:
        print("\n✨ ドライラン完了！ --dry-run を外して実行すればプレイリストが作成されます。")
        return

    if not video_ids:
        print("❌ 追加できる曲がありません")
        return

    # ── プレイリスト作成 ──
    print(f"\n📝 プレイリスト作成中: {playlist_name}")
    try:
        playlist_id = ytmusic.create_playlist(
            title=playlist_name,
            description=description,
            privacy_status="PRIVATE",  # PRIVATE / PUBLIC / UNLISTED
            video_ids=video_ids
        )
        print(f"✅ プレイリスト作成完了！")
        print(f"🔗 https://music.youtube.com/playlist?list={playlist_id}")
        print(f"   ({len(video_ids)}曲追加済み)")
    except Exception as e:
        print(f"❌ プレイリスト作成エラー: {e}")

        # フォールバック：空のプレイリストを作成してから1曲ずつ追加
        print("   → 1曲ずつ追加する方法にフォールバックします...")
        try:
            playlist_id = ytmusic.create_playlist(
                title=playlist_name,
                description=description,
                privacy_status="PRIVATE"
            )
            added = 0
            for vid in video_ids:
                try:
                    ytmusic.add_playlist_items(playlist_id, [vid])
                    added += 1
                    time.sleep(REQUEST_DELAY)
                except Exception as add_err:
                    print(f"  ⚠️  追加失敗: {vid} → {add_err}")

            print(f"✅ プレイリスト作成完了！({added}/{len(video_ids)}曲)")
            print(f"🔗 https://music.youtube.com/playlist?list={playlist_id}")
        except Exception as fallback_err:
            print(f"❌ フォールバックも失敗: {fallback_err}")


def main():
    parser = argparse.ArgumentParser(
        description="🎵 YouTube Music DJ — JSONからプレイリスト自動生成"
    )
    parser.add_argument("json_file", help="プレイリストJSONファイルのパス、またはJSONが入ったディレクトリ")
    parser.add_argument("--phase", help="フェーズでフィルタ (例: 1_warmup, 2_design, 3_implement, 4_closing)")
    parser.add_argument("--mood", help="ムードでフィルタ (例: energy, chill, focus)")
    parser.add_argument("--tags", nargs="+", help="タグでフィルタ (例: 日本語ラップ 海外ラップ)")
    parser.add_argument("--priority", help="優先度でフィルタ (例: high, medium, low)")
    parser.add_argument("--dry-run", action="store_true", help="検索テストのみ（プレイリスト作成しない）")

    args = parser.parse_args()

    target = Path(args.json_file)

    # ディレクトリが指定された場合は全JSONを処理
    if target.is_dir():
        json_files = sorted(target.glob("*.json"))
        if not json_files:
            print(f"❌ JSONファイルが見つかりません: {target}")
            sys.exit(1)
        print(f"📂 ディレクトリ: {target}")
        print(f"   {len(json_files)}件のJSONファイルを処理します\n")
        for i, json_path in enumerate(json_files, 1):
            print(f"{'='*60}")
            print(f"[{i}/{len(json_files)}] {json_path.name}")
            print(f"{'='*60}")
            create_playlist_from_json(
                json_path=str(json_path),
                phase=args.phase,
                mood=args.mood,
                tags=args.tags,
                priority=args.priority,
                dry_run=args.dry_run
            )
            if i < len(json_files):
                print(f"\n⏳ 次のファイルまで少し待機...\n")
                time.sleep(2)
        print(f"\n{'='*60}")
        print(f"✨ 全{len(json_files)}件の処理が完了しました！")
    else:
        create_playlist_from_json(
            json_path=args.json_file,
            phase=args.phase,
            mood=args.mood,
            tags=args.tags,
            priority=args.priority,
            dry_run=args.dry_run
        )


if __name__ == "__main__":
    main()
