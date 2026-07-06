#!/usr/bin/env python3

# patch_gen.py
#
# Copyright (C) 2025 James Petersen <m@jamespetersen.ca>
# Licensed under MIT. See LICENSE

import os
import sys
from hashlib import sha1

from bsdiff4 import diff

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "apnds"))

from apnds.lz import decompress_code
from apnds.rom import HeaderField, Rom

AP_TITLES = {
    "heartgold": b"HGAP 0\x00\x00\x00\x00\x00\x00",
    "soulsilver": b"SSAP 0\x00\x00\x00\x00\x00\x00",
}

VANILLA_SHA1 = {
    "heartgold": "4fcded0e2713dc03929845de631d0932ea2b5a37",
    "soulsilver": "f8dc38ea20c17541a43b58c5e6d18c1732c7e582",
}


def read_rom(path: str) -> bytes:
    with open(path, "rb") as infile:
        return infile.read()


def validate_vanilla(path: str, version: str) -> bytes:
    data = read_rom(path)
    actual_sha1 = sha1(data).hexdigest()
    expected_sha1 = VANILLA_SHA1[version]
    if actual_sha1 != expected_sha1:
        print(
            f"{path}: expected clean US {version} SHA1 {expected_sha1}, got {actual_sha1}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return data


def normalize_rom(data: bytes, version: str) -> bytes:
    rom = Rom.from_bytes(data)

    rom.header[HeaderField.TITLE] = AP_TITLES[version]

    arm9 = bytearray(decompress_code(rom.arm9, len(rom.arm9) - 12)[0])
    arm9[0xBB4:0xBB8] = b"\x00\x00\x00\x00"
    rom.arm9 = bytes(arm9)

    for overlay_id in (12, 15):
        overlay = rom.arm9_overlays[overlay_id]
        overlay.data = decompress_code(overlay.data, len(overlay.data))[0]
        overlay.flags = 0

    return rom.to_bytes()


def main() -> None:
    if len(sys.argv) != 5 or sys.argv[1] not in AP_TITLES:
        print(f"usage: {sys.argv[0]} <heartgold|soulsilver> <vanilla.nds> <target.nds> <out.bsdiff4>", file=sys.stderr)
        raise SystemExit(2)

    version, vanilla, target, output = sys.argv[1:]
    patch = diff(
        normalize_rom(validate_vanilla(vanilla, version), version),
        normalize_rom(read_rom(target), version),
    )
    with open(output, "wb") as outfile:
        outfile.write(patch)


if __name__ == "__main__":
    main()
