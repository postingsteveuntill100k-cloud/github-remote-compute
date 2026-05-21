import os
import shutil
from dotenv import load_dotenv

load_dotenv()
MEDIA_ROOT = os.getenv("MEDIA_ROOT", "/mnt/storage/youtube/")

def purge_assets(project_dir: str):
    """Safely clears space on the 5TB drive for bad/failed states."""
    print(f"[TRASH] Purging bad assets from {project_dir}...")
    if os.path.exists(project_dir):
        shutil.rmtree(project_dir)
        print(f"[PURGED] Successfully deleted {project_dir}")
    else:
        print(f"[TRASH] Directory {project_dir} already empty or missing.")

def archive_reusable_assets(project_dir: str, video_path: str):
    """Moves high quality assets out of temp and into permanent storage."""
    archive_dir = os.path.join(MEDIA_ROOT, "reusable_resources")
    os.makedirs(archive_dir, exist_ok=True)

    print(f"[ARCHIVING] Moving reusable assets from {project_dir} to {archive_dir}...")
    if os.path.exists(project_dir):
        # We might move specific files like broll or audio. Here we just move the whole dir for simplicity as an example
        project_name = os.path.basename(project_dir)
        dest_path = os.path.join(archive_dir, project_name)

        # If it already exists in archive, purge it first to avoid shutil.move errors
        if os.path.exists(dest_path):
            shutil.rmtree(dest_path)

        shutil.move(project_dir, dest_path)
        print(f"[ARCHIVED] Successfully moved resources to {dest_path}")
    else:
        print(f"[ARCHIVING] Project dir {project_dir} not found.")

if __name__ == "__main__":
    test_dir = os.path.join(MEDIA_ROOT, "temp_projects", "test_project")
    os.makedirs(test_dir, exist_ok=True)
    archive_reusable_assets(test_dir, "test.mp4")
