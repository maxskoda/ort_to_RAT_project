import re
import unicodedata


def normalize_param_name(name: str) -> str:
    """
    Convert to pure ASCII, collapse all whitespace to a single space.
    This guarantees MATLAB sees unique clean names.
    """
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode()
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def sanitize_name(s: str) -> str:
    """Make safe filenames for all OS."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    return s.strip("_")
