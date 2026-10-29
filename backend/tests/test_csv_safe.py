import pandas as pd

from app.shared.csv_safe import safe_cell, safe_frame


def test_formula_cells_are_quoted():
    assert safe_cell('=HYPERLINK("http://evil","x")') == "'=HYPERLINK(\"http://evil\",\"x\")"
    assert safe_cell("-2+3|cmd") == "'-2+3|cmd"
    assert safe_cell("@SUM(A1)") == "'@SUM(A1)"
    assert safe_cell("TXN-1") == "TXN-1"
    assert safe_cell(12.5) == 12.5
    assert safe_cell(None) is None


def test_frame_keeps_numbers_and_fixes_text_and_headers():
    df = pd.DataFrame({"=id": ["=1+1", "ok"], "amount": [-5.0, 3.0]})
    out = safe_frame(df)
    assert list(out.columns) == ["'=id", "amount"]
    assert out["'=id"].tolist() == ["'=1+1", "ok"]
    assert out["amount"].tolist() == [-5.0, 3.0]
    assert "=1+1" not in out.to_csv(index=False).replace("'=1+1", "")
