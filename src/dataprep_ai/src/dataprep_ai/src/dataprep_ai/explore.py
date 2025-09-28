"""Streamlit explorer for quick EDA.

Usage:
  pip install "dataprep-ai[app]"
  streamlit run -m dataprep_ai.explore -- --csv path/to/data.csv
"""
import argparse
import pandas as pd
import numpy as np

def _app(df: pd.DataFrame):
    import streamlit as st
    import matplotlib.pyplot as plt

    st.title("DataPrep-AI: Explore")
    st.write("Quick EDA dashboard. Use the sidebar to filter.")

    with st.sidebar:
        st.header("Filters")
        cols = st.multiselect("Columns to view", list(df.columns), default=list(df.columns)[:5])
        nrows = st.slider("Rows", 100, min(5000, len(df)), min(1000, len(df)), step=100)

    st.subheader("Preview")
    st.dataframe(df[cols].head(nrows))

    st.subheader("Summary Stats (numeric)")
    st.write(df.select_dtypes(include=[np.number]).describe())

    st.subheader("Missingness")
    miss = df.isna().mean().sort_values(ascending=False)
    if not miss.empty:
        fig, ax = plt.subplots()
        miss.plot(kind="bar", ax=ax)
        ax.set_ylabel("Fraction missing")
        st.pyplot(fig)
    else:
        st.write("No missing values detected.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=str, help="Path to CSV file.")
    args, _ = parser.parse_known_args()
    if not args.csv:
        print("Please provide --csv path")
        return
    df = pd.read_csv(args.csv)
    _app(df)

if __name__ == "__main__":
    main()
