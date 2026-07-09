from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Type

class LLMResponse(BaseModel):
    text: str

class BaseLLM(ABC):
    name: str
    ctx_window: int
    padding_ctx_window:int = 500

    def _file_to_base64(self, file_path:str)->str:
        with open(file_path, "rb") as f:
            return f.read().encode("base64").decode("utf-8")

    @abstractmethod
    def generate(self, 
                 prompt:str, 
                 files:list[str]=None, 
                 OutputModel:Type[BaseModel]=LLMResponse)->BaseModel:
        ...

    @abstractmethod
    def calc_token_usage(self, prompt:str, files:list[str]=None)->int:
        ...

    def is_out_of_context(self, prompt:str, files:list[str])->bool:
        return self.calc_token_usage(prompt, files) > self.ctx_window - self.padding_ctx_window

