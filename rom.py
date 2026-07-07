# rom.py
#
# Copyright (C) 2025 James Petersen <m@jamespetersen.ca>
# Licensed under MIT. See LICENSE

import bsdiff4
from collections import Counter
import os
import pkgutil
from typing import Any, Dict, TYPE_CHECKING
from settings import get_settings
from worlds.Files import APAutoPatchInterface
import zipfile
import json

from .data.charmap import charmap
from .data.locations import locations, LocationTable
from .data.items import items

from .apnds.lz import decompress_code
from .apnds.rom import HeaderField, Rom, Overlay
from .apnds.narc import Narc

if TYPE_CHECKING:
    from . import PokemonHGSSWorld

HEARTGOLD_HASH = "258cea3a62ac0d6eb04b5a0fd764d788"
SOULSILVER_HASH = "8a6c8888bed9e1dce952f840351b73f2"

class PokemonHeartGoldPatch(APAutoPatchInterface):
    game = "Pokemon HeartGold and SoulSilver"
    patch_file_ending = ".apheartgold"
    hashes: list[str | bytes] = [HEARTGOLD_HASH]
    source_data: bytes
    files: Dict[str, bytes]
    result_file_ending = ".nds"

    @staticmethod
    def get_source_data() -> bytes:
        with open(get_settings().pokemon_hgss_settings.hg_rom_file, "rb") as infile:
            base_rom_bytes = bytes(infile.read())
        return base_rom_bytes

    @staticmethod
    def get_source_data_with_cache() -> bytes:
        if not hasattr(PokemonHeartGoldPatch, "source_data"):
            PokemonHeartGoldPatch.source_data = PokemonHeartGoldPatch.get_source_data()
        return PokemonHeartGoldPatch.source_data

    def patch(self, target: str) -> None:
        self.read()
        data = PokemonHeartGoldPatch.get_source_data_with_cache()
        rom = Rom.from_bytes(data)

        # change rom name
        rom.header[HeaderField.TITLE] = b'HGAP 0\x00\x00\x00\x00\x00\x00'

        # decompress arm9 and any overlays we need to edit
        arm9 = bytearray(decompress_code(rom.arm9,(len(rom.arm9) - 12))[0])
        overlay12 = bytearray(decompress_code(rom.arm9_overlays[12].data,len(rom.arm9_overlays[12].data))[0])
        overlay15 = bytearray(decompress_code(rom.arm9_overlays[15].data,len(rom.arm9_overlays[15].data))[0])
        arm9[0xBB4] = 0x00
        arm9[0xBB5] = 0x00
        arm9[0xBB6] = 0x00
        arm9[0xBB7] = 0x00
        rom.arm9_overlays[12].flags = 0
        rom.arm9_overlays[15].flags = 0
        rom.arm9 = bytes(arm9)
        rom.arm9_overlays[12].data = bytes(overlay12)
        rom.arm9_overlays[15].data = bytes(overlay15)
        rom_decomp = rom.to_bytes()

        # apply bsdiff4 file
        rom_patched = bsdiff4.patch(rom_decomp, self.get_file("base_patch_us_hg.bsdiff4"))
        rom = Rom.from_bytes(rom_patched)
        arm9 = bytearray(rom.arm9)
        overlay12 = bytearray(rom.arm9_overlays[12].data)
        overlay15 = bytearray(rom.arm9_overlays[15].data)

        # apply options
        options = json.loads(self.get_file("options.json"))
        if options["reusable_tms"]:
            arm9[0x825A7] = 0xE0
            overlay15[0x6239] = 0xE0
            a017 = Narc.from_bytes(rom.files["/a/0/1/7"])
            for ndx in range(306, 398):
                tm = bytearray(a017.files[ndx])
                tm[0x8] = 0xBF
                a017.files[ndx] = bytes(tm)
            rom.files["/a/0/1/7"] = a017.to_bytes()
        if options["always_catch"]:
            overlay12[0xFCE0] = 0x00
            overlay12[0xFCE1] = 0x00
            overlay12[0xFCE2] = 0x00
            overlay12[0xFCE3] = 0x00
        if options["exp_multiplier"] != 1:
            arm9[0x6FADA] = 0x6C
            arm9[0x6FADB] = 0x00
            arm9[0x6FB2E] = options["exp_multiplier"]
            arm9[0x6FB2F] = 0x20
            arm9[0x6FB30] = 0x45
            arm9[0x6FB31] = 0x43
            arm9[0x6FB32] = 0x3A
            arm9[0x6FB33] = 0xE0
            arm9[0x6FB44] = 0x65
            arm9[0x6FB45] = 0x89
        if options["fps60"]:
            arm9[0xE28] = 0x00
            arm9[0xE29] = 0x00
        if options["instant_text"]:
            arm9[0x2346] = 0x00
            arm9[0x2347] = 0x21
            arm9[0x202EE] = 0x0C
            arm9[0x202EF] = 0x1C
            arm9[0x202F0] = 0x18
            arm9[0x202F1] = 0x48
            arm9[0x2031E] = 0x10
            arm9[0x2031F] = 0xBD
            arm9[0x20320] = 0x2D
            arm9[0x20321] = 0x3C
            arm9[0x20322] = 0xE5
            arm9[0x20323] = 0xE7
            arm9[0x2032E] = 0xDF
            arm9[0x2032F] = 0xD0
            arm9[0x2033A] = 0xF1
            arm9[0x2033B] = 0xE7
        if options["fast_hb_speed"]:
            overlay12[0x2E17A] = 0xC0
            overlay12[0x2E17B] = 0x02
            overlay12[0x2E1C0] = 0x20
            overlay12[0x2E1C1] = 0x1C
            overlay12[0x2E1CE] = 0x20
            overlay12[0x2E1CF] = 0x1C
            arm9[0x81750] = 0x21
            arm9[0x81751] = 0x1C
        if not options["hm_cut_ins"]:
            arm9[0x43768] = 0x0B
            arm9[0x43769] = 0xE0

        rom.arm9 = bytes(arm9)
        rom.arm9_overlays[12].data = bytes(overlay12)
        rom.arm9_overlays[15].data = bytes(overlay15)

        ap_bin = self.get_file("ap.bin")
        rom.files["/ap.bin"] = ap_bin

        with open(target, 'wb') as f:
            f.write(rom.to_bytes())

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.files = {}

    def get_manifest(self) -> Dict[str, Any]:
        manifest = super().get_manifest()
        manifest["result_file_ending"] = self.result_file_ending
        manifest["allowed_hashes"] = self.hashes
        return manifest

    def read_contents(self, opened_zipfile: zipfile.ZipFile) -> Dict[str, Any]:
        manifest = super().read_contents(opened_zipfile)
        for file in opened_zipfile.namelist():
            if file not in ["archipelago.json"]:
                self.files[file] = opened_zipfile.read(file)
        return manifest

    def write_contents(self, opened_zipfile: zipfile.ZipFile) -> None:
        super().write_contents(opened_zipfile)
        for file in self.files:
            opened_zipfile.writestr(file, self.files[file],
                                    compress_type=zipfile.ZIP_STORED if file.endswith(".bsdiff4") else None)

    def get_file(self, file: str) -> bytes:
        if file not in self.files:
            self.read()
        print(self.files.keys())
        return self.files[file]

    def write_file(self, file_name: str, file: bytes) -> None:
        self.files[file_name] = file

class PokemonSoulSilverPatch(APAutoPatchInterface):
    game = "Pokemon HeartGold and SoulSilver"
    patch_file_ending = ".apsoulsilver"
    hashes: list[str | bytes] = [SOULSILVER_HASH]
    source_data: bytes
    files: Dict[str, bytes]
    result_file_ending = ".nds"

    @staticmethod
    def get_source_data() -> bytes:
        with open(get_settings().pokemon_hgss_settings.ss_rom_file, "rb") as infile:
            base_rom_bytes = bytes(infile.read())
        return base_rom_bytes

    @staticmethod
    def get_source_data_with_cache() -> bytes:
        if not hasattr(PokemonSoulSilverPatch, "source_data"):
            PokemonSoulSilverPatch.source_data = PokemonSoulSilverPatch.get_source_data()
        return PokemonSoulSilverPatch.source_data

    def patch(self, target: str) -> None:
        self.read()
        data = PokemonSoulSilverPatch.get_source_data_with_cache()
        rom = Rom.from_bytes(data)

        # change rom name
        rom.header[HeaderField.TITLE] = b'SSAP 0\x00\x00\x00\x00\x00\x00'

        # decompress arm9 and any overlays we need to edit
        arm9 = bytearray(decompress_code(rom.arm9,(len(rom.arm9) - 12))[0])
        overlay12 = bytearray(decompress_code(rom.arm9_overlays[12].data,len(rom.arm9_overlays[12].data))[0])
        overlay15 = bytearray(decompress_code(rom.arm9_overlays[15].data,len(rom.arm9_overlays[15].data))[0])
        arm9[0xBB4] = 0x00
        arm9[0xBB5] = 0x00
        arm9[0xBB6] = 0x00
        arm9[0xBB7] = 0x00
        rom.arm9_overlays[12].flags = 0
        rom.arm9_overlays[15].flags = 0
        rom.arm9 = bytes(arm9)
        rom.arm9_overlays[12].data = bytes(overlay12)
        rom.arm9_overlays[15].data = bytes(overlay15)
        rom_decomp = rom.to_bytes()

        # apply bsdiff4 file
        rom_patched = bsdiff4.patch(rom_decomp, self.get_file("base_patch_us_ss.bsdiff4"))
        rom = Rom.from_bytes(rom_patched)
        arm9 = bytearray(rom.arm9)
        overlay12 = bytearray(rom.arm9_overlays[12].data)
        overlay15 = bytearray(rom.arm9_overlays[15].data)

        # apply options
        options = json.loads(self.get_file("options.json"))
        if options["reusable_tms"]:
            arm9[0x825A7] = 0xE0
            overlay15[0x6239] = 0xE0
            a017 = Narc.from_bytes(rom.files["/a/0/1/7"])
            for ndx in range(306, 398):
                tm = bytearray(a017.files[ndx])
                tm[0x8] = 0xBF
                a017.files[ndx] = bytes(tm)
            rom.files["/a/0/1/7"] = a017.to_bytes()
        if options["always_catch"]:
            overlay12[0xFCE0] = 0x00
            overlay12[0xFCE1] = 0x00
            overlay12[0xFCE2] = 0x00
            overlay12[0xFCE3] = 0x00
        if options["exp_multiplier"] != 1:
            arm9[0x6FADA] = 0x6C
            arm9[0x6FADB] = 0x00
            arm9[0x6FB2E] = options["exp_multiplier"]
            arm9[0x6FB2F] = 0x20
            arm9[0x6FB30] = 0x45
            arm9[0x6FB31] = 0x43
            arm9[0x6FB32] = 0x3A
            arm9[0x6FB33] = 0xE0
            arm9[0x6FB44] = 0x65
            arm9[0x6FB45] = 0x89
        if options["fps60"]:
            arm9[0xE28] = 0x00
            arm9[0xE29] = 0x00
        if options["instant_text"]:
            arm9[0x2346] = 0x00
            arm9[0x2347] = 0x21
            arm9[0x202EE] = 0x0C
            arm9[0x202EF] = 0x1C
            arm9[0x202F0] = 0x18
            arm9[0x202F1] = 0x48
            arm9[0x2031E] = 0x10
            arm9[0x2031F] = 0xBD
            arm9[0x20320] = 0x2D
            arm9[0x20321] = 0x3C
            arm9[0x20322] = 0xE5
            arm9[0x20323] = 0xE7
            arm9[0x2032E] = 0xDF
            arm9[0x2032F] = 0xD0
            arm9[0x2033A] = 0xF1
            arm9[0x2033B] = 0xE7
        if options["fast_hb_speed"]:
            overlay12[0x2E17A] = 0xC0
            overlay12[0x2E17B] = 0x02
            overlay12[0x2E1C0] = 0x20
            overlay12[0x2E1C1] = 0x1C
            overlay12[0x2E1CE] = 0x20
            overlay12[0x2E1CF] = 0x1C
            arm9[0x81750] = 0x21
            arm9[0x81751] = 0x1C
        if not options["hm_cut_ins"]:
            arm9[0x43768] = 0x0B
            arm9[0x43769] = 0xE0

        rom.arm9 = bytes(arm9)
        rom.arm9_overlays[12].data = bytes(overlay12)
        rom.arm9_overlays[15].data = bytes(overlay15)

        ap_bin = self.get_file("ap.bin")
        rom.files["/ap.bin"] = ap_bin

        with open(target, 'wb') as f:
            f.write(rom.to_bytes())

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.files = {}

    def get_manifest(self) -> Dict[str, Any]:
        manifest = super().get_manifest()
        manifest["result_file_ending"] = self.result_file_ending
        manifest["allowed_hashes"] = self.hashes
        return manifest

    def read_contents(self, opened_zipfile: zipfile.ZipFile) -> Dict[str, Any]:
        manifest = super().read_contents(opened_zipfile)
        for file in opened_zipfile.namelist():
            if file not in ["archipelago.json"]:
                self.files[file] = opened_zipfile.read(file)
        return manifest

    def write_contents(self, opened_zipfile: zipfile.ZipFile) -> None:
        super().write_contents(opened_zipfile)
        for file in self.files:
            opened_zipfile.writestr(file, self.files[file],
                                    compress_type=zipfile.ZIP_STORED if file.endswith(".bsdiff4") else None)

    def get_file(self, file: str) -> bytes:
        if file not in self.files:
            self.read()
        print(self.files.keys())
        return self.files[file]

    def write_file(self, file_name: str, file: bytes) -> None:
        self.files[file_name] = file

PokemonHGSSPatch = PokemonHeartGoldPatch | PokemonSoulSilverPatch

def encode_name(name: str) -> bytes | None:
    ret = bytes()
    state = "normal"
    buf = ""
    for c in name:
        match state:
            case "normal":
                if c == '\\':
                    state = "escape"
                elif c == '{':
                    state = "bracket"
                    buf = ""
                elif c in charmap:
                    ret += charmap[c].to_bytes(length=2, byteorder='little')
                else:
                    return None
            case "escape":
                if "\\" + c in charmap:
                    ret += charmap["\\" + c].to_bytes(length=2, byteorder='little')
                    state = "normal"
                else:
                    return None
            case "bracket":
                if c == '}':
                    if buf in charmap:
                        ret += charmap[buf].to_bytes(length=2, byteorder='little')
                    else:
                        return None
                    state = "normal"
                else:
                    buf += c
        if len(ret) >= 15:
            return None
    return ret + b'\xFF' * (16 - len(ret))

def encode_name_relaxed(name: str) -> bytes:
    ret = bytes()
    for c in name[:7]:
        ret += charmap.get(c, charmap["?"]).to_bytes(length=2, byteorder='little')
    return ret + b'\xFF' * (16 - len(ret))

def encode_option_name(name: str, strictness: str) -> bytes | None:
    if strictness == "strict":
        return encode_name(name)
    return encode_name_relaxed(name)

def process_name(name: str, world: "PokemonHGSSWorld", strictness: str) -> bytes:
    if name == "vanilla":
        return b'\xFF' * 16
    if name == "random":
        other_players = [world.multiworld.get_file_safe_player_name(id) for id in world.multiworld.player_name if id != world.player] # type: ignore
        world.random.shuffle(other_players)
        # if no player name matches, then return vanilla
        for name in other_players:
            ret = encode_option_name(name, strictness)
            if ret:
                return ret
        return b'\xFF' * 16
    if name == "player_name":
        ret = encode_option_name(world.multiworld.get_file_safe_player_name(world.player), strictness)
    else:
        ret = encode_option_name(name, strictness)
    if ret is not None:
        return ret
    else:
        return b'\xFF' * 16

def generate_output(world: "PokemonHGSSWorld", output_directory: str, patch: PokemonHGSSPatch) -> None:
    game_opts = world.options.game_options
    ap_bin = bytes()
    ap_bin += process_name(game_opts.default_player_name, world, game_opts.name_strictness)
    ap_bin += process_name(game_opts.default_rival_name, world, game_opts.name_strictness)

    match game_opts.default_gender:
        case "male":
            ap_bin += b'\x00'
        case "female":
            ap_bin += b'\x01'
        case "random":
            ap_bin += world.random.choice([b'\x00', b'\x01'])
        case "vanilla":
            ap_bin += b'\x02'
        case _:
            raise ValueError(f"invalid default gender: \"{game_opts.default_gender}\"")

    ap_bin += {"slow": 0, "mid": 1, "fast": 2}[game_opts.text_speed].to_bytes(length=1, byteorder='little')
    ap_bin += {"stereo": 0, "mono": 1}[game_opts.sound].to_bytes(length=1, byteorder='little')
    ap_bin += {"on": 0, "off": 1}[game_opts.battle_scene].to_bytes(length=1, byteorder='little')
    ap_bin += {"shift": 0, "set": 1}[game_opts.battle_style].to_bytes(length=1, byteorder='little')
    ap_bin += {"normal": 0, "start=x": 1, "l=a": 2}[game_opts.button_mode].to_bytes(length=1, byteorder='little')

    text_frame = game_opts.text_frame
    if isinstance(text_frame, int) and 1 <= text_frame <= 20:
        ap_bin += (text_frame - 1).to_bytes(length=1, byteorder='little')
    elif text_frame == "random":
        ap_bin += world.random.randint(0, 19).to_bytes(length=1, byteorder='little')
    else:
        raise ValueError(f"invalid text frame: \"{text_frame}\"")

    #if world.options.hm_badge_requirement.value == 1:
    #    hm_accum = 0
    #    hm_order = ["CUT", "FLY", "SURF", "STRENGTH", "WHIRLPOOL", "ROCK_SMASH", "WATERFALL", "ROCK_CLIMB"]
    #    for i, v in enumerate(hm_order):
    #        if v in world.options.remove_badge_requirements:
    #            hm_accum |= 1 << i
    #else:
    #    hm_accum = 0xFF
    #ap_bin += hm_accum.to_bytes(length=1, byteorder='little')

    def add_opt_byte(name: str):
        nonlocal ap_bin
        ap_bin += getattr(world.options, name).value.to_bytes(length=1, byteorder='little')

    add_opt_byte("exp_multiplier")
    #add_opt_byte("regional_dex_goal")
    #add_opt_byte("remote_items")

    match game_opts.received_items_notification:
        case "nothing":
            ap_bin += b'\x00'
        case "message":
            ap_bin += b'\x03'
        case "jingle":
            ap_bin += b'\x04'
        case _:
            raise ValueError(f"invalid received items notification: \"{game_opts.received_items_notification}\"")
    #add_opt_byte("blind_trainers")
    add_opt_byte("fps60")
    add_opt_byte("hm_cut_ins")
    #ap_bin += (world.options.hb_speed.value - 1).to_bytes(length=1, byteorder='little')

    if len(ap_bin) % 2 == 1:
        ap_bin += b'\x00'

    tables: dict[LocationTable, bytearray] = {}

    def put_in_table(table: LocationTable, id: int, item_id: int):
        if table not in tables:
            tables[table] = bytearray()
        l = len(tables[table])
        if id >= l // 2:
            tables[table] = tables[table] + b'\x00\xF0' * (id - l // 2 + 1)
        tables[table][2*id:2*(id+1)] = item_id.to_bytes(length=2, byteorder='little')

    filled_locations = set()

    for location in world.multiworld.get_locations(world.player):
        if location.address is None or location.item is None or location.item.code is None:
            continue
        table = LocationTable(location.address >> 16)
        id = location.address & 0xFFFF
        filled_locations.add(location.name)
        if location.item.player == world.player:
            item_id = location.item.code
        else:
            item_id = 0xE000
        put_in_table(table, id, item_id)

    for location in locations.values():
        if location.label not in filled_locations:
            if isinstance(location.original_item, str):
                original_item = location.original_item
            else:
                original_item = world.random.choice(location.original_item)
            put_in_table(location.table, location.id, items[original_item].get_raw_id())

    ap_bin += len(tables).to_bytes(length=4, byteorder='little')
    for table in sorted(tables.keys()):
        data = tables[table]
        ap_bin += table.value.to_bytes(length=4, byteorder='little')
        ap_bin += (len(data) // 2).to_bytes(length=4, byteorder='little')
        ap_bin += data

    precollected = world.multiworld.precollected_items[world.player]
    start_inventory: Counter[int] = Counter(map(lambda item : item.code, precollected)) # type: ignore
    entries = [code.to_bytes(length=2, byteorder='little') + count.to_bytes(length=2, byteorder='little') for code, count in start_inventory.items()]
    ap_bin += len(entries).to_bytes(length=4, byteorder='little')
    ap_bin += b''.join(entries)

    patch.write_file("ap.bin", ap_bin)
    options = {}
    options["reusable_tms"] = bool(world.options.reusable_tms)
    options["always_catch"] = bool(world.options.always_catch)
    options["exp_multiplier"] = int(world.options.exp_multiplier)
    options["fps60"] = bool(world.options.fps60)
    options["instant_text"] = bool(world.options.instant_text)
    options["fast_hb_speed"] = bool(world.options.fast_hb_speed)
    options["hm_cut_ins"] = bool(world.options.hm_cut_ins)
    options["game_options"] = dict(world.options.game_options.value)
    patch.write_file("options.json", json.dumps(options))

    out_file_name = world.multiworld.get_out_file_name_base(world.player)
    patch.write(os.path.join(output_directory, f"{out_file_name}{patch.patch_file_ending}"))
