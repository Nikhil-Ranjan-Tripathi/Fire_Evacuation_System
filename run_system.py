import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

os.makedirs("data", exist_ok=True)

config_path = Path("data/pushbullet_config.json")
if not config_path.exists():
    from src.pushbullet_notifier import PushbulletNotifier
    PushbulletNotifier()
    print("Created pushbullet_config.json - Add your API key for notifications")
from src.gui_dashboard import main

if __name__ == "__main__":
    print("Fire Evacuation Router")
    print("-" * 40)
    main()