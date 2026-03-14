from io import BytesIO

import pandas as pd
from fastapi import UploadFile


async def parse_tabular_file(file: UploadFile) -> list[dict]:
    content = await file.read()
    if file.filename.lower().endswith(".csv"):
        df = pd.read_csv(BytesIO(content))
    else:
        df = pd.read_excel(BytesIO(content))
    return df.fillna("").to_dict(orient="records")
