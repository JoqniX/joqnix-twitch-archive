import json
import subprocess
import time
from pathlib import Path

CHANNELS = ["joqnix", "joqnix_247"]
COOKIES_FILE = "cookies.txt"

ARCHIVE_ROOT = Path("data/twitch_archive")
INDEX_FILE = ARCHIVE_ROOT / "index.json"

MINIMUM_AGE_SECONDS = 1800  # 30 minutes


def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr)
        return None
    return result.stdout


def load_index():
    if not INDEX_FILE.exists():
        return {
            "channels": {
                ch: {"vod_ids": []} for ch in CHANNELS
            }
        }
    return json.loads(INDEX_FILE.read_text())


def save_index(data):
    INDEX_FILE.write_text(json.dumps(data, indent=2))


def fetch_channel_vods(channel):
    print(f"Fetching VOD list for {channel}...")
    url = f"https://www.twitch.tv/{channel}/videos?filter=archives"

    cmd = f'yt-dlp --cookies {COOKIES_FILE} -J "{url}"'
    output = run(cmd)

    if not output:
        return []

    data = json.loads(output)
    vods = data.get("entries", [])

    print(f"{channel} returned {len(vods)} entries")
    return vods


def download_thumbnail(url, folder):
    subprocess.run(
        f'curl -L "{url}" -o "{folder}/thumbnail.jpg"',
        shell=True
    )


def download_chat(vod_id, folder):
    print(f"Downloading chat for {vod_id}...")

    result = subprocess.run(
        f'TwitchDownloaderCLI chatdownload '
        f'--id {vod_id} '
        f'-o "{folder}/chat_raw.json"',
        shell=True
    )

    if result.returncode != 0:
        print(f"⚠️ Chat failed for {vod_id}. Skipping.")
        return False

    return True


def is_valid_archive(vod):
    if not vod.get("was_live"):
        print(f"Skipping non-livestream: {vod.get('id')}")
        return False

    if vod.get("is_live"):
        print(f"Skipping live stream: {vod.get('id')}")
        return False

    if not vod.get("duration"):
        print(f"Skipping unfinished VOD: {vod.get('id')}")
        return False

    timestamp = vod.get("timestamp")
    if timestamp:
        if time.time() - timestamp < MINIMUM_AGE_SECONDS:
            print(f"Skipping too recent VOD: {vod.get('id')}")
            return False

    return True


def archive_metadata(channel, vod, folder):
    metadata = {
        "id": vod["id"],
        "title": vod.get("title"),
        "created_at": vod.get("upload_date"),
        "timestamp": vod.get("timestamp"),
        "duration_seconds": vod.get("duration"),
        "webpage_url": vod.get("webpage_url"),
        "thumbnail": vod.get("thumbnail"),
        "channel": channel
    }

    (folder / "metadata.json").write_text(
        json.dumps(metadata, indent=2)
    )


def main():
    ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)
    index_data = load_index()

    for channel in CHANNELS:
        channel_root = ARCHIVE_ROOT / channel
        channel_root.mkdir(parents=True, exist_ok=True)

        existing_ids = set(
            index_data["channels"][channel]["vod_ids"]
        )

        vods = fetch_channel_vods(channel)

        for vod in vods:
            vod_id = vod["id"]

            if not is_valid_archive(vod):
                continue

            folder = channel_root / vod_id
            folder.mkdir(parents=True, exist_ok=True)

            chat_file = folder / "chat_raw.json"

            # If metadata not archived yet
            if vod_id not in existing_ids:
                print(f"Archiving metadata for {channel} VOD: {vod_id}")
                archive_metadata(channel, vod, folder)

                if vod.get("thumbnail"):
                    download_thumbnail(vod["thumbnail"], folder)

                index_data["channels"][channel]["vod_ids"].append(vod_id)

            # If chat missing, attempt download
            if not chat_file.exists():
                print(f"Chat missing for {vod_id}, attempting download...")
                download_chat(vod_id, folder)
            else:
                print(f"Chat already exists for {vod_id}")

    save_index(index_data)


if __name__ == "__main__":
    main()
