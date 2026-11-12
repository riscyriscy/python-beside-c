"""Sign a firmware image, verify it, and watch tampering fail.

Run: python3 signing_demo.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

FIELDS = ("name", "version", "size", "sha256")


def signed_bytes(m: dict[str, object]) -> bytes:
    """The exact bytes that are signed: the four fields, in a fixed form."""
    return json.dumps({k: m[k] for k in FIELDS}, sort_keys=True).encode()


def make_manifest(image: Path, key: Ed25519PrivateKey) -> dict[str, object]:
    data = image.read_bytes()
    m: dict[str, object] = {
        "name": image.name,
        "version": "1.4.2",
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    m["signature"] = key.sign(signed_bytes(m)).hex()
    return m


def verify(m: dict[str, object], image: Path, pub: Ed25519PublicKey) -> str:
    data = image.read_bytes()
    if len(data) != m["size"] or hashlib.sha256(data).hexdigest() != m["sha256"]:
        return "FAIL: image does not match the manifest"
    try:
        pub.verify(bytes.fromhex(str(m["signature"])), signed_bytes(m))
    except InvalidSignature:
        return "FAIL: signature does not match the manifest and this key"
    return "OK: image intact, manifest signed by the expected key"


def main() -> None:
    image = Path("fw.bin")
    good = bytes((i * 7 + 3) % 256 for i in range(512))  # deterministic content
    image.write_bytes(good)
    key = Ed25519PrivateKey.generate()  # on a real line this lives in a signing service
    pub = key.public_key()
    m = make_manifest(image, key)
    Path("manifest.json").write_text(json.dumps(m, indent=2) + "\n")
    shown = {k: v for k, v in m.items() if k != "signature"}
    print(json.dumps(shown, indent=2))
    print(f"signature: {len(str(m['signature'])) // 2} bytes (hex in the file)")

    loaded = json.loads(Path("manifest.json").read_text())
    print("untouched image    :", verify(loaded, image, pub))
    image.write_bytes(good[:100] + bytes([good[100] ^ 0x01]) + good[101:])
    print("one bit flipped    :", verify(loaded, image, pub))
    fixed = dict(loaded, sha256=hashlib.sha256(image.read_bytes()).hexdigest())
    print("hash updated too   :", verify(fixed, image, pub))
    image.write_bytes(good)
    print("rolled-back version:", verify(dict(loaded, version="1.0.0"), image, pub))
    other = make_manifest(
        image, Ed25519PrivateKey.generate()
    )  # signed with another key
    print("wrong signer       :", verify(other, image, pub))


if __name__ == "__main__":
    main()
