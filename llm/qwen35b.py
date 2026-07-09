from llm.base import BaseLLM, LLMResponse

import os
import base64
import mimetypes
from typing import Type, List, Optional
from pydantic import BaseModel
from openai import OpenAI

class QwenLLM(BaseLLM):
    def __init__(self, 
                 model_name: str = "qwen/qwen3.6-35b-a3b",
                 ctx_window: int = 125000, 
                 api_key: Optional[str] = None):
        
        self.name = model_name
        self.ctx_window = ctx_window
        self.padding_ctx_window = 1000
        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY"),
        )

    def _encode_file_to_base64_data_url(self, file_path: str) -> str:
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            if file_path.endswith('.pdf'): mime_type = 'application/pdf'
            elif file_path.endswith('.mp4'): mime_type = 'video/mp4'
            else: mime_type = 'application/octet-stream'
            
        with open(file_path, "rb") as f:
            encoded_string = base64.b64encode(f.read()).decode("utf-8")
            
        return f"data:{mime_type};base64,{encoded_string}"

    def _build_content_blocks(self, prompt: str, files: Optional[List[str]] = None) -> List[dict]:
        content_blocks = [{"type": "text", "text": prompt}]
        
        if not files:
            return content_blocks
            
        for file_path in files:
            if not os.path.exists(file_path):
                continue
                
            data_url = self._encode_file_to_base64_data_url(file_path)
            ext = file_path.lower().split('.')[-1]
            
            if ext in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
                content_blocks.append({
                    "type": "image_url",
                    "image_url": {"url": data_url}
                })
            elif ext in ['mp4', 'webm', 'mkv', 'avi']:
                content_blocks.append({
                    "type": "video_url", 
                    "video_url": {"url": data_url}
                })
            elif ext == 'pdf':
                # --- SỬA THEO ĐÚNG CẤU TRÚC FILE PLUGINS CỦA OPENROUTER ---
                content_blocks.append({
                    "type": "file",
                    "file": {
                        "filename": os.path.basename(file_path),
                        "file_data": data_url
                    }
                })
            else:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text_content = f.read()
                    content_blocks.append({
                        "type": "text",
                        "text": f"\n\n--- Nội dung file [{os.path.basename(file_path)}] ---\n{text_content}"
                    })
                except Exception:
                    pass
                    
        return content_blocks

    def generate(self, 
                 prompt: str, 
                 files: Optional[List[str]] = None, 
                 OutputModel: Type[BaseModel] = LLMResponse) -> BaseModel:
        
        content = self._build_content_blocks(prompt, files)
        
        # Thiết lập payload tin nhắn
        messages = [{"role": "user", "content": content}]
        
        # Xử lý Structured Outputs nếu cần
        response_format = None
        if OutputModel != LLMResponse:
            response_format = {"type": "json_object", "schema": OutputModel.model_json_schema()}
            messages.append({
                "role": "system", 
                "content": f"You must respond strictly in JSON format matching this schema: {OutputModel.model_json_schema()}"
            })

        # Cấu hình plugin phân tích file theo tài liệu OpenRouter
        # Mặc định sử dụng 'mistral-ocr' hoặc cấu hình 'cloudflare-ai'
        plugins_config = [
            {
                "id": "file-parser",
                "pdf": {
                    "engine": "mistral-ocr" 
                }
            }
        ]

        # Gọi API với extra_body để truyền cấu trúc plugins của OpenRouter vào
        response = self.client.chat.completions.create(
            model=self.name,
            messages=messages,
            response_format=response_format,
            extra_body={"plugins": plugins_config} # <-- Bổ sung ở đây
        )
        
        raw_text = response.choices[0].message.content
        
        if OutputModel == LLMResponse:
            return LLMResponse(text=raw_text)
        else:
            return OutputModel.model_validate_json(raw_text)

    def calc_token_usage(self, prompt: str, files: Optional[List[str]] = None) -> int:
        text_tokens = len(prompt.split()) * 2
        
        file_tokens = 0
        if files:
            for file_path in files:
                ext = file_path.lower().split('.')[-1]
                if ext in ['jpg', 'jpeg', 'png', 'webp']:
                    file_tokens += 3000
                elif ext in ['mp4', 'webm', 'avi']:
                    file_tokens += 15000
                elif ext == 'pdf':
                    file_tokens += 4000
                else:
                    if os.path.exists(file_path):
                        file_tokens += int(os.path.getsize(file_path) / 4) # File text thuần
                        
        return text_tokens + file_tokens
    