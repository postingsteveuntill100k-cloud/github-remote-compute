import os
import random
import time
from dotenv import load_dotenv

load_dotenv()
MEDIA_ROOT = os.getenv("MEDIA_ROOT", "/mnt/storage/youtube/")

def download_assets(project_id: str, data: dict):
    """Mocks downloading assets for the given project to MEDIA_ROOT."""
    print(f"[DOWNLOADING] Fetching assets for project {project_id}...")

    project_dir = os.path.join(MEDIA_ROOT, "temp_projects", project_id)
    os.makedirs(project_dir, exist_ok=True)

    # Mock downloading files
    assets = ["broll_1.mp4", "broll_2.mp4", "voiceover.mp3", "thumbnail_bg.jpg"]
    downloaded_files = []

    # Simulate download success or failure (90% success rate)
    is_good = random.random() < 0.90

    if is_good:
        for asset in assets:
            file_path = os.path.join(project_dir, asset)
            with open(file_path, "w") as f:
                f.write(f"Mock content for {asset} - Topic: {data['topic']}")
            downloaded_files.append(file_path)

        print(f"[GOOD DATA] Successfully downloaded assets to {project_dir}")
        return True, project_dir, downloaded_files
    else:
        print(f"[BAD DATA] Failed to download all assets properly for {project_id}")
        return False, project_dir, []

if __name__ == "__main__":
    download_assets("test_project", {"topic": "Test Topic"})
