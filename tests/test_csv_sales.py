import csv
import tempfile
import unittest
from pathlib import Path
from csv_sales import FIELDS, process


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


class SalesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def source(self, rows, encoding="utf-8-sig"):
        path = self.root / "input.csv"
        with path.open("w", encoding=encoding, newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(FIELDS)
            writer.writerows(rows)
        return path

    def test_sample_matches_committed_expected_output(self):
        repo = Path(__file__).resolve().parents[1]
        out = self.root / "out"
        result = process(sorted((repo / "sample").glob("*.csv")), out)
        self.assertEqual(result, {"accepted": 5, "rejected": 5})
        for name in ("clean.csv", "errors.csv", "daily_summary.csv"):
            self.assertEqual((out / name).read_bytes(), (repo / "output" / name).read_bytes())
        self.assertEqual(read(out / "daily_summary.csv"), [
            {"date": "2026-10-01", "quantity": "3", "amount": "1100.00"},
            {"date": "2026-10-02", "quantity": "7", "amount": "1161.50"},
            {"date": "2026-10-03", "quantity": "1", "amount": "300.00"}])

    def test_quoted_newlines_and_decimal_amount(self):
        path = self.source([["T1", "2026-10-01", '仮想,商品\n"青"', "3", "0.10"]])
        out = self.root / "out"
        self.assertEqual(process([path], out)["accepted"], 1)
        self.assertEqual(read(out / "clean.csv")[0]["amount"], "0.30")
        self.assertEqual(read(out / "clean.csv")[0]["item"], '仮想,商品\n"青"')

    def test_invalid_rows_and_duplicates_are_isolated(self):
        valid = ["T1", "2026-10-01", "仮想", "1", "100"]
        path = self.source([valid, valid, ["", "2026-02-30", "仮想", "0", "NaN"]])
        out = self.root / "out"
        self.assertEqual(process([path], out), {"accepted": 1, "rejected": 2})
        errors = read(out / "errors.csv")
        self.assertEqual(errors[0]["reason"], "duplicate_order_item")
        for reason in ("missing:order_id", "invalid_date", "invalid_quantity", "invalid_unit_price"):
            self.assertIn(reason, errors[1]["reason"])

    def test_cp932_and_formula_text(self):
        path = self.source([["T1", "2026-10-01", "架空品", "1", "1"],
                            ["T2", "2026-10-01", "=1+1", "1", "1"]], "cp932")
        out = self.root / "out"
        self.assertEqual(process([path], out, "cp932"), {"accepted": 1, "rejected": 1})
        self.assertEqual(read(out / "errors.csv")[0]["item"], "'=1+1")

    def test_schema_error_creates_no_output(self):
        path = self.root / "bad.csv"
        path.write_text("wrong,header\n1,2\n", encoding="utf-8")
        out = self.root / "out"
        with self.assertRaises(ValueError):
            process([path], out)
        self.assertFalse(out.exists())

    def test_existing_output_is_not_overwritten(self):
        path = self.source([["T1", "2026-10-01", "仮想", "1", "1"]])
        out = self.root / "out"
        out.mkdir()
        (out / "keep.txt").write_text("keep")
        with self.assertRaises(FileExistsError):
            process([path], out)
        self.assertEqual((out / "keep.txt").read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
