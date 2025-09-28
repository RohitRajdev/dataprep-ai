from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
import json

try:
    import polars as pl
except Exception:
    pl = None

import pandas as pd
import numpy as np
from pydantic import BaseModel, Field, field_validator
from rich.console import Console
from rich.table import Table

console = Console()

def _is_polars_df(obj) -> bool:
    return pl is not None and isinstance(obj, pl.DataFrame)

def _to_pandas(df):
    if _is_polars_df(df):
        return df.to_pandas(use_pyarrow=False)
    return df

def _from_pandas(df_pd, like):
    if _is_polars_df(like):
        return pl.from_pandas(df_pd)
    return df_pd

class CleaningConfig(BaseModel):
    id_columns: Sequence[str] = Field(default_factory=list)
    numeric_imputation: str = "median"  # "mean" | "median" | "constant"
    numeric_constant: float = 0.0
    categorical_imputation: str = "mode"  # "mode" | "constant"
    categorical_constant: str = "UNKNOWN"
    outlier_strategy: str = "iqr_cap"  # "none" | "iqr_cap" | "zscore_remove"
    zscore_threshold: float = 4.0
    categorical_normalization: bool = True
    category_aliases: Dict[str, Sequence[str]] = Field(default_factory=dict)
    drop_duplicates: bool = True
    report_title: str = "DataPrep-AI Cleaning Report"

    @field_validator('numeric_imputation')
    @classmethod
    def _check_num_imp(cls, v):
        assert v in {"mean", "median", "constant"}
        return v

    @field_validator('categorical_imputation')
    @classmethod
    def _check_cat_imp(cls, v):
        assert v in {"mode", "constant"}
        return v

    @field_validator('outlier_strategy')
    @classmethod
    def _check_out(cls, v):
        assert v in {"none", "iqr_cap", "zscore_remove"}
        return v

class RevertPatch(BaseModel):
    dtype_changes: Dict[str, str] = {}
    imputations: Dict[str, Dict[str, Any]] = {}
    cat_norm_maps: Dict[str, Dict[str, str]] = {}
    outlier_caps: Dict[str, Dict[str, Any]] = {}
    zscore_removed_rows: List[int] = []
    dropped_duplicates_rows: List[Tuple[int, Dict[str, Any]]] = []

@dataclass
class CleanResult:
    df: Any  # pandas or polars
    changes: List[Dict[str, Any]]
    summary_markdown: str
    patch: RevertPatch

    def to_json(self, path: str):
        with open(path, "w") as f:
            json.dump({"changes": self.changes, "summary_markdown": self.summary_markdown, "patch": self.patch.model_dump()}, f, indent=2)

    def revert(self) -> Any:
        df = _to_pandas(self.df).copy()
        p = self.patch

        if p.dropped_duplicates_rows:
            import pandas as pd
            recs = [r for _, r in p.dropped_duplicates_rows]
            restore_df = pd.DataFrame.from_records(recs)
            df = pd.concat([df, restore_df], ignore_index=True)

        for col, info in p.outlier_caps.items():
            idxs = info.get("indices", [])
            old = info.get("old", [])
            for i, v in zip(idxs, old):
                if i < len(df):
                    df.at[i, col] = v

        for col, mapping in p.cat_norm_maps.items():
            if col in df.columns:
                df[col] = df[col].map(lambda x: mapping.get(str(x), x))

        for col, info in p.imputations.items():
            idxs = info.get("indices", [])
            olds = info.get("old", [])
            for i, v in zip(idxs, olds):
                if i < len(df):
                    df.at[i, col] = v

        return _from_pandas(df, self.df)

def _impute_numeric_series(s: pd.Series, strategy: str, constant: float):
    if s.isna().sum() == 0:
        return s, None, [], []
    if strategy == "mean":
        val = s.mean()
    elif strategy == "median":
        val = s.median()
    else:
        val = constant
    idxs = s[s.isna()].index.tolist()
    olds = [np.nan] * len(idxs)
    return s.fillna(val), float(val), idxs, olds

def _impute_categorical_series(s: pd.Series, strategy: str, constant: str):
    if s.isna().sum() == 0:
        return s, None, [], []
    if strategy == "mode":
        if s.dropna().empty:
            val = constant
        else:
            val = s.mode(dropna=True).iloc[0]
    else:
        val = constant
    idxs = s[s.isna()].index.tolist()
    olds = [np.nan] * len(idxs)
    return s.fillna(val), str(val), idxs, olds

def _normalize_categories(s: pd.Series, aliases):
    mapping = {}
    base = s.astype(str).str.strip().str.lower()
    for canonical, alist in aliases.items():
        canonical_l = str(canonical).strip().lower()
        for a in alist:
            mapping[str(a).strip().lower()] = canonical_l
    normalized = base.map(lambda x: mapping.get(x, x)).str.title()
    reverse = {}
    for k, v in mapping.items():
        reverse[v.title()] = k.title()
    return normalized, reverse

def _iqr_caps(s: pd.Series):
    q1 = s.quantile(0.25)
    q3 = s.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    mask = (s < lower) | (s > upper)
    idxs = s[mask].index.tolist()
    olds = s[mask].tolist()
    capped = s.clip(lower, upper)
    return capped, float(lower), float(upper), idxs, olds

def _zscore_filter(s: pd.Series, thr: float):
    mu, sd = s.mean(), s.std(ddof=0)
    if sd == 0 or np.isnan(sd):
        return s, 0, [], []
    z = (s - mu) / sd
    keep = z.abs() <= thr
    rem = (~keep)
    idxs = s[rem].index.tolist()
    olds = s[rem].tolist()
    return s[keep], int(rem.sum()), idxs, olds

def clean(df_any: Any, config: Optional[CleaningConfig] = None) -> CleanResult:
    cfg = config or CleaningConfig()
    df_like = df_any
    df = _to_pandas(df_any)
    work = df.copy()
    changes: List[Dict[str, Any]] = []
    patch = RevertPatch(imputations={}, cat_norm_maps={}, outlier_caps={}, zscore_removed_rows=[], dropped_duplicates_rows=[])

    start_rows, start_cols = work.shape

    # 1) Imputation
    for col in work.columns:
        s = work[col]
        if pd.api.types.is_numeric_dtype(s):
            new_s, val, idxs, olds = _impute_numeric_series(s, cfg.numeric_imputation, cfg.numeric_constant)
            if val is not None and len(idxs) > 0:
                changes.append({"step": "impute_numeric","column": col,"value": val,"missing_before": int(s.isna().sum())})
                patch.imputations[col] = {"indices": idxs, "old": olds}
            work[col] = new_s
        else:
            new_s, val, idxs, olds = _impute_categorical_series(s, cfg.categorical_imputation, cfg.categorical_constant)
            if val is not None and len(idxs) > 0:
                changes.append({"step": "impute_categorical","column": col,"value": val,"missing_before": int(s.isna().sum())})
                patch.imputations[col] = {"indices": idxs, "old": olds}
            work[col] = new_s

    # 2) Categorical normalization
    if cfg.categorical_normalization:
        for col in work.select_dtypes(include=["object","string"]).columns:
            work[col] = work[col].astype(str)
            new_s, reverse_map = _normalize_categories(work[col], cfg.category_aliases)
            if not new_s.equals(work[col]):
                changes.append({"step":"normalize_categories","column": col,"aliases_applied": cfg.category_aliases})
                patch.cat_norm_maps[col] = reverse_map
            work[col] = new_s

    # 3) Outliers
    removed_row_indices = set()
    if cfg.outlier_strategy == "iqr_cap":
        for col in work.select_dtypes(include=[np.number]).columns:
            s = work[col]
            capped, lower, upper, idxs, olds = _iqr_caps(s)
            if len(idxs) > 0:
                changes.append({"step":"outlier_cap_iqr","column": col,"lower": lower,"upper": upper,"capped": len(idxs)})
                patch.outlier_caps[col] = {"indices": idxs, "old": olds}
            work[col] = capped
    elif cfg.outlier_strategy == "zscore_remove":
        for col in work.select_dtypes(include=[np.number]).columns:
            s = work[col]
            filtered, removed, idxs, olds = _zscore_filter(s, cfg.zscore_threshold)
            if removed > 0:
                changes.append({"step":"outlier_remove_zscore","column": col,"removed": removed,"threshold": cfg.zscore_threshold})
                removed_row_indices.update(idxs)
        if removed_row_indices:
            patch.zscore_removed_rows = sorted(list(removed_row_indices))
            work = work.drop(index=patch.zscore_removed_rows, errors="ignore")

    # 4) Duplicates
    if cfg.drop_duplicates:
        subset = list(cfg.id_columns) if cfg.id_columns else None
        if subset:
            dup_mask = work.duplicated(subset=subset, keep="first")
        else:
            dup_mask = work.duplicated(keep="first")
        dropped = work[dup_mask]
        if not dropped.empty:
            changes.append({"step":"drop_duplicates","removed": int(len(dropped)),"subset": subset})
            patch.dropped_duplicates_rows = [(int(i), dropped.loc[i].to_dict()) for i in dropped.index]
        work = work.drop_duplicates(subset=subset, keep="first")

    # Summary
    end_rows, end_cols = work.shape
    tbl = Table(title=cfg.report_title)
    tbl.add_column("Metric"); tbl.add_column("Value")
    tbl.add_row("Rows before", str(start_rows))
    tbl.add_row("Rows after", str(end_rows))
    tbl.add_row("Columns", str(end_cols))
    tbl.add_row("Steps applied", ", ".join(sorted({c['step'] for c in changes})) if changes else "None")
    console.print(tbl)

    md = [f"# {cfg.report_title}","",f"- **Rows before:** {start_rows}",f"- **Rows after:** {end_rows}",f"- **Columns:** {end_cols}","","## Steps"]
    if not changes:
        md.append("No changes applied.")
    else:
        for c in changes:
            md.append(f"- `{c['step']}` \u2192 {json.dumps({k:v for k,v in c.items() if k!='step'})}")
    summary_markdown = "\\n".join(md)

    work = work.reset_index(drop=True)
    out_df = _from_pandas(work, df_like)
    return CleanResult(df=out_df, changes=changes, summary_markdown=summary_markdown, patch=patch)
