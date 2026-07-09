import whisper
from typing import Tuple
from pydantic import BaseModel, Field

class AudioInfo(BaseModel):
    transcript:str
    timed_transcript:str
    language:str

class AudioProcessor:
    def __init__(self, model_size: str = "base"):
        print(f"Loading mode openai/whisper-{model_size}...")
        self.model = whisper.load_model(model_size)
    
    def transcribe(self, audio_path: str) -> AudioInfo:
        print(f"Processing audio: {audio_path}")
        result = self.model.transcribe(audio_path, fp16=False)
        transcript = result.get("text", "").strip()
        language = result.get("language", "unknown")
        
        timed_chunks = []
        segments = result.get("segments", [])
        for segment in segments:
            start = segment.get("start", 0.0)
            end = segment.get("end", 0.0)
            text = segment.get("text", "").strip()
            
            start_str = f"{int(start // 60):02d}:{int(start % 60):02d}"
            end_str = f"{int(end // 60):02d}:{int(end % 60):02d}"
            
            timed_chunks.append(f"[{start_str}-{end_str}] {text}")
            
        timed_transcript = "\n".join(timed_chunks)
        
        return AudioInfo(
            transcript=transcript,
            timed_transcript=timed_transcript,
            language=language
        )

if __name__ == "__main__":
    processor = AudioProcessor(model_size="base")
    audio_file_path = "workshop_03.22.m4a"
    
    try:
        audio_info = processor.transcribe(audio_file_path)
        print("\n--- Language ---")
        print(audio_info.language)
        
        print("\n--- TRANSCRIPT ---")
        print(audio_info.transcript)
        
        print("\n--- TIMED TRANSCRIPT ---")
        print(audio_info.timed_transcript)
        
    except Exception as e:
        print(f"Processing file audio error: {e}")
    
    