"""Only the holder of the ephemeral private key can read preview artifacts."""

import io
import zipfile
from pathlib import Path

import pytest
from nacl.exceptions import CryptoError
from nacl.public import PrivateKey, SealedBox
from scripts.seal_event_preview import MAX_PREVIEW_BYTES, seal_preview


def test_private_recipient_round_trip_and_wrong_key_rejection(tmp_path: Path) -> None:
    root = tmp_path / "preview"
    root.mkdir()
    content = "출처가 확인된 비게시 미리보기"
    (root / "preview.md").write_text(content)
    (root / "manifest.json").write_text('{"published": false}')
    (root / "ignored.log").write_text("native output must never be packed")
    key = PrivateKey.generate()
    output = tmp_path / "preview.sealed"
    seal_preview(root, bytes(key.public_key).hex(), output)
    assert content.encode() not in output.read_bytes()
    with pytest.raises(CryptoError):
        SealedBox(PrivateKey.generate()).decrypt(output.read_bytes())
    plain = SealedBox(key).decrypt(output.read_bytes())
    with zipfile.ZipFile(io.BytesIO(plain)) as archive:
        assert set(archive.namelist()) == {"manifest.json", "preview.md"}
        assert archive.read("preview.md").decode() == content


@pytest.mark.parametrize("failure", ["key", "oversize", "symlink"])
def test_invalid_inputs_do_not_emit_artifact(tmp_path: Path, failure: str) -> None:
    root = tmp_path / "preview"
    root.mkdir()
    path = root / "preview.md"
    path.write_text("preview")
    key = bytes(PrivateKey.generate().public_key).hex()
    if failure == "key":
        key = "invalid"
    elif failure == "oversize":
        path.write_bytes(b"x" * (MAX_PREVIEW_BYTES + 1))
    else:
        outside = tmp_path / "outside.md"
        outside.write_text("private")
        (root / "link.md").symlink_to(outside)
    output = tmp_path / "preview.sealed"
    with pytest.raises(ValueError):
        seal_preview(root, key, output)
    assert not output.exists()
