"""Download the trained detector weights from the repository's GitHub Releases.

The weights are not in git (see docs/model_weights.md). Run inside the backend container:
    docker compose run --rm --no-deps web python -m scripts.download_detector [--tag model-v1]

Without --tag it takes the newest release whose tag starts with "model". The file is saved to
storage/models/detector.pt; restart the server (docker compose restart web) to load it.
"""
import argparse
import json
import urllib.request

from vision.detector import DETECTOR_WEIGHTS

REPOSITORY = "elirazkatzin1/SmartRefrigerator"
# Matches model-v2 as documented, and also modelv1, the tag of the first release
TAG_PREFIX = "model"
ASSET_NAME = "detector.pt"


def find_asset_url(tag: str | None) -> tuple[str, str]:
    """The tag and download URL of detector.pt in the requested (or newest model-) release."""
    with urllib.request.urlopen(f"https://api.github.com/repos/{REPOSITORY}/releases") as response:
        # Newest first
        releases = json.load(response)
    for release in releases:
        if (release["tag_name"] == tag) if tag else release["tag_name"].startswith(TAG_PREFIX):
            for asset in release["assets"]:
                if asset["name"] == ASSET_NAME:
                    return release["tag_name"], asset["browser_download_url"]
            raise SystemExit(f"Release {release['tag_name']} has no {ASSET_NAME} attached")
    wanted = f"release {tag}" if tag else f"release with a tag starting with '{TAG_PREFIX}'"
    raise SystemExit(f"No {wanted} in https://github.com/{REPOSITORY}/releases")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tag", help="release tag, e.g. model-v2 (default: the newest model release)")
    args = parser.parse_args()

    tag, url = find_asset_url(args.tag)
    DETECTOR_WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    # Download next to the target and rename, so a failed download never leaves a broken detector.pt
    partial = DETECTOR_WEIGHTS.with_suffix(".pt.part")
    print(f"Downloading {ASSET_NAME} from release {tag}...")
    urllib.request.urlretrieve(url, partial)
    partial.replace(DETECTOR_WEIGHTS)
    print(f"Saved {DETECTOR_WEIGHTS.stat().st_size / 1e6:.1f} MB to storage/models/{DETECTOR_WEIGHTS.name}")
    print("Restart the server to load it: docker compose restart web")


if __name__ == "__main__":
    main()
