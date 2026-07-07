# options.py
#
# Copyright (C) 2025 James Petersen <m@jamespetersen.ca>
# Licensed under MIT. See LICENSE

from dataclasses import dataclass
from typing import Any
from schema import And, Optional, Or, Schema
from Options import Choice, Toggle, DefaultOnToggle, OptionDict, OptionError, OptionSet, PerGameCommonOptions, Range, OptionGroup

class GameVersion(Choice):
    """Select HeartGold or SoulSilver version"""
    display_name = "Game Version"
    option_heartgold = 0
    option_soulsilver = 1
    default = "random"

class Goal(Choice):
    """
    The goal of the randomizer.
    
    champion: defeat the Elite Four and Champion Lance
    """
    # champion_rematch: defeat the Elite Four and Chapion Lance a second time
    # red: climb Mt. Silver and defeat Trainer Red
    display_name = "Goal"
    option_champion = 0
    # option_champion_rematch = 1
    # option_red = 2
    default = 0

class StartMode(Choice):
    """
    The starting mode.
    
    vanilla: start in New Bark Town with Route 30 blocked until you give the Mystery Egg to Professor Elm
    """
    # skip_tutorial: start in New Bark Town with Route 30 already open
    display_name = "Start Mode"
    option_vanilla = 0
    # option_skip_tutorial = 1
    # option_random_start = 2
    default = 0

class ReusableTMs(Toggle):
    """Makes TMs reusable, this also means pokemon can't hold TMs."""
    display_name = "Reusable TMs"

class AlwaysCatch(Toggle):
    """Have a 100% chance of catching any catchable encounter."""
    display_name = "Always Catch"

class ExpMultiplier(Range):
    """
    Set an experience multiplier for all gained experience.

    If you set this to 0 you will still recieve 1 exp per opponent defeated.
    """
    display_name = "Exp. Multiplier"
    range_start = 0
    range_end = 255
    default = 1

class RandomizeHMs(DefaultOnToggle):
    """Adds the HMs to the pool."""
    display_name = "Randomize HMs"

class RandomizeBadges(DefaultOnToggle):
    """Adds the badges to the pool."""
    display_name = "Randomize Badges"

class RandomizeOverworlds(DefaultOnToggle):
    """Adds overworld items to the pool."""
    display_name = "Randomize Overworld Items"

class RandomizeHiddens(Toggle):
    """Adds hidden items to the pool."""
    display_name = "Randomize Hidden Items"

class RandomizeNPCs(DefaultOnToggle):
    """Adds NPC gifts to the pool."""
    display_name = "Randomize NPC Gifts"

class RandomizeApricorns(Toggle):
    """Adds apricorn trees to the pool."""
    display_name = "Randomize Apricorn Trees"

class RandomizeKeyItems(Choice):
    """Adds key items to the pool."""
    display_name = "Randomize Key Items"
    option_vanilla = 0
    option_most = 1
    option_all = 2
    default = 1

    def are_most_randomized(self) -> bool:
        return self.value >= self.option_most

class RandomizeRods(DefaultOnToggle):
    """Adds the fishing rods to the pool."""
    display_name = "Randomize Rods"

class RandomizeRunningShoes(Toggle):
    """Adds the running shoes to the pool."""
    display_name = "Randomize Running Shoes"

class RandomizeBicycle(Toggle):
    """Adds the bicycle to the pool."""
    display_name = "Randomize Bicycle"

class RandomizePokedex(Toggle):
    """Add the Pokedex to the pool. Note: this also adds the national dex to the pool."""
    display_name = "Randomize Pokedex"

class RandomizePokegearCards(Toggle):
    """Adds the Pokégear Map card and Radio cards to the pool."""
    display_name = "Randomize Pokegear Cards"

class RandomizePass(Toggle):
    """
    Add the Pass to the item pool.
    The Pass can be used to travel between Goldenrod City (Johto) and Saffron City (Kanto).
    """
    display_name = "Randomize Pass"

class RandomizeSSTicket(Toggle):
    """
    Add the S.S. Ticket to the item pool.
    The S.S. Ticket can be used to travel between Olivine City (Johto) and Vermilion City (Kanto).
    """
    display_name = "Randomize S.S. Ticket"

class VisibilityHMLogic(DefaultOnToggle):
    """Logically require Flash for traversing and finding locations in applicable regions."""
    display_name = "Logically Require Flash for Applicable Regions"

class DowsingMachineLogic(DefaultOnToggle):
    """Logically require the Dowsing Machine to find hidden items."""
    display_name = "Logically Require Dowsing Machine for Hidden Items"

class FPS60(Toggle):
    """Whether the 60 FPS patch should be applied."""
    display_name = "60 FPS"

class InstantText(Toggle):
    """Whether to apply near-instant text speed."""
    display_name = "Instant Text Speed"

class FastHBSpeed(Toggle):
    """Whether to apply fast Health and Exp bars."""
    display_name = "Fast Healthbar"

class HMCutIns(DefaultOnToggle):
    """Whether HM Cut-Ins should be played."""
    display_name = "HM Cut-Ins"

class RemoteItems(Toggle):
    """
    Whether local items should be given in-game, or sent by the server.
    This overrides the show randomized progression items option: all items are shown.
    It is highly recommended to use nothing for received items notification, otherwise
    you will be notified twice for each item.
    """
    display_name = "Remote Items"

class ShowUnrandomizedProgressionItems(Toggle):
    """
    Whether unrandomized progression items should be sent to the server and
    displayed in the chat. This also means that trackers will consider it a location
    to be checked. If this is off, some trackers may assume that it is obtained when
    accessible.
    """
    display_name = "Show Unrandomized Progression Items"

#class HmBadgeRequirements(DefaultOnToggle):
#    """Require the corresponding badge to use an HM outside of battle."""
#    display_name = "Require Badges for HMs"

#class RemoveBadgeRequirement(OptionSet):
#    """
#    Specify which HMs do not require a badge to use outside of battle. This overrides the HM Badge Requirements setting.
#
#    HMs should be provided in the form: "FLY", "WATERFALL", "ROCK_SMASH", etc.
#    """
#    display_name = "Remove Badge Requirement"
#    valid_keys = ["CUT", "FLY", "SURF", "STRENGTH", "WHIRLPOOL" "ROCK_SMASH", "WATERFALL", "ROCK_CLIMB"]

#class AddMasterRepel(Toggle):
#    """
#    Add a master repel item to the item pool. The master repel is a key item.
#    It is a repel that blocks all encounters, and never runs out.
#    """
#    display_name = "Add Master Repel"

#class BlindTrainers(Toggle):
#    """Set whether trainers will be blind."""
#    display_name = "Blind Trainers"

class GameOptions(OptionDict):
    """
    Presets in-game options.

    Allowed options and values, with default first:

    text_speed: mid/slow/fast - Sets the text speed
    sound: stereo/mono - Sets the sound mode
    battle_scene: on/off - Sets whether the battle animations are shown
    battle_style: shift/set - Sets whether pokemon can be changed when the opponent's pokemon faints
    button_mode: normal/start=x/l=a - Sets the button mode
    text_frame: 1-20 - Sets the textbox frame. "random" will pick a random frame.
    received_items_notification: jingle/nothing/message - Sets the received_items_notification.
    default_player_name: player_name/custom/random/vanilla - Sets the default player name. with player_name, tries to use the AP player name.
    default_rival_name: random/custom/player_name/vanilla - Sets the default rival name. with random, picks from one of the players in the AP.
    name_strictness: relaxed/strict - How strict setting the default player/rival name is.
    default_gender: vanilla/male/female/random - Sets the default gender.

    The text_speed, sound, battle_scene, battle_style, button_mode, text_frame, and received_items_notification
    options can additionally be modified in the in-game options menu.
    """
    display_name = "Game Options"
    default = {
        "text_speed": "mid",
        "sound": "stereo",
        "battle_scene": "on",
        "battle_style": "shift",
        "button_mode": "normal",
        "text_frame": 1,
        "received_items_notification": "jingle",
        "default_player_name": "player_name",
        "default_rival_name": "random",
        "name_strictness": "relaxed",
        "default_gender": "vanilla",
    }
    schema = Schema({
        Optional("text_speed"): Or("mid", "slow", "fast"),
        Optional("sound"): Or("stereo", "mono"),
        Optional("battle_scene"): Or("on", "off"),
        Optional("battle_style"): Or("shift", "set"),
        Optional("button_mode"): Or("normal", "start=x", "l=a"),
        Optional("text_frame"): Or("random", And(int, lambda value: 1 <= value <= 20)),
        Optional("received_items_notification"): Or("jingle", "nothing", "message"),
        Optional("default_player_name"): str,
        Optional("default_rival_name"): str,
        Optional("name_strictness"): Or("relaxed", "strict"),
        Optional("default_gender"): Or("vanilla", "male", "female", "random"),
    })

    def __getattr__(self, name: str) -> Any:
        if name in GameOptions.default:
            return self.value.get(name, GameOptions.default[name])
        else:
            raise AttributeError(name, self)

#class NationalDexNumMons(Range):
#    """
#    Number of seen regional Pokémon required to complete the Regional
#    Pokédex. (This is when you can receive the National Dex from Oak)
#    """
#    display_name = "National Dex Num Mons"
#    range_start = 1
#    # range end will be expanded as more encounters are added.
#    range_end = 80
#    default = 6060

#class AddBag(Toggle):
#    """
#    Add the bag to the item pool. Before obtaining it, the bag cannot be opened in the menu.
#    """
#    display_name = "Add Bag"

@dataclass
class PokemonHGSSOptions(PerGameCommonOptions):
    version: GameVersion
    goal: Goal
    start_mode: StartMode
    reusable_tms: ReusableTMs
    always_catch: AlwaysCatch
    exp_multiplier: ExpMultiplier
    remote_items: RemoteItems
    show_unrandomized_progression_items: ShowUnrandomizedProgressionItems
    game_options: GameOptions

    hms: RandomizeHMs
    badges: RandomizeBadges
    overworlds: RandomizeOverworlds
    hiddens: RandomizeHiddens
    npc_gifts: RandomizeNPCs
    apricorn_trees: RandomizeApricorns
    key_items: RandomizeKeyItems
    rods: RandomizeRods
    running_shoes: RandomizeRunningShoes
    bicycle: RandomizeBicycle
    pokedex: RandomizePokedex
    pokegear_cards: RandomizePokegearCards
    train_pass: RandomizePass
    ss_ticket: RandomizeSSTicket

    visibility_hm_logic: VisibilityHMLogic
    dowsing_machine_logic: DowsingMachineLogic

    fps60: FPS60
    instant_text: InstantText
    fast_hb_speed: FastHBSpeed
    hm_cut_ins: HMCutIns

#    hm_badge_requirement: HmBadgeRequirements
#    remove_badge_requirements: RemoveBadgeRequirement
#    blind_trainers: BlindTrainers
#    regional_dex_goal: NationalDexNumMons
#    master_repel: AddMasterRepel
#    bag: AddBag

    # def requires_badge(self, hm: str) -> bool:
    #     return self.hm_badge_requirement.value == 1 or hm in self.remove_badge_requirements

    def validate(self) -> None:
        if not (self.overworlds or self.hiddens or self.npc_gifts or self.key_items.value > 0):
            raise OptionError(f"at least one of overworlds, hiddens, npc_gifts, or key_items must be enabled")
        # if self.bag and self.dowsing_machine_logic and not (self.overworlds or self.npc_gifts or self.rods or self.running_shoes or self.pokedex or self.key_items.value > 0):
        #     raise OptionError(f"if the bag is enabled, then at least one of overworlds, npc_gifts, rods, running_shoes, pokedex, or key_items must be enabled")

OPTION_GROUPS = [
#	OptionGroup(
#		"Gameplay Options",
#		[GameVersion, Goal, StartMode, ReusableTMs, AlwaysCatch, ExpMultiplier],
#	),
	OptionGroup(
		"Location/Item Randomization Options",
		[RandomizeHMs, RandomizeBadges, RandomizeOverworlds, RandomizeHiddens, RandomizeNPCs, RandomizeApricorns, RandomizeKeyItems, RandomizeRods, RandomizeRunningShoes, RandomizeBicycle, RandomizePokedex, RandomizePokegearCards, RandomizePass, RandomizeSSTicket],
	),
	OptionGroup(
		"Logic Options",
		[VisibilityHMLogic, DowsingMachineLogic],
	),
	OptionGroup(
		"Speed Up Options",
		[FPS60, InstantText, FastHBSpeed, HMCutIns],
	),
	OptionGroup(
		"Notification Options",
		[RemoteItems, ShowUnrandomizedProgressionItems],
	),
	OptionGroup(
		"Game Options",
		[GameOptions],
	),
]
