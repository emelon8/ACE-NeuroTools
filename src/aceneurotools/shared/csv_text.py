"""Edit UTF-8 CSV cells without reserializing untouched cells or line endings."""

from __future__ import annotations

import csv
import io
import os
import tempfile
from pathlib import Path


def _records(text):
    records, cells = [], []
    start = i = 0
    quoted = False
    while i < len(text):
        char = text[i]
        if char == '"':
            if quoted and i + 1 < len(text) and text[i + 1] == '"':
                i += 2
                continue
            if quoted or i == start:
                quoted = not quoted
        if not quoted and char in ",\r\n":
            cells.append(text[start:i])
            if char != ",":
                ending = "\r\n" if text[i : i + 2] == "\r\n" else char
                records.append((cells, ending))
                cells = []
                i += len(ending)
                start = i
                continue
            start = i + 1
        i += 1
    if cells or start < len(text):
        cells.append(text[start:])
        records.append((cells, ""))
    if quoted:
        raise ValueError("CSV contains an unterminated quoted field.")
    return records


def _encode(value, quoted=False):
    buffer = io.StringIO(newline="")
    csv.writer(buffer, quoting=csv.QUOTE_ALL if quoted else csv.QUOTE_MINIMAL, lineterminator="\r\n").writerow(
        [str(value)]
    )
    return buffer.getvalue()[:-2]


def edit_csv(path, *, changes=None, number=None, add_columns=(), append=None):
    """Preserve original spelling of every untouched cell, BOM and record terminator."""
    path = Path(path)
    original = path.read_bytes()
    bom = original.startswith(b"\xef\xbb\xbf")
    text = original.decode("utf-8-sig")
    records = _records(text)
    if not records:
        raise ValueError("CSV requires a header.")
    rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    header = rows[0]
    if "line number" not in header:
        raise ValueError("CSV requires line number.")
    identity = header.index("line number")
    additions = [name for name in add_columns if name not in header]
    target = None
    for index, ((cells, ending), row) in enumerate(zip(records, rows)):
        if not row:
            continue
        if len(row) != len(header):
            raise ValueError("CSV row width differs from header.")
        quote_new = all(cell.startswith('"') for cell in cells)
        if index == 0:
            cells.extend(_encode(name, quote_new) for name in additions)
        else:
            cells.extend(_encode("", quote_new) for _ in additions)
            if row[identity] == str(number):
                if target is not None:
                    raise ValueError("Repeated experiment number.")
                target = index
    columns = header + additions
    if changes:
        if target is None:
            raise ValueError(f"Experiment {number} not found.")
        for key, value in changes.items():
            index = columns.index(key)
            old = records[target][0][index]
            records[target][0][index] = _encode(value, old.startswith('"'))
    if append is not None:
        ending = next((ending for _, ending in records if ending), "\n")
        if records[-1][1] == "":
            records[-1] = records[-1][0], ending
        quote_new = all(cell.startswith('"') for cell in records[0][0])
        records.append(([_encode(append.get(name, ""), quote_new) for name in columns], ending))
    content = ("\ufeff" if bom else "") + "".join(",".join(cells) + ending for cells, ending in records)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".ace-csv-")
    staged = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(staged, path.stat().st_mode & 0o777)
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)
