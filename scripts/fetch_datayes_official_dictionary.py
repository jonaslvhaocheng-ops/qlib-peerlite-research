#!/usr/bin/env python3
"""Freeze exact public DataYes dictionary entries as hashed source evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE_URL = "https://gw.datayes.com/data_dic/es/searchAll"
TARGETS = (
    "mkt_equd",
    "idx_cons_core",
    "md_security",
    "md_trade_cal",
    "mkt_limit",
    "md_sec_halt",
    "equ_inst_sstate",
    "mkt_adjf",
)


def fetch_exact(table_name: str) -> dict[str, object]:
    query = urlencode({"text": table_name, "from": 0, "size": 50})
    url = f"{BASE_URL}?{query}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Qlib-PeerLite-source-evidence/0.1",
        },
    )
    with urlopen(request, timeout=30) as response:
        body = response.read()
        status = response.status
        content_type = response.headers.get("Content-Type")
    payload = json.loads(body)
    exact = [item for item in payload.get("data", []) if item.get("nameEn") == table_name]
    if len(exact) != 1:
        raise RuntimeError(
            f"Expected exactly one official dictionary entry for {table_name}, found {len(exact)}"
        )
    return {
        "request_url": url,
        "http_status": status,
        "content_type": content_type,
        "api_success": payload.get("success"),
        "api_message": payload.get("msg"),
        "api_total_matches": payload.get("total"),
        "exact_entry": exact[0],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    evidence = {
        "schema_version": "qlib_peerlite_datayes_public_dictionary_v1",
        "fetched_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "publisher": "DataYes",
        "dictionary_home": "https://datadic.datayes.com/",
        "api_base": BASE_URL,
        "transport": "public HTTPS read-only GET",
        "entries": {target: fetch_exact(target) for target in TARGETS},
        "interpretation_limits": [
            "The captured response proves the public dictionary content at fetch time.",
            "It does not prove that the vendor retains all historical revisions.",
            "UPDATE_TIME is not reinterpreted as a market-availability timestamp.",
        ],
    }
    output_path = args.output_dir / "datayes_public_dictionary.json"
    output_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "qlib_peerlite_evidence_manifest_v1",
        "files": {output_path.name: hashlib.sha256(output_path.read_bytes()).hexdigest()},
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(args.output_dir), **manifest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
