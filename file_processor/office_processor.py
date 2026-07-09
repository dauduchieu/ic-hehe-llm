import os
import subprocess
import shutil
from typing import Optional

class OfficeProcessor:
    def __init__(self, libreoffice_path: Optional[str] = None):
        self.libreoffice_cmd = libreoffice_path or self._find_libreoffice()

    def _find_libreoffice(self) -> str:
        for cmd in ["soffice", "libreoffice"]:
            if shutil.which(cmd):
                return cmd
        
        default_paths = [
            "/usr/bin/libreoffice",
            "/usr/bin/soffice",
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",  # Mac
            "C:\\Program Files\\LibreOffice\\program\\soffice.exe"   # Windows
        ]
        for path in default_paths:
            if os.path.exists(path):
                return path
        
        return "soffice"

    def to_pdf(self, file_path: str, output_pdf_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Không tìm thấy file đầu vào: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in [".docx", ".doc", ".pptx", ".ppt"]:
            raise ValueError(f"Định dạng file {ext} không được hỗ trợ bởi bộ chuyển đổi này.")

        output_pdf_path = os.path.abspath(output_pdf_path)
        output_dir = os.path.dirname(output_pdf_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        abs_input_path = os.path.abspath(file_path)
        
        # Câu lệnh CLI thần thánh của LibreOffice: Chạy ngầm, không bật UI phần mềm, xuất ra PDF
        cmd = [
            self.libreoffice_cmd,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", output_dir,
            abs_input_path
        ]

        try:
            print(f"Đang xử lý miễn phí file [{ext.upper()}]: {os.path.basename(file_path)}...")
            # Thực thi câu lệnh hệ thống
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Tên file PDF mặc định mà LibreOffice tự sinh ra (trùng tên file gốc chỉ đổi đuôi)
            base_name = os.path.splitext(os.path.basename(abs_input_path))[0]
            default_generated_pdf = os.path.join(output_dir, f"{base_name}.pdf")
            
            # Nếu đường dẫn user yêu cầu khác với tên mặc định, tiến hành đổi tên (rename)
            if os.path.exists(default_generated_pdf) and default_generated_pdf != output_pdf_path:
                if os.path.exists(output_pdf_path):
                    os.remove(output_pdf_path)
                os.rename(default_generated_pdf, output_pdf_path)
                
            print(f"🎉 Chuyển đổi thành công sang PDF: {output_pdf_path}")
            return output_pdf_path

        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Lỗi khi chạy LibreOffice. Hãy chắc chắn bạn đã cài đặt LibreOffice (Miễn phí).\n"
                f"Chi tiết lỗi hệ thống: {e.stderr}"
            )
        except Exception as e:
            raise RuntimeError(f"Lỗi không xác định: {e}")


# === VÍ DỤ INTEGRATION TRONG DATA LAKE PIPELINE ===
if __name__ == "__main__":
    # Khởi tạo bộ xử lý duy nhất cho cả Word và Slide
    office_converter = OfficeProcessor()
    
    # 1. Test với file Word (.docx)
    try:
        pdf_word = office_converter.to_pdf(
            file_path="TONG-HOP-QUIZ.docx", 
            output_pdf_path="TONG-HOP-QUIZ.pdf"
        )
    except Exception as e:
        print(f"Lỗi xử lý DOCX: {e}")
        
    # 2. Test với file PowerPoint (.pptx) - Hoàn toàn tương tự!
    try:
        pdf_slide = office_converter.to_pdf(
            file_path="2 NewCh1&2sửa.ppt", 
            output_pdf_path="2 NewCh1&2sửa.pdf"
        )
    except Exception as e:
        print(f"Lỗi xử lý PPTX: {e}")