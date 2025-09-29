[![CI](https://github.com/RohitRajdev/dataprep-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/RohitRajdev/dataprep-ai/actions)
[![PyPI](https://img.shields.io/pypi/v/dataprep-ai)](https://pypi.org/project/dataprep-ai/)
[![Python Versions](https://img.shields.io/pypi/pyversions/dataprep-ai)](https://pypi.org/project/dataprep-ai/)
[![License](https://img.shields.io/pypi/l/dataprep-ai)](https://github.com/RohitRajdev/dataprep-ai/blob/main/LICENSE)
[![Downloads](https://static.pepy.tech/badge/dataprep-ai/month)](https://pepy.tech/project/dataprep-ai)







# dataprep-ai

**One-line, opinionated data cleaning for pandas/Polars.**  
Fix missing values, inconsistent categories, outliers, and duplicates with transparent logs and a reproducible report.

---

## Installation

```bash
pip install dataprep-ai

----
For the optional explorer app:
pip install "dataprep-ai[app]"

Requirements

Python: 3.9 – 3.12

OS: Linux, macOS, Windows

Required libs (auto-installed): pandas, numpy, pyarrow, scikit-learn, pydantic, rich

Optional:

polars (enabled automatically where supported) — Polars round-trip I/O

streamlit, matplotlib — only needed for the explorer

Quickstart:

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
    categorical_normalization=True,
    drop_duplicates=False
))

print(result.summary_markdown)  # see cleaning report
df_clean = result.df            # cleaned DataFrame
result.to_json("clean_report.json")

Streamlit Explorer:

pip install "dataprep-ai[app]"
streamlit run -m dataprep_ai.explore -- --csv your.csv

Backends

Input = pandas.DataFrame → Output = pandas.DataFrame

Input = polars.DataFrame → Output = polars.DataFrame (internally converts via pandas in v0.1)

License

Apache-2.0


