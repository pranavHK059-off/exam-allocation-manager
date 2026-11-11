"""Run the five synthetic CSV datasets through the allocation engine.

Run from the project root with:
    python verify_test_datasets.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys
import pandas as pd

from allocation_engine import allocate

ROOT = Path(__file__).resolve().parent
DATA_ROOT = ROOT / "test_datasets"
REQUIRED = {
    "students": {"candidate_id", "candidate_name", "subject", "paper", "date", "start_time", "duration_min", "extra_time_min", "equipment"},
    "rooms": {"room_id", "capacity", "unusable_seats", "available_from", "available_to", "room_type", "status", "notes"},
    "proctors": {"proctor_id", "proctor_name", "available_from", "available_to", "subjects_taught"},
    "equipment": {"equipment_type", "quantity"},
}


def load_table(folder: Path, kind: str) -> list[dict]:
    path = folder / f"{kind}.csv"
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = REQUIRED[kind] - set(frame.columns)
    if missing:
        raise AssertionError(f"{path.name}: missing columns {sorted(missing)}")
    if frame.empty:
        raise AssertionError(f"{path.name}: no data rows")
    return frame.to_dict(orient="records")


def verify(folder: Path) -> None:
    records = {kind: load_table(folder, kind) for kind in REQUIRED}
    result = allocate(
        records["students"], records["rooms"], records["proctors"], records["equipment"], options={}
    )
    if result["unresolved_count"]:
        unresolved_reasons = Counter(reason for row in result["entries"] for reason in row["reason_codes"])
        raise AssertionError(f"{folder.name}: {result['unresolved_count']} unresolved; reasons={unresolved_reasons}")
    if result["meta"]["independent_check_issues"]:
        raise AssertionError(f"{folder.name}: independent-check issues {result['meta']['independent_check_issues']}")

    occupancy = Counter(
        (row["room_id"], row["date"], row["start_minute"], row["subject"], row["paper"])
        for row in result["entries"] if row["room_id"]
    )
    capacities = {
        (row["room_id"], row["date"], row["start_minute"], row["subject"], row["paper"]): int(row["room_capacity"])
        for row in result["entries"] if row["room_id"]
    }
    underfilled = [(key, n, capacities[key]) for key, n in occupancy.items() if n != capacities[key]]
    if underfilled:
        raise AssertionError(f"{folder.name}: expected exact room fills, got {underfilled[:5]}")

    print(
        f"PASS {folder.name}: {result['entry_count']} rows; "
        f"{result['meta']['room_bookings']} fully occupied room bookings; "
        f"{result['meta']['proctor_bookings']} proctor bookings; 0 unresolved; 0 audit issues"
    )


def main() -> int:
    folders = sorted(path for path in DATA_ROOT.iterdir() if path.is_dir() and (path / "students.csv").exists())
    if len(folders) != 5:
        print(f"Expected exactly five dataset folders under {DATA_ROOT}; found {len(folders)}", file=sys.stderr)
        return 2
    try:
        for folder in folders:
            verify(folder)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print("All five exact-fit datasets passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
