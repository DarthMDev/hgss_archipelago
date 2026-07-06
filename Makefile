
.PHONY: data_gen check_apnds check_patches

Q ?= @
PYTHON ?= python3

ROMS := us_hg us_ss
SOURCES := __init__.py \
	 client.py \
	 items.py \
	 locations.py \
	 options.py \
	 regions.py \
	 rom.py \
	 rules.py \
	 LICENSE \
	 archipelago.json
DOCS := docs/setup_en.md \
	docs/en_Pokemon\ HeartGold_SoulSilver.md
DATA := data_gen/encounters.toml \
	data_gen/items.toml \
	data_gen/locations.toml \
	data_gen/regions.toml \
	data_gen/rom_interface.toml \
	data_gen/rules.toml \
	data_gen/species.toml \
	data_gen_templates/__init__.py \
	data_gen_templates/charmap.py \
	data_gen_templates/encounters.py \
	data_gen_templates/items.py \
	data_gen_templates/locations.py \
	data_gen_templates/regions.py \
	data_gen_templates/rules.py \
	data_gen_templates/species.py \
	data_gen.py \
	data_gen_rules.py
DATA_GEN_OUT := data/__init__.py \
	data/charmap.py \
	data/encounters.py \
	data/items.py \
	data/locations.py \
	data/regions.py \
	data/rules.py \
	data/species.py

PATCHES := $(ROMS:%=patches/base_patch_%.bsdiff4)
APNDS_SRC := apnds/apnds
POKEHEARTGOLD_DIR ?= ../pokeheartgold
HG_SOURCE ?= roms/us_hg.nds
SS_SOURCE ?= roms/us_ss.nds
HG_TARGET ?= $(POKEHEARTGOLD_DIR)/build/heartgold.us/pokeheartgold.us.nds
SS_TARGET ?= $(POKEHEARTGOLD_DIR)/build/soulsilver.us/pokesoulsilver.us.nds

default: pokemon_hgss.apworld

patches/base_patch_us_hg.bsdiff4: $(HG_SOURCE) $(HG_TARGET) check_apnds
	@echo DIFF $<
	$Q$(PYTHON) patch_gen.py heartgold $(HG_SOURCE) $(HG_TARGET) $@

patches/base_patch_us_ss.bsdiff4: $(SS_SOURCE) $(SS_TARGET) check_apnds
	@echo DIFF $<
	$Q$(PYTHON) patch_gen.py soulsilver $(SS_SOURCE) $(SS_TARGET) $@

data_gen: $(DATA)
	@echo DATA GEN
	$Q$(PYTHON) data_gen.py

check_patches: $(PATCHES)
	@echo CHECK PATCHES
	$Qfor patch in $(PATCHES); do \
		test -s "$$patch" || { echo "empty patch asset: $$patch"; exit 1; }; \
	done

check_apnds:
	@echo CHECK APNDS
	$Qtest -f "$(APNDS_SRC)/rom.py" || { echo "missing apnds dependency: clone/extract apnds so $(APNDS_SRC)/rom.py exists"; exit 1; }

pokemon_hgss.apworld: data_gen $(SOURCES) $(PATCHES) check_patches check_apnds
	@echo MAKE APWORLD
	$Qrm -f $@
	$Qmkdir -p pokemon_hgss/docs pokemon_hgss/data pokemon_hgss/patches
	$Qcp -R $(APNDS_SRC) pokemon_hgss/apnds
	$Qcp $(DATA_GEN_OUT) pokemon_hgss/data
	$Qcp $(DOCS) pokemon_hgss/docs
	$Qcp $(PATCHES) pokemon_hgss/patches
	$Qcp $(SOURCES) pokemon_hgss/
	$Qfind pokemon_hgss -type d -name __pycache__ -prune -exec rm -r {} +
	$Qfind pokemon_hgss -name '*.pyc' -delete
	$Qfind pokemon_hgss -name .DS_Store -delete
	$Qzip -r $@ pokemon_hgss
	$Qrm -r pokemon_hgss
