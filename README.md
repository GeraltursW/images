# Image Dataset

This repository contains a 3,500-photo dataset downloaded with `download_random_photo_urls.py`.

## Contents

- `zips/`: 12 zip archives, packaged at 300 photos per archive except the final archive.
- `manifest.csv`: CSV record of every downloaded image.
- `manifest.jsonl`: JSON Lines version of the manifest.
- `download_random_photo_urls.py`: downloader used to generate the dataset.
- `README_commons_downloader.md`: earlier Wikimedia Commons downloader notes.

## Counts

- `landscape`: 1,000
- `people`: 1,000
- `narrative`: 1,000
- `random`: 500

The source used for the final completed run was Picsum. The category names are folder/package buckets; Picsum itself serves random photos and does not provide strict semantic labels.
