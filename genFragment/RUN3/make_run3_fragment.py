#!/usr/bin/env python3
"""
Create a Run 3 fragment by reusing the corresponding Run 2 SLHA_TABLE.

Example:
    python3 make_run3_fragment.py --breaking-scale 500 --ctau 100
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
RUN2_DIR = SCRIPT_DIR.parent / "RUN2"
RUN3_TEMPLATE = SCRIPT_DIR / "GMSB_L_xxx_ctau_xxx_13p6TeV_fragment.py"


def build_run2_input_path(breaking_scale: str, ctau: str) -> Path:
    return RUN2_DIR / f"GMSB_L_{breaking_scale}_ctau_{ctau}_13TeV_fragment.py"


def build_run3_output_path(breaking_scale: str, ctau: str) -> Path:
    return SCRIPT_DIR / f"GMSB_L_{breaking_scale}_ctau_{ctau}_13p6TeV_fragment.py"


def extract_slha_table(run2_text: str) -> str:
    match = re.search(r"SLHA_TABLE\s*=\s*'''[\s\S]*?'''", run2_text)
    if not match:
        raise RuntimeError("Could not find SLHA_TABLE in the Run 2 fragment")
    return match.group(0)


def extract_run3_template_body(template_text: str) -> str:
    body = template_text.lstrip()
    if body.startswith("SLHA_TABLE"):
        raise RuntimeError("Run 3 template unexpectedly contains its own SLHA_TABLE block")
    return body


def build_run3_fragment(slha_table_block: str, run3_body: str) -> str:
    return f"{slha_table_block}\n\n\n{run3_body}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Run 3 fragment from the matching Run 2 SLHA table.")
    parser.add_argument(
        "--breaking-scale",
        required=True,
        help="Value between L- and TeV, for example 500.",
    )
    parser.add_argument(
        "--ctau",
        required=True,
        help="Value between Ctau- and cm, for example 100.",
    )
    args = parser.parse_args()

    run2_input = build_run2_input_path(args.breaking_scale, args.ctau)
    run3_output = build_run3_output_path(args.breaking_scale, args.ctau)

    try:
        run2_text = run2_input.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: missing Run 2 fragment: {run2_input}", file=sys.stderr)
        return 1

    try:
        template_text = RUN3_TEMPLATE.read_text(encoding="utf-8")
        slha_table_block = extract_slha_table(run2_text)
        run3_body = extract_run3_template_body(template_text)
        run3_output.write_text(build_run3_fragment(slha_table_block, run3_body), encoding="utf-8")
    except (OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Run 2 source : {run2_input}")
    print(f"Run 3 output : {run3_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
