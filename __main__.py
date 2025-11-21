"""
CLI entry point for ORSO → RAT MATLAB project converter.

Usage
-----
    python -m ort_to_rat path/to/model.ort [--out ./rat_models] [--name MyModel]
"""

import argparse
import shutil
from pathlib import Path

from .file_utils import sanitize_name
from .orsopy_extract import process_orso_file
from .emit_matlab_model import emit_matlab_model
from .emit_matlab_driver import emit_matlab_driver


def main():
    parser = argparse.ArgumentParser(
        description="Convert an ORSO .ort file into a RAT (Rascal) MATLAB model + project."
    )
    parser.add_argument("ort_file", help="Path to ORSO .ort file")
    parser.add_argument(
        "--out", default="./rat_models", help="Output directory for MATLAB files"
    )
    parser.add_argument(
        "--name", default=None, help="Base name for output files (default: ORSO stem)"
    )
    args = parser.parse_args()

    ort_path = Path(args.ort_file)
    base = sanitize_name(args.name or ort_path.stem)
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    # ---- Copy ORSO file to ./data ----
    data_dir = outdir / "data"
    data_dir.mkdir(exist_ok=True)
    copied_ort = data_dir / ort_path.name
    shutil.copy2(ort_path, copied_ort)
    print(f"✔ Copied ORSO data file → {copied_ort.as_posix()}")

    # ---- Extract layers & bilayer info from ORSO ----
    (
        layers_all,
        bulk_ins,
        bulk_outs,
        contrast_names,
        bilayer_specs,
    ) = process_orso_file(ort_path)

    # ---- Generate MATLAB model (.m) ----
    internal_layers_first = layers_all[0][1:-1]  # skip BulkIn/BulkOut
    model_code = emit_matlab_model(base, internal_layers_first, bilayer_specs)
    model_file = outdir / f"{base}_auto.m"
    model_file.write_text(model_code, encoding="utf-8")
    print(f"✔ Wrote model file: {model_file.as_posix()}")

    # ---- Generate MATLAB driver (.m) ----
    rel_ort_path = Path("data") / ort_path.name
    driver_code = emit_matlab_driver(
        base,
        bulk_ins,
        bulk_outs,
        layers_all,
        str(rel_ort_path),
        contrast_names,
        bilayer_specs,
    )

    driver_file = outdir / f"{base}_auto_script.m"
    driver_file.write_text(driver_code, encoding="utf-8")
    print(f"✔ Wrote driver script: {driver_file.as_posix()}")

    print("\n✅ Conversion complete.")
    print(f"→ Open '{driver_file.name}' in RAT and run the project directly.")


if __name__ == "__main__":
    main()
