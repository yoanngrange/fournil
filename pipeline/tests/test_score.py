import numpy as np
import pandas as pd

from pipeline import score


def test_percentile_ties_and_missing():
    s = pd.Series([10, 20, 20, 30, np.nan], index=list("abcde"))
    p = score.percentile(s)
    assert p["a"] == 0 and p["d"] == 1000
    assert p["b"] == p["c"] == 500  # ties share the mid-rank
    assert np.isnan(p["e"])


def test_crime_is_inverted_and_no_bakery_is_boosted():
    df = pd.DataFrame(
        {
            "pop": [1000, 1000, 2000, 500],
            "bakeries": [0, 1, 1, 0],
            "income": [20000, 21000, 22000, 23000],
            "growth": [0.1, 0.2, 0.3, 0.4],
            "crime": [5.0, 10.0, 20.0, np.nan],
        },
        index=["none", "one", "big", "tiny"],
    )
    raw = score.criteria(df)
    assert np.isnan(raw.at["none", "per_bakery"])  # no bakery: no ratio, shown as "aucune"
    assert raw.at["one", "per_bakery"] == 1000
    pct = score.percentiles(raw, df)
    assert pct.at["none", "per_bakery"] > pct.at["one", "per_bakery"]
    assert pct.at["none", "per_bakery"] > pct.at["big", "per_bakery"]  # 1000 × 3 > 2000 / 1
    assert pct.at["none", "crime"] == 1000  # lowest crime ranks best
    assert np.isnan(pct.at["tiny", "crime"])
    assert pct["sell_soon"].isna().all()
