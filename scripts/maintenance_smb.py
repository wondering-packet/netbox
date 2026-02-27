#!/usr/bin/env python3
"""
maintenance_prune_smb.py

Prunes old Jenkins artifacts stored on SMB / shared storage.

Expected directory layout:

  ROOT/
    <job_name_1>/
      <run_id>/
        artifact_files...
    <job_name_2>/
      <run_id>/
        artifact_files...

Logic:
- Each immediate directory under ROOT is treated as a Jenkins job
- Inside each job directory:
    - run_id folders are sorted by last modified time (mtime)
    - newest N run_id folders are kept
    - older run_id folders are deleted

Usage:
  python3 maintenance_prune_smb.py --root /mnt/jenkins-artifacts --keep 200
  python3 maintenance_prune_smb.py --root /mnt/jenkins-artifacts --keep 200 --dry-run
"""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunDir:
    """Represents one <run_id> directory."""
    path: Path
    mtime: float


def list_run_dirs(job_dir: Path) -> list[RunDir]:
    """
    List all run_id directories under a job directory,
    sorted newest -> oldest by modification time.
    """
    runs: list[RunDir] = []

    for child in job_dir.iterdir():
        if not child.is_dir():
            continue
        try:
            runs.append(RunDir(path=child, mtime=child.stat().st_mtime))
        except FileNotFoundError:
            # Directory vanished mid-scan (race condition)
            continue

    return sorted(runs, key=lambda r: r.mtime, reverse=True)


def delete_dir(p: Path, dry_run: bool) -> None:
    """
    Delete a directory tree safely.
    In dry-run mode, only print what would be deleted.
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
    ap.add_argument(
        "--root",
        required=True,
        help="Root directory containing per-job artifact folders (SMB mount)",
    )
    ap.add_argument(
        "--keep",
        type=int,
        default=3,
        help="Number of newest run_id folders to keep per job",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without deleting anything",
    )
    args = ap.parse_args()

    root = Path(args.root).resolve()
    keep = max(0, args.keep)

    if not root.exists() or not root.is_dir():
        print(f"ERROR: root does not exist or is not a directory: {root}")
        return 2

    print(f"Artifacts root : {root}")
    print(f"Keep per job  : {keep}")
    if args.dry_run:
        print("Mode          : DRY-RUN")

    # Each immediate child under ROOT is a Jenkins job directory
    for job_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        runs = list_run_dirs(job_dir)
        total = len(runs)

        if total <= keep:
            print(f"OK: {job_dir.name} has {total} run(s); nothing to prune.")
            continue

        to_delete = runs[keep:]
        print(
            f"PRUNE: {job_dir.name} has {total} run(s); "
            f"deleting {len(to_delete)} old run(s)."
        )

        for run in to_delete:
            delete_dir(run.path, args.dry_run)

    print("Maintenance pruning complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
