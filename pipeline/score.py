"""Raw criterion values and national percentile ranks (docs/SPEC.md §4)."""

import numpy as np
import pandas as pd

from pipeline.config import CRITERIA, LOWER_IS_BETTER, NO_BAKERY_BOOST, NO_BAKERY_BOOST_FROM, NO_BAKERY_BOOST_FULL


def criteria(df: pd.DataFrame) -> pd.DataFrame:
    """Raw value of each criterion, in the units shown to the user (NaN = not available)."""
    # Inhabitants per existing bakery; none when the commune has no bakery (shown as "aucune").
    per_bakery = (df["pop"] / df["bakeries"]).where(df["bakeries"] > 0)
    raw = pd.DataFrame(
        {
            "per_bakery": per_bakery,
            "income": df["income"],
            "growth": df["growth"],
            "crime": df["crime"],
            "sell_soon": np.nan,  # RNE signal arrives in M6
        },
        index=df.index,
    )
    # Uninhabited communes (the Meuse villages destroyed in 1916) are not scored.
    return raw.where(df["pop"] > 0)


def percentile(values: pd.Series) -> pd.Series:
    """Rank among communes with a value, 0..1000 (ties share the mid-rank); NaN stays NaN."""
    valid = values.dropna()
    if len(valid) < 2:
        return pd.Series(np.nan, index=values.index)
    p = (valid.rank(method="average") - 1) / (len(valid) - 1)
    return (1000 * p).round().reindex(values.index)


def no_bakery_factor(pop: pd.Series) -> pd.Series:
    """Boost for a commune without a bakery: 1 below NO_BAKERY_BOOST_FROM inhabitants (too small to
    sustain a bakery, so ranked as if it had one), NO_BAKERY_BOOST from NO_BAKERY_BOOST_FULL, linear between."""
    share = ((pop - NO_BAKERY_BOOST_FROM) / (NO_BAKERY_BOOST_FULL - NO_BAKERY_BOOST_FROM)).clip(0, 1)
    return 1 + (NO_BAKERY_BOOST - 1) * share


def percentiles(raw: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """National percentile per criterion, already inverted where lower is better.

    A commune without a bakery has no "inhabitants per bakery"; it is ranked on its population times
    no_bakery_factor (no competition is an opportunity, but only for a commune big enough).
    """
    ranked = raw.copy()
    no_bakery = (df["bakeries"] == 0) & (df["pop"] > 0)
    pop = df.loc[no_bakery, "pop"]
    ranked.loc[no_bakery, "per_bakery"] = pop * no_bakery_factor(pop)
    out = pd.DataFrame({c: percentile(ranked[c]) for c in CRITERIA}, index=raw.index)
    for c in LOWER_IS_BETTER:
        out[c] = 1000 - out[c]
    for c in CRITERIA:
        _check(ranked[c], out[c], c, inverted=c in LOWER_IS_BETTER)
    return out


def _check(values: pd.Series, pct: pd.Series, name: str, inverted: bool) -> None:
    """Percentiles stay in 0..1000 and follow the order of the values.

    Ties share a mid-rank, so the extremes are not always exactly 0 and 1000 (e.g. the many
    communes with no recorded offence all share one rank).
    """
    both = pd.DataFrame({"v": values, "p": pct}).dropna()
    if both.empty:
        return
    if both.p.min() < 0 or both.p.max() > 1000:
        raise AssertionError(f"percentiles of {name} outside 0..1000")
    steps = both.sort_values("v").p.diff().dropna()
    if (steps > 0).any() if inverted else (steps < 0).any():
        raise AssertionError(f"percentiles of {name} do not follow the order of its values")
