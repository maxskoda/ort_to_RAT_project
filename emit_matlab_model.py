"""
Emit MATLAB custom-layers model function for RAT.
"""


def emit_matlab_model(base_name: str, layers: list, bilayers: list) -> str:
    """
    Generate RAT custom-layers MATLAB model function.

    Parameters
    ----------
    base_name : str
        Base name for the MATLAB function (suffix '_auto' is added).

    layers : list of dict
        ORSO-resolved normal layers:
            { "name": str, "thickness": float, "sld": float, "roughness": float }

    bilayers : list of dict
        Each bilayer dict must contain:
            - "inner": lipid name
            - "outer": lipid name
            - v_head_inner, v_tail_inner, v_head_outer, v_tail_outer
            - sld_head_inner, sld_tail_inner, sld_head_outer, sld_tail_outer

        These are injected by Python (via molgroups or fallback).
    """
    from unicodedata import normalize as _unorm

    fn = f"{base_name}_auto"

    def clean_comment(s: str) -> str:
        return _unorm("NFKD", str(s)).encode("ascii", "ignore").decode()

    # ----------------------------------------------------------------------
    # MATLAB HEADER
    # ----------------------------------------------------------------------
    header = f"""function [output, subRough] = {fn}(params, bulkIn, bulkOut, contrast)
% {fn}  Auto-generated from ORSO .ort (+ bilayer support)
%
% Parameter ordering in 'params':
%   1) Substrate Roughness
%   Then, for each non-bilayer layer:
%       [thickness, SLD, roughness]
%   Then, for each bilayer j:
%       [APM, HeadHydInner, HeadHydOuter, BilayerHydration, Rough]
%
% Returns an N×3 array: [thickness  SLD  roughness]
%
% Bilayer expansion (4 layers):
%   head(inner) → tail(inner) → tail(outer) → head(outer)
%
% Hydration mixes intrinsic SLD with bulkOut(contrast).
%

"""

    lines = []
    lines.append(header)
    lines.append("idx = 1;")
    lines.append("subRough = params(idx); idx = idx + 1;")
    lines.append("")

    # ----------------------------------------------------------------------
    # UNPACK NORMAL LAYERS
    # ----------------------------------------------------------------------
    lines.append("% ---- Unpack non-bilayer layer parameters ----")
    for i, L in enumerate(layers, start=1):
        lname = clean_comment(L.get("name", f"Layer{i}"))
        lines.append(f"% Layer {i}: {lname}")
        lines.append(f"layer{i}Thick = params(idx); idx = idx + 1;")
        lines.append(f"layer{i}SLD   = params(idx); idx = idx + 1;")
        lines.append(f"layer{i}Rough = params(idx); idx = idx + 1;")
        lines.append("")

    # ----------------------------------------------------------------------
    # UNPACK BILAYER FIT PARAMETERS
    # ----------------------------------------------------------------------
    lines.append("% ---- Unpack bilayer fit parameters ----")
    for j, bl in enumerate(bilayers, start=1):
        inner = clean_comment(bl["inner"])
        outer = clean_comment(bl["outer"])

        lines.append(f"% Bilayer {j}: inner={inner}, outer={outer}")
        lines.append(f"bilayer{j}APM              = params(idx); idx = idx + 1;")
        lines.append(f"bilayer{j}HeadHydInner     = params(idx); idx = idx + 1;")
        lines.append(f"bilayer{j}HeadHydOuter     = params(idx); idx = idx + 1;")
        lines.append(f"bilayer{j}BilayerHydration = params(idx); idx = idx + 1;")
        lines.append(f"bilayer{j}Rough            = params(idx); idx = idx + 1;")
        lines.append("")

    # ----------------------------------------------------------------------
    # INJECT PHYSICAL CONSTANTS FOR BILAYERS
    # ----------------------------------------------------------------------
    if bilayers:
        lines.append("% ---- Bilayer physical constants (from molgroups or fallback) ----")
        for j, bl in enumerate(bilayers, start=1):
            inner = clean_comment(bl["inner"])
            outer = clean_comment(bl["outer"])

            v_hi = bl["v_head_inner"]
            v_ti = bl["v_tail_inner"]
            v_ho = bl["v_head_outer"]
            v_to = bl["v_tail_outer"]

            sld_hi = bl["sld_head_inner"]
            sld_ti = bl["sld_tail_inner"]
            sld_ho = bl["sld_head_outer"]
            sld_to = bl["sld_tail_outer"]

            lines.append(f"%% Bilayer {j} constants (inner={inner}, outer={outer})")
            lines.append(f"vHeadInner{j} = {v_hi:.6g};")
            lines.append(f"vTailInner{j} = {v_ti:.6g};")
            lines.append(f"vHeadOuter{j} = {v_ho:.6g};")
            lines.append(f"vTailOuter{j} = {v_to:.6g};")

            lines.append(f"sldHeadInner{j} = {sld_hi:.6g};")
            lines.append(f"sldTailInner{j} = {sld_ti:.6g};")
            lines.append(f"sldHeadOuter{j} = {sld_ho:.6g};")
            lines.append(f"sldTailOuter{j} = {sld_to:.6g};")
            lines.append("")

    # ----------------------------------------------------------------------
    # FINAL LAYER STACK BUILD
    # ----------------------------------------------------------------------
    lines.append("% ---- Build final layer stack ----")
    lines.append("output = [];")
    lines.append("")

    # Normal layers first
    for i, L in enumerate(layers, start=1):
        lines.append(f"% Non-bilayer layer {i}")
        lines.append(f"L{i} = [layer{i}Thick, layer{i}SLD, layer{i}Rough];")
        lines.append(f"output = [output; L{i}];")
        lines.append("")

    # Bilayers → 4 sublayers
    for j, bl in enumerate(bilayers, start=1):
        lines.append(f"% Bilayer {j} → 4 layers (head/ tail / tail / head)")

        lines.append(f"headInnerThick{j} = vHeadInner{j} / bilayer{j}APM;")
        lines.append(f"tailInnerThick{j} = vTailInner{j} / bilayer{j}APM;")
        lines.append(f"tailOuterThick{j} = vTailOuter{j} / bilayer{j}APM;")
        lines.append(f"headOuterThick{j} = vHeadOuter{j} / bilayer{j}APM;")

        # Hydration mixing
        lines.append(
            f"headInnerSLD{j} = bilayer{j}HeadHydInner     * bulkOut(contrast) + (1 - bilayer{j}HeadHydInner)     * sldHeadInner{j};"
        )
        lines.append(
            f"headOuterSLD{j} = bilayer{j}HeadHydOuter     * bulkOut(contrast) + (1 - bilayer{j}HeadHydOuter)     * sldHeadOuter{j};"
        )
        lines.append(
            f"tailInnerSLD{j} = bilayer{j}BilayerHydration * bulkOut(contrast) + (1 - bilayer{j}BilayerHydration) * sldTailInner{j};"
        )
        lines.append(
            f"tailOuterSLD{j} = bilayer{j}BilayerHydration * bulkOut(contrast) + (1 - bilayer{j}BilayerHydration) * sldTailOuter{j};"
        )

        # Identical roughness for all sublayers
        lines.append(f"bilayerRough{j} = bilayer{j}Rough;")

        # Construct MATLAB blocks
        lines.append(
            f"headInner{j} = [headInnerThick{j}, headInnerSLD{j}, bilayerRough{j}];"
        )
        lines.append(
            f"tailInner{j} = [tailInnerThick{j}, tailInnerSLD{j}, bilayerRough{j}];"
        )
        lines.append(
            f"tailOuter{j} = [tailOuterThick{j}, tailOuterSLD{j}, bilayerRough{j}];"
        )
        lines.append(
            f"headOuter{j} = [headOuterThick{j}, headOuterSLD{j}, bilayerRough{j}];"
        )

        lines.append(
            f"bilayerBlock{j} = [headInner{j}; tailInner{j}; tailOuter{j}; headOuter{j}];"
        )
        lines.append(f"output = [output; bilayerBlock{j}];")
        lines.append("")

    lines.append("end")

    return "\n".join(lines)
