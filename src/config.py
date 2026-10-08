"""EVE - Game Configuration Constants"""

# Display
SCREEN_WIDTH = 0   # Set at runtime from display info
SCREEN_HEIGHT = 0  # Set at runtime from display info
FULLSCREEN = True
FPS = 60
TITLE = "EVE - Empire vs Empire"

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
DARK_GRAY = (64, 64, 64)
LIGHT_GRAY = (192, 192, 192)
RED = (220, 50, 50)
GREEN = (50, 200, 50)
BLUE = (50, 100, 220)
GOLD = (255, 215, 0)
DARK_RED = (139, 0, 0)
DARK_GREEN = (0, 100, 0)
DARK_BLUE = (0, 0, 139)

# Class colors
ENFORCER_COLOR = (70, 130, 180)   # Steel blue
SNIPER_COLOR = (34, 139, 34)     # Forest green
ASSASSIN_COLOR = (148, 0, 211)   # Purple
DEMO_COLOR = (255, 69, 0)        # Red-orange

# Rarity colors (frame colors for member cards)
RARITY_COLORS = {
    "common": WHITE,
    "uncommon": (50, 205, 50),    # Lime green
    "rare": (65, 105, 225),       # Royal blue
    "super_rare": GOLD,
}

# Rarity stat multipliers
RARITY_MULTIPLIERS = {
    "common": 1.0,
    "uncommon": 1.2,
    "rare": 1.5,
    "super_rare": 2.0,
}

# --- Enemy member rarity by city GDP-per-capita ----------------------------
# Richer territories field better-equipped (higher-rarity) gangs. Each enemy
# member rolls its rarity independently from the bracket its city's per-capita
# income falls into. A bracket is (upper_bound_usd, [common, uncommon, rare,
# super_rare] weights) and the first bracket whose upper bound exceeds the
# income wins; the final bracket (upper bound = infinity) catches the top.
# Weights are relative (need not sum to 100) and are fed straight to
# random.choices. Anchored at [95,5,0,0] for the lowest bracket and [0,0,0,100]
# for the highest; the middle brackets sweep the mass through uncommon then rare
# (smooth hump handoff). See docs/building_progression.md sibling analysis.
#
# Data note: ~95% of real cities fall at or below $120k/capita, so most gangs
# roll from the first five brackets (mostly common/uncommon). The $1M+ brackets
# are low-population data artifacts (county unincorporated-remainder slices).
RARITY_INCOME_BRACKETS = [
    #  upper $      common uncommon rare super_rare
    (   20_000, [95,  5,  0,   0]),
    (   40_000, [65, 33,  2,   0]),
    (   60_000, [56, 40,  4,   0]),
    (   80_000, [47, 47,  6,   0]),
    (  100_000, [37, 53, 10,   0]),
    (  120_000, [29, 56, 14,   1]),
    (  140_000, [21, 57, 21,   1]),
    (  160_000, [14, 56, 28,   2]),
    (  180_000, [ 9, 51, 36,   4]),
    (  200_000, [ 6, 44, 44,   6]),
    (  250_000, [ 4, 36, 51,   9]),
    (  300_000, [ 2, 28, 56,  14]),
    (  400_000, [ 1, 21, 57,  21]),
    (  500_000, [ 1, 14, 56,  29]),
    (  750_000, [ 0, 10, 53,  37]),
    (1_000_000, [ 0,  6, 47,  47]),
    (5_000_000, [ 0,  4, 40,  56]),
    (10_000_000,[ 0,  2, 33,  65]),
    (float("inf"), [0, 0, 0, 100]),
]

# --- Class skills (rarity-keyed) -------------------------------------------
# Sniper: chance for a shot vs a member to CRIT (deal SNIPER_CRIT_MULT x damage).
SNIPER_CRIT_CHANCE = {
    "common": 0.05,
    "uncommon": 0.10,
    "rare": 0.15,
    "super_rare": 0.20,
}
SNIPER_CRIT_MULT = 1.5

# Assassin: chance to DECAPITATE (instakill) a member already below
# ASSASSIN_DECAP_HP_THRESHOLD of max HP; otherwise a normal hit.
ASSASSIN_DECAP_CHANCE = {
    "common": 0.10,
    "uncommon": 0.20,
    "rare": 0.30,
    "super_rare": 0.40,
}
ASSASSIN_DECAP_HP_THRESHOLD = 0.20   # target must be under 20% HP to be executable

# Battle
BATTLE_DURATION = 300  # 5 minutes in seconds

# Grid
GRID_ROWS = 3
GRID_COLS = 3

# Member base stats (per level 1 common)
BASE_STATS = {
    "enforcer": {
        "hp": 150,
        "damage_player": 12,
        "damage_building": 5,
        "mitigation": 0.3,   # 30% damage reduction
        "speed": 1.0,        # Movement speed multiplier
        "attack_interval": 2.0,  # Seconds between attacks
    },
    "sniper": {
        "hp": 80,
        "damage_player": 20,     # (swapped with assassin) heavy per-shot vs members
        "damage_building": 6,    # (swapped with assassin)
        "mitigation": 0.1,
        "speed": 0.8,
        "attack_interval": 2.5,  # Slow but ranged
    },
    "assassin": {
        "hp": 90,
        "damage_player": 15,     # (swapped with sniper) lighter per-shot, but fast + can execute
        "damage_building": 8,    # (swapped with sniper)
        "mitigation": 0.1,
        "speed": 1.5,
        "attack_interval": 1.0,  # Fast flurry
    },
    "demolitionist": {
        "hp": 100,
        "damage_player": 8,
        "damage_building": 25,
        "mitigation": 0.2,
        "speed": 0.9,
        "attack_interval": 1.8,  # Moderate, steady building damage
    },
}

# Building
BUILDING_BASE_HP = 500
BUILDING_DEFENDER_SLOTS = 3  # Max defenders per building

# --- Building Upgrade System ---------------------------------------------
# Every building starts as a Warehouse. A Warehouse can be upgraded (with
# money) into one of the tier-1 specialist buildings. A Safehouse can then be
# further upgraded into a Bunker.
#
# Chain:
#   warehouse -> headquarters | armory | hospital | safehouse
#              | sniper_tower | research_lab | nuclear_silo
#   safehouse -> bunker
#
# Each entry:
#   display_name : human-readable label
#   hp           : max HP for this building type (warehouse keeps BUILDING_BASE_HP)
#   upgrade_cost : money cost to upgrade INTO this type (0 for the base warehouse)
#   upgrades_from: the type that can be upgraded into this one (None for base)
#   max_count    : max number of this type allowed per empire (None = unlimited)
#   name_index   : index used by renderer/building_order sprite mapping
#   max_level    : highest level this type can reach (Warehouse=1, Safehouse=3, rest=4)
#   levels       : per-level ladder, levels[n-1] describes level n. Each entry:
#                    hp   : max HP at that level
#                    cost : money to level FROM the previous level INTO this one
#                           (level 1 "cost" is the upgrade-into cost from the
#                           source type; for the base warehouse it is 0)
#                  Plus optional per-type skill fields that scale with level:
#                    bonus_packs (hospital)  : extra health packs granted on battle start
#                    charge_time (nuclear silo): seconds to charge the nuke 0->100%
#
# Level 1 of every type mirrors the flat "hp"/"upgrade_cost" values, so existing
# saves (and any code reading the flat fields) behave identically.
BUILDING_TYPES = {
    "warehouse": {
        "display_name": "Warehouse", "hp": BUILDING_BASE_HP, "upgrade_cost": 0,
        "upgrades_from": None, "max_count": None, "name_index": 3, "max_level": 1,
        "levels": [
            {"hp": BUILDING_BASE_HP, "cost": 0},
        ],
    },
    "safehouse": {
        "display_name": "Safehouse", "hp": 650, "upgrade_cost": 14000,
        "upgrades_from": "warehouse", "max_count": 2, "name_index": 8, "max_level": 3,
        "levels": [
            {"hp": 650,  "cost": 14000},
            {"hp": 850,  "cost": 316000},
            {"hp": 1100, "cost": 562000},
        ],
    },
    "armory": {
        "display_name": "Armory", "hp": 750, "upgrade_cost": 31000,
        "upgrades_from": "warehouse", "max_count": 1, "name_index": 1, "max_level": 4,
        "levels": [
            {"hp": 750,  "cost": 31000},
            {"hp": 950,  "cost": 133000},
            {"hp": 1200, "cost": 1519000},
            {"hp": 1500, "cost": 13000000},
        ],
    },
    "hospital": {
        "display_name": "Hospital", "hp": 750, "upgrade_cost": 46000,
        "upgrades_from": "warehouse", "max_count": 1, "name_index": 2, "max_level": 4,
        "levels": [
            {"hp": 750,  "cost": 46000,    "bonus_packs": 0},
            {"hp": 950,  "cost": 177000,   "bonus_packs": 2},
            {"hp": 1200, "cost": 1873000,  "bonus_packs": 4},
            {"hp": 1500, "cost": 14000000, "bonus_packs": 6},
        ],
    },
    "research_lab": {
        "display_name": "Research Lab", "hp": 800, "upgrade_cost": 1232000,
        "upgrades_from": "warehouse", "max_count": 1, "name_index": 7, "max_level": 4,
        "levels": [
            {"hp": 800,  "cost": 1232000},
            {"hp": 1000, "cost": 2848000},
            {"hp": 1300, "cost": 3511000},
            {"hp": 1600, "cost": 16000000},
        ],
    },
    "sniper_tower": {
        "display_name": "Sniper Tower", "hp": 850, "upgrade_cost": 68000,
        "upgrades_from": "warehouse", "max_count": 1, "name_index": 6, "max_level": 4,
        "levels": [
            {"hp": 850,  "cost": 68000},
            {"hp": 1050, "cost": 237000},
            {"hp": 1350, "cost": 2310000},
            {"hp": 1700, "cost": 15000000},
        ],
    },
    "nuclear_silo": {
        "display_name": "Nuclear Silo", "hp": 950, "upgrade_cost": 11000000,
        "upgrades_from": "warehouse", "max_count": 1, "name_index": 5, "max_level": 4,
        "levels": [
            {"hp": 950,  "cost": 11000000, "charge_time": BATTLE_DURATION * 1.00},
            {"hp": 1200, "cost": 17000000, "charge_time": BATTLE_DURATION * 0.85},
            {"hp": 1500, "cost": 18000000, "charge_time": BATTLE_DURATION * 0.70},
            {"hp": 1900, "cost": 21000000, "charge_time": BATTLE_DURATION * 0.55},
        ],
    },
    "headquarters": {
        "display_name": "Headquarters", "hp": 1300, "upgrade_cost": 10000,
        "upgrades_from": "warehouse", "max_count": 1, "name_index": 0, "max_level": 4,
        "levels": [
            {"hp": 1300, "cost": 10000},
            {"hp": 1700, "cost": 100000},
            {"hp": 2200, "cost": 1000000},
            {"hp": 3000, "cost": 10000000},
        ],
    },
    "bunker": {
        "display_name": "Bunker", "hp": 1300, "upgrade_cost": 4328000,
        "upgrades_from": "safehouse", "max_count": 2, "name_index": 4, "max_level": 4,
        "levels": [
            {"hp": 1300, "cost": 4328000},
            {"hp": 1700, "cost": 6579000},
            {"hp": 2200, "cost": 19000000},
            {"hp": 3000, "cost": 22000000},
        ],
    },
}

# A Safehouse must reach this level before it can be upgraded into a Bunker.
SAFEHOUSE_BUNKER_MIN_LEVEL = 3

# Starting money for a brand-new player (fresh profile only; saved balance
# takes over once a profile exists). New players earn money by winning wars.
STARTING_MONEY = 0

# --- HQ leveling / member cap ----------------------------------------------
# Roster size is gated by the HQ. No HQ => BASE_MEMBER_CAP. Each HQ level adds
# HQ_MEMBERS_PER_LEVEL, up to HQ_MAX_LEVEL (Lv4 => 40 + 4*10 = 80).
BASE_MEMBER_CAP = 40
HQ_MEMBERS_PER_LEVEL = 10
HQ_MAX_LEVEL = 4
# Building slot (0-indexed) a newly-activated backup member lands in. Building 3
# (index 2) is the safe backline where non-enforcers default; the player can
# then reassign from there. Keeps activation from reshuffling other members.
DEFAULT_ACTIVATE_SLOT = 2
# Bench/backup force: recruits won from defeated empires wait here until you
# move them into the active roster. Capped independently of the HQ roster cap.
BACKUP_FORCE_CAP = 80
# HQ HP per level (Lv1 matches BUILDING_TYPES["headquarters"]["hp"]).
HQ_LEVEL_HP = {1: 1300, 2: 1700, 3: 2200, 4: 3000}
# Money cost to level the HQ FROM level n-1 TO level n (steeply escalating).
# Building an HQ (Warehouse -> HQ) costs BUILDING_TYPES cost ($10k) and yields
# Lv1. Level-up costs follow the x10-per-level anchor curve (L2 100k, L3 1M,
# L4 10M), matching headquarters' per-level ladder in BUILDING_TYPES.
HQ_LEVEL_UP_COST = {2: 100000, 3: 1000000, 4: 10000000}

# --- Police raid boss -------------------------------------------------------------------
# Once a city is conquered you can repeatedly "Challenge Police" — a much harder
# fight built from the city's police_power. A win pays this multiple of the
# standard war reward (30% of the police empire's net worth, i.e. 100 x sum of
# member levels). The police boss is a maxed level-40 roster, so this is already
# a large, difficulty-appropriate payout; the multiplier is the tuning knob for
# how premium the elite fight should feel. The city is never marked conquered by
# this and there is no loss penalty.
POLICE_REWARD_MULT = 1.0

# --- Visual US map: adjacency-based state unlocking ------------------------
# A state on the visual US map is challengeable if it is your home state, or if
# any state bordering it has been conquered to at least this fraction of its
# cities. Intended live value is 0.50 (own half a neighbour to spill over);
# set low (0.01) for testing so a single conquest unlocks neighbours.
STATE_UNLOCK_THRESHOLD = 0.01   # TEST value; intended production value = 0.50

# Health Packs
HEALTH_PACKS_START = 8  # Starting health packs per battle

# AI
AI_ORDER_INTERVAL = 6.0      # Seconds between AI attack waves
AI_FIRST_ORDER_DELAY = 5.0   # Seconds before AI issues first order

# AI target scoring: the AI focuses the highest-VALUE building it can currently
# reach. A building's score = its type value + the sum of its live defenders'
# values. Only buildings the AI can see/reach are ever scored. Tune here.
AI_TARGET_SCORE_DEFENDER = 2          # a live non-enforcer defender
AI_TARGET_SCORE_ENFORCER = 1          # a live enforcer defender
AI_TARGET_SCORE_BUILDING = {          # by building type (fallback = _DEFAULT)
    "armory": 20,
    "hospital": 10,
}
AI_TARGET_SCORE_BUILDING_DEFAULT = 5  # HQ, safehouse, bunker, sniper tower, lab, silo, warehouse

# AI targeting PERSONALITIES (profiles). Each enemy is assigned one profile
# deterministically from a seed (city id + side), so a city's gang and its
# police boss can fight differently but always the same way on replay. A
# profile only changes HOW a reachable building is scored; the wave/phase logic
# is shared. See ai_profiles.py. Tunables per profile live here.
#
# "value" is the baseline (reproduces AI_TARGET_SCORE_* above). The path-taker
# profiles score by how contested a building is (defender count, weighted by
# ENFORCER weight so tanks count differently); the destroyer profiles heap a
# large bonus on one building type and otherwise fall back to the value model.
AI_PROFILE_DEFAULT = "value"          # used when no profile is specified
AI_PROFILE_POLICE = "hard_path"       # the police raid boss always dives the toughest
# Pool the deterministic seed picker draws a GANG profile from (police is fixed
# to AI_PROFILE_POLICE). Weighted by repetition — duplicate a name to make it
# more common.
AI_PROFILE_GANG_POOL = [
    "value", "value",
    "easy_path",
    "hard_path",
    "hospital_destroyer",
    "armory_destroyer",
    "random_path",
]
# Per-profile knobs.
AI_PROFILE_PARAMS = {
    # Beeline a building TYPE: this bonus is added when the building matches,
    # on top of the shared "value" base score, so once the target type is gone
    # the profile degrades gracefully to value-based targeting.
    "hospital_destroyer": {"target_type": "hospital", "bonus": 1000},
    "armory_destroyer": {"target_type": "armory", "bonus": 1000},
    # Path takers score purely by contested-ness: weighted live-defender count
    # (+ small building-type value tiebreak). hard_path maximizes it, easy_path
    # minimizes it (negated).
    "hard_path": {"sign": 1},
    "easy_path": {"sign": -1},
}

# Movement (pixels per second on the battlefield)
MEMBER_MOVE_SPEED = 48

# Combat
ATTACK_RANGE = 50      # Pixels - melee range
SNIPER_RANGE = 200     # Pixels - sniper can shoot from further
DEMO_RANGE = 200       # Pixels - demo shoots at buildings from range

# Projectiles
PROJECTILE_SPEED_SNIPER = 400   # Pixels per second
PROJECTILE_SPEED_DEMO = 250     # Pixels per second (slower, heavier)
PROJECTILE_SPEED_ENFORCER = 350 # Pixels per second
PROJECTILE_SPEED_ASSASSIN = 450 # Pixels per second (fast)

# Ammo
AMMO_MAX = 10          # Starting/max ammo per member
AMMO_REGEN_INTERVAL = 10.0  # Seconds per ammo regen

# Points
POINTS_PER_BUILDING_DESTROYED = 100
POINTS_PER_MEMBER_KILLED = 10

# --- Building powers (active only while the building stands) ----------------
HOSPITAL_PACK_INTERVAL = 25.0      # s; each active Hospital yields +1 health pack this often
ARMORY_AMMO_SPEEDUP = 2.0          # ammo regenerates this many x faster while an Armory stands
SNIPER_TOWER_DAMAGE_BONUS = 0.5    # +50% damage for a Sniper stationed in a Sniper Tower
RESEARCH_LAB_REVEAL = (3, 4, 6, 7, 8)   # buildings 4/5/7/8/9 become see-able + attackable
NUKE_CHARGE_TIME = BATTLE_DURATION       # Nuclear Silo charges 0->100% over the full battle
NUKE_BUILDING_DAMAGE = 800         # nuke damage to the CENTER building in the blast, at FULL charge
NUKE_MEMBER_DAMAGE = 600           # nuke damage to a CENTER member in the blast, at FULL charge
# Nuke can only be launched once charge reaches this fraction, and firing is a
# ONE-SHOT: after launching, the silo never recharges that battle.
NUKE_MIN_CHARGE = 0.30
# Distance-based blast falloff within the 3x3, applied to BOTH buildings and
# members (on top of the charge fraction): center (target) full, orthogonal
# (L/R/U/D) neighbours reduced, diagonal neighbours reduced further. This makes
# the target choice matter (not always "nuke the center building").
NUKE_SPLASH_CENTER = 1.00
NUKE_SPLASH_ORTHOGONAL = 0.70
NUKE_SPLASH_DIAGONAL = 0.50
ENEMY_NUKE_THRESHOLD = 0.30        # enemy AI fires its nuke once charge reaches this fraction
                                   # (= the minimum), aimed at its CURRENT attack target

# UI Layout
# Top bar: timer + scores (0-40px)
# Class stats bar: (40-110px)  
# Battlefield: (115-600px)
# Order prompt + buttons: (610-720px)
HUD_HEIGHT = 40
STATS_Y = 42
STATS_HEIGHT = 70
BATTLEFIELD_X = 40
BATTLEFIELD_Y = 115
BATTLEFIELD_WIDTH = 1200   # Will be recalculated in main
BATTLEFIELD_HEIGHT = 490   # Will be recalculated in main
GRID_CELL_SIZE = 200       # 2x from 120
ORDER_PANEL_HEIGHT = 140

# Building / Member visual sizes (2x)
BUILDING_SIZE = 100        # Was 50
MEMBER_ICON_SIZE = 40      # Was 20
