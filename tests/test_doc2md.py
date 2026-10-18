"""Tests for scripts/tools/doc2md."""

from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONVERT_PY = ROOT / "scripts" / "tools" / "doc2md" / "convert.py"


def _load_doc2md():
    spec = importlib.util.spec_from_file_location("doc2md_convert", CONVERT_PY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


doc2md = _load_doc2md()


def _minimal_png_bytes() -> bytes:
    # 1x1 PNG
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _write_minimal_docx(path: Path, *, with_media: bool = True) -> None:
    """Write a tiny valid-enough docx zip for media extraction + markitdown."""
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Hello doc2md test — mục F2 mẫu</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
</Relationships>
"""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)
        if with_media:
            zf.writestr("word/media/image1.png", _minimal_png_bytes())


def test_clean_markdown_collapses_blank_lines():
    raw = "a\n\n\n\nb  \n"
    assert doc2md.clean_markdown(raw) == "a\n\nb\n"


def test_extract_office_media(tmp_path: Path):
    src = tmp_path / "sample.docx"
    _write_minimal_docx(src, with_media=True)
    media_dir = tmp_path / "media"
    files = doc2md.extract_office_media(src, media_dir)
    assert len(files) == 1
    assert files[0].name == "image1.png"
    assert files[0].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_sidecar_and_convert_roundtrip(tmp_path: Path):
    pytest.importorskip("markitdown")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    src = src_dir / "Mo ta F2.docx"
    _write_minimal_docx(src, with_media=True)
    (src_dir / "plot_sidecar.png").write_bytes(_minimal_png_bytes())

    out = tmp_path / "out"
    result = doc2md.convert_file(src, out, use_sidecar=True)

    assert result.md_path.is_file()
    text = result.md_path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "purpose: ai-consumable-markdown" in text
    assert "Hello doc2md test" in text or "doc2md" in text.lower()
    assert result.engine in {"markitdown", "pandoc"}
    assert len(result.media_files) >= 1
    assert len(result.sidecar_files) == 1
    assert "## Extracted media" in text
    assert "./sidecar/plot_sidecar.png" in text


def test_cli_help_exits_zero():
    with pytest.raises(SystemExit) as ei:
        doc2md.main(["--help"])
    assert ei.value.code == 0


def test_unsupported_extension(tmp_path: Path):
    bad = tmp_path / "x.bin"
    bad.write_bytes(b"nope")
    with pytest.raises(ValueError, match="Định dạng chưa hỗ trợ"):
        doc2md.convert_file(bad, tmp_path / "out")
