"""Running the IDL/SSW steps on filament, unattended.

``iris_prep`` is deep SSW IDL and stays on filament. Rather than editing paths
into a ``.pro`` file and babysitting an interactive session for 7-9 hours, this
module renders the script from a template, uploads it, and launches it detached
so it survives the SSH connection closing and the campus VPN dropping.

    >>> from iris_mosaics import MosaicConfig
    >>> from iris_mosaics import remote
    >>> cfg = MosaicConfig.load('20240811')
    >>> print(remote.render('prep1', cfg))          # doctest: +SKIP
    >>> remote.launch('prep1', cfg)                 # doctest: +SKIP
    >>> remote.status('prep1', cfg)                 # doctest: +SKIP
    'running'

Completion is detected by a sentinel file written by the *shell*, not by IDL,
so a crashed or killed IDL is reported as failed rather than hanging forever.

Two properties of filament shape everything here:

- The login shell is **tcsh**, which rejects bash-isms (``2>&1`` is an
  "Ambiguous output redirect") and aliases ``rm`` to ``rm -i``. Remote commands
  are therefore piped to ``sh`` over stdin rather than passed as arguments --
  ssh flattens arguments for the login shell to re-parse, so argument quoting
  would have to survive tcsh as well as sh.
- ``/disk/data`` runs at capacity, so output directories are created but old
  levels are never removed automatically. See :func:`cleanup_level`.
"""

from __future__ import annotations

import dataclasses
import pathlib as pl
import subprocess

from .transfer import FILAMENT_HOST

IDL_DIR = pl.Path(__file__).parent.parent / "idl"

#: Where generated scripts, logs and sentinels are kept on filament.
REMOTE_WORK_DIR = "/disk/data/cbunn/calibrated_iris_mosaics"


@dataclasses.dataclass(frozen=True)
class IdlStep:
    """One of the two IDL passes."""

    name: str
    template: str
    input_level: str
    output_level: str
    keywords: str
    manifest_step: str
    description: str


STEPS = {
    "prep1": IdlStep(
        name="prep1",
        template="prep_part1.pro.template",
        input_level="level_1",
        output_level="level_11",
        keywords="/noflat, /nobad, /nowarp, /filter_fid",
        manifest_step="level_11",
        description="iris_prep through the FUV background subtraction (~7 h)",
    ),
    "prep2": IdlStep(
        name="prep2",
        template="prep_part2.pro.template",
        input_level="level_12",
        output_level="level_15",
        keywords=(
            "/nosat, /nodark, /noback, /shift_wave, /shift_fid, /poly2d, "
            "/filter_wave, /filter_fid, /filter_aia"
        ),
        manifest_step="level_15",
        description="remainder of iris_prep, no background subtraction (~9 h)",
    ),
}

#: Directory names on filament, mirroring the local archive layout.
REMOTE_LEVEL_DIRS = {
    "level_1": "level_1",
    "level_11": "level_11_plus_iris_prep_bg_sub",
    "level_12": "level_12",
    "level_15": "level_15",
}


def _get_step(step: str) -> IdlStep:
    if step not in STEPS:
        raise KeyError(f"unknown IDL step {step!r}; known: {', '.join(STEPS)}")
    return STEPS[step]


def remote_level_dir(cfg, level: str) -> str:
    """Path of a processing level on filament."""
    return f"{cfg.remote_root}/{REMOTE_LEVEL_DIRS.get(level, level)}"


def job_name(step: str, cfg) -> str:
    """Identifier for this mosaic's run of this step."""
    return f"irismos_{step}_{cfg.date}"


def _paths(step: str, cfg) -> dict:
    s = _get_step(step)
    name = job_name(step, cfg)
    return {
        "script": f"{REMOTE_WORK_DIR}/{name}.pro",
        "log": f"{REMOTE_WORK_DIR}/{name}.log",
        "sentinel": f"{REMOTE_WORK_DIR}/{name}.done",
        "input_glob": f"{remote_level_dir(cfg, s.input_level)}/*.fits",
        "output_dir": remote_level_dir(cfg, s.output_level),
    }


def render(step: str, cfg) -> str:
    """Fill the step's IDL template in for this mosaic."""
    s = _get_step(step)
    p = _paths(step, cfg)
    template = (IDL_DIR / s.template).read_text(encoding="utf-8")
    return template.format(
        input_glob=p["input_glob"],
        output_dir=p["output_dir"],
        keywords=s.keywords,
    )


def _ssh(command: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell script on filament, bypassing the tcsh login shell.

    The script is piped to a remote ``sh`` over stdin rather than passed as an
    argument. ssh flattens arguments into a single string for the login shell to
    re-parse, so anything quoted has to survive tcsh's parsing as well as sh's;
    stdin sidesteps that entirely and lets the script contain whatever it likes.
    """
    argv = ["ssh", "-o", "BatchMode=yes", FILAMENT_HOST, "sh"]
    return subprocess.run(
        argv, input=command, capture_output=True, text=True, check=check
    )


def launch(step: str, cfg, dry_run: bool = False) -> str:
    """Render, upload and start the step detached on filament.

    Returns the job name. The job keeps running after this process exits and
    after the VPN drops; poll it with :func:`status`.

    Refuses to start if the step is already running, so a re-run cannot end up
    with two IDL processes writing the same output directory.
    """
    s = _get_step(step)
    p = _paths(step, cfg)
    script = render(step, cfg)

    if dry_run:
        return script

    current = status(step, cfg)
    if current == "running":
        raise RuntimeError(
            f"{job_name(step, cfg)} is already running on filament; "
            "wait for it or stop it before relaunching"
        )

    if "IRIS_MOSAICS_EOF" in script:
        raise ValueError("rendered script contains the heredoc delimiter")

    # Upload the script and launch it in one piped shell script. The heredoc is
    # quoted so the remote shell does not expand anything inside the IDL source.
    # The sentinel is written by the shell, not by IDL, so a crash is visible.
    inner = (
        f"cd {REMOTE_WORK_DIR} && "
        f"sswidl < {p['script']} > {p['log']} 2>&1; "
        f"echo $? > {p['sentinel']}"
    )
    remote_script = "\n".join([
        f"mkdir -p {REMOTE_WORK_DIR} {p['output_dir']}",
        f"cat > {p['script']} <<'IRIS_MOSAICS_EOF'",
        script.rstrip("\n"),
        "IRIS_MOSAICS_EOF",
        f"rm -f {p['sentinel']} {p['log']}",
        f"screen -dmS {job_name(step, cfg)} sh -c '{inner}'",
        "",
    ])
    _ssh(remote_script)
    return job_name(step, cfg)


def status(step: str, cfg) -> str:
    """One of ``running``, ``done``, ``failed``, ``not started``.

    ``done`` means the shell recorded exit status 0; ``failed`` means it
    recorded anything else, or the screen session vanished without writing a
    sentinel at all.
    """
    p = _paths(step, cfg)
    name = job_name(step, cfg)
    out = _ssh(
        f"if [ -f {p['sentinel']} ]; then echo SENTINEL:$(cat {p['sentinel']}); "
        f"elif screen -ls | grep -q {name}; then echo RUNNING; "
        f"else echo ABSENT; fi",
        check=False,
    ).stdout.strip().splitlines()
    line = out[-1].strip() if out else "ABSENT"

    if line.startswith("SENTINEL:"):
        code = line.split(":", 1)[1].strip()
        return "done" if code == "0" else "failed"
    if line == "RUNNING":
        return "running"
    return "not started"


def log(step: str, cfg, lines: int = 40) -> str:
    """Tail the step's IDL log from filament."""
    p = _paths(step, cfg)
    return _ssh(f"tail -n {lines} {p['log']} 2>/dev/null || true",
                check=False).stdout


def output_count(step: str, cfg) -> int:
    """How many files the step has written so far.

    Useful as a progress indicator while a multi-hour run is going.
    """
    from .transfer import remote_count

    s = _get_step(step)
    return remote_count(remote_level_dir(cfg, s.output_level))


def stop(step: str, cfg) -> None:
    """Kill a running job."""
    _ssh(f"screen -S {job_name(step, cfg)} -X quit", check=False)


def cleanup_level(cfg, level: str, expected_count: int, confirm: bool = False) -> str:
    """Delete a superseded level from filament to reclaim space.

    ``/disk/data`` runs at capacity, so old levels must go — but only once the
    data is safely in the local archive. This refuses unless the caller passes
    the number of files it has verified locally *and* that number matches what
    is on filament, and unless ``confirm=True`` is given explicitly.

    Deleting data is not something to do on inference: the local archive is the
    only copy that matters, so the check is deliberately strict.
    """
    from .transfer import remote_count

    target = remote_level_dir(cfg, level)
    actual = remote_count(target)

    if actual != expected_count:
        raise RuntimeError(
            f"refusing to delete {target}: it holds {actual} files but the "
            f"verified local copy has {expected_count}. Reconcile before deleting."
        )
    if not confirm:
        raise RuntimeError(
            f"refusing to delete {target} ({actual} files) without confirm=True"
        )

    _ssh(f"rm -rf {target}")
    return target
