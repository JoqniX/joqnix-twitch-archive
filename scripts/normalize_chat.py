import json
from pathlib import Path

ARCHIVE_ROOT = Path("data/twitch_archive")


def seconds_to_hms(seconds):
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}"


def normalize_chat_file(chat_path):
    normalized_path = chat_path.parent / "chat_normalized.json"

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
        offset = comment.get("content_offset_seconds", 0)

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

        commenter = comment.get("commenter", {})
        message = comment.get("message", {})

        normalized["messages"].append({
            "id": comment.get("_id"),
            "timestamp_seconds": offset,
            "timestamp_hms": seconds_to_hms(offset),
            "timestamp_iso": comment.get("created_at"),
            "user": {
                "id": commenter.get("_id"),
                "display_name": commenter.get("display_name"),
                "login": commenter.get("name"),
                "avatar_url": commenter.get("logo"),   # ← NEW FIELD
                "color": message.get("user_color"),
                "badges": message.get("user_badges", [])
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
