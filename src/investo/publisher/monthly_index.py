"""Monthly retrospective index writer."""

from __future__ import annotations

from pathlib import Path

MONTHLY_INDEX_PATH = Path("archive/monthly/index.md")


def update_monthly_index(*, monthly_root: Path = Path("archive/monthly")) -> Path:
    monthly_root.mkdir(parents=True, exist_ok=True)
    pages = sorted(path for path in monthly_root.glob("*.md") if path.name != "index.md")
    lines = ["# 월간 회고", ""]
    if not pages:
        lines.append("아직 생성된 월간 회고가 없습니다.")
    else:
        for path in pages:
            lines.append(f"- [{path.stem}]({path.name})")
    lines.append("")
    target = monthly_root / "index.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


__all__ = ["MONTHLY_INDEX_PATH", "update_monthly_index"]
