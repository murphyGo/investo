"""Encrypt private preview files for one externally held recipient key."""

from __future__ import annotations

import argparse
import io
import os
import re
import zipfile
from pathlib import Path

from nacl.public import PublicKey, SealedBox

MAX_PREVIEW_BYTES = 2 * 1024 * 1024


def seal_preview(root: Path, recipient_hex: str, output: Path) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", recipient_hex):
        raise ValueError("invalid recipient public key")
    files = sorted(path for path in root.rglob("*") if path.suffix in {".md", ".json"})
    if not files or len(files) > 12:
        raise ValueError("invalid preview file count")
    packed = io.BytesIO()
    size = 0
    with zipfile.ZipFile(packed, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("preview file escapes output directory")
            if not path.is_file() or path.stat().st_size > MAX_PREVIEW_BYTES - size:
                raise ValueError("preview exceeds byte limit")
            data = path.read_bytes()
            size += len(data)
            if size > MAX_PREVIEW_BYTES:
                raise ValueError("preview exceeds byte limit")
            archive.writestr(path.relative_to(root).as_posix(), data)
    ciphertext = SealedBox(PublicKey(bytes.fromhex(recipient_hex))).encrypt(packed.getvalue())
    output.write_bytes(ciphertext)
    output.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        seal_preview(
            args.input_dir, os.environ.get("PREVIEW_RECIPIENT_PUBLIC_KEY", ""), args.output
        )
    except (OSError, ValueError, RuntimeError):
        print("preview_encryption=failed")
        return 1
    print("preview_encryption=complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
