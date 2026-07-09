import pandas as pd
from answer_maker import AnswerMaker
from llm.qwen35b import QwenLLM
from information_extractor.llm_ie import LLMIE
from information_extractor.excel_ie import ExcelIE
from information_extractor.csv_ie import CSVIE

import json

llm = QwenLLM(api_key="...")
coder_llm = QwenLLM(api_key="...")

llm_ie = LLMIE(llm=llm)
excel_ie = ExcelIE(llm=llm, coder_llm=coder_llm)
csv_ie = CSVIE(llm=llm, coder_llm=coder_llm)

answer_maker = AnswerMaker(llm=llm, 
                           default_ie=llm_ie, 
                           specific_ie={
                               excel_ie: ["xlsx", "xls"],
                               csv_ie: ["csv"]
                           })

profile_path = "all_profiles.json"
question_df = pd.read_csv("questions.csv")

submission_rows = []

print(f"🚀 Bắt đầu quá trình sinh câu trả lời cho {len(question_df)} câu hỏi...")

for idx, question in question_df.iterrows():
    q_id = question.id
    q_text = question.question

    try:
        a = answer_maker.answer(q_text, profile_path)
        final_ans = a.final_answer
        evidences_str = json.dumps(a.evidences, ensure_ascii=False)
        
        print(f"\n[SUCCESS] ID: {q_id} | Question: {q_text}")
        print(f"   ↳ Answer: {final_ans}")
        print(f"   ↳ Evidences: {evidences_str}")

    except Exception as e:
        print(f"\n❌ [ERROR] Lỗi khi xử lý câu hỏi ID {q_id}: {e}")
        final_ans = "Error or timeout during processing"
        evidences_str = "[]"

    submission_rows.append({
        "id": q_id,
        "answer": final_ans,
        "evidences": evidences_str
    })
    
    submission_df = pd.DataFrame(submission_rows)
    output_csv_path = "submission.csv"
    submission_df.to_csv(output_csv_path, index=False, encoding="utf-8-sig")

print(f"\n🎉 QUÁ TRÌNH HOÀN TẤT! Đã lưu file kết quả tại: {output_csv_path}")
