# Pokémon HeartGold and SoulSilver Archipelago (AP)

The setup guide is [here](docs/setup_en.md).

## Running From Source

The following are required.

- Additionally to what Archipelago requires, the `pyparsing` library is required.
  This can be installed via PIP.

With these, clone this repository in the `worlds` directory of the Archipelago repository.
With every modification to the files in `data_gen` or `data_gen_templates`, and when first cloning the
repository, the `data_gen.py` file must be executed. (Do `python data_gen.py` in the root directory of the repository)

The latest release of [apnds](https://github.com/ljtpetersen/apnds), extracted to the root of the repository.

To make the `.apworld` file, run `make` within the root directory of the repository.

## DeSmuME Connector (experimental)

`connector_desmume_generic.lua` lets macOS/Linux users connect through DeSmuME instead of BizHawk.
It implements the same TCP/JSON protocol as Archipelago's `connector_bizhawk_generic.lua`, so the
existing BizHawk Client works unchanged. See the DeSmuME section of the
[setup guide](docs/setup_en.md) for usage.

**Warning:** this requires a DeSmuME build with the experimental macOS Lua support enabled, which is
**not** in the stock release. Use [DarthMDev/desmume](https://github.com/DarthMDev/desmume), and note
you must build the **debug/dev build** yourself — you need to know how to compile DeSmuME on macOS
(Xcode) to get that Lua support. It also needs LuaSocket for Lua 5.1 (`luarocks --lua-version=5.1
install luasocket`).

## Where Help is Needed

- Better documentation! (`docs/setup_en.md` and `en_Pokemon HeartGold_SoulSilver.md`)
- Better location labels. In [`data_gen/locations.toml`](data_gen/locations.toml), for each location, simply modify the `label` field.
  No other changes necessary.
- Correct logic. There are probably some places with incorrect logic. If you find any of these, open up an issue, and I'll get to fixing it promptly.
- Correct item classifications. 
- Verify we have everything in locations
- encounters info 
- Rom patching
- make sure we have everything in rules
- more options for events

## What is Missing

- Encounter randomization and level scaling.
- More victory conditions (including rules)
- Trainersanity.
- Dexsanity.
- Various QOL things.

## Credit for the base(Platinum)

- Thanks to [ljtpetersen](https://github.com/ljtpetersen) for being the creator of pokemon platinum archipelago
- Thanks to [Linneus](https://github.com/Linneus) for map changes and help with scripts/events/rules,
  as well as for creating item icons.
- Thanks to [gerbiljames](https://github.com/gerbiljames) for help with structuring the client and world.
- Thanks to [ZobeePlays](https://github.com/ZobeePlays) and [Useless](https://github.com/UselessWater3) for location names.

## Credit
