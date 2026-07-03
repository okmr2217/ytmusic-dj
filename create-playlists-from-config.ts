/**
 * playlists-config.json からYouTubeプレイリストを一括作成するスクリプト
 *
 * 【運用方針】
 * - 作成専用。同じtitleのプレイリストがチャンネル内に既に存在する場合はスキップする
 *   (既存プレイリストへの曲の追加・同期は行わない)
 * - 既存判定は毎回 playlists.list でチャンネル内を検索してtitle照合する(state.json等は使わない)
 *
 * 事前準備:
 * 1. Google Cloud Console で OAuthクライアントID(デスクトップアプリ)を発行
 * 2. 環境変数 YT_CLIENT_ID / YT_CLIENT_SECRET を設定
 * 3. playlists-config.json を用意(サンプルは playlists-config.example.json 参照)
 *
 * 実行:
 *   npx tsx create-playlists-from-config.ts ./playlists-config.json
 */

import { google, youtube_v3 } from "googleapis";
import * as http from "http";
import * as fs from "fs";
import * as path from "path";
import open from "open";
import { Logger } from "./logger";

type GoogleAuthClient = InstanceType<typeof google.auth.OAuth2>;

// ---- 設定 ----------------------------------------------------------------

const CLIENT_ID = process.env.YT_CLIENT_ID ?? "YOUR_CLIENT_ID.apps.googleusercontent.com";
const CLIENT_SECRET = process.env.YT_CLIENT_SECRET ?? "YOUR_CLIENT_SECRET";
const REDIRECT_PORT = 53682;
const REDIRECT_URI = `http://localhost:${REDIRECT_PORT}/oauth2callback`;
const TOKEN_PATH = path.join(__dirname, "token.json");
const LOG_DIR = path.join(__dirname, "logs");
const SCOPES = ["https://www.googleapis.com/auth/youtube"];

const INSERT_DELAY_MS = 300;

// ---- 設定ファイルの型 ---------------------------------------------------------

interface TrackConfig {
  videoId: string;
  title?: string;
  artist?: string;
}

interface PlaylistConfig {
  title: string;
  description?: string;
  privacyStatus?: "private" | "public" | "unlisted";
  tracks: TrackConfig[];
}

interface RootConfig {
  playlists: PlaylistConfig[];
}

// ---- OAuth認可 --------------------------------------------------------------

async function getAuthedClient(logger: Logger): Promise<GoogleAuthClient> {
  const oAuth2Client = new google.auth.OAuth2(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI);

  if (fs.existsSync(TOKEN_PATH)) {
    const token = JSON.parse(fs.readFileSync(TOKEN_PATH, "utf-8"));
    oAuth2Client.setCredentials(token);
    return oAuth2Client;
  }

  const authUrl = oAuth2Client.generateAuthUrl({
    access_type: "offline",
    scope: SCOPES,
    prompt: "consent",
  });

  logger.stdout("ブラウザで認可画面を開きます。開かない場合は以下のURLを手動で開いてください:");
  logger.stdout(authUrl);
  await open(authUrl);

  const code = await waitForAuthCode();
  const { tokens } = await oAuth2Client.getToken(code);
  oAuth2Client.setCredentials(tokens);

  fs.writeFileSync(TOKEN_PATH, JSON.stringify(tokens, null, 2));
  logger.stdout(`認可完了。トークンを ${TOKEN_PATH} に保存しました。`);

  return oAuth2Client;
}

function waitForAuthCode(): Promise<string> {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      if (!req.url) return;
      const url = new URL(req.url, `http://localhost:${REDIRECT_PORT}`);
      const code = url.searchParams.get("code");

      if (code) {
        res.end("認可が完了しました。このタブは閉じて構いません。");
        server.close();
        resolve(code);
      } else {
        res.end("認可コードが取得できませんでした。");
        server.close();
        reject(new Error("No auth code in callback"));
      }
    });
    server.listen(REDIRECT_PORT);
  });
}

// ---- 設定ファイル読み込み -------------------------------------------------------

function loadConfig(configPath: string): RootConfig {
  const raw = fs.readFileSync(configPath, "utf-8");
  const config: RootConfig = JSON.parse(raw);

  if (!Array.isArray(config.playlists) || config.playlists.length === 0) {
    throw new Error("設定ファイルに playlists 配列が見つかりません");
  }

  for (const p of config.playlists) {
    if (!p.title) throw new Error("title が未設定のプレイリストがあります");
    if (!Array.isArray(p.tracks) || p.tracks.length === 0) {
      throw new Error(`"${p.title}" に tracks が設定されていません`);
    }
    for (const t of p.tracks) {
      if (!t.videoId) throw new Error(`"${p.title}" 内に videoId が未設定のtrackがあります`);
    }
  }

  return config;
}

// ---- 既存プレイリストの取得(title照合用) -----------------------------------------

async function fetchExistingPlaylistTitles(
  auth: GoogleAuthClient
): Promise<Map<string, string>> {
  const youtube = google.youtube({ version: "v3", auth });
  const titleToId = new Map<string, string>();

  let pageToken: string | undefined = undefined;

  do {
    const res: { data: youtube_v3.Schema$PlaylistListResponse } = await youtube.playlists.list({
      part: ["snippet"],
      mine: true,
      maxResults: 50,
      pageToken,
    });

    for (const item of res.data.items ?? []) {
      const title = item.snippet?.title;
      const id = item.id;
      if (title && id) titleToId.set(title, id);
    }

    pageToken = res.data.nextPageToken ?? undefined;
  } while (pageToken);

  return titleToId;
}

// ---- YouTube API 操作 --------------------------------------------------------

async function createPlaylist(
  auth: GoogleAuthClient,
  config: PlaylistConfig
): Promise<string> {
  const youtube = google.youtube({ version: "v3", auth });

  const res = await youtube.playlists.insert({
    part: ["snippet", "status"],
    requestBody: {
      snippet: {
        title: config.title,
        description: config.description ?? "",
      },
      status: {
        privacyStatus: config.privacyStatus ?? "private",
      },
    },
  });

  const playlistId = res.data.id;
  if (!playlistId) throw new Error("プレイリストIDの取得に失敗しました");
  return playlistId;
}

async function addVideoToPlaylist(
  auth: GoogleAuthClient,
  playlistId: string,
  videoId: string
): Promise<{ ok: true } | { ok: false; reason: string }> {
  const youtube = google.youtube({ version: "v3", auth });

  try {
    await youtube.playlistItems.insert({
      part: ["snippet"],
      requestBody: {
        snippet: {
          playlistId,
          resourceId: {
            kind: "youtube#video",
            videoId,
          },
        },
      },
    });
    return { ok: true };
  } catch (err: any) {
    const reason = err?.errors?.[0]?.reason ?? err?.message ?? "unknown";
    return { ok: false, reason };
  }
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---- メイン処理 --------------------------------------------------------------

async function main() {
  const [, , configPath] = process.argv;

  const logger = new Logger(LOG_DIR);

  if (!configPath) {
    logger.error("使い方: npx tsx create-playlists-from-config.ts <playlists-config.jsonのパス>");
    await logger.close();
    process.exit(1);
  }

  logger.stdout(`ログファイル: ${logger.filePath}`);

  const config = loadConfig(configPath);
  const auth = await getAuthedClient(logger);

  logger.stdout("既存プレイリストを取得中...");
  const existingTitles = await fetchExistingPlaylistTitles(auth);
  logger.stdout(`チャンネル内に既存プレイリスト ${existingTitles.size}件`);

  const summary: {
    title: string;
    status: "created" | "skipped";
    playlistId: string;
    successCount?: number;
    failedTracks?: { videoId: string; title?: string; artist?: string; reason: string }[];
  }[] = [];

  for (const playlistConfig of config.playlists) {
    logger.stdout(`\n=== "${playlistConfig.title}" ===`);

    if (existingTitles.has(playlistConfig.title)) {
      const existingId = existingTitles.get(playlistConfig.title)!;
      logger.stdout(`既に存在するためスキップ (playlistId: ${existingId})`);
      summary.push({ title: playlistConfig.title, status: "skipped", playlistId: existingId });
      continue;
    }

    const playlistId = await createPlaylist(auth, playlistConfig);
    logger.stdout(`作成完了 (playlistId: ${playlistId})`);

    let successCount = 0;
    const failedTracks: { videoId: string; title?: string; artist?: string; reason: string }[] = [];

    for (let i = 0; i < playlistConfig.tracks.length; i++) {
      const track = playlistConfig.tracks[i];
      const result = await addVideoToPlaylist(auth, playlistId, track.videoId);

      const label = track.title
        ? `${track.artist ? track.artist + " - " : ""}${track.title}`
        : track.videoId;

      // 曲単位のログはファイルのみ(標準出力には出さない)
      if (result.ok) {
        successCount++;
        logger.detail(`[${i + 1}/${playlistConfig.tracks.length}] OK: ${label}`);
      } else {
        const reason = result.reason;
        failedTracks.push({ ...track, reason });
        logger.detail(`[${i + 1}/${playlistConfig.tracks.length}] NG (${reason}): ${label}`);
      }

      await sleep(INSERT_DELAY_MS);
    }

    logger.stdout(`追加完了: ${successCount}/${playlistConfig.tracks.length}曲成功(詳細はログファイル参照)`);

    summary.push({
      title: playlistConfig.title,
      status: "created",
      playlistId,
      successCount,
      failedTracks,
    });
  }

  // ---- サマリ出力 ----
  logger.stdout("\n\n========== 完了サマリ ==========");
  for (const s of summary) {
    if (s.status === "skipped") {
      logger.stdout(`- [SKIP] ${s.title} (既存: ${s.playlistId})`);
    } else {
      logger.stdout(
        `- [CREATED] ${s.title} → ${s.successCount}/${s.successCount! + (s.failedTracks?.length ?? 0)}曲追加成功 (https://www.youtube.com/playlist?list=${s.playlistId})`
      );
    }
  }

  const failedAny = summary.some((s) => s.failedTracks && s.failedTracks.length > 0);
  if (failedAny) {
    const failedPath = path.join(__dirname, "failed.json");
    fs.writeFileSync(
      failedPath,
      JSON.stringify(
        summary.filter((s) => s.failedTracks && s.failedTracks.length > 0),
        null,
        2
      )
    );
    logger.stdout(`\n一部曲の追加に失敗したプレイリストがあります。詳細: ${failedPath}`);
  }

  await logger.close();
}

main().catch(async (err) => {
  console.error("致命的エラー:", err);
  process.exit(1);
});
