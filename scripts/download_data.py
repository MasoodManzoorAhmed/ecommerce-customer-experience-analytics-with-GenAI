"""Download the Olist Brazilian e-commerce dataset from Kaggle into data/raw/.

Kaggle serves public datasets without login through its download endpoint, so
no API key is needed. Run from the project root:

    python scripts/download_data.py
"""

from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

DATASET = "olistbr/brazilian-ecommerce"
URL = f"https://www.kaggle.com/api/v1/datasets/download/{DATASET}"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

EXPECTED_FILES = [
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
]


def download_zip(url: str) -> bytes:
    """Return the dataset archive as bytes (follows Kaggle's redirect to storage)."""
    request = urllib.request.Request(url, headers={"User-Agent": "olist-portfolio/1.0"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


def extract_expected(archive: bytes, target: Path) -> list[Path]:
    """Extract only the expected CSVs (by base name) so no unexpected paths are written."""
    target.mkdir(parents=True, exist_ok=True)
    written = []
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        members = {Path(name).name: name for name in zf.namelist()}
        missing = [f for f in EXPECTED_FILES if f not in members]
        if missing:
            raise FileNotFoundError(f"Archive is missing expected files: {missing}")
        for name in EXPECTED_FILES:
            out = target / name
            out.write_bytes(zf.read(members[name]))
            written.append(out)
    return written


def main() -> int:
    if all((RAW_DIR / f).exists() for f in EXPECTED_FILES):
        print(f"All {len(EXPECTED_FILES)} files already present in {RAW_DIR}; nothing to do.")
        return 0
    print(f"Downloading {DATASET} ...")
    archive = download_zip(URL)
    print(f"Downloaded {len(archive) / 1e6:.1f} MB; extracting to {RAW_DIR}")
    for path in extract_expected(archive, RAW_DIR):
        print(f"  {path.name:45s} {path.stat().st_size / 1e6:8.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
