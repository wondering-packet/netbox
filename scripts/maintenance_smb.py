#!/usr/bin/env python3
"""
maintenance_smb.py

Prunes old Jenkins artifacts stored on SMB / shared storage.

Supports BOTH layouts:

A) With branch level (your current layout):
  ROOT/
    <job_name>/
      <branch_name>/        (e.g., main)
        <run_id>/
          artifact_files...

B) Without branch level:
  ROOT/
    <job_name>/
      <run_id>/
        artifact_files...

Logic:
- For each <job_name> under ROOT:
    - If it contains branch directories (like "main"), prune run_id folders inside each branch dir.
    - Else, prune run_id folders directly under the job dir.
- Keep newest N run_id folders (by directory mtime) per (job, branch).

Usage:
  python3 scripts/maintenance_smb.py --root /mnt/jenkins-artifacts --keep 200
  python3 scripts/maintenance_smb.py --root /mnt/jenkins-artifacts --keep 2 --dry-run
"""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunDir:
    path: Path
    mtime: float


def is_run_id_dir(p: Path) -> bool:
    """
    Heuristic: a run_id dir is usually numeric (BUILD_ID), like "1", "38", "204".
    If you ever use non-numeric run IDs, relax this check.
    """
    return p.is_dir() and p.name.isdigit()


def list_run_dirs(parent: Path) -> list[RunDir]:
    """
    Return run_id directories under `parent`, sorted newest -> oldest by mtime.
    """
    runs: list[RunDir] = []
    for child in parent.iterdir():
        if not is_run_id_dir(child):
            continue
        try:
            runs.append(RunDir(path=child, mtime=child.stat().st_mtime))
        except FileNotFoundError:
            continue
    return sorted(runs, key=lambda r: r.mtime, reverse=True)


def delete_dir(p: Path, dry_run: bool) -> None:
    if not p.exists():
        return
    if dry_run:
        print(f"[DRY-RUN] Would delete: {p}")
        return
    shutil.rmtree(p, ignore_errors=True)
    print(f"Deleted: {p}")


def prune_container(container: Path, keep: int, dry_run: bool, label: str) -> None:
    """
    Prune run_id directories inside `container`.
    """
    runs = list_run_dirs(container)
    total = len(runs)

    if total == 0:
        print(f"SKIP: {label} has 0 run(s) detected under {container}")
        return

    if total <= keep:
        print(f"OK: {label} has {total} run(s); nothing to prune.")
        return

    to_delete = runs[keep:]
    print(
        f"PRUNE: {label} has {total} run(s); deleting {len(to_delete)} old run(s).")

    for run in to_delete:
        delete_dir(run.path, dry_run)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True,
                    help="SMB artifacts root (e.g. /mnt/jenkins-artifacts)")
    ap.add_argument("--keep", type=int, default=200,
                    help="Keep newest N runs per job/branch")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show actions without deleting")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    keep = max(0, args.keep)

    if not root.exists() or not root.is_dir():
        print(f"ERROR: root not found or not a directory: {root}")
        return 2

    print(f"Artifacts root : {root}")
    print(f"Keep per scope : {keep} (scope = job[/branch])")
    if args.dry_run:
        print("Mode          : DRY-RUN")

    # Each immediate child is a job directory
    for job_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
        # Detect if this job has a branch level (like main/)
        branch_dirs = [p for p in job_dir.iterdir() if p.is_dir()
                       and not p.name.isdigit()]

        # If there is a "main" dir (or any non-numeric dirs), treat those as branch dirs
        if branch_dirs:
            for branch_dir in sorted(branch_dirs):
                label = f"{job_dir.name}/{branch_dir.name}"
                prune_container(branch_dir, keep, args.dry_run, label)
        else:
            # Flat layout: run_id dirs directly under job_dir
            label = f"{job_dir.name}"
            prune_container(job_dir, keep, args.dry_run, label)

    print("Maintenance pruning complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
