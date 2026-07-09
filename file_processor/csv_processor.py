import os
import pandas as pd
from typing import List, Dict, Any
from pydantic import BaseModel

class CSVInfo(BaseModel):
    num_rows: int
    num_cols: int
    schema_dict: Dict[str, str]
    sample_data: List[Dict[str, Any]]
    structed_summary: str


class CSVProcessor:
    def __init__(self, sample_rows: int = 5):
        self.sample_rows = sample_rows

    def _map_dtype(self, pandas_type: str) -> str:
        t = str(pandas_type).lower()
        if 'int' in t or 'float' in t:
            return "num"
        if 'bool' in t:
            return "bool"
        if 'date' in t:
            return "datetime"
        return "str"

    def process(self, csv_path: str) -> CSVInfo:
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Không tìm thấy file: {csv_path}")

        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        
        num_rows = len(df)
        num_cols = len(df.columns)

        schema_dict = {
            str(col): self._map_dtype(str(dtype)) 
            for col, dtype in df.dtypes.items()
        }

        df_sample = df.head(self.sample_rows)
        sample_data = df_sample.to_dict(orient="records")

        summary_lines = [
            f"File: {os.path.basename(csv_path)}",
            f"Structure: {num_rows} rows, {num_cols} columns.",
            "Columns & Data Types:",
        ]
        for col, c_type in schema_dict.items():
            summary_lines.append(f"  - {col} ({c_type})")
            
        summary_lines.append("Sample Rows Preview:")
        summary_lines.append(str(sample_data))
        
        structed_summary = "\n".join(summary_lines)

        return CSVInfo(
            num_rows=num_rows,
            num_cols=num_cols,
            schema_dict=schema_dict,
            sample_data=sample_data,
            structed_summary=structed_summary
        )

if __name__ == "__main__":
    test_file = "sales_data.csv"
    df_test = pd.DataFrame({
        "Order_ID": [1001, 1002, 1003],
        "Product": ["Laptop", "Mouse", "Keyboard"],
        "Price": [1200.50, 25.00, None],
        "In_Stock": [True, True, False]
    })
    df_test.to_csv(test_file, index=False)

    processor = CSVProcessor(sample_rows=3)
    info = processor.process(test_file)

    print("--- TEXT ---")
    print(info.structed_summary)

