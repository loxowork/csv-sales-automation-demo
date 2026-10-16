"""Synthetic CSV sales validation demo. Standard library only; no network IO."""
import argparse
import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

FIELDS = ["order_id", "date", "item", "quantity", "unit_price"]
CLEAN = FIELDS + ["amount"]
ERROR = ["source", "row", "reason"] + FIELDS


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def safe_cell(value):
    """Protect textual cells when CSV is opened in spreadsheet software."""
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def process(inputs, output_dir, encoding="utf-8-sig"):
    clean, errors, seen = [], [], set()
    totals = defaultdict(lambda: [0, Decimal("0")])
    # Parse all inputs before creating output, so bad schemas do not leave partial results.
    for path in sorted(map(Path, inputs)):
        with path.open(encoding=encoding, newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            if reader.fieldnames != FIELDS:
                raise ValueError(f"{path.name}: expected header {','.join(FIELDS)}")
            for number, raw in enumerate(reader, 2):
                row = {key: (raw.get(key) or "").strip() for key in FIELDS}
                reasons = []
                if None in raw or any(raw.get(key) is None for key in FIELDS):
                    reasons.append("column_count")
                missing = [key for key in FIELDS if not row[key]]
                if missing:
                    reasons.append("missing:" + ",".join(missing))
                for key in ("order_id", "item"):
                    if row[key].startswith(("=", "+", "-", "@")):
                        reasons.append("formula_prefix:" + key)
                try:
                    if date.fromisoformat(row["date"]).isoformat() != row["date"]:
                        raise ValueError
                except ValueError:
                    reasons.append("invalid_date")
                try:
                    if not row["quantity"].isascii() or not row["quantity"].isdigit():
                        raise ValueError
                    quantity = int(row["quantity"])
                    if not 1 <= quantity <= 1_000_000:
                        raise ValueError
                except ValueError:
                    reasons.append("invalid_quantity")
                try:
                    price = Decimal(row["unit_price"])
                    if not price.is_finite() or not 0 <= price <= Decimal("1000000000"):
                        raise ValueError
                    if price.as_tuple().exponent < -2:
                        raise ValueError
                except (InvalidOperation, ValueError):
                    reasons.append("invalid_unit_price")
                key = (row["order_id"], row["item"])
                if key in seen:
                    reasons.append("duplicate_order_item")
                if reasons:
                    errors.append({"source": safe_cell(path.name), "row": number,
                                   "reason": ";".join(reasons),
                                   **{k: safe_cell(v) for k, v in row.items()}})
                    continue
                seen.add(key)
                amount = price * quantity
                clean.append({**row, "quantity": str(quantity),
                              "unit_price": f"{price:.2f}", "amount": f"{amount:.2f}"})
                totals[row["date"]][0] += quantity
                totals[row["date"]][1] += amount
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("output directory must be empty (existing results are not overwritten)")
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "clean.csv", CLEAN, clean)
    write_csv(output_dir / "errors.csv", ERROR, errors)
    write_csv(output_dir / "daily_summary.csv", ["date", "quantity", "amount"],
              [{"date": day, "quantity": values[0], "amount": f"{values[1]:.2f}"}
               for day, values in sorted(totals.items())])
    return {"accepted": len(clean), "rejected": len(errors)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--encoding", default="utf-8-sig", choices=["utf-8-sig", "cp932"])
    args = parser.parse_args()
    try:
        result = process(args.inputs, args.output_dir, args.encoding)
    except (OSError, ValueError, UnicodeError, csv.Error) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(f"accepted={result['accepted']} rejected={result['rejected']}")


if __name__ == "__main__":
    main()
