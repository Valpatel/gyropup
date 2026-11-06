"""Physical source locations and stable artifact identities; no geometry changes."""
from pathlib import Path, PurePosixPath


def artifact_identity(root: Path, path: Path) -> str:
    """Public records keep exports/ IDs while files belong to hardware/exports/."""
    relative = Path(path).resolve().relative_to((Path(root) / 'hardware/exports').resolve())
    return (PurePosixPath('exports') / relative.as_posix()).as_posix()


def artifact_path(root: Path, identity: str) -> Path:
    """Resolve a canonical export ID once, with no obsolete-source fallback."""
    value = PurePosixPath(identity)
    if (not identity.startswith('exports/') or value.is_absolute() or '..' in value.parts
            or '\\' in identity or '\0' in identity or str(value) != identity):
        raise ValueError('Not a canonical exports identity')
    path = Path(root) / 'hardware' / value
    if not path.resolve().is_relative_to((Path(root) / 'hardware/exports').resolve()):
        raise ValueError('Export identity escapes its owning directory')
    return path


def design_identity(root: Path, path: Path) -> str:
    """A browser-facing design identity is separate from its owning source path."""
    relative = Path(path).resolve().relative_to((Path(root) / 'hardware/designs').resolve())
    return (PurePosixPath('designs') / relative.as_posix()).as_posix()
