import sys

# Patch for numpy 2.0 pickle
import numpy as np
import pandas as pd

if "numpy._core" not in sys.modules and hasattr(np, "core"):
    sys.modules["numpy._core"] = np.core
    # Also patch submodules
    for sub in ["multiarray", "umath", "numeric", "fromnumeric", "defchararray"]:
        if hasattr(np.core, sub):
            sys.modules[f"numpy._core.{sub}"] = getattr(np.core, sub)


def check_pred(path):
    print(f"Checking {path}")
    try:
        df = pd.read_pickle(path)
        print(f"Columns: {df.columns}")
        if isinstance(df.index, pd.MultiIndex):
            print(f"Index names: {df.index.names}")
            dates = df.index.get_level_values("datetime")
            print(f"Date range: {dates.min()} to {dates.max()}")
            instruments = df.index.get_level_values("instrument").unique()
            print(f"Instruments count: {len(instruments)}")
            print(f"Sample instruments: {instruments[:5]}")
        else:
            print("Not a MultiIndex")
            print(df.head())
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    check_pred(r"e:\code\quantmind\research\data_adapter\qlib_data\predictions\pred.pkl")
