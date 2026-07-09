from abc import ABC, abstractmethod
from typing import List, Optional, Type
from pydantic import BaseModel, Field

class ExtractionResult(BaseModel):
    status: str = Field(description="Information found status. Only select 1 of 3: 'FOUND', 'PARTIAL', 'NOT_FOUND'.")
    extracted_info: str = Field(description="Specific, detailed information extracted from the file related to the question. If the status is 'NOT_FOUND', leave it blank or write 'Not found'.")
    quotes: List[str] = Field(description="Sentences, timestamps, or data lines quoted ORIGINAL from the file are used as evidence.")
    missing_info: Optional[str] = Field(description="If the status is 'PARTIAL', please specify which pieces of information are missing and which this file has not yet answered.")

class BaseIE(ABC):
    @abstractmethod
    def extract(self, query: str, processed_file_paths: str, original_file_path: str)->str:
        pass

