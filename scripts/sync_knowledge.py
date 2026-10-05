"""同步全书；网络失败时保持已有语料。支持 --source 本地仓库路径。"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.knowledge import load_entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="已下载的 HowToLiveBetter 仓库")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="life-guide-sync-") as temporary:
        temp = Path(temporary)
        source = args.source.resolve() if args.source else temp / "upstream"
        if args.source is None:
            # clone 自带 git 提交身份；不用执行任何上游脚本。
            subprocess.run(["git", "clone", "--depth", "1",
                            "https://github.com/eternity4719/HowToLiveBetter.git", str(source)],
                           check=True, timeout=60, capture_output=True)
        if not (source / "book").is_dir() or not (source / "README.md").is_file():
            raise ValueError("指定目录不是 HowToLiveBetter 正文仓库")
        candidates = sorted((source / "book").glob("*.md"))
        candidates = [p for p in candidates if re.match(r"\d+-", p.name) and not p.is_symlink()]
        entries = load_entries(source / "book")
        if not entries:
            raise ValueError("没有解析到完整条目，已有知识库未改动")
        staged = temp / "staged"
        staged.mkdir()
        for path in candidates:
            shutil.copy2(path, staged / path.name)
        commit = None
        if (source / ".git").exists():
            commit = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                                    check=True, capture_output=True, text=True).stdout.strip()
        manifest = {
            "scope": "imported",
            "description": f"导入 {len(candidates)} 个章节文件，共 {len(entries)} 个完整条目",
            "fetched_on": datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat(),
            "upstream": "https://github.com/eternity4719/HowToLiveBetter",
            "commit": commit,
            "license": "CC BY 4.0",
            "method": "本地正文目录导入" if args.source else "GitHub 浅克隆",
        }
        # 先验证再替换；同步时应停止服务，完成后重启重新建立索引。
        data = ROOT / "data"
        backup = data / "book.previous"
        if backup.exists():
            shutil.rmtree(backup)
        (data / "book").rename(backup)
        try:
            shutil.copytree(staged, data / "book")
            (data / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception:
            shutil.rmtree(data / "book", ignore_errors=True)
            backup.rename(data / "book")
            raise
        shutil.rmtree(backup)
        print(manifest["description"] + "；重启服务生效。")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"同步未完成（{type(exc).__name__}）。可先下载仓库，再使用 --source 导入。", file=sys.stderr)
        sys.exit(1)
