"""List the components in a CycloneDX SBOM. Run: python3 sbom_list.py sbom.cdx.json"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(path: Path) -> None:
    bom = json.loads(path.read_text())
    tool = bom["metadata"]["tools"][0]
    fmt = f"{bom['bomFormat']} {bom['specVersion']}"
    print(f"{fmt}, written by {tool['name']} {tool['version']}")
    root = bom["metadata"]["component"]
    print(f"project: {root['name']} {root['version']}")
    keys: set[str] = set()
    for c in bom["components"]:
        keys |= set(c)
        refs = c.get("externalReferences", [])
        hashes = sum(len(r.get("hashes", [])) for r in refs)
        print(f"  {c['name']:<12} {c['version']:<8} {c['purl']:<28} "
              f"{len(refs):>3} files {hashes:>3} hashes")
    print("fields per component:", ", ".join(sorted(keys)))
    print("sections:", " ".join(bom))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
