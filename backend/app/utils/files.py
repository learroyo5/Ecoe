from io import BytesIO
import re
import unicodedata

import pandas as pd
from fastapi import UploadFile


def normalize_header(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


async def parse_tabular_file(file: UploadFile) -> list[dict]:
    content = await file.read()
    if file.filename.lower().endswith(".csv"):
        df = pd.read_csv(BytesIO(content))
    else:
        df = pd.read_excel(BytesIO(content))
    df.columns = [normalize_header(column) for column in df.columns]
    return df.fillna("").to_dict(orient="records")
