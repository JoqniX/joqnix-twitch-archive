import json
import subprocess
from pathlib import Path

CHANNELS = ["joqnix", "joqnix_247"]
COOKIES_FILE = "cookies.txt"

ARCHIVE_ROOT = Path("data/twitch_archive")
INDEX_FILE = ARCHIVE_ROOT / "index.json"


def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr)
        exit(1)
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
    url = f"https://www.twitch.tv/{channel}/videos"
    cmd = f'yt-dlp --cookies {COOKIES_FILE} -J "{url}"'
    output = run(cmd)
    data = json.loads(output)
    return data.get("entries", [])


def download_thumbnail(url, folder):
    run(f'curl -L "{url}" -o "{folder}/thumbnail.jpg"')


def download_chat(vod_id, folder):
    run(
        f'TwitchDownloaderCLI chatdownload '
        f'--id {vod_id} '
        f'-o "{folder}/chat_raw.json"'
    )


def archive_vod(channel, vod, index_data):
    vod_id = vod["id"]
    folder = ARCHIVE_ROOT / channel / vod_id
    folder.mkdir(parents=True, exist_ok=True)

    metadata = {
        "id": vod_id,
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

    if vod.get("thumbnail"):
        download_thumbnail(vod["thumbnail"], folder)

    download_chat(vod_id, folder)

    index_data["channels"][channel]["vod_ids"].append(vod_id)


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
            if vod_id in existing_ids:
                continue

            print(f"Archiving {channel} VOD: {vod_id}")
            archive_vod(channel, vod, index_data)

    save_index(index_data)


if __name__ == "__main__":
    main()
