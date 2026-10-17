"""Reference list of communes (COG) and mapping of older commune codes onto the frozen vintage."""

from functools import cache

import pandas as pd

from pipeline import fetch
from pipeline.config import in_scope

MAX_UNMAPPED_SHARE = 0.001  # DATA.md §1: fail the build above 0.1 % unmapped codes


def communes() -> pd.DataFrame:
    """Communes in scope (metropolitan France + Corsica): code_insee, name, dep, reg."""
    cog = pd.read_csv(fetch.path("cog"), dtype=str)
    com = cog[cog.TYPECOM == "COM"]
    com = com[com.DEP.map(in_scope)]
    return (
        com.rename(columns={"COM": "code_insee", "LIBELLE": "name", "DEP": "dep", "REG": "reg"})[
            ["code_insee", "name", "dep", "reg"]
        ]
        .sort_values("code_insee")
        .reset_index(drop=True)
    )


@cache
def _out_of_scope_codes() -> set[str]:
    # Only true communes: delegated/associated communes have no DEP and often share the code of
    # the commune nouvelle they belong to.
    cog = pd.read_csv(fetch.path("cog"), dtype=str)
    com = cog[cog.TYPECOM == "COM"]
    return set(com[~com.DEP.map(in_scope)].COM)


@cache
def code_mapping() -> dict[str, str]:
    """Old commune code -> code in the frozen vintage, following merges recorded in the COG history.

    Also maps the municipal arrondissements of Paris, Lyon and Marseille onto their commune
    (MVP keeps those three cities whole).
    """
    cog = pd.read_csv(fetch.path("cog"), dtype=str)
    arm = cog[cog.TYPECOM == "ARM"]
    mvt = pd.read_csv(fetch.path("cog_mvt"), dtype=str)
    mvt = mvt[(mvt.COM_AV != mvt.COM_AP) & (mvt.TYPECOM_AP == "COM")].sort_values("DATE_EFF")
    mapping: dict[str, str] = {}
    for old, new in zip(mvt.COM_AV, mvt.COM_AP):
        mapping[old] = new
    # Follow chains (A -> B in 2019, B -> C in 2024).
    for old in list(mapping):
        seen, new = {old}, mapping[old]
        while new in mapping and new not in seen:
            seen.add(new)
            new = mapping[new]
        mapping[old] = new
    mapping.update(zip(arm.COM, arm.COMPARENT))
    return mapping


def align(df: pd.DataFrame, valid_codes: set[str], source: str, additive: bool) -> pd.DataFrame:
    """Re-key a per-commune table (index = commune code) onto the frozen COG.

    Additive tables (counts, populations) are summed when several old communes merged into one.
    Non-additive values (medians, rates) of merged communes are dropped: we cannot rebuild them.
    Codes that still do not match are logged; the build fails if they exceed MAX_UNMAPPED_SHARE.
    Rows of communes that exist in the COG but are out of scope (overseas) are dropped silently.
    """
    overseas_or_abroad = df.index.str[:2].isin(["97", "98", "99"])
    df = df[~df.index.isin(_out_of_scope_codes()) & ~overseas_or_abroad]
    unknown = df.index.difference(pd.Index(sorted(valid_codes)))
    if len(unknown):
        mapping = code_mapping()
        mapped = df.index.to_series().map(lambda c: c if c in valid_codes else mapping.get(c, c))
        if additive:
            df = df.groupby(mapped.values).sum(min_count=1)
        else:
            df = df.set_axis(mapped.values)
            df = df[~df.index.duplicated(keep=False)]
        unknown = df.index.difference(pd.Index(sorted(valid_codes)))
    if len(unknown):
        share = len(unknown) / max(len(df), 1)
        print(f"  [{source}] {len(unknown)} codes not in COG ({share:.3%}): {list(unknown[:10])}")
        if share > MAX_UNMAPPED_SHARE:
            raise RuntimeError(f"{source}: too many unmapped commune codes ({share:.2%})")
    return df[df.index.isin(valid_codes)]
