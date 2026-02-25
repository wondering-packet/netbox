#!/usr/bin/env python3
"""
warning: had chatgpt write this script. review carefully.

cleanup_run_artifacts.py

Goal:
  Keep only the latest N RUN_ID artifact folders and delete older ones.

Folder layout (per build):
  ./artifacts/<RUN_ID>/*
  ./artifacts-cleanup/<RUN_ID>/*

What "latest" means:
  We rank each RUN_ID by the most recent modification time (mtime) of its folder
  across both roots. Newest RUN_IDs are kept, older ones are deleted.

Safety:
  Use --dry-run first to see what would be deleted without actually deleting anything.

Examples:
  python3 cleanup_run_artifacts.py --keep 200 --dry-run
  python3 cleanup_run_artifacts.py --keep 200
  python3 cleanup_run_artifacts.py --artifacts ./artifacts --cleanup ./artifacts-cleanup --keep 200
"""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunInfo:
    run_id: str
    mtime: float  # "last modified time" (seconds since epoch)


def _dir_mtime(p: Path) -> float:
    """
    Return directory modification time. If the dir doesn't exist, return 0.
    """
    try:
        return p.stat().st_mtime
    except FileNotFoundError:
        return 0.0


def _list_run_ids(root: Path) -> set[str]:
    """
    Return all immediate subdirectory names under a root.
    Example: root/artifacts/12345 -> run_id "12345"
    """
    if not root.exists():
        return set()

    run_ids: set[str] = set()
    for child in root.iterdir():
        if child.is_dir():
            run_ids.add(child.name)
    return run_ids


def _delete_dir(p: Path, dry_run: bool) -> None:
    """
    Delete a directory tree (like rm -rf), or print what would happen in dry-run mode.
    """
    if not p.exists():
        return
    if dry_run:
        print(f"[DRY-RUN] Would delete: {p}")
        return
    shutil.rmtree(p, ignore_errors=True)
    print(f"Deleted: {p}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", default="./artifacts",
                    help="Path to artifacts root")
    ap.add_argument("--cleanup", default="./artifacts-cleanup",
                    help="Path to artifacts-cleanup root")
    ap.add_argument("--keep", type=int, default=200,
                    help="How many newest RUN_IDs to keep")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show actions without deleting anything")
    args = ap.parse_args()

    artifacts_root = Path(args.artifacts).resolve()
    cleanup_root = Path(args.cleanup).resolve()
    keep_n = max(0, args.keep)

    # 1) Discover RUN_IDs from both roots (union).
    run_ids = _list_run_ids(artifacts_root) | _list_run_ids(cleanup_root)

    if not run_ids:
        print("No RUN_ID folders found. Nothing to do.")
        return 0

    # 2) Build a RunInfo list with a "recency score" (mtime).
    # We use the max mtime across both locations so the RUN_ID reflects latest activity.
    runs: list[RunInfo] = []
    for rid in run_ids:
        mtime = max(
            _dir_mtime(artifacts_root / rid),
            _dir_mtime(cleanup_root / rid),
        )
        runs.append(RunInfo(run_id=rid, mtime=mtime))

    # 3) Sort runs: newest first.
    runs.sort(key=lambda r: r.mtime, reverse=True)

    # 4) Decide which RUN_IDs to keep vs delete.
    keep_set = {r.run_id for r in runs[:keep_n]}
    delete_set = [r.run_id for r in runs[keep_n:]]

    print(f"Artifacts root:        {artifacts_root}")
    print(f"Artifacts-cleanup root:{cleanup_root}")
    print(f"Total RUN_IDs found:   {len(runs)}")
    print(f"Keeping newest:        {min(keep_n, len(runs))}")
    print(f"Deleting older:        {len(delete_set)}")
    if args.dry_run:
        print("Mode: DRY-RUN (no deletions will happen)")

    # 5) Delete old RUN_ID folders from BOTH roots (if they exist).
    for rid in delete_set:
        _delete_dir(artifacts_root / rid, args.dry_run)
        _delete_dir(cleanup_root / rid, args.dry_run)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
