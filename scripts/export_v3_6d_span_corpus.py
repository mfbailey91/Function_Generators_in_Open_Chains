#!/usr/bin/env python3
"""Export the V3.6D canonical span corpus."""

from __future__ import annotations

import argparse
from pathlib import Path

from inequality_mechanisms.audits.span_corpus import export_span_corpus
from inequality_mechanisms.experiments.span_wrench_config import DEFAULT_CONFIG_REL


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_REL)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    path = export_span_corpus(config_path=args.config, output=args.output)
    print(path)


if __name__ == "__main__":
    main()
