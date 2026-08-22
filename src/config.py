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
        "damage_player": 15,
        "damage_building": 8,
        "mitigation": 0.1,
        "speed": 0.8,
        "attack_interval": 2.5,  # Slow but ranged
    },
    "assassin": {
        "hp": 90,
        "damage_player": 20,
        "damage_building": 6,
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
BUILDING_TYPES = {
    "warehouse":    {"display_name": "Warehouse",    "hp": BUILDING_BASE_HP, "upgrade_cost": 0,     "upgrades_from": None,        "max_count": None, "name_index": 3},
    "safehouse":    {"display_name": "Safehouse",    "hp": 650,              "upgrade_cost": 1500,  "upgrades_from": "warehouse", "max_count": 2,    "name_index": 8},
    "armory":       {"display_name": "Armory",       "hp": 750,              "upgrade_cost": 2500,  "upgrades_from": "warehouse", "max_count": 1,    "name_index": 1},
    "hospital":     {"display_name": "Hospital",     "hp": 750,              "upgrade_cost": 2500,  "upgrades_from": "warehouse", "max_count": 1,    "name_index": 2},
    "research_lab": {"display_name": "Research Lab", "hp": 800,              "upgrade_cost": 3500,  "upgrades_from": "warehouse", "max_count": 1,    "name_index": 7},
    "sniper_tower": {"display_name": "Sniper Tower", "hp": 850,              "upgrade_cost": 3500,  "upgrades_from": "warehouse", "max_count": 1,    "name_index": 6},
    "nuclear_silo": {"display_name": "Nuclear Silo", "hp": 950,              "upgrade_cost": 10000, "upgrades_from": "warehouse", "max_count": 1,    "name_index": 5},
    "headquarters": {"display_name": "Headquarters", "hp": 1300,             "upgrade_cost": 6000,  "upgrades_from": "warehouse", "max_count": 1,    "name_index": 0},
    "bunker":       {"display_name": "Bunker",       "hp": 1300,             "upgrade_cost": 5000,  "upgrades_from": "safehouse", "max_count": 2,    "name_index": 4},
}

# Starting money for a brand-new player (fresh profile only; saved balance
# takes over once a profile exists). New players earn money by winning wars.
STARTING_MONEY = 0

# --- HQ leveling / member cap ----------------------------------------------
# Roster size is gated by the HQ. No HQ => BASE_MEMBER_CAP. Each HQ level adds
# HQ_MEMBERS_PER_LEVEL, up to HQ_MAX_LEVEL (Lv4 => 40 + 4*10 = 80).
BASE_MEMBER_CAP = 40
HQ_MEMBERS_PER_LEVEL = 10
HQ_MAX_LEVEL = 4
# Bench/backup force: recruits won from defeated empires wait here until you
# move them into the active roster. Capped independently of the HQ roster cap.
BACKUP_FORCE_CAP = 80
# HQ HP per level (Lv1 matches BUILDING_TYPES["headquarters"]["hp"]).
HQ_LEVEL_HP = {1: 1300, 2: 1700, 3: 2200, 4: 3000}
# Money cost to level the HQ FROM level n-1 TO level n (steeply escalating).
# Building an HQ (Warehouse -> HQ) costs BUILDING_TYPES cost and yields Lv1.
HQ_LEVEL_UP_COST = {2: 8000, 3: 20000, 4: 45000}

# --- Police raid boss ------------------------------------------------------
# Once a city is conquered you can repeatedly "Challenge Police" — a much harder
# fight built from the city's police_power. A win pays this multiple of the
# standard war reward (30% of the police empire's net worth, i.e. 100 x sum of
# member levels). The police boss is a maxed level-40 roster, so this is already
# a large, difficulty-appropriate payout; the multiplier is the tuning knob for
# how premium the elite fight should feel. The city is never marked conquered by
# this and there is no loss penalty.
POLICE_REWARD_MULT = 1.0

# Health Packs
HEALTH_PACKS_START = 8  # Starting health packs per battle

# AI
AI_ORDER_INTERVAL = 6.0      # Seconds between AI attack waves
AI_FIRST_ORDER_DELAY = 5.0   # Seconds before AI issues first order

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
NUKE_BUILDING_DAMAGE = 800         # nuke damage to each building in the 3x3 blast, at FULL charge
NUKE_MEMBER_DAMAGE = 600           # nuke damage to each member in the 3x3 blast, at FULL charge
ENEMY_NUKE_THRESHOLD = 0.75        # enemy AI fires its nuke once charge reaches this fraction

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
