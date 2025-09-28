![CI](https://github.com/RohitRajdev/dataprep-ai/actions/workflows/ci.yml/badge.svg)

dataprep-ai

One-line, opinionated data cleaning for pandas/Polars.

Fix missing values, inconsistent categories, outliers, and duplicates with transparent logs and a reproducible report.

pip install dataprep-ai

Quickstart

import pandas as pd
from dataprep_ai import clean, CleaningConfig

df = pd.DataFrame({
  "age":[23, None, 25, 1000],
  "income":[52000, 58000, None, 1200000],
  "city":["NY","New York","nyc", None],
  "id":[1,2,2,4]
})

result = clean(df, CleaningConfig(
  id_columns=["id"],
  outlier_strategy="iqr_cap",
  categorical_normalization=True
))

print(result.summary_markdown)
df_clean = result.df
result.to_json("clean_report.json")

Streamlit explorer
pip install "dataprep-ai[app]"
streamlit run -m dataprep_ai.explore -- --csv your.csv

License

Apache-2.0
