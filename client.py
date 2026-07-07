# client.py
#
# Copyright (C) 2025 James Petersen <m@jamespetersen.ca>
# Licensed under MIT. See LICENSE

from collections.abc import Mapping, Set
from dataclasses import dataclass
from NetUtils import ClientStatus
from typing import TYPE_CHECKING, Tuple

import Utils

from .data.locations import FlagCheck, LocationCheck, locations, VarCheck, OnceCheck
from .locations import raw_id_to_const_name
from .options import Goal #, RemoteItems

import worlds._bizhawk as bizhawk
from worlds._bizhawk.client import BizHawkClient

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext

# HGSS US Version legacy Save Data pointer (from the original Lua test).
# Patched ROMs expose a small AP struct in RAM, which the client scans for.
AP_STRUCT_PTR_ADDRESS = 0x02111880
AP_STRUCT_SCAN_START = 0x02000000
AP_STRUCT_SCAN_END = 0x02400000
AP_STRUCT_SCAN_CHUNK_SIZE = 0x4000
AP_SUPPORTED_VERSIONS = {0}
AP_MAGIC = b' AP '

# Archipelago's BizHawk/DeSmuME connector replies to each read batch on a
# single line, and the client reads it with asyncio's default StreamReader
# limit (64 KiB). A base64-encoded READ response is ~4/3 the raw byte count,
# so a batch reading more than ~48 KiB overruns that limit
# (LimitOverrunError). Split large reads into batches that stay well under
# it. 0x8000 raw bytes -> ~44 KiB of base64, comfortably below 64 KiB.
READ_BATCH_SIZE = 0x8000


async def guarded_read_chunked(ctx: "BizHawkClientContext", read_requests, guard_values):
    """guarded_read that splits large reads across batches so no single
    connector response line exceeds the client's readline limit. Returns a
    list of bytes matching read_requests, or None if a guard failed."""
    results = [bytearray() for _ in read_requests]
    for idx, (address, size, domain) in enumerate(read_requests):
        offset = 0
        while offset < size:
            n = min(READ_BATCH_SIZE, size - offset)
            read = await bizhawk.guarded_read(
                ctx.bizhawk_ctx, [(address + offset, n, domain)], guard_values
            )
            if read is None:
                return None
            results[idx].extend(read[0])
            offset += n
    return [bytes(chunk) for chunk in results]

@dataclass(frozen=True)
class VersionData:
    savedata_ptr_offset: int
    champion_flag: int
    recv_item_id_offset: int
    vars_flags_offset_in_save: int
    vars_offset_in_vars_flags: int
    vars_flags_size: int
    flags_offset_in_vars_flags: int
    ap_save_offset: int
    recv_item_count_offset_in_ap_save: int
    once_loc_flags_offset_in_ap_save: int
    once_loc_flags_count: int
    supports_received_items: bool

AP_VERSION_DATA: Mapping[int, VersionData] = {
    0: VersionData(
        savedata_ptr_offset=16,
        
        # Calculated ID for S.S. Ticket (0x10F2 Bit 2)
        # This flag persists forever after the League
        champion_flag=34706, 
        
        recv_item_id_offset=20,
        ap_save_offset=0,
        recv_item_count_offset_in_ap_save=24,
        
        # EVENT FLAGS READING
        # Based on your RA file, flags seem to start around 0x1000
        # We start reading at 0x0 for simplicity so our IDs match (Offset * 8)
        vars_flags_offset_in_save=0, 
        
        # We need to read enough bytes to cover the highest offset in your file
        # Highest seen was 0x25EEC (Pokemon behind player)
        # Reading 0x30000 bytes covers everything safely.
        vars_flags_size=0x30000, 
        
        vars_offset_in_vars_flags=0,
        flags_offset_in_vars_flags=0,
        
        once_loc_flags_offset_in_ap_save=0,
        once_loc_flags_count=0,
        supports_received_items=True,
    ),
}

@dataclass(frozen=True)
class VarsFlags:
    flags: bytes
    vars: bytes
    once_loc_flags: bytes

    def is_checked(self, check: LocationCheck) -> bool:
        if isinstance(check, FlagCheck):
            return self.get_flag(check.id) ^ check.invert
        elif isinstance(check, VarCheck):
            var = self.get_var(check.id)
            if var is not None:
                return check.op(var, check.value)
            else:
                return False
        elif isinstance(check, OnceCheck):
            return self.get_once_flag(check.id) ^ check.invert
        else:
            return False

    def get_once_flag(self, flag_id: int) -> bool:
        if flag_id // 8 < len(self.once_loc_flags):
            return self.once_loc_flags[flag_id // 8] & (1 << (flag_id & 7)) != 0
        else:
            return False

    def get_flag(self, flag_id: int) -> bool:
        if flag_id > 0 and flag_id // 8 < len(self.flags):
            return self.flags[flag_id // 8] & (1 << (flag_id & 7)) != 0
        else:
            return False

    def get_var(self, var_id: int) -> int | None:
        if var_id - 0x4000 < len(self.vars) // 2:
            var_id -= 0x4000
            return int.from_bytes(self.vars[2 * var_id:2 * (var_id + 1)], byteorder='little')

class PokemonHGSSClient(BizHawkClient):
    game = "Pokemon HeartGold and SoulSilver"
    system = "NDS"
    patch_suffix = (".apheartgold", ".apsoulsilver")
    ap_struct_address: int = 0
    savedata_address: int = 0
    has_ap_struct: bool = False
    rom_version: int = 0
    goal_flag: FlagCheck | None
    local_checked_locations: Set[int]
    expected_header: bytes

    def initialize_client(self):
        self.ap_struct_address = 0
        self.savedata_address = 0
        self.has_ap_struct = False
        self.goal_flag = None
        self.local_checked_locations = set()
        self.expected_header = AP_MAGIC * 3 + self.rom_version.to_bytes(length=4, byteorder='little')

    async def validate_rom(self, ctx: "BizHawkClientContext") -> bool:
        from CommonClient import logger

        try:
            # Read ROM Header (0x0 to 0xC)
            rom_name_bytes = (await bizhawk.read(ctx.bizhawk_ctx, [(0, 12, "ROM")]))[0]
            # Clean up null bytes
            rom_name = bytes([byte for byte in rom_name_bytes if byte != 0]).decode("ascii")
            
            # HGSS Game Codes are usually "IPKE" (HG) or "IPGE" (SS)
            # The internal name at offset 0x0 is usually "POKEMON HG" or "POKEMON SS"
            if rom_name.startswith("POKEMON HG") or rom_name.startswith("POKEMON SS"):
                # This is a vanilla ROM, warn user they need the AP patch
                logger.info("ERROR: You are running an unpatched HGSS ROM. Please generate a patched ROM.")
                return False
            
            # Check for our custom Patch Header
            elif rom_name.startswith("HGAP") or rom_name.startswith("SSAP"):
                # Logic to check version number...
                # return True
                pass
            else:
                return False
        except UnicodeDecodeError:
            return False
        except bizhawk.RequestFailedError:
            return False

        ctx.game = self.game
        ctx.items_handling = 0b001
        self.want_slot_data = True
        self.watcher_timeout = 0.125

        self.initialize_client()

        return True

    async def get_savedata_addr(self, ctx: "BizHawkClientContext") -> None:
        pointer_savedata_addr = 0

        try:
            addr = int.from_bytes((await bizhawk.read(ctx.bizhawk_ctx, [(AP_STRUCT_PTR_ADDRESS, 4, "ARM9 System Bus")]))[0], byteorder='little')
            if 0x2000000 < addr and addr < AP_STRUCT_PTR_ADDRESS:
                header = (await bizhawk.read(ctx.bizhawk_ctx, [(addr, 16, "ARM9 System Bus")]))[0]
                if header == self.expected_header:
                    self.ap_struct_address = addr
                    self.has_ap_struct = True
                    print(f"found ap struct at addr {addr:X}")
                    return
                else:
                    pointer_savedata_addr = addr
        except bizhawk.RequestFailedError:
            pass

        if await self.scan_ap_struct(ctx):
            return

        if pointer_savedata_addr != 0:
            self.savedata_address = pointer_savedata_addr
            self.has_ap_struct = False
            print(f"found save data at addr {pointer_savedata_addr:X}")

    async def scan_ap_struct(self, ctx: "BizHawkClientContext") -> bool:
        previous = b""

        for addr in range(AP_STRUCT_SCAN_START, AP_STRUCT_SCAN_END, AP_STRUCT_SCAN_CHUNK_SIZE):
            size = min(AP_STRUCT_SCAN_CHUNK_SIZE, AP_STRUCT_SCAN_END - addr)
            try:
                chunk = (await bizhawk.read(ctx.bizhawk_ctx, [(addr, size, "ARM9 System Bus")]))[0]
            except bizhawk.RequestFailedError:
                previous = b""
                continue

            buffer = previous + chunk
            offset = buffer.find(self.expected_header)
            if offset != -1:
                self.ap_struct_address = addr - len(previous) + offset
                self.has_ap_struct = True
                print(f"found ap struct at addr {self.ap_struct_address:X}")
                return True

            previous = buffer[-(len(self.expected_header) - 1):]

        return False

    async def game_watcher(self, ctx: "BizHawkClientContext") -> None:
        if ctx.server is None or ctx.server.socket.closed or ctx.slot_data is None:
            return

        version_data = AP_VERSION_DATA[self.rom_version]

        if self.ap_struct_address == 0 and self.savedata_address == 0:
            await self.get_savedata_addr(ctx)
            return

        if ctx.slot_data["goal"] == Goal.option_champion:
            self.goal_flag = FlagCheck(id=version_data.champion_flag)

        #if ctx.slot_data["remote_items"] == RemoteItems.option_true and not ctx.items_handling & 0b010: # type: ignore
        #    ctx.items_handling = 0b011
        #    Utils.async_start(ctx.send_msgs([{
        #        "cmd": "ConnectUpdate",
        #        "items_handling": ctx.items_handling
        #    }]))

        try:
            guards: Mapping[str, Tuple[int, bytes, str]] = {}
            guard_values = []

            if self.has_ap_struct:
                ap_struct_guard = (self.ap_struct_address, self.expected_header, "ARM9 System Bus")
                guards["AP STRUCT VALID"] = ap_struct_guard

                actual_header = (await bizhawk.read(ctx.bizhawk_ctx, [(ap_struct_guard[0], 16, "ARM9 System Bus")]))[0]
                if actual_header != self.expected_header:
                    self.ap_struct_address = 0
                    return

                read_result = await bizhawk.guarded_read(
                    ctx.bizhawk_ctx,
                    [
                        (self.ap_struct_address + version_data.savedata_ptr_offset, 4, "ARM9 System Bus"),
                    ],
                    [guards["AP STRUCT VALID"]]
                )

                if read_result is None:
                    return

                guards["SAVEDATA PTR"] = (self.ap_struct_address + version_data.savedata_ptr_offset, read_result[0], "ARM9 System Bus")
                guard_values.append(guards["AP STRUCT VALID"])
            else:
                savedata_ptr_bytes = self.savedata_address.to_bytes(length=4, byteorder='little')
                guards["SAVEDATA PTR"] = (AP_STRUCT_PTR_ADDRESS, savedata_ptr_bytes, "ARM9 System Bus")

            guard_values.append(guards["SAVEDATA PTR"])
            savedata_ptr = int.from_bytes(guards["SAVEDATA PTR"][1], byteorder='little')

            if self.has_ap_struct and version_data.supports_received_items:
                guards["READY TO RECV"] = (self.ap_struct_address + version_data.recv_item_id_offset, b'\xFF\xFF', "ARM9 System Bus")
                read_result = await bizhawk.guarded_read(
                    ctx.bizhawk_ctx,
                    [
                        (self.ap_struct_address + version_data.recv_item_count_offset_in_ap_save, 4, "ARM9 System Bus"),
                        (self.ap_struct_address + version_data.recv_item_id_offset, 2, "ARM9 System Bus"),
                    ],
                    guard_values + [guards["READY TO RECV"]]
                )

                if read_result is None:
                    return

                recv_item_count = int.from_bytes(read_result[0], byteorder='little')
                recv_item_id = int.from_bytes(read_result[1], byteorder='little')
                if recv_item_id == 0xFFFF and recv_item_count < len(ctx.items_received):
                    next_item = ctx.items_received[recv_item_count].item
                    await bizhawk.write(
                        ctx.bizhawk_ctx,
                        [
                            (self.ap_struct_address + version_data.recv_item_id_offset, next_item.to_bytes(length=2, byteorder='little'), "ARM9 System Bus"),
                        ]
                    )

            read_requests = [
                (savedata_ptr + version_data.vars_flags_offset_in_save, version_data.vars_flags_size, "ARM9 System Bus"),
            ]
            if version_data.once_loc_flags_count > 0:
                read_requests.append((savedata_ptr + version_data.ap_save_offset + version_data.once_loc_flags_offset_in_ap_save, version_data.once_loc_flags_count // 8, "ARM9 System Bus"))

            read_result = await guarded_read_chunked(ctx, read_requests, guard_values)
            if read_result is None:
                return
            vars_flags_bytes = read_result[0]
            if version_data.vars_offset_in_vars_flags == version_data.flags_offset_in_vars_flags:
                vars_bytes = vars_flags_bytes
                flags_bytes = vars_flags_bytes
            else:
                vars_bytes = vars_flags_bytes[version_data.vars_offset_in_vars_flags:version_data.flags_offset_in_vars_flags]
                flags_bytes = vars_flags_bytes[version_data.flags_offset_in_vars_flags:]

            once_loc_flags = read_result[1] if version_data.once_loc_flags_count > 0 else b""
            vars_flags = VarsFlags(flags=flags_bytes, vars=vars_bytes, once_loc_flags=once_loc_flags)

            local_checked_locations = set()
            game_clear = vars_flags.is_checked(self.goal_flag) # type: ignore

            for k, loc in map(lambda k : (k, locations[raw_id_to_const_name[k]]), ctx.missing_locations):
                if vars_flags.is_checked(loc.check):
                    local_checked_locations.add(k)

            if local_checked_locations != self.local_checked_locations:
                await ctx.check_locations(local_checked_locations)

                self.local_checked_locations = local_checked_locations

            if not ctx.finished_game and game_clear:
                ctx.finished_game = True
                await ctx.send_msgs([{
                    "cmd": "StatusUpdate",
                    "status": ClientStatus.CLIENT_GOAL,
                }])
        except bizhawk.RequestFailedError:
            pass
