"""Build the corpus: download every URL in sources.csv, extract text, chunk it.

Output: data/chunks.jsonl (one chunk per line) and data/manifest.json
(per-source fetch status and date). Run once before starting the app:

    python ingest.py
"""
import csv
import io
import json
import re
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).parent
DATA = ROOT / "data"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/124 Safari/537.36"}
CHUNK_WORDS = 160
OVERLAP_WORDS = 40
MAX_PDF_PAGES = 60  # SIDs run to 100+ pages; the facts we need are in the front half


def clean(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "form"]):
        tag.decompose()
    return clean(soup.get_text("\n"))


def pdf_to_text(blob: bytes) -> str:
    reader = PdfReader(io.BytesIO(blob))
    pages = []
    for page in reader.pages[:MAX_PDF_PAGES]:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            continue
    return clean("\n".join(pages))


def chunk(text: str):
    words = text.split()
    step = CHUNK_WORDS - OVERLAP_WORDS
    for start in range(0, max(len(words), 1), step):
        piece = words[start : start + CHUNK_WORDS]
        if len(piece) < 25:
            break
        yield " ".join(piece)


def main():
    DATA.mkdir(exist_ok=True)
    today = date.today().strftime("%d %b %Y")
    manifest, n_chunks = [], 0
    with open(ROOT / "sources.csv") as f, open(DATA / "chunks.jsonl", "w") as out:
        for row in csv.DictReader(f):
            url = row["url"]
            status = "ok"
            try:
                r = requests.get(url, headers=UA, timeout=60)
                r.raise_for_status()
                is_pdf = "pdf" in r.headers.get("content-type", "") or url.lower().endswith(".pdf")
                text = pdf_to_text(r.content) if is_pdf else html_to_text(r.text)
            except Exception as e:
                text, status = "", f"failed: {e}"
            count = 0
            for i, piece in enumerate(chunk(text)):
                out.write(json.dumps({**row, "chunk_id": f"{len(manifest)}-{i}", "text": piece, "fetched": today}) + "\n")
                count += 1
            n_chunks += count
            manifest.append({**row, "status": status, "chars": len(text), "chunks": count, "fetched": today})
            print(f"{status:6.6} {count:4d} chunks  {row['title']}")
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\n{n_chunks} chunks from {len(manifest)} sources")


if __name__ == "__main__":
    main()
