import json
from pathlib import Path

ARCHIVE_ROOT = Path("data/twitch_archive")


def normalize_chat(folder):
    raw_file = folder / "chat_raw.json"
    if not raw_file.exists():
        return

    raw_data = json.loads(raw_file.read_text())
    normalized = []

    for comment in raw_data.get("comments", []):
        normalized.append({
            "timestamp": comment.get("content_offset_seconds"),
            "author": comment.get("commenter", {}).get("display_name"),
            "user_id": comment.get("commenter", {}).get("_id"),
            "message": comment.get("message", {}).get("body"),
            "badges": [
                badge.get("id")
                for badge in comment.get("message", {}).get("user_badges", [])
            ],
            "platform": "twitch"
        })

    (folder / "chat_normalized.json").write_text(
        json.dumps(normalized, indent=2)
    )


def main():
    for channel_folder in ARCHIVE_ROOT.iterdir():
        if not channel_folder.is_dir():
            continue
        if channel_folder.name == "index.json":
            continue

        for vod_folder in channel_folder.iterdir():
            if vod_folder.is_dir():
                normalize_chat(vod_folder)


if __name__ == "__main__":
    main()
