"""Transfers between the local archive and filament.

rsync is used rather than scp/sftp because the transfers run for hours and the
campus VPN can drop: rsync resumes instead of starting over, and verifies what
arrived. On Windows, rsync is reached through WSL (Windows OpenSSH has no
rsync), so local paths are translated to their ``/mnt/<drive>`` form.

    >>> from iris_mosaics import MosaicConfig
    >>> from iris_mosaics.transfer import push, remote_free_bytes
    >>> cfg = MosaicConfig.load('20240811')
    >>> push(cfg.level_path('level_12'), f'{cfg.remote_root}/level_12', dry_run=True)

Note on ``size_only``: rsync's default compares size *and* modification time.
Data uploaded before this module existed (by scp or pysftp) has mtimes that do
not match the local copies, so a default rsync re-sends everything. Passing
``size_only=True`` compares size alone, which correctly recognises those files
as already present. Use it when reconciling against a pre-existing remote copy;
leave it off for a fresh transfer.
"""

from __future__ import annotations

import pathlib as pl
import platform
import subprocess

#: Host to reach filament by. The bare alias needs an ssh config entry, which
#: WSL does not inherit from Windows, so the fully qualified form is used.
FILAMENT_HOST = "cbunn@filament.physics.montana.edu"

#: Identity file, as seen from wherever rsync runs.
WSL_IDENTITY = "~/.ssh/id_ed25519"


def to_wsl_path(path) -> str:
    """Translate a Windows path to the ``/mnt/<drive>`` form WSL sees.

    Paths that are already POSIX are returned unchanged.

        >>> to_wsl_path(r'D:\\IRIS data\\deep_mosaics\\20240811')
        '/mnt/d/IRIS data/deep_mosaics/20240811'
    """
    text = str(path).replace("\\", "/")
    if len(text) > 1 and text[1] == ":":
        drive, rest = text[0].lower(), text[2:].lstrip("/")
        return f"/mnt/{drive}/{rest}"
    return text


def _rsync_argv(
    src: str, dst: str, dry_run: bool, size_only: bool, extra: tuple[str, ...]
) -> list[str]:
    ssh = f"ssh -o BatchMode=yes -i {WSL_IDENTITY}"
    argv = ["rsync", "-a", "--partial", "--progress", "-e", ssh]
    if dry_run:
        argv.append("--dry-run")
    if size_only:
        argv.append("--size-only")
    argv.extend(extra)
    argv.extend([src, dst])
    if platform.system() == "Windows":
        argv = ["wsl", "-e", *argv]
    return argv


def push(
    local_dir,
    remote_dir: str,
    dry_run: bool = False,
    size_only: bool = False,
    extra: tuple[str, ...] = (),
) -> subprocess.CompletedProcess:
    """Send a local directory's contents to filament.

    Trailing slashes are added so the *contents* are synced into ``remote_dir``,
    not nested inside another directory.
    """
    src = to_wsl_path(local_dir).rstrip("/") + "/"
    dst = f"{FILAMENT_HOST}:{remote_dir.rstrip('/')}/"
    return subprocess.run(_rsync_argv(src, dst, dry_run, size_only, extra), check=True)


def pull(
    remote_dir: str,
    local_dir,
    dry_run: bool = False,
    size_only: bool = False,
    extra: tuple[str, ...] = (),
) -> subprocess.CompletedProcess:
    """Fetch a directory's contents from filament into the local archive."""
    src = f"{FILAMENT_HOST}:{remote_dir.rstrip('/')}/"
    dst = to_wsl_path(local_dir).rstrip("/") + "/"
    return subprocess.run(_rsync_argv(src, dst, dry_run, size_only, extra), check=True)


def _ssh(command: str) -> str:
    """Run one command on filament and return its stdout.

    The remote login shell is tcsh, which rejects bash-isms and has interactive
    aliases (``rm`` is ``rm -i``), so everything is wrapped in ``sh -c``.
    """
    argv = ["ssh", "-o", "BatchMode=yes", FILAMENT_HOST, "sh", "-c", f"'{command}'"]
    result = subprocess.run(argv, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def remote_free_bytes(path: str = "/disk/data") -> int:
    """Free space on filament, in bytes.

    ``/disk/data`` is a shared NFS mount that runs at capacity, so check this
    before starting a transfer.
    """
    out = _ssh(f"df -B1 --output=avail {path} | tail -1")
    return int(out.splitlines()[-1].strip())


def remote_count(remote_dir: str, pattern: str = "*.fits") -> int:
    """Number of matching files in a directory on filament."""
    out = _ssh(f"ls -1 {remote_dir}/{pattern} 2>/dev/null | wc -l")
    return int(out.splitlines()[-1].strip())


def local_bytes(local_dir, pattern: str = "*.fits") -> int:
    """Total size of the files a transfer would send."""
    return sum(f.stat().st_size for f in pl.Path(local_dir).glob(pattern))


def check_room(local_dir, pattern: str = "*.fits", path: str = "/disk/data") -> None:
    """Raise unless filament has room for the files in ``local_dir``.

    Filling a shared group disk is worse than failing early.
    """
    needed = local_bytes(local_dir, pattern)
    free = remote_free_bytes(path)
    if needed >= free:
        raise RuntimeError(
            f"not enough room on filament {path}: need {needed / 1e9:.1f} GB, "
            f"{free / 1e9:.1f} GB free. Delete a superseded level first "
            "(only after its output is downloaded and verified locally)."
        )
