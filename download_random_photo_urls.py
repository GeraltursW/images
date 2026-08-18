#!/usr/bin/env python3
"""
Download 3,500 photos from random-image URL services and package them into
zip files of 300 images each.

Default source:
- loremflickr.com for tagged categories

Fallback:
- picsum.photos for fully random images

This downloader does not need an API key. It records the final redirected image
URL for each saved file in manifest.csv and manifest.jsonl.
"""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import os
import random
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_COUNTS = {
    "landscape": 1000,
    "people": 1000,
    "narrative": 1000,
    "random": 500,
}

TAGS = {
    "landscape": [
        "landscape",
        "mountain",
        "forest",
        "coast",
        "lake",
        "desert",
        "sunset,landscape",
        "nature,landscape",
    ],
    "people": [
        "people",
        "portrait",
        "person",
        "street,people",
        "worker,people",
        "friends,people",
        "family,people",
        "face,portrait",
    ],
    "narrative": [
        "street,life",
        "documentary",
        "event,people",
        "market,people",
        "festival,people",
        "work,people",
        "city,people",
        "travel,people",
    ],
    "random": [
        "random",
        "photo",
        "travel",
        "city",
        "nature",
        "people",
        "architecture",
        "street",
    ],
}


def parse_counts(raw: str | None) -> Dict[str, int]:
    counts = dict(DEFAULT_COUNTS)
    if not raw:
        return counts
    for piece in raw.split(","):
        key, value = piece.split("=", 1)
        key = key.strip()
        if key not in counts:
            raise ValueError(f"Unknown category: {key}")
        counts[key] = int(value)
    return counts


def build_url(source: str, width: int, height: int, category: str, unique: str) -> str:
    tag = random.choice(TAGS[category])
    if source == "loremflickr":
        encoded_tag = urllib.parse.quote(tag)
        return f"https://loremflickr.com/{width}/{height}/{encoded_tag}?lock={unique}"
    if source == "picsum":
        return f"https://picsum.photos/seed/{unique}/{width}/{height}"
    raise ValueError(f"Unknown source: {source}")


def extension_from_response(response: Any) -> str:
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if content_type in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    if content_type == "image/png":
        return ".png"
    guessed = mimetypes.guess_extension(content_type)
    return guessed if guessed in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"


def download_image(url: str, dest_without_ext: Path, user_agent: str, retries: int) -> Dict[str, str] | None:
    headers = {"User-Agent": user_agent, "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"}
    last_error = ""
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=60) as response:
                content_type = response.headers.get("Content-Type", "")
                if not content_type.lower().startswith("image/"):
                    last_error = f"not an image: {content_type}"
                    time.sleep(min(60, 2 ** attempt))
                    continue
                ext = extension_from_response(response)
                dest = dest_without_ext.with_suffix(ext)
                tmp = dest.with_suffix(dest.suffix + ".part")
                with tmp.open("wb") as handle:
                    shutil.copyfileobj(response, handle)
                if tmp.stat().st_size < 1024:
                    tmp.unlink(missing_ok=True)
                    last_error = "file too small"
                    time.sleep(min(60, 2 ** attempt))
                    continue
                tmp.replace(dest)
                return {
                    "filename": str(dest),
                    "final_url": response.geturl(),
                    "content_type": content_type,
                }
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
            wait = min(120, 2 ** attempt)
            print(f"Download failed: {last_error}; waiting {wait}s", file=sys.stderr)
            time.sleep(wait)
    print(f"Skipped after retries: {url} ({last_error})", file=sys.stderr)
    return None


def append_manifest(csv_path: Path, jsonl_path: Path, row: Dict[str, Any]) -> None:
    new_csv = not csv_path.exists()
    fieldnames = ["category", "filename", "source", "request_url", "final_url", "content_type"]
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if new_csv:
            writer.writeheader()
        writer.writerow(row)
    with jsonl_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def existing_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len([p for p in path.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}])


def download_category(
    root: Path,
    category: str,
    wanted: int,
    source: str,
    width: int,
    height: int,
    delay: float,
    retries: int,
    user_agent: str,
    workers: int,
) -> int:
    folder = root / "photos" / category
    folder.mkdir(parents=True, exist_ok=True)
    csv_path = root / "manifest.csv"
    jsonl_path = root / "manifest.jsonl"
    current = existing_count(folder)
    print(f"[{category}] already have {current}/{wanted}")

    if workers > 1:
        next_index = current + 1
        while current < wanted:
            batch_size = min(workers * 4, wanted - current)
            futures = {}
            with ThreadPoolExecutor(max_workers=workers) as executor:
                for _ in range(batch_size):
                    unique = f"{category}-{next_index}-{random.randint(100000, 999999)}"
                    request_url = build_url(source, width, height, category, unique)
                    dest_without_ext = folder / f"{category}_{next_index:04d}_{unique}"
                    future = executor.submit(download_image, request_url, dest_without_ext, user_agent, retries)
                    futures[future] = (request_url, next_index)
                    next_index += 1

                for future in as_completed(futures):
                    request_url, _index = futures[future]
                    result = future.result()
                    if result is None:
                        continue
                    current += 1
                    filename = Path(result["filename"]).relative_to(root)
                    append_manifest(
                        csv_path,
                        jsonl_path,
                        {
                            "category": category,
                            "filename": str(filename),
                            "source": source,
                            "request_url": request_url,
                            "final_url": result["final_url"],
                            "content_type": result["content_type"],
                        },
                    )
                    if current % 25 == 0 or current == wanted:
                        print(f"[{category}] downloaded {current}/{wanted}")
            time.sleep(delay)
        return current

    while current < wanted:
        current += 1
        unique = f"{category}-{current}-{random.randint(100000, 999999)}"
        request_url = build_url(source, width, height, category, unique)
        dest_without_ext = folder / f"{category}_{current:04d}_{unique}"
        result = download_image(request_url, dest_without_ext, user_agent, retries)
        if result is None:
            current -= 1
            time.sleep(delay)
            continue
        filename = Path(result["filename"]).relative_to(root)
        append_manifest(
            csv_path,
            jsonl_path,
            {
                "category": category,
                "filename": str(filename),
                "source": source,
                "request_url": request_url,
                "final_url": result["final_url"],
                "content_type": result["content_type"],
            },
        )
        if current % 25 == 0 or current == wanted:
            print(f"[{category}] downloaded {current}/{wanted}")
        time.sleep(delay)
    return current


def zip_photos(root: Path, chunk_size: int) -> int:
    photos_root = root / "photos"
    zips_root = root / "zips"
    zips_root.mkdir(parents=True, exist_ok=True)
    for old_zip in zips_root.glob("photos_part_*.zip"):
        old_zip.unlink()
    files = sorted(p for p in photos_root.rglob("*") if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    part_count = 0
    for index in range(0, len(files), chunk_size):
        part_count += 1
        zip_path = zips_root / f"photos_part_{part_count:03d}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for file_path in files[index : index + chunk_size]:
                archive.write(file_path, file_path.relative_to(root))
        print(f"wrote {zip_path} ({len(files[index:index + chunk_size])} files)")
    return part_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Download random/tagged photos and zip them.")
    parser.add_argument("--out", default="random_photo_dataset")
    parser.add_argument("--counts", help="Example: landscape=1000,people=1000,narrative=1000,random=500")
    parser.add_argument("--source", choices=["loremflickr", "picsum"], default="loremflickr")
    parser.add_argument("--zip-size", type=int, default=300)
    parser.add_argument("--width", type=int, default=1200)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--workers", type=int, default=1, help="Concurrent downloads. Try 4-8 for Picsum.")
    parser.add_argument("--user-agent", default="Mozilla/5.0 PhotoDatasetDownloader/1.0")
    parser.add_argument("--skip-zip", action="store_true")
    args = parser.parse_args()

    root = Path(args.out).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    counts = parse_counts(args.counts)

    print(f"Output: {root}")
    print(f"Source: {args.source}")
    for category, wanted in counts.items():
        download_category(
            root,
            category,
            wanted,
            args.source,
            args.width,
            args.height,
            args.delay,
            args.retries,
            args.user_agent,
            args.workers,
        )

    if not args.skip_zip:
        zip_photos(root, args.zip_size)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
