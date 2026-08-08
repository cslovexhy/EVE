"""Download lieutenant portrait images from the UE Fandom wiki via API."""

import json
import os
import time
import subprocess
import urllib.request
import urllib.error
from pathlib import Path


# Our 40 player member names
# We'll try to find wiki lieutenant images for each
# The wiki file is typically: File:Lieutenant_NAME.png (lowercase)
PLAYER_NAMES = [
    "Hammer", "Duke", "Tank", "Brick", "Ironside",
    "Magnus", "Bulwark", "Titan", "Rocco", "Slab",
    "Fox", "Kate", "Hawkeye", "Scope", "Viper",
    "Longshot", "Whisper", "Deadshot", "Iris", "Bolt",
    "Phantom", "Nightshade", "Shadow", "Wraith", "Stiletto",
    "Venom", "Specter", "Mirage", "Silhouette", "Dagger",
    "Hotwire", "Blade", "Fuse", "Bomber", "Sparks",
    "Inferno", "Nitro", "Torch", "Kaboom", "Blast",
]

# Map names that don't match wiki naming or need substitutes
WIKI_FILE_OVERRIDES = {
    # Names that exist on wiki but with slightly different file naming
    "Brick": "brutus",         # Use Brutus portrait
    "Ironside": "ironside",
    "Bulwark": "boulder",      # Use Boulder portrait
    "Slab": "basher",          # Use Basher portrait
    "Longshot": "arrow",       # Use Arrow portrait
    "Whisper": "charon",       # Use Charon portrait
    "Iris": "ariel",           # Use Ariel portrait
    "Silhouette": "azura",     # Use Azura portrait
    "Kaboom": "backfire",      # Use Backfire portrait
    "Blast": "buster",         # Use Buster portrait
    "Bomber": "big_chris",     # Use Big Chris portrait
    "Sparks": "blink",         # Use Blink portrait
}

OUTPUT_DIR = Path(__file__).parent.parent / "assets" / "portraits"
API_BASE = "https://underworld-empire.fandom.com/api.php"


def get_image_url(file_name: str) -> str:
    """Use MediaWiki API to get the direct image URL for a file."""
    params = (
        f"?action=query"
        f"&titles=File:{file_name}"
        f"&prop=imageinfo"
        f"&iiprop=url"
        f"&format=json"
    )
    url = API_BASE + params
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EVE-Game-Dev/1.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        return None
    
    pages = data.get("query", {}).get("pages", {})
    for page_id, page_data in pages.items():
        if page_id == "-1":
            return None  # File not found
        imageinfo = page_data.get("imageinfo", [])
        if imageinfo:
            return imageinfo[0].get("url")
    
    return None


def download_with_curl(url: str, save_path: Path) -> bool:
    """Download file using curl (more reliable with Fandom CDN)."""
    result = subprocess.run(
        ["curl", "-sL", "-o", str(save_path), url],
        capture_output=True, timeout=30
    )
    if result.returncode == 0 and save_path.exists() and save_path.stat().st_size > 500:
        return True
    if save_path.exists():
        save_path.unlink()
    return False


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Remove test file
    test_file = OUTPUT_DIR / "test_overkill.png"
    if test_file.exists():
        test_file.unlink()
    
    downloaded = 0
    skipped = 0
    failed = 0
    
    for name in PLAYER_NAMES:
        save_path = OUTPUT_DIR / f"{name.lower()}.png"
        
        # Skip if already downloaded
        if save_path.exists() and save_path.stat().st_size > 500:
            print(f"  [{name}] Already exists, skipping")
            skipped += 1
            continue
        
        # Determine wiki file name to look for
        wiki_name = WIKI_FILE_OVERRIDES.get(name, name.lower())
        
        # Try common file name patterns
        file_candidates = [
            f"Lieutenant_{wiki_name}.png",
            f"Lieutenant_{wiki_name.lower()}.png",
            f"Lieutenant_{wiki_name.title()}.png",
        ]
        
        img_url = None
        for candidate in file_candidates:
            img_url = get_image_url(candidate)
            if img_url:
                break
        
        if not img_url:
            print(f"  [{name}] No image found (tried: {wiki_name})")
            failed += 1
            time.sleep(0.3)
            continue
        
        print(f"  [{name}] Downloading...")
        if download_with_curl(img_url, save_path):
            size = save_path.stat().st_size
            print(f"  [{name}] OK ({size:,} bytes)")
            downloaded += 1
        else:
            print(f"  [{name}] Download failed")
            failed += 1
        
        time.sleep(0.5)  # Be polite
    
    print(f"\nDone! Downloaded: {downloaded}, Skipped: {skipped}, Failed: {failed}")
    print(f"Portraits saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
