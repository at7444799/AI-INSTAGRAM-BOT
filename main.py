import os
import time
import json
import random
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

IG_USER_ID = os.getenv("IG_USER_ID")
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
PUBLIC_REPO_RAW_BASE = os.getenv("PUBLIC_REPO_RAW_BASE")

VIDEOS_DIR = Path("videos")
PHOTOS_DIR = Path("photos")
POSTED_DIR = Path("posted")
POSTED_DIR.mkdir(exist_ok=True)

GRAPH_URL = "https://graph.facebook.com/v20.0"


def get_next_file(folder: Path, extensions):
    files = [f for f in folder.iterdir() if f.suffix.lower() in extensions]
    if not files:
        return None
    return sorted(files)[0]


def generate_caption(file_name: str, content_type: str):
    prompt = f"""
Create an Instagram caption for a clearly virtual AI influencer.

Rules:
- Make it natural, stylish, and short
- Mention this is a virtual/AI creator in a subtle honest way
- Add 12 relevant hashtags
- No fake claims like real travel, real body, real person
- Content type: {content_type}
- File name/context: {file_name}

Return only the final caption.
"""

    if not NVIDIA_API_KEY:
        return (
            "A new moment from my virtual world ✨\n\n"
            "#AIInfluencer #VirtualCreator #DigitalHuman #AIGirl #VirtualModel "
            "#InstagramCreator #AestheticReels #AIArt #DigitalCreator #FutureFashion "
            "#ContentCreator #ReelsIndia"
        )

    url = "https://integrate.api.nvidia.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": NVIDIA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are an expert Instagram growth copywriter.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.8,
        "max_tokens": 300,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()

    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def create_media_container(media_url: str, caption: str, is_video: bool):
    endpoint = f"{GRAPH_URL}/{IG_USER_ID}/media"

    payload = {
        "access_token": IG_ACCESS_TOKEN,
        "caption": caption,
    }

    if is_video:
        payload["media_type"] = "REELS"
        payload["video_url"] = media_url
    else:
        payload["image_url"] = media_url

    response = requests.post(endpoint, data=payload, timeout=60)
    response.raise_for_status()

    return response.json()["id"]


def wait_until_ready(container_id: str):
    endpoint = f"{GRAPH_URL}/{container_id}"

    for _ in range(20):
        response = requests.get(
            endpoint,
            params={
                "fields": "status_code",
                "access_token": IG_ACCESS_TOKEN,
            },
            timeout=30,
        )
        response.raise_for_status()

        status = response.json().get("status_code")
        print("Upload status:", status)

        if status == "FINISHED":
            return True

        if status == "ERROR":
            raise Exception("Instagram media processing failed")

        time.sleep(30)

    raise TimeoutError("Instagram media was not ready in time")


def publish_container(container_id: str):
    endpoint = f"{GRAPH_URL}/{IG_USER_ID}/media_publish"

    response = requests.post(
        endpoint,
        data={
            "creation_id": container_id,
            "access_token": IG_ACCESS_TOKEN,
        },
        timeout=60,
    )

    response.raise_for_status()
    return response.json()


def move_to_posted(file_path: Path):
    target = POSTED_DIR / file_path.name
    file_path.rename(target)
    print(f"Moved {file_path} to {target}")


def main():
    if not IG_USER_ID or not IG_ACCESS_TOKEN or not PUBLIC_REPO_RAW_BASE:
        raise Exception("Missing required environment variables")

    video = get_next_file(VIDEOS_DIR, [".mp4", ".mov"])
    photo = get_next_file(PHOTOS_DIR, [".jpg", ".jpeg", ".png"])

    if video:
        selected_file = video
        is_video = True
        content_type = "Instagram Reel"
        media_url = f"{PUBLIC_REPO_RAW_BASE}/videos/{selected_file.name}"
    elif photo:
        selected_file = photo
        is_video = False
        content_type = "Instagram photo post"
        media_url = f"{PUBLIC_REPO_RAW_BASE}/photos/{selected_file.name}"
    else:
        print("No videos or photos found.")
        return

    print("Selected file:", selected_file)
    print("Media URL:", media_url)

    caption = generate_caption(selected_file.name, content_type)
    print("Caption generated:")
    print(caption)

    container_id = create_media_container(media_url, caption, is_video)
    print("Container created:", container_id)

    wait_until_ready(container_id)

    result = publish_container(container_id)
    print("Published:", json.dumps(result, indent=2))

    move_to_posted(selected_file)


if __name__ == "__main__":
    main()
