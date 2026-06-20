import random

def generate_metadata(data: dict):
    """Generates SEO-optimized titles, descriptions, and tags."""
    print("[METADATA] Generating SEO metadata...")
    topic = data.get('topic', 'Default Topic')
    title = f"The Truth About {topic} in 2024!"
    description = f"In this video we explore {topic}. {data.get('script', '')[:50]}..."
    tags = data.get('keywords', '').split(', ') + [topic, "2024"]

    return {
        "title": title,
        "description": description,
        "tags": tags
    }

def authenticate_youtube():
    """Mock OAuth2 authentication flow for YouTube Data API v3."""
    print("[AUTH] Mocking OAuth2 YouTube Data API v3 authentication...")
    # Normally we'd use google-auth-oauthlib and build the service here
    return True

def upload_video(project_id: str, video_path: str, data: dict):
    """Mocks uploading the generated video to YouTube."""
    if not authenticate_youtube():
        print("[BAD DATA] Failed to authenticate YouTube API.")
        return False, None

    metadata = generate_metadata(data)
    print(f"[UPLOADING] Uploading '{video_path}' with Title: {metadata['title']}")

    # Simulate a successful upload with 95% probability
    is_good = random.random() < 0.95
    if is_good:
        video_id = f"yt_{random.randint(1000, 9999)}"
        print(f"[GOOD DATA] Video {project_id} uploaded successfully! Link: https://youtube.com/watch?v={video_id}")
        return True, video_id
    else:
        print(f"[BAD DATA] Video upload failed for project {project_id}.")
        return False, None

if __name__ == "__main__":
    upload_video("test_project", "/mnt/storage/youtube/temp_projects/test_project/final_video_test_project.mp4", {"topic": "AI Automation", "keywords": "ai, automation", "script": "This is a great video about AI."})
