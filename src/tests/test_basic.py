import pandas as pd
from dataprep_ai import clean, CleaningConfig

def test_basic_clean():
    df = pd.DataFrame({
        "age":[23, None, 25, 1000],
        "city":["NY","New York","nyc", None]
    })
    cfg = CleaningConfig(
        category_aliases={"New York": ["NY","nyc","new york"]},
        drop_duplicates=False  # keep all rows for this test
    )
    res = clean(df, cfg)
    assert len(res.df) == 4
    assert res.df["age"].isna().sum() == 0
    assert "Rows before" in res.summary_markdown
