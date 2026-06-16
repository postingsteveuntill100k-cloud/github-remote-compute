import random
import time
from database import get_connection

def call_flash_tier_1():
    """Tier 1: Lightweight Flash model gathers raw trending topics and keywords."""
    print("[TIER 1 - FLASH] Gathering raw trending topics and keywords...")
    topics = ["AI Automation", "Python Tutorials", "Tech Gadgets 2024", "Space Exploration"]
    topic = random.choice(topics)
    keywords = f"{topic.lower().replace(' ', ', ')}, trending, new"
    return {"topic": topic, "keywords": keywords}

def call_pro_tier_2(tier_1_data):
    """Tier 2: Pro model analyzes retention potential and writes script structure."""
    print(f"[TIER 2 - PRO] Analyzing retention and writing script for: {tier_1_data['topic']}...")
    # Simulate some analysis
    retention_score = random.uniform(0.6, 0.95)
    script_structure = f"Intro hook for {tier_1_data['topic']}, body points 1-3, strong CTA."
    return {
        "topic": tier_1_data['topic'],
        "keywords": tier_1_data['keywords'],
        "retention_score": retention_score,
        "script": script_structure
    }

def call_flash_tier_3(tier_2_data):
    """Tier 3: Flash model double-checks formatting and constraints."""
    print("[TIER 3 - FLASH] Cross-checking constraints and formatting...")
    # Simulate a check: if retention score is > 0.7, it's good, else bad.
    if tier_2_data['retention_score'] > 0.7:
        is_good = True
    else:
        is_good = False
    return is_good, tier_2_data

def save_trend(data):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO trends (keyword, channel_data) VALUES (?, ?)",
                       (data['keywords'], f"Script: {data['script']}"))
        conn.commit()
    except Exception as e:
        print(f"Error saving trend: {e}")
    finally:
        conn.close()

def analyze_trends():
    """Runs the multi-tier analysis and returns result and data."""
    t1_data = call_flash_tier_1()
    t2_data = call_pro_tier_2(t1_data)
    is_good, final_data = call_flash_tier_3(t2_data)

    if is_good:
        print(f"[GOOD DATA] Trend analysis successful: {final_data['topic']}")
        save_trend(final_data)
        return True, final_data
    else:
        print(f"[BAD DATA] Trend analysis failed quality check (Score: {final_data['retention_score']:.2f})")
        return False, final_data

if __name__ == "__main__":
    analyze_trends()
