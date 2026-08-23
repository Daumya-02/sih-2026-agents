import os, glob, pickle
import numpy as np
import faiss
from pypdf import PdfReader
from google import genai
import time

from dotenv import load_dotenv
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
print("client is created")

DOCS_DIR = "docs"
INDEX_PATH = "guideline_index.faiss"
CHUNKS_PATH = "guideline_chunks.pkl"
CHUNK_SIZE = 400

def chunk_text(text, size=CHUNK_SIZE):
    words = text.split()
    return [" ".join(words[i:i+size]) for i in range(0, len(words), size)]

def embed(text):
    for attempt in range(5):
        try:
            result = client.models.embed_content(
                model="models/gemini-embedding-001", contents=text
            )
            return result.embeddings[0].values
        except Exception as e:
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                wait = 15 * (attempt + 1)
                print(f"Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Failed after retries")

def build_index():
    chunks = []
    for path in glob.glob(f"{DOCS_DIR}/*.pdf"):
        reader = PdfReader(path)
        full_text = " ".join(p.extract_text() or "" for p in reader.pages)
        for c in chunk_text(full_text):
            if len(c.strip()) > 50:
                chunks.append({"text": c, "source": os.path.basename(path)})

    print(f"Embedding {len(chunks)} chunks...")
    vectors = []
    for i, c in enumerate(chunks):
        vectors.append(embed(c["text"]))
        print(f"Embedded {i+1}/{len(chunks)}")
        time.sleep(3)   # stay under free-tier TPM

    vectors = np.array(vectors, dtype="float32")

    index = faiss.IndexFlatL2(vectors.shape[1])
    index.add(vectors)
    faiss.write_index(index, INDEX_PATH)
    with open(CHUNKS_PATH, "wb") as f:
        pickle.dump(chunks, f)
    print("Done.")

if __name__ == "__main__":
    build_index()