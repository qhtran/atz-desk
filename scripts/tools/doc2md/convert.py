#!/usr/bin/env python3
"""
doc2md — convert office/PDF docs to AI-friendly Markdown + media folders.

Primary engine: Microsoft MarkItDown
Fallback:       pandoc (if installed on PATH)
Also:           unzip embedded Office media; optional sidecar images next to source.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Callable, Iterable

SUPPORTED_EXT = {
    ".docx",
    ".doc",
    ".xlsx",
    ".xls",
    ".pptx",
    ".ppt",
    ".pdf",
    ".html",
    ".htm",
    ".csv",
    ".json",
    ".xml",
    ".txt",
    ".md",
    ".rtf",
    ".epub",
    ".msg",
    ".eml",
}

OFFICE_ZIP_MEDIA_PREFIXES = (
    "word/media/",
    "xl/media/",
    "ppt/media/",
)

SIDECAR_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tif", ".tiff"}

# Collapse runs of blank lines; trim trailing spaces on each line.
_RE_BLANK_RUNS = re.compile(r"\n{3,}")
_RE_TRAIL_SPACE = re.compile(r"[ \t]+$", re.MULTILINE)
_RE_EMPTY_TABLE_ROW = re.compile(r"^\|(?:\s*\|)+\s*$", re.MULTILINE)


@dataclass
class ConvertResult:
    source: Path
    md_path: Path
    media_dir: Path
    sidecar_dir: Path
    engine: str
    media_files: list[Path] = field(default_factory=list)
    sidecar_files: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug_stem(path: Path) -> str:
    """ASCII-ish folder name; keep Unicode but strip awkward chars."""
    stem = path.stem.strip()
    stem = re.sub(r"[\\/:*?\"<>|]+", "_", stem)
    stem = re.sub(r"\s+", "_", stem)
    return stem[:120] or "document"


def _sha256_short(path: Path, n: int = 10) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def clean_markdown(text: str) -> str:
    """Light cleanup so the MD is cheaper for AI context."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _RE_TRAIL_SPACE.sub("", text)
    text = _RE_EMPTY_TABLE_ROW.sub("", text)
    text = _RE_BLANK_RUNS.sub("\n\n", text)
    return text.strip() + "\n"


def build_frontmatter(
    *,
    source: Path,
    engine: str,
    media_count: int,
    sidecar_count: int,
    content_sha: str,
) -> str:
    # YAML-ish frontmatter without requiring PyYAML (keep tool deps tiny).
    src = str(source.resolve())
    lines = [
        "---",
        f'source: "{src}"',
        f'format: "{source.suffix.lower().lstrip(".")}"',
        f'converted_at: "{_utc_now_iso()}"',
        f'engine: "{engine}"',
        f"media_count: {media_count}",
        f"sidecar_count: {sidecar_count}",
        f'content_sha256_10: "{content_sha}"',
        "purpose: ai-consumable-markdown",
        "---",
        "",
    ]
    return "\n".join(lines)


def extract_office_media(source: Path, media_dir: Path) -> list[Path]:
    """Copy embedded images from docx/xlsx/pptx zip packages."""
    if source.suffix.lower() not in {".docx", ".xlsx", ".pptx"}:
        return []
    if not zipfile.is_zipfile(source):
        return []

    written: list[Path] = []
    media_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as zf:
        for name in zf.namelist():
            lower = name.replace("\\", "/")
            if not any(lower.startswith(p) for p in OFFICE_ZIP_MEDIA_PREFIXES):
                continue
            if lower.endswith("/"):
                continue
            base = Path(lower).name
            if not base or base.startswith("."):
                continue
            dest = media_dir / base
            # Avoid overwrite collisions.
            if dest.exists():
                dest = media_dir / f"{Path(base).stem}_{len(written)}{Path(base).suffix}"
            with zf.open(name) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)
            written.append(dest)
    return written


def collect_sidecar_images(source: Path, sidecar_dir: Path) -> list[Path]:
    """Copy image files sitting next to the source document."""
    parent = source.parent
    copied: list[Path] = []
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    for p in sorted(parent.iterdir()):
        if not p.is_file():
            continue
        if p.resolve() == source.resolve():
            continue
        if p.suffix.lower() not in SIDECAR_IMAGE_EXT:
            continue
        dest = sidecar_dir / p.name
        shutil.copy2(p, dest)
        copied.append(dest)
    return copied


def append_media_index(md: str, media_files: Iterable[Path], sidecar_files: Iterable[Path]) -> str:
    """Append a short index so AI/humans can find extracted plots without Office."""
    media_files = list(media_files)
    sidecar_files = list(sidecar_files)
    if not media_files and not sidecar_files:
        return md

    parts = [md.rstrip(), "", "## Extracted media", ""]
    if media_files:
        parts.append("### Embedded (`media/`)")
        parts.append("")
        for p in media_files:
            parts.append(f"- ![{p.name}](./media/{p.name})")
        parts.append("")
    if sidecar_files:
        parts.append("### Sidecar images (`sidecar/`)")
        parts.append("")
        for p in sidecar_files:
            parts.append(f"- ![{p.name}](./sidecar/{p.name})")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def convert_with_markitdown(source: Path) -> str:
    try:
        from markitdown import MarkItDown
    except ImportError as e:
        raise RuntimeError(
            "markitdown chưa cài. Chạy: pip install -r scripts/tools/doc2md/requirements.txt"
        ) from e
    result = MarkItDown().convert(str(source))
    text = getattr(result, "text_content", None) or ""
    if not str(text).strip():
        raise RuntimeError("MarkItDown trả về nội dung rỗng")
    return str(text)


def pandoc_available() -> bool:
    return shutil.which("pandoc") is not None


def convert_with_pandoc(source: Path, out_md: Path, media_dir: Path) -> str:
    if not pandoc_available():
        raise RuntimeError("pandoc không có trên PATH")

    media_dir.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    # pandoc writes media under <extract-media>/media/...
    cmd = [
        "pandoc",
        str(source),
        "-t",
        "gfm",
        "-o",
        str(out_md),
        f"--extract-media={media_dir.parent}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"pandoc failed ({proc.returncode}): {err[:500]}")

    body = out_md.read_text(encoding="utf-8", errors="replace")
    # Normalize pandoc media paths into ./media/
    pandoc_media = media_dir.parent / "media"
    if pandoc_media.is_dir() and pandoc_media.resolve() != media_dir.resolve():
        for p in pandoc_media.rglob("*"):
            if p.is_file():
                dest = media_dir / p.name
                if dest.exists():
                    dest = media_dir / f"{p.stem}_p{dest.stat().st_size}{p.suffix}"
                shutil.move(str(p), str(dest))
        shutil.rmtree(pandoc_media, ignore_errors=True)
        body = body.replace("](media/", "](./media/")
        body = re.sub(r"\]\((?:\./)?media/([^)]+)\)", r"](./media/\1)", body)
    return body


def convert_file(
    source: Path,
    output_root: Path,
    *,
    use_sidecar: bool = True,
    prefer_pandoc: bool = False,
    keep_empty_dirs: bool = False,
) -> ConvertResult:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Không thấy file: {source}")

    ext = source.suffix.lower()
    if ext not in SUPPORTED_EXT:
        raise ValueError(f"Định dạng chưa hỗ trợ: {ext}. Hỗ trợ: {sorted(SUPPORTED_EXT)}")

    stem = _slug_stem(source)
    work_dir = output_root.expanduser().resolve() / stem
    media_dir = work_dir / "media"
    sidecar_dir = work_dir / "sidecar"
    md_path = work_dir / f"{stem}.md"
    work_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    engine = ""
    body = ""

    engines: list[tuple[str, Callable[[], str]]] = []
    if prefer_pandoc and pandoc_available():
        engines.append(("pandoc", lambda: convert_with_pandoc(source, md_path, media_dir)))
        engines.append(("markitdown", lambda: convert_with_markitdown(source)))
    else:
        engines.append(("markitdown", lambda: convert_with_markitdown(source)))
        if pandoc_available():
            engines.append(("pandoc", lambda: convert_with_pandoc(source, md_path, media_dir)))
        else:
            warnings.append("pandoc không có trên PATH — bỏ qua fallback")

    last_err: Exception | None = None
    for name, fn in engines:
        try:
            body = fn()
            engine = name
            break
        except Exception as e:  # noqa: BLE001 — collect and try next engine
            last_err = e
            warnings.append(f"{name} thất bại: {e}")

    if not body.strip():
        raise RuntimeError(f"Không convert được {source.name}: {last_err}")

    # Embedded Office media (even if pandoc already extracted some).
    media_files = extract_office_media(source, media_dir)
    # If pandoc left files in media_dir, include them.
    if media_dir.is_dir():
        seen = {p.resolve() for p in media_files}
        for p in sorted(media_dir.iterdir()):
            if p.is_file() and p.resolve() not in seen:
                media_files.append(p)

    sidecar_files: list[Path] = []
    if use_sidecar:
        sidecar_files = collect_sidecar_images(source, sidecar_dir)

    body = clean_markdown(body)
    body = append_media_index(body, media_files, sidecar_files)
    content_sha = _sha256_short(source)
    front = build_frontmatter(
        source=source,
        engine=engine,
        media_count=len(media_files),
        sidecar_count=len(sidecar_files),
        content_sha=content_sha,
    )
    md_path.write_text(front + body, encoding="utf-8")

    if not keep_empty_dirs:
        if media_dir.is_dir() and not any(media_dir.iterdir()):
            media_dir.rmdir()
        if sidecar_dir.is_dir() and not any(sidecar_dir.iterdir()):
            sidecar_dir.rmdir()

    return ConvertResult(
        source=source,
        md_path=md_path,
        media_dir=media_dir,
        sidecar_dir=sidecar_dir,
        engine=engine,
        media_files=media_files,
        sidecar_files=sidecar_files,
        warnings=warnings,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="doc2md",
        description="Convert docx/xlsx/pdf/... → Markdown + media/ (AI-friendly).",
    )
    p.add_argument("input", type=Path, help="Đường dẫn file nguồn")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("docs/refs/_converted"),
        help="Thư mục gốc output (mặc định: docs/refs/_converted)",
    )
    p.add_argument(
        "--no-sidecar",
        action="store_true",
        help="Không copy ảnh nằm cạnh file nguồn",
    )
    p.add_argument(
        "--prefer-pandoc",
        action="store_true",
        help="Thử pandoc trước MarkItDown",
    )
    p.add_argument(
        "--keep-empty-dirs",
        action="store_true",
        help="Giữ media/ và sidecar/ dù trống",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = convert_file(
            args.input,
            args.output,
            use_sidecar=not args.no_sidecar,
            prefer_pandoc=args.prefer_pandoc,
            keep_empty_dirs=args.keep_empty_dirs,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[DBG-doc2md] ERR-DOC2MD-001 {e}", file=sys.stderr)
        return 1

    print(f"[DBG-doc2md] OK engine={result.engine}")
    print(f"[DBG-doc2md] md={result.md_path}")
    print(f"[DBG-doc2md] media={len(result.media_files)} sidecar={len(result.sidecar_files)}")
    for w in result.warnings:
        print(f"[DBG-doc2md] WARN {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
