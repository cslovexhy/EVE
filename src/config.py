"""EVE - Game Configuration Constants"""

# Display
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
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

# AI
AI_ORDER_INTERVAL = 8.0      # Seconds between AI orders
AI_FIRST_ORDER_DELAY = 5.0   # Seconds before AI issues first order

# Movement (pixels per second on the battlefield)
MEMBER_MOVE_SPEED = 48

# Combat
ATTACK_RANGE = 50      # Pixels - melee range
SNIPER_RANGE = 200     # Pixels - sniper can shoot from further

# Stealth (Assassins)
STEALTH_DELAY = 5.0    # Seconds out of combat before going stealth

# Points
POINTS_PER_BUILDING_DESTROYED = 100
POINTS_PER_MEMBER_KILLED = 10

# UI Layout
BATTLEFIELD_X = 40
BATTLEFIELD_Y = 60
BATTLEFIELD_WIDTH = 1200
BATTLEFIELD_HEIGHT = 540
GRID_CELL_SIZE = 120
HUD_HEIGHT = 60
ORDER_PANEL_HEIGHT = 120
