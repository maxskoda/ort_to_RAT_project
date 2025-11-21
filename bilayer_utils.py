"""
Utilities for lipid bilayers: molgroups interaction and stack token detection.
"""

import re

# Optional dependencies: molgroups + numpy
try:
    import numpy as np
    import molgroups.lipids as lipids

    HAS_MOLGROUPS = True
except ImportError:  # pragma: no cover - environment dependent
    HAS_MOLGROUPS = False
    np = None
    lipids = None


# Precompiled regex for bilayer tokens in model.stack
RE_BILAYER = re.compile(
    r"""^bilayer\s*\(\s*inner\s*=\s*([A-Za-z0-9_]+)\s*,\s*outer\s*=\s*([A-Za-z0-9_]+)\s*\)\s*$"""
)


def scalar_nsl(x):
    """Convert molgroups nSLs (scalar or array) to a single float."""
    if np is None:
        try:
            return float(x)
        except Exception:
            return 0.0

    try:
        arr = np.array(x)
        return float(arr.sum())
    except Exception:
        try:
            return float(x)
        except Exception:
            return 0.0

def get_lipid_constants(lipid_name: str):
    """
    Fetch head/tail volumes and SLDs for a lipid from molgroups.lipids.
    Falls back to DPPC if name not found.

    Returns dict:
      {
        'name': ...,
        'head_vol': float,   # Å^3
        'head_sld': float,   # Å^-2
        'tail_vol': float,   # Å^3
        'tail_sld': float,   # Å^-2
      }
    or None if molgroups is unavailable.
    """
    if not HAS_MOLGROUPS:
        return None

    obj = getattr(lipids, lipid_name, None)
    if obj is None:
        # Fallback to DPPC as generic phospholipid
        obj = getattr(lipids, "DPPC")

    # ---- Headgroup ----
    try:
        # original approach
        head_components = obj.headgroup[1]["components"]
        head_vol = sum(getattr(c, "cell_volume", 0.0) for c in head_components)
        head_nsl = scalar_nsl([getattr(c, "nSLs", 0.0) for c in head_components])
    except Exception:
        head_vol = 0.0
        head_nsl = 0.0

    # try alternative attributes if head_vol is still zero
    if head_vol <= 0:
        # some lipids may expose a total volume directly
        head_vol = float(getattr(obj, "headgroup_volume", 0.0) or 0.0)

    # absolute fallback for weird cases (e.g. DOPG)
    if head_vol <= 0:
        head_vol = 330.0  # typical phosphocholine-ish head volume (Å^3)

    # SLD: nSL (fm) → Å, then / Å^3
    head_sld = 0.0
    if head_vol > 0 and head_nsl != 0:
        head_sld = head_nsl * 1e-5 / head_vol

    # ---- Tails ----
    try:
        tail = obj.tails
        tail_vol = float(getattr(tail, "cell_volume", 0.0) or 0.0)
        tail_nsl = scalar_nsl(getattr(tail, "nSLs", 0.0))
    except Exception:
        tail_vol = 0.0
        tail_nsl = 0.0

    if tail_vol <= 0:
        tail_vol = 800.0  # generic pair-of-C16 tails-ish fallback

    tail_sld = 0.0
    if tail_vol > 0 and tail_nsl != 0:
        tail_sld = tail_nsl * 1e-5 / tail_vol

    return {
        "name": lipid_name,
        "head_vol": float(head_vol),
        "head_sld": float(head_sld),
        "tail_vol": float(tail_vol),
        "tail_sld": float(tail_sld),
    }


def extract_bilayers_from_model(model):
    """
    Detect bilayer(inner=XXX, outer=YYY) tokens in model.stack.

    - Removes bilayer(...) tokens from the stack string, so orsopy can parse.
    - Returns list of bilayer specs:
        [{'inner': 'DPPC', 'outer': 'POPC'}, ...]
    """
    stack = getattr(model, "stack", "")
    tokens = [t.strip() for t in stack.split("|")]

    bilayers = []
    kept = []

    for t in tokens:
        m = RE_BILAYER.match(t)
        if m:
            inner = m.group(1)
            outer = m.group(2)
            bilayers.append({"inner": inner, "outer": outer})
        else:
            kept.append(t)

    new_stack = " | ".join(kept)
    model.stack = new_stack
    return bilayers

def _flatten_lipid(prefix: str, consts):
    """
    Expand molgroups lipid constants into flat keys with fallback.
    prefix: 'inner' or 'outer'
    """
    if consts is None:
        # total fallback values (still physical-ish)
        return {
            f"v_head_{prefix}": 300.0,
            f"v_tail_{prefix}": 800.0,
            f"sld_head_{prefix}": 1e-6,
            f"sld_tail_{prefix}": 1e-6,
        }

    return {
        f"v_head_{prefix}": consts["head_vol"],
        f"sld_head_{prefix}": consts["head_sld"],
        f"v_tail_{prefix}": consts["tail_vol"],
        f"sld_tail_{prefix}": consts["tail_sld"],
    }


def build_bilayer_specs(bilayer_specs_raw):
    """
    Convert raw bilayer tokens [{'inner':..., 'outer':...}, ...]
    into enriched bilayer specs with molgroups constants.

    Returns list of dicts:
        {
          "inner": "...", "outer": "...",
          "v_head_inner", "v_tail_inner",
          "v_head_outer", "v_tail_outer",
          "sld_head_inner", "sld_tail_inner",
          "sld_head_outer", "sld_tail_outer"
        }
    """
    bilayer_specs = []

    if not bilayer_specs_raw:
        return bilayer_specs

    if not HAS_MOLGROUPS:
        raise RuntimeError(
            "Detected bilayer(...) in model stack, but molgroups.lipids is not installed."
        )

    for spec in bilayer_specs_raw:
        inner = spec["inner"]
        outer = spec["outer"]

        inner_consts = get_lipid_constants(inner)
        outer_consts = get_lipid_constants(outer)

        flat_inner = _flatten_lipid("inner", inner_consts)
        flat_outer = _flatten_lipid("outer", outer_consts)

        bilayer_specs.append(
            {
                "inner": inner,
                "outer": outer,
                **flat_inner,
                **flat_outer,
            }
        )

    return bilayer_specs
