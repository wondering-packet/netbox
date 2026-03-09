#!/usr/bin/env python3
"""
maintenance_smb.py

Prune old Jenkins artifact folders directly from an SMB share using `smbclient`.

This script is designed for the following real-world setup:

    SMB server : dc-01.intra.wonderingpacket.com # this is my lab server. it's passes as a parameter from the Jenkins pipeline.
    SMB share  : jenkins-artifacts # another parameter from the Jenkins pipeline.
    SMB base   : netbox # another parameter from the Jenkins pipeline.

Expected remote layout under SMB_BASE:

A) Flat layout (no branch folder)
   netbox/
     <job_name>/
       <run_id>/
         artifact_files...

B) Branch layout
   netbox/
     <job_name>/
       <branch_name>/
         <run_id>/
           artifact_files...

Examples from your environment:

    netbox/
      Netbox_Git_WAN_IP_Cleanup_Weekly/
        3/
        4/
        5/

      Netbox_Git_WAN_IP_Reconcilation_Auto/
        main/
          18/
          19/
          23/
        feature-vipin-dev-2/
          4/
          5/

How pruning works:
- Each top-level directory under SMB_BASE is treated as a Jenkins job.
- For each job:
    - If numeric run folders exist directly under the job, prune those.
    - For each non-numeric child folder (such as a branch folder), if numeric
      run folders exist under it, prune those too.
- Newest runs are determined by numeric run ID, not mtime.
  This is intentional because Jenkins build numbers are numeric and monotonic.

Why numeric sort instead of SMB timestamps?
- Parsing timestamps from `smbclient ls` output is possible, but messy and brittle.
- Jenkins run IDs are reliable enough for retention pruning.
- Build 26 is newer than build 23. Nice and boring. We like boring here.

Security note:
- The script accepts --username and --password because the Jenkins pipeline
  is passing them in.
- Internally, the script writes them to a temporary smbclient auth file and
  uses `smbclient -A <authfile>` so credentials are not re-exposed on child
  process command lines.

Requirements:
- `smbclient` must be installed on the Jenkins agent/node running this script.

Example pipeline invocation:

    python3 scripts/maintenance_smb.py \
      --server "dc-01.intra.wonderingpacket.com" \
      --share "jenkins-artifacts" \
      --base "netbox" \
      --keep 200 \
      --username "$SMB_CREDS_USR" \
      --password "$SMB_CREDS_PSW"

Dry-run example:

    python3 scripts/maintenance_smb.py \
      --server "dc-01.intra.wonderingpacket.com" \
      --share "jenkins-artifacts" \
      --base "netbox" \
      --keep 2 \
      --dry-run \
      --username "$SMB_CREDS_USR" \
      --password "$SMB_CREDS_PSW"
"""

from __future__ import annotations

import argparse
import os
import posixpath
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import List


# -----------------------------------------------------------------------------
# Data models
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class RemoteEntry:
    """
    Represents a single directory entry returned by `smbclient ls`.

    We only really care about:
    - name
    - whether it is a directory

    Example smbclient output line (directory):
        main                                D        0  Mon Mar  9 15:28:43 2026

    Example smbclient output line (file):
        3_2026-03-09-10-38-43_cleanup_logs.json      A    1234  Mon Mar  9 ...

    The parser is intentionally conservative:
    - if a line doesn't look like a valid entry, we ignore it
    """
    name: str
    is_dir: bool


@dataclass(frozen=True)
class RunFolder:
    """
    Represents a Jenkins build/run folder.

    Example names:
        3
        19
        204

    We convert the folder name to an integer so we can sort newest -> oldest.
    """
    name: str
    number: int


# -----------------------------------------------------------------------------
# SMB client wrapper
# -----------------------------------------------------------------------------

class SMBClient:
    """
    Thin wrapper around the `smbclient` CLI.

    Why wrap it?
    - keeps subprocess code in one place
    - keeps authentication handling in one place
    - makes the main pruning logic much easier to read

    Important safety rule:
    - all remote paths are treated as relative to `base`
    - the script never intentionally operates outside that base path
    """

    def __init__(
        self,
        server: str,
        share: str,
        base: str,
        username: str,
        password: str,
        smbclient_bin: str = "smbclient",
    ) -> None:
        self.server = server
        self.share = share
        self.base = self._normalize_rel(base)
        self.username = username
        self.password = password
        self.smbclient_bin = smbclient_bin
        self.service = f"//{self.server}/{self.share}"

        # Create a temporary auth file for smbclient.
        # This avoids passing credentials directly on child process CLI flags.
        self._auth_file = tempfile.NamedTemporaryFile(
            mode="w",
            prefix="smbclient-auth-",
            delete=False,
            encoding="utf-8",
        )
        self._auth_file.write(f"username = {self.username}\n")
        self._auth_file.write(f"password = {self.password}\n")
        self._auth_file.flush()
        self._auth_file.close()

        # Lock down file permissions.
        os.chmod(self._auth_file.name, 0o600)

    def close(self) -> None:
        """Best-effort cleanup of the temporary auth file."""
        try:
            os.unlink(self._auth_file.name)
        except FileNotFoundError:
            pass

    def _normalize_rel(self, rel_path: str) -> str:
        """
        Normalize a relative SMB path and prevent path traversal.

        Allowed:
            ""
            "netbox"
            "job/main"
            "job/main/26"

        Rejected:
            "/absolute/path"
            "../escape"
            "job/../../escape"

        We keep everything relative because this script must stay inside the
        SMB base boundary (`netbox` in your case).
        """
        if rel_path is None:
            return ""

        rel_path = rel_path.strip().replace("\\", "/")

        if rel_path in ("", "."):
            return ""

        if rel_path.startswith("/"):
            raise ValueError(
                f"Absolute remote path is not allowed: {rel_path}")

        normalized = posixpath.normpath(rel_path)

        if normalized == ".":
            return ""

        if normalized.startswith("../") or normalized == "..":
            raise ValueError(f"Path escapes base boundary: {rel_path}")

        return normalized

    def _full_dir(self, rel_path: str) -> str:
        """
        Combine SMB base + relative path.

        Examples:
            base='netbox', rel=''                  -> 'netbox'
            base='netbox', rel='job1'             -> 'netbox/job1'
            base='netbox', rel='job1/main'        -> 'netbox/job1/main'
        """
        rel_path = self._normalize_rel(rel_path)
        if not rel_path:
            return self.base
        return posixpath.join(self.base, rel_path)

    def _run(self, remote_dir: str, command: str) -> str:
        """
        Execute an smbclient command and return stdout.

        We use:
            smbclient //<server>/<share> -A <authfile> -D <remote_dir> -c <command>

        Example:
            smbclient //server/share -A /tmp/auth -D netbox -c 'ls'
        """
        remote_dir = self._normalize_rel(remote_dir)
        full_dir = self._full_dir(remote_dir)

        cmd = [
            self.smbclient_bin,
            self.service,
            "-A", self._auth_file.name,
            "-D", full_dir,
            "-c", command,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            raise RuntimeError(
                f"smbclient command failed\n"
                f"  service : {self.service}\n"
                f"  dir     : {full_dir}\n"
                f"  command : {command}\n"
                f"  rc      : {result.returncode}\n"
                f"  stdout  : {stdout}\n"
                f"  stderr  : {stderr}"
            )

        return result.stdout

    def list_dirs(self, rel_path: str) -> List[RemoteEntry]:
        """
        List directory entries under the given remote path and return only directories.

        This method parses `smbclient ls` output.

        Why only directories?
        - pruning logic only cares about:
            jobs
            branch folders
            run folders
        - artifact files are irrelevant for discovery
        """
        output = self._run(rel_path, "ls")
        entries: List[RemoteEntry] = []

        for line in output.splitlines():
            entry = self._parse_ls_line(line)
            if entry is None:
                continue
            if entry.is_dir:
                entries.append(entry)

        return entries

    def delete_tree(self, rel_path: str) -> None:
        """
        Recursively delete a directory tree using `smbclient deltree`.

        Example:
            rel_path = "Netbox_Git_WAN_IP_Reconcilation_Auto/main/18"

        We run the command from SMB_BASE and delete the relative path from there.
        That keeps the deletion boundary anchored under `netbox`.
        """
        rel_path = self._normalize_rel(rel_path)

        if not rel_path:
            raise ValueError("Refusing to delete empty path.")

        # Basic extra guardrail: never let this script delete the base itself.
        if rel_path in (".", "/"):
            raise ValueError("Refusing to delete invalid path.")

        # Use double quotes around the target so job/folder names with spaces
        # have a better chance of behaving correctly.
        self._run("", f'deltree "{rel_path}"')

    @staticmethod
    def _parse_ls_line(line: str) -> RemoteEntry | None:
        """
        Parse a single line of `smbclient ls` output.

        Strategy:
        - split on 2+ spaces because smbclient aligns columns using runs of spaces
        - expected rough shape:
              <name>  <attrs>  <size>  <date...>

        Examples:
            main                                D        0  Mon Mar  9 15:28:43 2026
            3                                   D        0  Mon Mar  9 10:38:43 2026
            file.json                           A      123  Mon Mar  9 10:38:43 2026

        Notes:
        - "." and ".." are ignored
        - if the line is weird, we ignore it rather than exploding dramatically
        """
        raw = line.rstrip()
        if not raw.strip():
            return None

        # smbclient often prefixes lines with spaces. That's fine.
        parts = re.split(r"\s{2,}", raw.strip(), maxsplit=3)
        if len(parts) < 4:
            return None

        name, attrs, _size, _date = parts

        if name in (".", ".."):
            return None

        is_dir = "D" in attrs
        return RemoteEntry(name=name, is_dir=is_dir)


# -----------------------------------------------------------------------------
# Pruning helpers
# -----------------------------------------------------------------------------

def is_run_id_name(name: str) -> bool:
    """
    Determine whether a folder name looks like a Jenkins build/run folder.

    We intentionally define a run folder as purely numeric:
        "1", "27", "204"

    This fits Jenkins build numbers and avoids accidental deletion of random
    folders with human names.

    If you ever switch to non-numeric run IDs, this logic must be updated.
    """
    return name.isdigit()


def list_run_folders(smb: SMBClient, rel_container: str) -> List[RunFolder]:
    """
    Return numeric run folders under a remote container, sorted newest -> oldest.

    Examples:
        rel_container = "Netbox_Git_WAN_IP_Cleanup_Weekly"
        rel_container = "Netbox_Git_WAN_IP_Reconcilation_Auto/main"
    """
    runs: List[RunFolder] = []

    for entry in smb.list_dirs(rel_container):
        if not is_run_id_name(entry.name):
            continue
        runs.append(RunFolder(name=entry.name, number=int(entry.name)))

    # Newest first, based on Jenkins build number
    runs.sort(key=lambda r: r.number, reverse=True)
    return runs


def delete_run_folder(smb: SMBClient, rel_path: str, dry_run: bool) -> None:
    """
    Delete a single remote run folder.

    Example:
        Netbox_Git_WAN_IP_Reconcilation_Auto/main/18
    """
    if dry_run:
        print(f"[DRY-RUN] Would delete: {rel_path}")
        return

    smb.delete_tree(rel_path)
    print(f"Deleted: {rel_path}")


def prune_container(
    smb: SMBClient,
    rel_container: str,
    keep: int,
    dry_run: bool,
    label: str,
) -> None:
    """
    Prune run folders inside a single container.

    A "container" means one of:
    - a flat job directory
        Example: Netbox_Git_WAN_IP_Cleanup_Weekly
    - a branch directory under a job
        Example: Netbox_Git_WAN_IP_Reconcilation_Auto/main

    The label is just human-readable logging text.
    """
    runs = list_run_folders(smb, rel_container)
    total = len(runs)

    if total == 0:
        print(f"SKIP: {label} has 0 run(s) under {rel_container}")
        return

    if total <= keep:
        print(f"OK: {label} has {total} run(s); nothing to prune.")
        return

    to_delete = runs[keep:]
    print(
        f"PRUNE: {label} has {total} run(s); "
        f"keeping {keep}, deleting {len(to_delete)} old run(s)."
    )

    for run in to_delete:
        run_rel = posixpath.join(rel_container, run.name)
        delete_run_folder(smb, run_rel, dry_run)


def process_job(
    smb: SMBClient,
    job_name: str,
    keep: int,
    dry_run: bool,
) -> None:
    """
    Process one Jenkins job under SMB_BASE.

    Discovery logic:
    - Direct numeric folders under the job are treated as flat run folders.
    - Non-numeric child folders are treated as possible branch folders.
      If they contain numeric run folders, they are pruned as branch containers.

    This handles both layouts safely and avoids hardcoding job-specific behavior.
    """
    job_rel = job_name
    children = smb.list_dirs(job_rel)

    direct_run_dirs = [e.name for e in children if is_run_id_name(e.name)]
    possible_branch_dirs = [
        e.name for e in children if not is_run_id_name(e.name)]

    # Layout A: direct job/run_id folders
    if direct_run_dirs:
        prune_container(
            smb=smb,
            rel_container=job_rel,
            keep=keep,
            dry_run=dry_run,
            label=job_name,
        )

    # Layout B: job/branch/run_id folders
    for subdir in sorted(possible_branch_dirs):
        branch_rel = posixpath.join(job_rel, subdir)
        branch_runs = list_run_folders(smb, branch_rel)

        if not branch_runs:
            # Not a run container. Could be a random helper folder someday.
            print(f"SKIP: {job_name}/{subdir} has no numeric run folders.")
            continue

        prune_container(
            smb=smb,
            rel_container=branch_rel,
            keep=keep,
            dry_run=dry_run,
            label=f"{job_name}/{subdir}",
        )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Prune old Jenkins artifact folders from an SMB share."
    )
    ap.add_argument(
        "--server",
        required=True,
        help="SMB server hostname or IP (e.g. dc-01.intra.wonderingpacket.com)",
    )
    ap.add_argument(
        "--share",
        required=True,
        help="SMB share name (e.g. jenkins-artifacts)",
    )
    ap.add_argument(
        "--base",
        required=True,
        help="Base folder inside the share to operate under (e.g. netbox)",
    )
    ap.add_argument(
        "--keep",
        type=int,
        default=200,
        help="Keep newest N runs per job or per job/branch container",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without deleting it",
    )
    ap.add_argument(
        "--username",
        required=True,
        help="SMB username (passed from Jenkins credentials)",
    )
    ap.add_argument(
        "--password",
        required=True,
        help="SMB password (passed from Jenkins credentials)",
    )
    ap.add_argument(
        "--smbclient-bin",
        default="smbclient",
        help="Path to smbclient binary (default: smbclient)",
    )

    args = ap.parse_args()

    keep = max(0, args.keep)

    smb = SMBClient(
        server=args.server,
        share=args.share,
        base=args.base,
        username=args.username,
        password=args.password,
        smbclient_bin=args.smbclient_bin,
    )

    try:
        print(f"SMB server     : {args.server}")
        print(f"SMB share      : {args.share}")
        print(f"SMB base       : {args.base}")
        print(f"Keep per scope : {keep} (scope = job[/branch])")
        if args.dry_run:
            print("Mode           : DRY-RUN")

        # List top-level directories under SMB_BASE.
        # Each one is treated as a Jenkins job folder.
        jobs = sorted(entry.name for entry in smb.list_dirs(""))

        if not jobs:
            print("No job directories found under SMB base.")
            return 0

        for job_name in jobs:
            process_job(
                smb=smb,
                job_name=job_name,
                keep=keep,
                dry_run=args.dry_run,
            )

        print("Maintenance pruning complete.")
        return 0

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    finally:
        smb.close()


if __name__ == "__main__":
    raise SystemExit(main())
