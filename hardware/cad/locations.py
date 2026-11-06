"""Physical source locations and stable artifact identities; no geometry changes."""
from pathlib import Path, PurePosixPath


def artifact_identity(root: Path, path: Path) -> str:
    """Public records keep exports/ IDs while files belong to hardware/exports/."""
    root = Path(root).resolve()
    path = Path(path).resolve()
    owning = root / 'hardware/exports'
    if path.is_relative_to(owning):
        return (PurePosixPath('exports') / path.relative_to(owning).as_posix()).as_posix()
    # Existing sweep/optimiser outputs can live elsewhere inside the checkout.
    # Their actual relative identity is retained; this grants no site publication.
    return path.relative_to(root).as_posix()


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
    root = Path(root).resolve()
    path = Path(path).resolve()
    owning = root / 'hardware/designs'
    if path.is_relative_to(owning):
        return (PurePosixPath('designs') / path.relative_to(owning).as_posix()).as_posix()
    return path.relative_to(root).as_posix()
