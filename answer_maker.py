from llm.base import BaseLLM
from information_extractor.base import BaseIE

from pydantic import BaseModel, Field
from typing import List

class PotentialFilePlan(BaseModel):
    origin_path: str = Field(description="original file path from profile database.")
    reason: str = Field(description="the reason why this file potential to answer the question.")
    file_specific_query: str = Field(description="The sub-question is specifically designed for this file to extract the key information (e.g., 'Find May's revenue in the table')..")

class ExecutionPlan(BaseModel):
    potential_files: List[PotentialFilePlan] = Field(description="A list of potential files, sorted in descending order of priority.")

from pydantic import BaseModel, Field
from typing import List, Optional

class FinalQAOutput(BaseModel):
    evidences: List[str] = Field(
        description="Danh sách các đường dẫn file gốc thực sự đóng góp thông tin chính xác để trả lời câu hỏi."
    )
    reasoning: str = Field(
        description="Tóm tắt ngắn gọn các bước logic hoặc phép toán/lọc dữ liệu đã thực hiện để ra kết quả."
    )
    final_answer: str = Field(
        description="Đáp án cuối cùng duy nhất (Short Answer). CHỈ điền giá trị cốt lõi, con số cụ thể, hoặc tên thực thể. Không giải thích, không thêm chữ rác, không chứa markdown, tối ưu để so khớp exact match với Groundtruth."
    )

import os
import json
from typing import List, Dict, Optional, Type
from pydantic import BaseModel

from llm.base import BaseLLM
from information_extractor.base import BaseIE, ExtractionResult

class AnswerMaker:
    def __init__(self, llm: BaseLLM, default_ie: BaseIE, specific_ie: Optional[Dict[BaseIE, List[str]]] = None):
        self.llm = llm
        self.default_ie = default_ie
        self.specific_ie = specific_ie or {}
        
        self.ext_to_ie_map: Dict[str, BaseIE] = {}
        for ie_engine, exts in self.specific_ie.items():
            for ext in exts:
                self.ext_to_ie_map[ext.lower().replace(".", "")] = ie_engine

    def _get_ie_for_file(self, file_path: str) -> BaseIE:
        ext = file_path.lower().split('.')[-1]
        return self.ext_to_ie_map.get(ext, self.default_ie)

    def plan(self, question: str, profiles_path: str) -> ExecutionPlan:
        if not os.path.exists(profiles_path):
            raise FileNotFoundError(f"Không tìm thấy file profiles tại: {profiles_path}")
            
        with open(profiles_path, "r", encoding="utf-8") as f:
            profiles_data = json.load(f)

        prompt = f"""You are the Master Planner of a Data Lake QA system.
Your job is to read a list of file profiles (including their paths and semantic summaries) and select the MINIMUM number of files required to fully answer the user's question. Do not skip any file that potentially contains the answer.

User Question: "{question}"

Available File Profiles:
{json.dumps(profiles_data, ensure_ascii=False, indent=2)}

CRITICAL INSTRUCTIONS:
1. Select only files that are highly relevant to the question.
2. Sort the selected files in the 'potential_files' list by order of necessity/importance (most critical files first).
3. For each selected file, create a 'file_specific_query'. This is a tailored instruction/question for that specific file to extract exactly what we need (e.g., if user asks for total revenue, and the file is a call log, specific query could be 'Extract any mention of contract values or revenue numbers').

Output your plan strictly matching the requested JSON schema."""

        execution_plan: ExecutionPlan = self.llm.generate(
            prompt=prompt,
            files=None,
            OutputModel=ExecutionPlan
        )
        return execution_plan

    def answer(self, question: str, profiles_path: str) -> str:
        # Bước 1: Lập kế hoạch chọn file
        print(f"📋 Đang lập kế hoạch tìm kiếm file cho câu hỏi: '{question}'")
        execution_plan = self.plan(question, profiles_path)
        
        if not execution_plan.potential_files:
            return "Hệ thống đã quét qua hồ dữ liệu nhưng không tìm thấy file nào chứa thông tin liên quan đến câu hỏi của bạn."

        print(f"🎯 Đã tìm thấy {len(execution_plan.potential_files)} file tiềm năng.")
        
        # Đọc lại file profiles để map từ origin_path sang processed_path nhanh hơn
        with open(profiles_path, "r", encoding="utf-8") as f:
            profiles_list = json.load(f)
        path_to_processed_map = {p["origin_path"]: p["processed_path"] for p in profiles_list}

        # Lưu trữ tất cả các mảnh thông tin thu thập được từ các file
        collected_context = []

        # Bước 2: Vòng lặp duyệt qua từng file tiềm năng theo đúng thứ tự ưu tiên
        for idx, file_plan in enumerate(execution_plan.potential_files):
            origin_path = file_plan.origin_path
            specific_query = file_plan.file_specific_query
            
            # Lấy danh sách các file đã qua xử lý (ví dụ: danh sách ảnh từ excel)
            processed_paths = path_to_processed_map.get(origin_path, [])
            
            if not processed_paths:
                print(f"⚠️ Bỏ qua {origin_path} do không tìm thấy file sau xử lý (processed_paths rỗng).")
                continue
                
            print(f"\n[{idx + 1}/{len(execution_plan.potential_files)}] Đang trích xuất: {origin_path}")
            print(f"💡 Query chuyên biệt cho file: '{specific_query}'")
            
            # Tự động chọn bộ IE phù hợp (ví dụ ExcelIE cho xlsx, LLMIE cho pdf)
            ie_engine = self._get_ie_for_file(origin_path)
            
            # Tiến hành trích xuất sâu (gửi danh sách file sau xử lý vào IE)
            result: ExtractionResult = ie_engine.extract(
                query=specific_query,
                processed_file_paths=processed_paths, # Nhận danh sách list[str] đúng chuẩn bạn vừa sửa
                original_file_path=origin_path
            )
            
            print(f"🔍 Trạng thái trích xuất: {result.status}")
            
            if result.status in ["FOUND", "PARTIAL"]:
                # Đóng gói thông tin kèm nguồn gốc rõ ràng để LLM cuối tổng hợp không bị lộn
                file_evidence = f"--- Nguồn từ file: {origin_path} ---\nNội dung trích xuất: {result.extracted_info}\nBằng chứng trực tiếp: {result.quotes}\n"
                collected_context.append(file_evidence)
                
                # Logic cốt lõi của Baseline: Nếu đã tìm đủ (FOUND) thông tin, DỪNG vòng lặp ngay lập tức
                # if result.status == "FOUND":
                #     print("🎯 Đã tìm đủ thông tin cần thiết! Kết thúc sớm vòng lặp.")
                #     break
            else:
                print(f"⏭️ File {origin_path} không cung cấp thêm thông tin hữu ích.")

        if not collected_context:
            return "Mặc dù tìm thấy các file có vẻ tiềm năng, nhưng khi đi sâu vào phân tích chi tiết, hệ thống không thể trích xuất được thông tin xác thực nào."

        # Bước 3: Tổng hợp toàn bộ context đã gom được để LLM viết câu trả lời cuối cùng cho user
        print("\n✍️ Đang tổng hợp dữ liệu thu thập được để soạn câu trả lời cấu trúc...")
        
        final_generation_prompt = f"""You are the Final Answer Synthesizer in a Data Lake QA system.
Your job is to parse the verified extraction outputs and synthesize them strictly into the requested JSON schema.

User Question: "{question}"

Verified Facts Extracted from Data Lake (Execution Outputs & Synthesized Text):
{"".join(collected_context)}

CRITICAL FORMATTING INSTRUCTIONS:
1. 'evidences': Extract only the real file paths that were used in the calculations or facts (e.g., ["dlake/biomedical/1-s2.0-S0092867420301070-mmc6.xlsx"]).
2. 'reasoning': Briefly explain the aggregation logic (e.g., "Summed significant unique genes across Sheet 3 (18) and Sheet 6 (379)...").
3. 'final_answer': This must be the STRICT, RAW short answer. 
   - If the groundtruth is expected to be a number, return ONLY the raw string of that final number (e.g., "16").
   - If it is a list of genes, return only their exact names (e.g., "CDK12 and SMARCA4").
   - DO NOT include prefixes like "The final answer is", DO NOT include source citations inside this field, and DO NOT add conversational prose. Keep it completely clean."""

        # Gọi LLM sinh dữ liệu dưới dạng cấu trúc Pydantic Model
        final_response: FinalQAOutput = self.llm.generate(
            prompt=final_generation_prompt, 
            files=None,
            OutputModel=FinalQAOutput
        )
        
        # Bạn có thể return object Pydantic này, hoặc return text JSON/chỉ return field mong muốn tùy cấu trúc pipeline chính
        return final_response

