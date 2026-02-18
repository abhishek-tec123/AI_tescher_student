import fitz
import pytesseract
from PIL import Image
from concurrent.futures import ProcessPoolExecutor, as_completed
import os
import logging
import time

# ---------- Logging Setup ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

pdf_path = "/Users/macbook/Desktop/langchain_adk/data/BPSC Computer TRE 4.0_____ Part-1 (4 sheet) final.pdf"


def _process_pdf_page(args):
    pdf_path, page_number = args
    start_time = time.time()

    pdf = fitz.open(pdf_path)
    page = pdf[page_number]

    text = page.get_text("text").strip()

    if len(text) > 50:
        method = "TEXT"
    else:
        pix = page.get_pixmap(dpi=200)  # faster than 300
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(
            img,
            config="--oem 3 --psm 6"
        )
        method = "OCR"

    pdf.close()

    duration = round(time.time() - start_time, 2)

    return page_number, text, method, duration


def extract_img_pdf_text_parallel(pdf_path):
    total_start = time.time()

    pdf = fitz.open(pdf_path)
    total_pages = len(pdf)
    pdf.close()

    logger.info(f"Starting extraction for {total_pages} pages")
    logger.info(f"Using {os.cpu_count()} CPU cores")

    results = [""] * total_pages

    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = [
            executor.submit(_process_pdf_page, (pdf_path, i))
            for i in range(total_pages)
        ]

        for future in as_completed(futures):
            page_number, text, method, duration = future.result()
            results[page_number] = text

            logger.info(
                f"Page {page_number + 1} | Method: {method} | Time: {duration}s"
            )

    total_time = round(time.time() - total_start, 2)
    logger.info(f"Extraction completed in {total_time} seconds")

    return "\n".join(results)


# if __name__ == "__main__":
#     extracted_text = extract_img_pdf_text_parallel(pdf_path)

#     with open("output.txt", "w", encoding="utf-8") as f:
#         f.write(extracted_text)

#     logger.info("Text saved to output.txt")
