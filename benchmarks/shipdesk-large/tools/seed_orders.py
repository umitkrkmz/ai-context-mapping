"""Print the seed catalog as a table (a demo helper, not used by the library)."""
from shipdesk.catalog_seed import load_seed
from shipdesk.money import to_display


def main() -> int:
    for sku, item in sorted(load_seed().items()):
        print(f"{sku}  {item.name:<24}{to_display(item.unit_cents):>8}  {item.weight_grams:>5} g")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
