import os, pickle
import numpy as np
import faiss
from google import genai
import time

from dotenv import load_dotenv
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

INDEX_PATH = "guideline_index.faiss"
CHUNKS_PATH = "guideline_chunks.pkl"

_index = faiss.read_index(INDEX_PATH)
with open(CHUNKS_PATH, "rb") as f:
    _chunks = pickle.load(f)

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

def retrieve_guideline(query: str, k: int = 4) -> dict:
    vec = np.array([embed(query)], dtype="float32")
    distances, indices = _index.search(vec, k)
    results = [_chunks[i] for i in indices[0] if i != -1]
    return {"results": results}