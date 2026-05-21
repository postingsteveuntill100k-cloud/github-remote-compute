import time
import uuid

import database
import trend_analyzer
import downloader
import video_editor
import uploader
import utils

def execute_pipeline():
    print("="*60)
    print("[PIPELINE START] Generating new project...")
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    database.update_project_state(project_id, "INIT")

    # ---------------------------------------------------------
    # STEP 1: Trend Analysis (Flash -> Pro -> Flash)
    # ---------------------------------------------------------
    print("\n--- STEP 1: TREND ANALYSIS ---")
    is_trend_good, trend_data = trend_analyzer.analyze_trends()

    if not is_trend_good:
        print("[BAD DATA - PURGING TO TRASH] Trend analysis failed criteria.")
        database.update_project_state(project_id, "TRASHED")
        database.log_verification(project_id, "TREND_ANALYSIS", "BAD", trend_data.get('retention_score', 0))
        return False

    print("[GOOD DATA - PROCEEDING] Trend criteria met.")
    database.update_project_state(project_id, "TREND_FOUND")
    database.log_verification(project_id, "TREND_ANALYSIS", "GOOD", trend_data.get('retention_score', 0))

    # ---------------------------------------------------------
    # STEP 2: Download Resources
    # ---------------------------------------------------------
    print("\n--- STEP 2: ASSETS DOWNLOADING ---")
    database.update_project_state(project_id, "ASSETS_DOWNLOADING")

    is_dl_good, project_dir, assets = downloader.download_assets(project_id, trend_data)

    if not is_dl_good:
        print("[BAD DATA - PURGING TO TRASH] Failed to download necessary assets.")
        utils.purge_assets(project_dir)
        database.update_project_state(project_id, "TRASHED")
        database.log_verification(project_id, "ASSETS_DOWNLOADING", "BAD")
        return False

    print("[GOOD DATA - PROCEEDING] All assets downloaded successfully.")
    database.log_verification(project_id, "ASSETS_DOWNLOADING", "GOOD")

    # ---------------------------------------------------------
    # STEP 3: Video Editing Wrapper
    # ---------------------------------------------------------
    print("\n--- STEP 3: VIDEO EDITING ---")
    database.update_project_state(project_id, "EDITING")

    is_edit_good, video_path = video_editor.edit_video(project_id, project_dir, assets)

    if not is_edit_good:
        print("[BAD DATA - PURGING TO TRASH] Failed to render video. Cleaning up assets.")
        utils.purge_assets(project_dir)
        database.update_project_state(project_id, "TRASHED")
        database.log_verification(project_id, "EDITING", "BAD")
        return False

    print("[GOOD DATA - PROCEEDING] Video rendered perfectly.")
    database.log_verification(project_id, "EDITING", "GOOD")

    # ---------------------------------------------------------
    # STEP 4: Metadata and Upload
    # ---------------------------------------------------------
    print("\n--- STEP 4: METADATA GENERATION & UPLOAD ---")
    database.update_project_state(project_id, "METADATA_GENERATION")

    is_upload_good, video_id = uploader.upload_video(project_id, video_path, trend_data)

    if not is_upload_good:
        print("[BAD DATA - PURGING TO TRASH] Upload failed.")
        utils.purge_assets(project_dir)
        database.update_project_state(project_id, "TRASHED")
        database.log_verification(project_id, "UPLOAD", "BAD")
        return False

    print("[GOOD DATA - PROCEEDING] Upload successful!")
    database.update_project_state(project_id, "UPLOADED")
    database.log_verification(project_id, "UPLOAD", "GOOD")

    # ---------------------------------------------------------
    # STEP 5: Post-Upload Archive
    # ---------------------------------------------------------
    print("\n--- STEP 5: POST-UPLOAD ARCHIVE ---")
    utils.archive_reusable_assets(project_dir, video_path)

    print(f"\n[PIPELINE COMPLETE] Project {project_id} successfully deployed!")
    return True

if __name__ == "__main__":
    # Continuous Loop Example (runs a few times for demo purposes)
    print("Starting YouTube Automation Pipeline...")
    # Make sure DB is initialized
    database.init_db()

    for _ in range(3):
        execute_pipeline()
        print("\nSleeping briefly before next iteration...\n")
        time.sleep(2)
