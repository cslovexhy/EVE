"""EVE - Building Placement Tool

Drag buildings onto the background to position them.
Click and drag any building to move it.
Press S to save positions to a file.
Press ESC to quit.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pygame
import json
import config

# Force a reasonable window size for the tool
TOOL_WIDTH = 1920
TOOL_HEIGHT = 1080


def main():
    pygame.init()
    
    screen = pygame.display.set_mode((TOOL_WIDTH, TOOL_HEIGHT))
    pygame.display.set_caption("EVE - Building Placement Tool (Drag to move, S to save, ESC to quit)")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 24)
    font_small = pygame.font.Font(None, 18)
    
    # Set config for positioning
    config.SCREEN_WIDTH = TOOL_WIDTH
    config.SCREEN_HEIGHT = TOOL_HEIGHT
    config.BATTLEFIELD_WIDTH = TOOL_WIDTH - 80
    config.BATTLEFIELD_HEIGHT = TOOL_HEIGHT - config.BATTLEFIELD_Y - config.ORDER_PANEL_HEIGHT
    
    bx = config.BATTLEFIELD_X
    by = config.BATTLEFIELD_Y
    bw = config.BATTLEFIELD_WIDTH
    bh = config.BATTLEFIELD_HEIGHT
    
    # Load background
    bg_path = os.path.join(os.path.dirname(__file__), "..", "assets", "bg", "battlefield.png")
    bg_img = pygame.image.load(bg_path).convert()
    bg_img = pygame.transform.smoothscale(bg_img, (bw, bh))
    
    # Load existing positions or use defaults
    positions_file = os.path.join(os.path.dirname(__file__), "..", "assets", "building_positions.json")
    
    # Default positions (current values from engine.py)
    buildings = []
    # Blue side (player) - buildings 1-9
    blue_defaults = [
        (0.380, 0.360), (0.283, 0.360), (0.186, 0.360),  # row 1: 1,2,3
        (0.370, 0.551), (0.261, 0.551), (0.151, 0.551),  # row 2: 4,5,6
        (0.330, 0.779), (0.201, 0.779), (0.072, 0.779),  # row 3: 7,8,9
    ]
    # Red side (enemy) - buildings 1-9
    red_defaults = [
        (0.622, 0.360), (0.719, 0.360), (0.816, 0.360),  # row 1: 1,2,3
        (0.632, 0.551), (0.741, 0.551), (0.851, 0.551),  # row 2: 4,5,6
        (0.662, 0.779), (0.791, 0.779), (0.920, 0.779),  # row 3: 7,8,9
    ]
    
    # Try to load saved positions
    if os.path.exists(positions_file):
        with open(positions_file, "r") as f:
            saved = json.load(f)
            blue_defaults = [tuple(p) for p in saved["blue"]]
            red_defaults = [tuple(p) for p in saved["red"]]
    
    # Convert to pixel positions
    blue_buildings = []
    for i, (px, py) in enumerate(blue_defaults):
        blue_buildings.append({
            "index": i,
            "x": bx + px * bw,
            "y": by + py * bh,
            "label": f"B{i+1}",
            "side": "blue",
        })
    
    red_buildings = []
    for i, (px, py) in enumerate(red_defaults):
        red_buildings.append({
            "index": i,
            "x": bx + px * bw,
            "y": by + py * bh,
            "label": f"R{i+1}",
            "side": "red",
        })
    
    all_buildings = blue_buildings + red_buildings
    
    # Drag state
    dragging = None
    drag_offset = (0, 0)
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_s:
                    # Save positions as fractions
                    blue_fracs = []
                    for b in blue_buildings:
                        fx = (b["x"] - bx) / bw
                        fy = (b["y"] - by) / bh
                        blue_fracs.append((round(fx, 4), round(fy, 4)))
                    red_fracs = []
                    for b in red_buildings:
                        fx = (b["x"] - bx) / bw
                        fy = (b["y"] - by) / bh
                        red_fracs.append((round(fx, 4), round(fy, 4)))
                    
                    data = {"blue": blue_fracs, "red": red_fracs}
                    with open(positions_file, "w") as f:
                        json.dump(data, f, indent=2)
                    print(f"Saved to {positions_file}")
                    print(f"Blue: {blue_fracs}")
                    print(f"Red:  {red_fracs}")
            
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                # Find building under cursor
                for b in all_buildings:
                    size = 40
                    if abs(mx - b["x"]) < size and abs(my - b["y"]) < size:
                        dragging = b
                        drag_offset = (b["x"] - mx, b["y"] - my)
                        break
            
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging = None
            
            elif event.type == pygame.MOUSEMOTION:
                if dragging:
                    mx, my = event.pos
                    dragging["x"] = mx + drag_offset[0]
                    dragging["y"] = my + drag_offset[1]
        
        # Draw
        screen.fill((0, 0, 0))
        
        # Background
        screen.blit(bg_img, (bx, by))
        
        # Draw buildings
        for b in all_buildings:
            x, y = int(b["x"]), int(b["y"])
            size = 35
            
            if b["side"] == "blue":
                color = (50, 100, 220)
                border = (100, 150, 255)
            else:
                color = (220, 50, 50)
                border = (255, 100, 100)
            
            # Highlight if dragging
            if b == dragging:
                border = (255, 255, 0)
            
            rect = pygame.Rect(x - size//2, y - size//2, size, size)
            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, border, rect, 2)
            
            # Label
            label = font_small.render(b["label"], True, (255, 255, 255))
            label_rect = label.get_rect(center=(x, y))
            screen.blit(label, label_rect)
        
        # Instructions
        instructions = font.render(
            "Drag buildings to position  |  S = Save  |  ESC = Quit", True, (200, 200, 200))
        screen.blit(instructions, (20, 10))
        
        # Show current position of dragged building
        if dragging:
            fx = (dragging["x"] - bx) / bw
            fy = (dragging["y"] - by) / bh
            pos_text = font.render(
                f'{dragging["label"]}: ({fx:.4f}, {fy:.4f})', True, (255, 255, 0))
            screen.blit(pos_text, (20, 35))
        
        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()


if __name__ == "__main__":
    main()
