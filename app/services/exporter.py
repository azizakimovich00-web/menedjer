from __future__ import annotations

import os
from datetime import datetime
from typing import Iterable, List, Sequence

from openpyxl import Workbook


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _file_stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def export_to_xlsx(headers: Sequence[str], rows: Iterable[Sequence], out_dir: str, prefix: str) -> str:
    _ensure_dir(out_dir)
    wb = Workbook()
    ws = wb.active
    ws.append(list(headers))
    for row in rows:
        ws.append(list(row))
    filename = f"{prefix}_{_file_stamp()}.xlsx"
    path = os.path.join(out_dir, filename)
    wb.save(path)
    return path
