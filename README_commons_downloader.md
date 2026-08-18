# Wikimedia Commons Photo Downloader

This folder contains a Python script that downloads 3,500 freely reusable photos from Wikimedia Commons and packages them into zip files of 300 images each.

## What It Downloads

- `landscape`: 1,000 landscape photos
- `people`: 1,000 people/portrait photos
- `narrative`: 1,000 documentary, event, street-life, and activity photos
- `random`: 500 random photos

The script records source page, author, license, license URL, and download URL in `manifest.csv` and `manifest.jsonl`.

## Full Run

From this folder:

```powershell
python .\download_commons_photos.py --out .\commons_photo_dataset --user-agent "YourProjectName/1.0 (your-email@example.com)"
```

The output will be:

```text
commons_photo_dataset/
  photos/
    landscape/
    people/
    narrative/
    random/
  zips/
    photos_part_001.zip
    photos_part_002.zip
    ...
  manifest.csv
  manifest.jsonl
```

## Smaller Test Run

```powershell
python .\download_commons_photos.py --out .\test_dataset --counts landscape=5,people=5,narrative=5,random=5 --zip-size 10
```

## Notes

- Wikimedia may return HTTP 429 if the current network is rate-limited. The script retries and waits automatically.
- For large runs, Wikimedia expects a descriptive `--user-agent` with a real contact email or project URL.
- If the run stops, launch the same command again. Existing downloaded files are kept, and the manifest helps avoid duplicate titles.
- Increase `--delay` if you see many 429 errors:

```powershell
python .\download_commons_photos.py --out .\commons_photo_dataset --delay 3
```

- Reduce file size with a smaller thumbnail width:

```powershell
python .\download_commons_photos.py --out .\commons_photo_dataset --thumb-width 1200
```
