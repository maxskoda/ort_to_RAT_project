"""
ort_to_rat
==========

Convert an ORSO .ort file into a RAT (Rascal) MATLAB model + project.

Usage
-----
    python -m ort_to_rat path/to/model.ort [--out ./rat_models] [--name MyModel]
"""

from .__main__ import main  # convenience
