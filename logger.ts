import * as fs from "fs";
import * as path from "path";

/**
 * ログ出力方針:
 * - stdout() : 標準出力 + ログファイル両方に書く。フェーズの見出しやサマリなど、
 *              画面で追いたい程度の粒度のログ用
 * - detail()  : ログファイルのみに書く。曲単位のOK/NGなど、量が多く画面を埋めるログ用
 * - error()   : 標準出力(console.error) + ログファイル両方
 */
export class Logger {
  private stream: fs.WriteStream;
  readonly filePath: string;

  constructor(logDir: string) {
    fs.mkdirSync(logDir, { recursive: true });

    const timestamp = new Date()
      .toISOString()
      .replace(/[:.]/g, "-"); // ファイル名に使えない文字を置換

    this.filePath = path.join(logDir, `run-${timestamp}.log`);
    this.stream = fs.createWriteStream(this.filePath, { flags: "a" });
  }

  private writeLine(line: string) {
    this.stream.write(line + "\n");
  }

  private timestamped(message: string): string {
    return `[${new Date().toISOString()}] ${message}`;
  }

  /** 標準出力 + ログファイル */
  stdout(message: string) {
    console.log(message);
    this.writeLine(this.timestamped(message));
  }

  /** ログファイルのみ(曲単位など量が多いログ用) */
  detail(message: string) {
    this.writeLine(this.timestamped(message));
  }

  /** 標準エラー出力 + ログファイル */
  error(message: string) {
    console.error(message);
    this.writeLine(this.timestamped(`[ERROR] ${message}`));
  }

  /** ストリームを閉じる。プロセス終了前に必ず呼ぶ */
  async close(): Promise<void> {
    return new Promise((resolve) => {
      this.stream.end(() => resolve());
    });
  }
}
