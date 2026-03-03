import json
from pathlib import Path

ARCHIVE_ROOT = Path("data/twitch_archive")


def normalize_chat_file(chat_path):
    normalized_path = chat_path.parent / "chat_normalized.json"

    # Skip if already normalized
    if normalized_path.exists():
        return

    print(f"Normalizing {chat_path}")

    with open(chat_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    comments = raw.get("comments", [])

    normalized = {
        "vod_id": raw.get("video", {}).get("id"),
        "streamer": raw.get("streamer", {}),
        "video": {
            "title": raw.get("video", {}).get("title"),
            "created_at": raw.get("video", {}).get("created_at"),
            "duration": raw.get("video", {}).get("length"),
            "game": raw.get("video", {}).get("game"),
        },
        "messages": []
    }

    for comment in comments:
        fragments = []

        for frag in comment.get("message", {}).get("fragments", []):
            if frag.get("emoticon"):
                fragments.append({
                    "type": "emote",
                    "id": frag["emoticon"]["emoticon_id"],
                    "name": frag["text"]
                })
            else:
                fragments.append({
                    "type": "text",
                    "text": frag["text"]
                })

        normalized["messages"].append({
            "id": comment.get("_id"),
            "timestamp": comment.get("content_offset_seconds"),
            "timestamp_iso": comment.get("created_at"),
            "user": {
                "id": comment.get("commenter", {}).get("_id"),
                "display_name": comment.get("commenter", {}).get("display_name"),
                "login": comment.get("commenter", {}).get("name"),
                "color": comment.get("message", {}).get("user_color"),
                "badges": comment.get("message", {}).get("user_badges", [])
            },
            "message": fragments
        })

    with open(normalized_path, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2)


def main():
    for channel_dir in ARCHIVE_ROOT.iterdir():
        if not channel_dir.is_dir():
            continue

        for vod_dir in channel_dir.iterdir():
            if not vod_dir.is_dir():
                continue

            chat_raw = vod_dir / "chat_raw.json"
            if chat_raw.exists():
                normalize_chat_file(chat_raw)


if __name__ == "__main__":
    main()
