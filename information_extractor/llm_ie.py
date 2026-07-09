from information_extractor.base import BaseIE, ExtractionResult
from llm.base import BaseLLM

class LLMIE(BaseIE):
    def __init__(self, llm: BaseLLM):
        self.llm = llm
    
    def extract(self, query: str, processed_file_paths: str, original_file_path: str) -> ExtractionResult:
        prompt = f"""You are an expert Information Extraction agent in a Data Lake QA system.
Your mission is to read the provided file and extract EVERY SINGLE PIECE of information relevant to the user's query.

User Query: "{query}"
Original File Path: "{original_file_path}"
Processed File Path: "{processed_file_paths}"

CRITICAL INSTRUCTIONS:
1. Accuracy First: Only extract information explicitly mentioned in the file. Do not assume, extrapolate, or use outside knowledge.
2. Granularity: Be extremely specific. Extract numbers, dates, names, figures, and technical details. Do not summarize loosely.
3. Status Mapping:
   - Set status to "FOUND" only if the file answers the query completely.
   - Set status to "PARTIAL" if the file provides some useful clues/data but cannot fully answer the query. You MUST specify what is missing in 'missing_info'.
   - Set status to "NOT_FOUND" if the file contains zero relevant information.
4. Evidence: Copy direct quotes, row indices, data cells, or timestamps into the 'quotes' field to prove your extraction is real.

Analyze the attached file carefully and output the result matching the requested schema."""

        try:
            result: ExtractionResult = self.llm.generate(
                prompt=prompt, 
                files=processed_file_paths, 
                OutputModel=ExtractionResult
            )
            return result
        except Exception as e:
            return ExtractionResult(
                status="NOT_FOUND",
                extracted_info=f"Error during extraction: {str(e)}",
                quotes=[],
                missing_info=None
            )
            
