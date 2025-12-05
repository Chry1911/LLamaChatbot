import pdfplumber
import docx
from io import BytesIO

def extract_text_from_file(file):
    filename = getattr(file, "filename", "file")
    ext = filename.lower().split(".")[-1]

    if ext == "pdf":
        with pdfplumber.open(file) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    
    if ext == "docx":
        doc = docx.Document(file)
        return "\n".join(para.text for para in doc.paragraphs)

    if ext == "txt":
        return file.read().decode("utf-8")

    return "Formato non supportato."
