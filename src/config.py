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

# Stealth (Assassins)
STEALTH_DELAY = 5.0    # Seconds out of combat before going stealth

# Ammo
AMMO_MAX = 10          # Starting/max ammo per member
AMMO_REGEN_INTERVAL = 10.0  # Seconds per ammo regen

# Points
POINTS_PER_BUILDING_DESTROYED = 100
POINTS_PER_MEMBER_KILLED = 10

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
