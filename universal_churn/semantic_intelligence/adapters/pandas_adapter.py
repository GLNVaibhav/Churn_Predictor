from __future__ import annotations
import pandas as pd
class PandasDatasetAdapter:
    def to_dataframe(self, dataset: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(dataset, pd.DataFrame): raise TypeError("V8 pandas adapter requires a pandas DataFrame.")
        return dataset
