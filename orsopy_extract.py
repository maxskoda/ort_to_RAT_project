"""
ORSO file loading and extraction of layers, bulks, contrasts, and bilayer specs.
"""

import re
from pathlib import Path

from orsopy.fileio.orso import load_orso

from .bilayer_utils import extract_bilayers_from_model, build_bilayer_specs


def safe_get_sld(material):
    """Try to get SLD from orsopy Material, fallback to 0.0 if parsing fails."""
    try:
        if material is not None and hasattr(material, "get_sld"):
            return float(material.get_sld().real)
    except Exception:
        return 0.0
    return 0.0


KNOWN_BULKS = ["D2O", "H2O", "AuMW", "SiMW", "SMW", "Si", "Air"]


def infer_bulk_name_from_layer(layer, fallback: str) -> str:
    """Try to determine a good bulk name based on layer properties."""
    mat = getattr(layer, "material", None)

    # Material name
    name = getattr(mat, "name", None)
    if isinstance(name, str) and name.strip():
        for kb in KNOWN_BULKS:
            if kb.lower() in name.lower():
                return kb

    # original_name
    orig = getattr(layer, "original_name", None)
    if isinstance(orig, str) and orig.strip():
        for kb in KNOWN_BULKS:
            if kb.lower() in orig.lower():
                return kb

    # formula
    formula = getattr(mat, "formula", "")
    if isinstance(formula, str):
        f = formula.lower()
        if "d2o" in f:
            return "D2O"
        if "h2o" in f:
            return "H2O"

    return fallback


def _extract_layer(li):
    """Extract a dict with name, thickness (Å), sld, roughness (Å) from a layer."""
    try:
        layer_name = (
            getattr(li, "original_name", None)
            or getattr(li.material, "name", None)
            or "Layer"
        )

        if getattr(li, "thickness", None) is not None:
            thickness = float(li.thickness.as_unit("angstrom"))
        else:
            thickness = 0.0

        sld = safe_get_sld(getattr(li, "material", None))

        if getattr(li, "roughness", None) is not None:
            rough = float(li.roughness.as_unit("angstrom"))
        else:
            rough = 3.0

        return {
            "name": layer_name.strip(),
            "thickness": thickness,
            "sld": sld,
            "roughness": rough,
        }
    except Exception as e:
        raise RuntimeError(f"Malformed layer encountered: {e}") from e


def process_orso_file(ort_path: Path):
    """
    Load an ORSO file and extract:
      - layers_all: list[contrast][layer dicts]
      - bulk_ins: list of {name, sld}
      - bulk_outs: list of {name, sld}
      - contrast_names: list of display-safe names
      - bilayer_specs: enriched bilayer specs from first model with bilayers
    """
    orso_data = load_orso(str(ort_path))
    print(f"✔ Loaded ORSO file with {len(orso_data)} dataset(s)")

    layers_all = []
    bulk_ins = []
    bulk_outs = []
    contrast_names = []
    bilayer_specs_raw = None  # from first dataset with bilayers

    for i, ds in enumerate(orso_data, start=1):
        sample = ds.info.data_source.sample
        model = getattr(sample, "model", None)
        name = getattr(sample, "name", f"Contrast_{i}")

        # Clean name: remove trailing thickness info like "th=..."
        contrast_label = re.sub(r"\s*th=.*$", "", name).strip()
        # Escape underscores for MATLAB legends
        contrast_names.append(contrast_label.replace("_", r"\_"))

        if model is None:
            print(f"⚠ No model found in dataset {i}, skipping.")
            continue

        # Extract & strip bilayers from stack (first dataset defines bilayer types)
        bilayers_here = extract_bilayers_from_model(model)
        if bilayers_here and bilayer_specs_raw is None:
            bilayer_specs_raw = bilayers_here

        try:
            resolved_layers = model.resolve_to_layers()
        except Exception as e:
            print(f"⚠ Warning: could not resolve layers for {contrast_label}: {e}")
            continue

        if len(resolved_layers) < 2:
            print(f"⚠ Skipping {contrast_label}: not enough layers.")
            continue

        # ---- Collect layer data (for parameters) ----
        contrast_layers = []
        for li in resolved_layers:
            try:
                contrast_layers.append(_extract_layer(li))
            except RuntimeError as e:
                print(f"⚠ Skipped malformed layer in {contrast_label}: {e}")

        layers_all.append(contrast_layers)

        # ---- Bulk media ----
        bulk_in_layer = resolved_layers[0]
        bulk_out_layer = resolved_layers[-1]

        bulk_in_name = infer_bulk_name_from_layer(bulk_in_layer, "Substrate")
        bulk_out_name = infer_bulk_name_from_layer(bulk_out_layer, "Air")

        bulk_in = {
            "name": bulk_in_name,
            "sld": safe_get_sld(getattr(bulk_in_layer, "material", None)),
        }
        bulk_out = {
            "name": bulk_out_name,
            "sld": safe_get_sld(getattr(bulk_out_layer, "material", None)),
        }

        bulk_ins.append(bulk_in)
        bulk_outs.append(bulk_out)

        print(f"   ↳ Contrast {i}: {contrast_label}")
        print(f"      BulkIn : {bulk_in['name']} (SLD={bulk_in['sld']:.3e})")
        print(f"      BulkOut: {bulk_out['name']} (SLD={bulk_out['sld']:.3e})")

    if not layers_all:
        raise RuntimeError("No valid models found in the ORSO file.")

    print(f"✔ Using {len(layers_all[0]) - 2} internal layers from first dataset")

    # ---- Enrich bilayer specs ----
    bilayer_specs = build_bilayer_specs(bilayer_specs_raw)

    return layers_all, bulk_ins, bulk_outs, contrast_names, bilayer_specs
