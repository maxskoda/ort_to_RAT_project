"""
Emit MATLAB driver script for multi-contrast RAT project.
"""

import re
from pathlib import Path


def _span(val, frac=0.2):
    """Return (min, val, max) for a given fractional span."""
    if abs(val) < 1e-12:
        return -1e-6, 0.0, 1e-6
    lo = val * (1 - frac)
    hi = val * (1 + frac)
    return (min(lo, hi), val, max(lo, hi))


def emit_matlab_driver(
    base_name: str,
    bulk_ins: list,
    bulk_outs: list,
    layers_all: list,
    ort_file: str,
    contrast_names: list,
    bilayer_specs: list,
) -> str:
    """
    Emit a MATLAB driver script for a multi-contrast RAT project.

    Parameters
    ----------
    base_name : str
        Base name for project and files.

    bulk_ins / bulk_outs : list of bulk dict
        { "name": str, "sld": float }

    layers_all : list of list of layer dicts
        Per-contrast layers (including bulks).

    ort_file : str
        Relative path to ORSO file (for readOrso).

    contrast_names : list of str
        Display names per contrast.

    bilayer_specs : list of dict
        As returned by build_bilayer_specs (only needed for parameter group).
    """
    fn = f"{base_name}_auto"
    title = f"{fn}_script"

    ort_name = Path(ort_file).as_posix().lstrip("/")

    lines = [
        f"""% {title}.m — Auto-generated from ORSO (+ bilayer support)

problem = createProject(name='{base_name}_Project', ...
                        model='custom layers', ...
                        geometry='substrate/liquid', ...
                        calcType='normal');

problem.showPriors = true;

% ---------- Parameter group ----------
params = {{"""
    ]

    # ------------------------------------------------------------------
    # INTERNAL LAYER PARAMETERS (from first dataset)
    # ------------------------------------------------------------------
    internal_layers = layers_all[0][1:-1]  # skip first/last as bulks

    for L in internal_layers:
        name = re.sub(r"\s+", " ", L["name"]).strip()

        tmin, tval, tmax = _span(L["thickness"], 0.3)
        smin, sval, smax = _span(L["sld"], 0.2)
        rmin, rval, rmax = _span(L["roughness"], 0.5)

        lines.append(
            f"  {{'{name} thickness', {tmin:.6g}, {tval:.6g}, {tmax:.6g}, true}};"
        )
        lines.append(
            f"  {{'{name} SLD',       {smin:.6g}, {sval:.6g}, {smax:.6g}, true}};"
        )
        lines.append(
            f"  {{'{name} rough',     {rmin:.6g}, {rval:.6g}, {rmax:.6g}, true}};"
        )

    # ------------------------------------------------------------------
    # BILAYER PARAMETERS
    # ------------------------------------------------------------------
    for j, bl in enumerate(bilayer_specs, start=1):
        lines.append(
            f"  % Bilayer {j} parameters (inner={bl['inner']}, outer={bl['outer']})"
        )

        # APM (Å²)
        lines.append(f"  {{'Bilayer{j} APM', 40, 60, 80, true}};")

        # Head hydration (inner and outer): 0–1
        lines.append(f"  {{'Bilayer{j} HeadHyd Inner', 0, 0.2, 1, true}};")
        lines.append(f"  {{'Bilayer{j} HeadHyd Outer', 0, 0.2, 1, true}};")

        # Tail hydration: 0–1
        lines.append(f"  {{'Bilayer{j} BilayerHydration', 0, 0.1, 1, true}};")

        # Roughness
        lines.append(f"  {{'Bilayer{j} Rough', 1, 4, 10, true}};")

    lines.append("};")
    lines.append("problem.addParameterGroup(params);")

    # ------------------------------------------------------------------
    # Scalefactor
    # ------------------------------------------------------------------
    lines.append(
        "problem.setScalefactor(1, 'name','Scalefactor 1', "
        "'value',1, 'min',0.5, 'max',2, 'fit',true);"
    )

    # ------------------------------------------------------------------
    # BULKS — de-duplicated across contrasts
    # ------------------------------------------------------------------
    lines.append("\n% ---------- Bulks ----------\n")

    used_in = set()
    used_out = set()
    map_in = {}
    map_out = {}

    bulk_in_names = []
    bulk_out_names = []

    def unique(base, used):
        name = base
        i = 2
        while name in used:
            name = f"{base}_{i}"
            i += 1
        used.add(name)
        return name

    def ensure_bulk(bulk, used_set, mapping, add_func_name):
        key = (bulk["name"], round(bulk["sld"], 8))
        if key in mapping:
            return mapping[key]

        safe_name = unique(bulk["name"], used_set)
        lo, _, hi = _span(bulk["sld"], 0.02)
        lines.append(
            f"problem.{add_func_name}('{safe_name}', {lo:.6g}, {bulk['sld']:.6g}, {hi:.6g}, false);"
        )
        mapping[key] = safe_name
        return safe_name

    for bi, bo in zip(bulk_ins, bulk_outs):
        name_in = ensure_bulk(bi, used_in, map_in, "addBulkIn")
        name_out = ensure_bulk(bo, used_out, map_out, "addBulkOut")

        bulk_in_names.append(name_in)
        bulk_out_names.append(name_out)

    # ------------------------------------------------------------------
    # MODEL FILE
    # ------------------------------------------------------------------
    lines += [
        f"""
% ---------- Custom model ----------
problem.addCustomFile('ORSO auto model','{fn}.m','matlab',pwd);

% ---------- Data ----------
data_cells = readOrso('{ort_name}');
numContrasts = length(data_cells);
fprintf('Detected %d data blocks in {ort_name}\\n', numContrasts);
numContrasts = min(numContrasts, {len(contrast_names)});
"""
    ]

    # ------------------------------------------------------------------
    # CONTRASTS
    # ------------------------------------------------------------------
    lines.append("% ---------- Contrasts ----------\n")

    for i, cname in enumerate(contrast_names, start=1):
        safe = re.sub(r"[^A-Za-z0-9_]+", "_", cname)
        lines.append(
            f"""
if {i} <= numContrasts

    backs = sprintf('Background Auto %d', {i});
    problem.addBackgroundParam(backs, 1e-8,1e-6,1e-4, true);
    problem.addBackground(backs,'constant',backs);

    dataName = '{safe}';
    problem.addData(dataName, data_cells{{{i}}}, [], []);

    problem.addContrast('name','{safe}', ...
                        'background',backs, ...
                        'resolution','Resolution 1', ...
                        'scalefactor','Scalefactor 1', ...
                        'BulkIn','{bulk_in_names[i-1]}', ...
                        'BulkOut','{bulk_out_names[i-1]}', ...
                        'data',dataName, ...
                        'model','ORSO auto model');
end
"""
        )

    # ------------------------------------------------------------------
    # RUN
    # ------------------------------------------------------------------
    lines.append(
        """
% ---------- Run ----------
controls = controlsClass();
[problem, results] = RAT(problem, controls);
plotRefSLD(problem, results);

projectToJson(problem, 'project.json');
controlsToJson(controls, 'controls.json');
"""
    )

    return "\n".join(lines)
