import os
import sys
import io
import json
import pandas as pd
from typing import List

from llm.base import BaseLLM
from information_extractor.base import BaseIE, ExtractionResult

class CSVIE(BaseIE):
    def __init__(self, llm: BaseLLM, coder_llm: BaseLLM):
        self.llm = llm
        self.coder_llm = coder_llm

    def _execute_code(self, code: str, csv_path: str) -> str:
        old_stdout = sys.stdout
        redirected_output = io.StringIO()
        sys.stdout = redirected_output
        
        # Cung cấp biến `csv_path` chỉ đường dẫn tới file CSV gốc để code đọc
        local_vars = {"csv_path": csv_path}
        
        try:
            exec(code, {}, local_vars)
        except Exception as e:
            print(f"Lỗi thực thi Code nội bộ: {str(e)}")
        finally:
            sys.stdout = old_stdout
            
        return redirected_output.getvalue()

    def extract(self, query: str, processed_file_paths: List[str], original_file_path: str) -> ExtractionResult:
        print(f"\n[CSV_IE_START] Phân tích file CSV gốc: {original_file_path}")
        
        if not processed_file_paths:
            return ExtractionResult(status="NOT_FOUND", extracted_info="Không tìm thấy file metadata JSON của CSV.", quotes=[], missing_info=None)
            
        # 1. Đọc file JSON chứa CSVInfo (file đầu tiên trong danh sách)
        metadata_json_path = processed_file_paths[0]
        if not os.path.exists(metadata_json_path):
            print(f"   ❌ [DEBUG_ERROR] Không tìm thấy file metadata tại: {metadata_json_path}")
            return ExtractionResult(status="NOT_FOUND", extracted_info="File metadata JSON không tồn tại.", quotes=[], missing_info=None)

        with open(metadata_json_path, "r", encoding="utf-8") as f:
            csv_info_data = json.load(f)
            
        print(f"   📋 Đã nạp thành công Metadata CSV. Tiến hành dựng Schema cho Coder LLM...")

        # 2. Tạo Prompt điều hướng cho Coder LLM dựa trên thông tin cấu trúc cột có sẵn
        code_prompt = f"""You are an expert Python Data Scientist and Bioinformatician. 
Your task is to write a short, clean Python script to answer the user's query by analyzing a CSV file.

User Query: "{query}"

The CSV file is located at the path stored in the variable `csv_path`.
CSV Structural Metadata (Columns, types, and summary):
{json.dumps(csv_info_data, ensure_ascii=False, indent=2)}

CRITICAL EXECUTION INSTRUCTIONS:
1. Use `pandas` to read the file via `pd.read_csv(csv_path)`.
2. ALWAYS handle mixed data types or string numbers safely by using `pd.to_numeric(df['column_name'], errors='coerce')` before applying numerical filters (like `< 0.05`).
3. Statistical Significance Rule: If filtering for significance, a row is valid ONLY when BOTH P-value < 0.05 AND FDR/Adjusted P-value < 0.05 using the bitwise intersection (`&`).
4. Counting Entities: If counting biological rows or genes, make sure to use `.nunique()` on the specific identification/Name column to avoid duplication. Drop NaN values if necessary.
5. You MUST use `print()` to print out the final answer/count clearly.
6. Return ONLY valid executable Python code block. Do not include markdown code ticks (```python) inside your actual execution path.

Write the Python code now:"""

        # 3. Sinh mã và thực thi trực tiếp trên file CSV gốc (original_file_path)
        code_response = self.coder_llm.generate(prompt=code_prompt, files=None)
        raw_code = code_response.text.replace("```python", "").replace("```", "").strip()
        
        print(f"   💻 [DEBUG_CODE] Đoạn code sinh ra cho CSV:\n{'-'*30}\n{raw_code}\n{'-'*30}")
        
        # Thực thi code trên file gốc
        execution_output = self._execute_code(raw_code, original_file_path)
        print(f"   🖥️ [DEBUG_STDOUT] Kết quả thực thi trên CSV gốc:\n{execution_output.strip()}")

        # 4. Đóng gói kết quả về đúng Schema chuẩn của hệ thống
        synthesis_prompt = f"""You are a data verifier. Analyze the calculated outputs from a CSV code execution environment and format them into the required response schema.

User Original Query: "{query}"
Calculated Outputs from Code Execution:
{execution_output}

Fill out the schema. If the calculated numbers fully answer the query, set status to 'FOUND'."""

        print("   🧠 Đang chuẩn hóa đầu ra về định dạng ExtractionResult...")
        final_result: ExtractionResult = self.llm.generate(
            prompt=synthesis_prompt,
            files=None,
            OutputModel=ExtractionResult
        )
        return final_result
    
