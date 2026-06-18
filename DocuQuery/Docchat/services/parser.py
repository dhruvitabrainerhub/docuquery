from pypdf import PdfReader

# def extract_text(pdf_path):
#     reader = PdfReader(pdf_path)

#     text = ""

#     for page in reader.pages:
#         page_text = page.extract_text()

#         if page_text:
#             text += page_text + "\n"

#     return text


def extract_text(pdf_path):
    reader = PdfReader(pdf_path)

    pages = []

    for page_num, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text()

        if page_text:
            pages.append(
                {
                    'page':page_num,
                    'text':page_text
                }
            )
    return pages