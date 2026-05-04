#!/usr/bin/env python3
"""
Extract a GEN-SIM fragment from McM for a given dataset name.

Workflow:
1. Build the McM dataset name from the GMSB breaking scale and ctau.
2. Query McM requests by dataset name.
3. Select the request whose sequence contains GEN-SIM.
4. Fetch the McM setup script for that PrepID.
5. Parse the fragment download URL from the setup script.
6. Download the fragment into the current directory.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


MCM_BASE = "https://cms-pdmv-prod.web.cern.ch/mcm"
USER_AGENT = "mcm-fragment-extractor/1.0"


def http_get(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request) as response:
        return response.read()


def load_json(url: str) -> Any:
    return json.loads(http_get(url).decode("utf-8"))


def build_dataset_name(breaking_scale: str, ctau: str) -> str:
    return f"GMSB_L-{breaking_scale}TeV_Ctau-{ctau}cm_TuneCP5_13TeV-pythia8"


def request_has_gensim(request_data: dict[str, Any]) -> bool:
    for sequence in request_data.get("sequences", []):
        for datatier in sequence.get("datatier", []):
            if datatier == "GEN-SIM":
                return True
    return False


def choose_gensim_request(results: list[dict[str, Any]]) -> dict[str, Any]:
    gensim_requests = [item for item in results if request_has_gensim(item)]
    if not gensim_requests:
        gs_like = [item for item in results if "GS" in item.get("prepid", "")]
        if len(gs_like) == 1:
            return gs_like[0]
        raise RuntimeError("Could not find a unique GEN-SIM request in McM results")

    prod_requests = [item for item in gensim_requests if item.get("type") == "Prod"]
    if len(prod_requests) == 1:
        return prod_requests[0]

    if len(gensim_requests) == 1:
        return gensim_requests[0]

    gensim_requests.sort(key=lambda item: (item.get("version", -1), item.get("prepid", "")), reverse=True)
    return gensim_requests[0]


def get_requests_for_dataset(dataset_name: str) -> list[dict[str, Any]]:
    encoded = quote(dataset_name, safe="")
    url = f"{MCM_BASE}/public/restapi/requests/from_dataset_name/{encoded}"
    payload = load_json(url)
    results = payload.get("results", [])
    if not isinstance(results, list) or not results:
        raise RuntimeError(f"No McM requests found for dataset {dataset_name}")
    return results


def get_setup_script(prepid: str) -> str:
    url = f"{MCM_BASE}/public/restapi/requests/get_setup/{prepid}"
    return http_get(url).decode("utf-8", errors="replace")


def extract_fragment_url(setup_script: str) -> str:
    match = re.search(r"https://cms-pdmv-prod\.web\.cern\.ch/mcm/public/restapi/requests/get_fragment/[A-Za-z0-9._-]+", setup_script)
    if not match:
        raise RuntimeError("Could not find a fragment URL in the McM setup script")
    return match.group(0)


def normalize_fragment_text(fragment_bytes: bytes) -> str:
    raw_text = fragment_bytes.decode("utf-8", errors="replace")
    stripped = raw_text.strip()

    # McM often returns the fragment as a JSON string literal rather than plain text.
    if stripped.startswith('"') and stripped.endswith('"'):
        text = json.loads(stripped)
    else:
        text = raw_text

    return text.lstrip("\n").replace("\r\n", "\n")


def download_fragment(fragment_url: str, output_path: Path) -> None:
    output_path.write_text(normalize_fragment_text(http_get(fragment_url)), encoding="utf-8")


def build_default_output(breaking_scale: str, ctau: str) -> Path:
    return Path.cwd() / f"GMSB_L_{breaking_scale}_ctau_{ctau}_13TeV_fragment.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="Download a GEN-SIM fragment from McM.")
    parser.add_argument(
        "--breaking-scale",
        required=True,
        help="Value between L- and TeV in the McM dataset name, for example 500.",
    )
    parser.add_argument(
        "--ctau",
        required=True,
        help="Value between Ctau- and cm in the McM dataset name, for example 100.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output fragment filename. Default: GMSB_L_xxx_ctau_xxx_13TeV_fragment.py in the current directory.",
    )
    args = parser.parse_args()

    try:
        dataset_name = build_dataset_name(args.breaking_scale, args.ctau)
        results = get_requests_for_dataset(dataset_name)
        request_data = choose_gensim_request(results)
        prepid = request_data["prepid"]
        setup_script = get_setup_script(prepid)
        fragment_url = extract_fragment_url(setup_script)
        output_path = Path(args.output) if args.output else build_default_output(args.breaking_scale, args.ctau)
        download_fragment(fragment_url, output_path)
    except (HTTPError, URLError) as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        return 1
    except (KeyError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Dataset       : {dataset_name}")
    print(f"GEN-SIM PrepID: {prepid}")
    print(f"Fragment URL  : {fragment_url}")
    print(f"Saved to      : {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
