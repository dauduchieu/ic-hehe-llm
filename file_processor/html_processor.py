from __future__ import annotations

import re
import json
from pathlib import Path
import pandas as pd
import trafilatura
from bs4 import BeautifulSoup
from markdownify import markdownify

REMOVE_TAGS = {
    "script", "style", "noscript", "svg", "canvas", "iframe",
    "footer", "header", "nav", "aside", "form", "button",
    "input", "meta", "link",
}

# Các class/id rác thường thấy trên các trang wiki hoặc tin tức
REMOVE_SELECTORS = [
    ".toc", ".mw-editsection", ".navbox", ".reference",
    ".references", ".metadata", ".catlinks",
]

class HTMLProcessor:
    def __init__(self):
        """Khởi tạo bộ xử lý HTML độc lập không kế thừa"""
        self.supported_extensions = [".html", ".htm"]

    def _clean_markdown(self, md: str) -> str:
        """Làm sạch các khoảng trắng và dòng trống dư thừa trong markdown"""
        md = re.sub(r"\n{3,}", "\n\n", md)
        md = re.sub(r"[ \t]+", " ", md)
        md = re.sub(r"\n +", "\n", md)
        return md.strip()

    def _extract_markdown(self, html: str) -> str:
        """Trích xuất nội dung văn bản chính dưới dạng Markdown"""
        # Ưu tiên sử dụng trafilatura để cào text chính xác, bỏ qua menu/ads
        extracted = trafilatura.extract(
            html,
            output_format="markdown",
            include_links=False,
            include_images=False,
            include_tables=True,
        )

        if extracted:
            return self._clean_markdown(extracted)

        # Fallback: Nếu trafilatura thất bại, dùng BeautifulSoup + markdownify
        soup = BeautifulSoup(html, "lxml")

        for tag in REMOVE_TAGS:
            for x in soup.find_all(tag):
                x.decompose()

        for selector in REMOVE_SELECTORS:
            for x in soup.select(selector):
                x.decompose()

        md = markdownify(str(soup), heading_style="ATX")
        return self._clean_markdown(md)

    def _extract_tables(self, html: str) -> list[dict]:
        """Trích xuất toàn bộ các bảng dữ liệu có trong file HTML"""
        tables = []
        try:
            # Sử dụng pandas để parse trực tiếp các thẻ <table>
            dfs = pd.read_html(html)
            for df in dfs:
                # Ép các cột tiêu đề về chuỗi ký tự text
                headers = [str(x) for x in df.columns]
                
                # Điền khoảng trống cho ô rỗng, ép kiểu và đưa về list lồng list
                rows = (
                    df.fillna("")
                    .astype(str)
                    .values
                    .tolist()
                )
                
                tables.append({
                    "headers": headers,
                    "rows": rows
                })
        except Exception:
            # Bỏ qua nếu trang HTML không chứa bảng hoặc cấu trúc bảng lỗi
            pass
        return tables

    def process(self, path: str | Path) -> dict:
        """
        Hàm xử lý chính: Đọc file HTML và trả về cấu trúc dict phẳng
        """
        path = Path(path)

        # Đọc nội dung file HTML chấp nhận bỏ qua ký tự lỗi mã hóa
        html = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        markdown_content = self._extract_markdown(html)
        tables_content = self._extract_tables(html)

        # Trả về dictionary thuần không thông qua Pydantic / BaseClass
        return {
            "file_path": str(path),
            "file_name": path.name,
            "file_type": "html",
            "markdown": markdown_content,
            "tables": tables_content,
            "metadata": {
                "num_tables": len(tables_content)
            }
        }

# --- KHU VỰC CHẠY THỬ (DEMO) ---
if __name__ == "__main__":
    processor = HTMLProcessor()
    
    # Tạo một file HTML giả lập để test nhanh
    sample_html = """
    <html>
        <head><style>body {color: red;}</style></head>
        <body>
            <nav>Menu link</nav>
            <h1>Tiêu đề bài viết</h1>
            <p>Đây là nội dung văn bản quan trọng cần trích xuất.</p>
            <table border="1">
                <tr><th>Mã SP</th><th>Giá</th></tr>
                <tr><td>A101</td><td>500k</td></tr>
            </table>
        </body>
    </html>
    """
    temp_file = Path("sample_test.html")
    temp_file.write_text(sample_html, encoding="utf-8")
    
    # Thực thi xử lý
    result = processor.process(temp_file)
    
    # In kết quả dạng JSON đẹp mắt để kiểm tra tiêu đề và bảng dữ liệu
    print(json.dumps(result, ensure_ascii=False, indent=4))
    
    # Dọn dẹp file test
    if temp_file.exists():
        temp_file.unlink()