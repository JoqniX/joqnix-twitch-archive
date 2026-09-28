import json
import os
import subprocess
import time
from pathlib import Path


CHANNELS = ["joqnix", "joqnix_247"]

COOKIES_FILE = "cookies.txt"

COOKIE_API_URL = (
    "https://api.joqnix.space/cookies/twitch.tv"
)

COOKIE_SYNC_TOKEN_ENV = "COOKIE_SYNC_TOKEN"

ARCHIVE_ROOT = Path("data/twitch_archive")
INDEX_FILE = ARCHIVE_ROOT / "index.json"
METADATA_INDEX_FILE = ARCHIVE_ROOT / "metadata_index.json"

MINIMUM_AGE_SECONDS = 1800
CHAT_RETRIES = 5
CHAT_DELAY = 60


def run(cmd):
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(result.stderr)
        return None

    return result.stdout


def normalize_vod_id(raw_id):
    if raw_id.startswith("v"):
        return raw_id[1:]

    return raw_id


def load_index():
    if not INDEX_FILE.exists():
        return {
            "channels": {
                ch: {
                    "vod_ids": []
                }
                for ch in CHANNELS
            }
        }

    return json.loads(
        INDEX_FILE.read_text()
    )


def save_index(data):
    INDEX_FILE.write_text(
        json.dumps(
            data,
            indent=2
        )
    )


def load_metadata_index():
    if not METADATA_INDEX_FILE.exists():
        return {}

    return json.loads(
        METADATA_INDEX_FILE.read_text()
    )


def save_metadata_index(data):
    METADATA_INDEX_FILE.write_text(
        json.dumps(
            data,
            indent=2
        )
    )


def fetch_twitch_cookies():
    """
    Fetch the current Twitch Netscape cookie file
    from the JoqniX Cookie Sync Cloudflare Worker.
    """

    token = os.environ.get(
        COOKIE_SYNC_TOKEN_ENV
    )

    if not token:
        raise RuntimeError(
            "COOKIE_SYNC_TOKEN environment variable is not configured."
        )

    print(
        "Fetching Twitch cookies from Cloudflare..."
    )

    try:
        result = subprocess.run(
            [
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--retry",
                "3",
                "--retry-delay",
                "2",
                "-H",
                f"Authorization: Bearer {token}",
                "-H",
                "Accept: application/json",
                COOKIE_API_URL
            ],
            capture_output=True,
            text=True,
            timeout=60
        )

    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            "Cloudflare cookie request timed out."
        ) from error

    if result.returncode != 0:
        error_message = (
            result.stderr.strip()
            or "Unknown curl error."
        )

        raise RuntimeError(
            "Cloudflare cookie request failed: "
            f"{error_message}"
        )

    raw_response = result.stdout

    try:
        data = json.loads(
            raw_response
        )
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Cloudflare returned invalid JSON."
        ) from error

    if not data.get("success"):
        raise RuntimeError(
            "Cloudflare cookie service returned "
            "an unsuccessful response."
        )

    netscape = data.get(
        "netscape"
    )

    if (
        not isinstance(
            netscape,
            str
        )
        or not netscape.strip()
    ):
        raise RuntimeError(
            "Cloudflare response did not contain "
            "a valid Netscape cookie file."
        )

    Path(
        COOKIES_FILE
    ).write_text(
        netscape,
        encoding="utf-8"
    )

    cookie_lines = [
        line
        for line in netscape.splitlines()
        if line.strip()
        and not line.startswith("#")
    ]

    print(
        f"Twitch cookie file updated "
        f"({len(cookie_lines)} cookies)."
    )

def fetch_channel_vods(channel):
    print(
        f"\nFetching VOD list for {channel}..."
    )

    url = (
        f"https://www.twitch.tv/"
        f"{channel}/videos?filter=archives"
    )

    cmd = (
        f'yt-dlp '
        f'--cookies "{COOKIES_FILE}" '
        f'-J "{url}"'
    )

    output = run(cmd)

    if not output:
        return []

    data = json.loads(
        output
    )

    vods = data.get(
        "entries",
        []
    )

    print(
        f"{channel} returned "
        f"{len(vods)} entries"
    )

    return vods


def download_thumbnail(url, folder):
    subprocess.run(
        f'curl -L "{url}" '
        f'-o "{folder}/thumbnail.jpg"',
        shell=True
    )


def download_chat(vod_id, folder):
    for attempt in range(
        1,
        CHAT_RETRIES + 1
    ):
        print(
            f"[{vod_id}] "
            f"Chat attempt "
            f"{attempt}/{CHAT_RETRIES}"
        )

        result = subprocess.run(
            f'TwitchDownloaderCLI chatdownload '
            f'--id {vod_id} '
            f'--output "{folder}/chat_raw.json"',
            shell=True
        )

        if result.returncode == 0:
            print(
                f"[{vod_id}] "
                f"✅ Chat download successful."
            )
            return True

        print(
            f"[{vod_id}] "
            f"⚠️ Failed. "
            f"Retrying in {CHAT_DELAY}s..."
        )

        time.sleep(
            CHAT_DELAY
        )

    print(
        f"[{vod_id}] "
        f"❌ Chat failed after retries."
    )

    return False


def is_valid_archive(vod):
    vod_id = normalize_vod_id(
        vod.get("id")
    )

    if not vod.get("was_live"):
        print(
            f"Skipping non-livestream: "
            f"{vod_id}"
        )
        return False

    if vod.get("is_live"):
        print(
            f"Skipping live stream: "
            f"{vod_id}"
        )
        return False

    if not vod.get("duration"):
        print(
            f"Skipping unfinished VOD: "
            f"{vod_id}"
        )
        return False

    timestamp = vod.get(
        "timestamp"
    )

    if timestamp:
        if (
            time.time() - timestamp
            < MINIMUM_AGE_SECONDS
        ):
            print(
                f"Skipping too recent VOD: "
                f"{vod_id}"
            )
            return False

    return True


def archive_metadata(
    channel,
    vod,
    folder
):
    vod_id = normalize_vod_id(
        vod["id"]
    )

    metadata = {
        "id": vod_id,
        "title": vod.get("title"),
        "created_at": vod.get(
            "upload_date"
        ),
        "timestamp": vod.get(
            "timestamp"
        ),
        "duration_seconds": vod.get(
            "duration"
        ),
        "webpage_url": vod.get(
            "webpage_url"
        ),
        "thumbnail": vod.get(
            "thumbnail"
        ),
        "channel": channel
    }

    (
        folder / "metadata.json"
    ).write_text(
        json.dumps(
            metadata,
            indent=2
        )
    )


def update_metadata_index(
    index,
    vod_id,
    channel,
    vod
):
    index[vod_id] = {
        "channel": channel,
        "timestamp": vod.get(
            "timestamp"
        ),
        "created_at_iso": vod.get(
            "upload_date"
        ),
        "duration_seconds": vod.get(
            "duration"
        ),
        "title": vod.get(
            "title"
        )
    }


def rebuild_metadata_from_file(
    metadata_index,
    vod_id,
    folder
):
    metadata_file = (
        folder / "metadata.json"
    )

    if not metadata_file.exists():
        return

    data = json.loads(
        metadata_file.read_text()
    )

    metadata_index[vod_id] = {
        "channel": data.get(
            "channel"
        ),
        "timestamp": data.get(
            "timestamp"
        ),
        "created_at_iso": data.get(
            "created_at"
        ),
        "duration_seconds": data.get(
            "duration_seconds"
        ),
        "title": data.get(
            "title"
        )
    }

    print(
        f"[metadata_index] "
        f"Rebuilt entry for {vod_id}"
    )


def main():
    ARCHIVE_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )

    # Always fetch a fresh Twitch cookie snapshot
    # before querying Twitch.
    fetch_twitch_cookies()

    index_data = load_index()
    metadata_index = load_metadata_index()

    for channel in CHANNELS:
        channel_root = (
            ARCHIVE_ROOT / channel
        )

        channel_root.mkdir(
            parents=True,
            exist_ok=True
        )

        existing_ids = set(
            index_data[
                "channels"
            ][channel][
                "vod_ids"
            ]
        )

        vods = fetch_channel_vods(
            channel
        )

        for vod in vods:
            raw_id = vod["id"]

            vod_id = normalize_vod_id(
                raw_id
            )

            if not is_valid_archive(
                vod
            ):
                continue

            folder = (
                channel_root / vod_id
            )

            folder.mkdir(
                parents=True,
                exist_ok=True
            )

            chat_file = (
                folder /
                "chat_raw.json"
            )

            # NEW VOD
            if vod_id not in existing_ids:
                print(
                    f"\nArchiving metadata "
                    f"for {channel} VOD: "
                    f"{vod_id}"
                )

                archive_metadata(
                    channel,
                    vod,
                    folder
                )

                if vod.get(
                    "thumbnail"
                ):
                    download_thumbnail(
                        vod["thumbnail"],
                        folder
                    )

                index_data[
                    "channels"
                ][channel][
                    "vod_ids"
                ].append(
                    vod_id
                )

                update_metadata_index(
                    metadata_index,
                    vod_id,
                    channel,
                    vod
                )

            # EXISTING VOD
            # Ensure metadata index entry exists
            else:
                if vod_id not in metadata_index:
                    rebuild_metadata_from_file(
                        metadata_index,
                        vod_id,
                        folder
                    )

            # CHAT DOWNLOAD
            if not chat_file.exists():
                print(
                    f"[{vod_id}] "
                    f"Chat missing. "
                    f"Attempting download..."
                )

                download_chat(
                    vod_id,
                    folder
                )

            else:
                print(
                    f"[{vod_id}] "
                    f"Chat already exists."
                )

    save_index(
        index_data
    )

    save_metadata_index(
        metadata_index
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        # Never leave the temporary cookie file
        # in the GitHub Actions workspace.
        try:
            Path(
                COOKIES_FILE
            ).unlink(
                missing_ok=True
            )
        except Exception as error:
            print(
                f"Warning: could not remove "
                f"{COOKIES_FILE}: {error}"
            )
