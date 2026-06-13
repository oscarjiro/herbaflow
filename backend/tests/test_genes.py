from app.pipeline.genes import distinct_gene_symbol_rows, distinct_gene_symbols


def test_distinct_gene_symbol_rows_first_seen_wins_and_drops_null():
    rows = [
        {"gene_symbol": "TP53", "x": 1},
        {"gene_symbol": None, "x": 2},
        {"gene_symbol": "TP53", "x": 3},
        {"gene_symbol": "EGFR", "x": 4},
    ]
    out = distinct_gene_symbol_rows(rows)
    assert [r["x"] for r in out] == [1, 4]  # first TP53 kept, null dropped, EGFR kept


def test_distinct_gene_symbols_returns_symbols_in_order():
    rows = [{"gene_symbol": "B"}, {"gene_symbol": "A"}, {"gene_symbol": "B"}]
    assert distinct_gene_symbols(rows) == ["B", "A"]
