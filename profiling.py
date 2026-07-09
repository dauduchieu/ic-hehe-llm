import os
import json
import shutil
from pathlib import Path
from pydantic import BaseModel

from llm.base import BaseLLM, LLMResponse
from llm.qwen35b import QwenLLM

from file_processor.audio_processor import AudioProcessor, AudioInfo
from file_processor.csv_processor import CSVProcessor, CSVInfo
from file_processor.excel_processor import ExcelProcessor
from file_processor.office_processor import OfficeProcessor
from file_processor.html_processor import HTMLProcessor

class Profile(BaseModel):
    origin_path: str
    processed_path: list[str]
    summary_text: str

class Profiler:
    def __init__(self, llm: BaseLLM, processed_dir: str = "processed_files", datalake_dir: str = "dlake"):
        self.llm = llm
        self.processed_dir = processed_dir
        self.datalake_dir = datalake_dir
        
        os.makedirs(self.processed_dir, exist_ok=True)
        
        self.audio_exts = ["mp3", "wav", "m4a"]
        self.csv_exts = ["csv"]
        self.excel_exts = ["xlsx", "xls"]
        self.office_exts = ["doc", "docx", "ppt", "pptx"]
        self.html_exts = ["html", "htm"]
        
        self.audio_processor = AudioProcessor()
        self.csv_processor = CSVProcessor()
        self.excel_processor = ExcelProcessor()
        self.office_processor = OfficeProcessor()
        self.html_processor = HTMLProcessor()
        
    def _get_file_stem(self, file_path: str) -> str:
        return Path(file_path).stem

    def _get_target_dir(self, file_path: str) -> str:
        """
        Tạo và trả về thư mục đích tương ứng với cấu trúc thư mục của file gốc trong Data Lake
        Ví dụ: dlake/finance/2026/report.xlsx -> processed_files/finance/2026/
        """
        relative_path = os.path.relpath(os.path.dirname(file_path), self.datalake_dir)
        if relative_path == ".":
            target_dir = self.processed_dir
        else:
            target_dir = os.path.join(self.processed_dir, relative_path)
        
        os.makedirs(target_dir, exist_ok=True)
        return target_dir
        
    def make_profile(self, file_path: str) -> Profile:
        file_path_obj = Path(file_path)
        ext = file_path_obj.suffix.lower().replace(".", "")
        stem = file_path_obj.stem
        
        # Lấy thư mục lưu trữ tương ứng theo cấu trúc
        target_dir = self._get_target_dir(file_path)
        
        processed_files = []
        summary_text = ""
        
        # 1. AUDIO
        if ext in self.audio_exts:
            audio_info: AudioInfo = self.audio_processor.transcribe(file_path)
            txt_out_path = os.path.join(target_dir, f"{stem}_transcript.txt")
            with open(txt_out_path, "w", encoding="utf-8") as f:
                f.write(audio_info.model_dump_json())
            processed_files.append(txt_out_path)
            
            prompt = f"Summarize the audio content based on its info and transcript.\n\nAudio Info:\n{audio_info.model_dump_json()}"
            response = self.llm.generate(prompt, files=None)
            summary_text = response.text
        
        # 2. CSV
        elif ext in self.csv_exts:
            csv_info: CSVInfo = self.csv_processor.process(file_path)
            json_out_path = os.path.join(target_dir, f"{stem}_metadata.json")
            with open(json_out_path, "w", encoding="utf-8") as f:
                f.write(csv_info.model_dump_json(indent=4))
            processed_files.append(json_out_path)
            
            prompt = f"Summarize the CSV file structure and purpose based on this info:\n{csv_info.structed_summary}"
            response = self.llm.generate(prompt, files=None)
            summary_text = response.text
        
        # 3. EXCEL
        elif ext in self.excel_exts:
            # Truyền target_dir vào để lưu ảnh đúng cấu trúc thư mục
            excel_images = self.excel_processor.vertical_compress_excel_to_image(file_path, output_dir=target_dir)
            image_paths = [ei["image_path"] for ei in excel_images]
            processed_files.extend(image_paths)
            prompt = "Summarize the excel sheet(s) based on the provided compressed image layout and values."
            response = self.llm.generate(prompt, files=image_paths)
            summary_text = response.text
        
        # 4. OFFICE (Word, Powerpoint)
        elif ext in self.office_exts:
            output_pdf = os.path.join(target_dir, f"{stem}.pdf")
            office_file = self.office_processor.to_pdf(file_path, output_pdf_path=output_pdf)
            processed_files.append(office_file)
            
            prompt = "Summarize the document file provided."
            response = self.llm.generate(prompt, files=[office_file])
            summary_text = response.text
        
        elif ext in self.html_exts:
            # Chạy bộ parser thu về dict chứa cấu trúc text Markdown và Bảng dữ liệu
            html_result = self.html_processor.process(file_path)
            
            # Xuất kết quả đã bóc tách sạch sẽ ra file JSON tương ứng trong thư mục processed_files
            json_out_path = os.path.join(target_dir, f"{stem}_html_cleaned.json")
            with open(json_out_path, "w", encoding="utf-8") as f:
                json.dump(html_result, f, ensure_ascii=False, indent=4)
            processed_files.append(json_out_path)
            
            # Đưa nội dung text Markdown thu gọn và số lượng bảng cho LLM đọc để làm bản tóm tắt (summary_text)
            prompt = f"""Summarize the purpose and content of this HTML webpage. 
Total tables found: {html_result['metadata']['num_tables']}

Main Webpage Text Content (in Markdown):
{html_result['markdown']}"""
            
            response = self.llm.generate(prompt, files=None)
            summary_text = response.text
        
        else:
            # Copy file giữ nguyên cấu trúc thư mục
            dest_path = os.path.join(target_dir, file_path_obj.name)
            shutil.copy(file_path, dest_path)
            processed_files.append(dest_path)
            
            prompt = "Summarize the file provided."
            try:
                response = self.llm.generate(prompt, files=[dest_path])
                summary_text = response.text
            except Exception:
                summary_text = f"File format {ext} copied but summary skipped due to LLM limitation."

        return Profile(
            origin_path=str(file_path),
            processed_path=processed_files,
            summary_text=summary_text
        )


def scan_and_profile_datalake(datalake_dir: str, output_profile_json: str, profiler: Profiler):
    all_profiles = []
    processed_origins = set()
    
    # --- LOGIC ĐỌC PROFILE CŨ ĐỂ KHÔNG CHẠY LẠI ---
    if os.path.exists(output_profile_json):
        try:
            with open(output_profile_json, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                if isinstance(old_data, list):
                    all_profiles = old_data
                    # Nạp toàn bộ đường dẫn gốc đã chạy xong vào một Set để check O(1)
                    processed_origins = {item["origin_path"] for item in old_data if "origin_path" in item}
                    print(f"🔄 Tìm thấy dữ liệu cũ. Đã xử lý {len(processed_origins)} files trước đó. Sẽ chạy tiếp tục...")
        except Exception as e:
            print(f"⚠️ Không thể đọc file json cũ hoặc file lỗi ({e}). Sẽ tiến hành quét mới hoàn toàn.")
            all_profiles = []
            processed_origins = set()

    print(f"Scan Data Lake: {datalake_dir}")
    
    for root, dirs, files in os.walk(datalake_dir):
        for file in files:
            if file.startswith("."):
                continue
                
            full_file_path = os.path.join(root, file)
            
            # KIỂM TRA: Nếu file đã có trong profile json rồi thì bỏ qua luôn
            if full_file_path in processed_origins:
                print(f"⏩ [SKIP] Đã có profile cũ, bỏ qua: {full_file_path}")
                continue
                
            print(f"\n[PROCESSING] -> {full_file_path}")
            
            try:
                profile_obj = profiler.make_profile(full_file_path)
                all_profiles.append(profile_obj.model_dump())
                print(f"✅ Make profile done for: {file}")
                
                # Lưu đè liên tục sau mỗi file để tránh mất dữ liệu nếu bị ngắt giữa chừng
                with open(output_profile_json, "w", encoding="utf-8") as f:
                    json.dump(all_profiles, f, ensure_ascii=False, indent=4)
                
                # Cập nhật luôn vào set quản lý để đồng bộ
                processed_origins.add(full_file_path)
                
            except Exception as e:
                print(f"❌ Error process file {full_file_path}: {e}")
        
    print(f"\n🎉 DONE: {output_profile_json}")


if __name__ == "__main__":
    DATALAKE_PATH = "Data-Lake"
    OUTPUT_JSON = "all_profiles.json"
    
    llm = QwenLLM(api_key="...")
    
    profiler_agent = Profiler(llm=llm, processed_dir="processed_files", datalake_dir=DATALAKE_PATH)
    
    scan_and_profile_datalake(DATALAKE_PATH, OUTPUT_JSON, profiler_agent)

