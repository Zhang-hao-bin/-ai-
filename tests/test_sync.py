import importlib.util
import json
from pathlib import Path
import shutil
import sys

from app.main import ROOT


def test_local_import_updates_manifest_and_preserves_full_entries(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("sync_knowledge", ROOT / "scripts/sync_knowledge.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = tmp_path / "project"
    (target / "data/book").mkdir(parents=True)
    source = tmp_path / "upstream"
    shutil.copytree(ROOT / "data/book", source / "book")
    (source / "README.md").write_text("正文仓库", encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", target)
    monkeypatch.setattr(sys, "argv", ["sync_knowledge.py", "--source", str(source)])
    module.main()
    manifest = json.loads((target / "data/manifest.json").read_text())
    assert manifest["scope"] == "imported"
    assert "17 个完整条目" in manifest["description"]
    assert (target / "data/book/08-别把自己搭进去.md").read_text() == (source / "book/08-别把自己搭进去.md").read_text()
    assert not (target / "data/book.previous").exists()
