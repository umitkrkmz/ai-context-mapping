"""Export order records from a JSON file to CSV, TSV, JSON, XML, HTML, or Markdown."""
import argparse
import json
import sys

from shipdesk.exporters import csv_export, html_export, json_export, markdown_export, tsv_export, xml_export

FORMATS = {"csv": csv_export, "tsv": tsv_export, "json": json_export, "xml": xml_export, "html": html_export, "md": markdown_export}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Export order records.")
    parser.add_argument("source", help="JSON file containing a list of order records")
    parser.add_argument("--format", choices=sorted(FORMATS), default="csv")
    args = parser.parse_args(argv)
    with open(args.source, encoding="utf-8") as handle:
        records = json.load(handle)
    sys.stdout.write(FORMATS[args.format].render(records) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
