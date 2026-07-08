from io import BytesIO
import re
import unicodedata

import pandas as pd
from fastapi import HTTPException, UploadFile

# Import files are small rosters, never bulk data: keep hard limits so a
# malformed or malicious upload (e.g. an Excel bomb) cannot exhaust memory.
MAX_IMPORT_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_IMPORT_ROWS = 2000


def normalize_header(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.strip().lower()
    # Remove trailing asterisks and other marker characters (*, †, etc.)
    normalized = re.sub(r"[*†‡]+$", "", normalized)
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


async def parse_tabular_file(file: UploadFile) -> list[dict]:
    content = await file.read()
    if len(content) > MAX_IMPORT_FILE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo de importacion excede el maximo de {MAX_IMPORT_FILE_BYTES // (1024 * 1024)} MB",
        )
    try:
        if (file.filename or "").lower().endswith(".csv"):
            df = pd.read_csv(BytesIO(content))
        else:
            df = pd.read_excel(BytesIO(content))
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="No se pudo leer el archivo. Verifica que sea un CSV o Excel valido.",
        ) from exc
    if len(df) > MAX_IMPORT_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo tiene {len(df)} filas; el maximo permitido es {MAX_IMPORT_ROWS}",
        )
    df.columns = [normalize_header(column) for column in df.columns]
    return df.fillna("").to_dict(orient="records")
