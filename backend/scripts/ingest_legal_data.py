"""
VIDHIVEDA Legal Knowledge Base Ingestion Script.
Reads local JSON datasets, caches them based on SHA-256 hash to prevent redundant embedding,
chunks text (300-500 tokens roughly), and batches embedding calls.
"""
import json
import sys
import hashlib
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DATASET_DIR
from app.services.embeddings import encode_batch_to_list
from app.services.vectorstore import add_documents, get_document_count

# Adjust chunks sizes for roughly 300-500 tokens
# Sentence transformer tokens are roughly 4 chars each, so 300-500 tokens is ~1200-2000 chars.
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200

CACHE_FILE = DATASET_DIR.parent / ".embed_cache.json"

DATASETS_TO_INGEST = [
    "constitution.json",
    "criminal_law_mapping.json",
    "landmark_cases.json",
    "case_categories.json",
    "court_hierarchy.json",
    "recent_developments.json"
]

def get_file_hash(file_path: Path) -> str:
    """Calculates SHA-256 hash of a file."""
    if not file_path.exists():
        return ""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()


def load_cache() -> Dict[str, str]:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def save_cache(cache: Dict[str, str]):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=4)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split text into overlapping chunks.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    sentences = text.replace('\n', ' ').split('. ')
    current_chunk = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = current_chunk + (". " if current_chunk else "") + sentence
        if len(candidate) > chunk_size and current_chunk:
            chunks.append(current_chunk + ".")
            words = current_chunk.split()
            overlap_words = int(len(words) * (overlap / chunk_size))
            current_chunk = " ".join(words[-overlap_words:]) + ". " + sentence if overlap_words > 0 else sentence
        else:
            current_chunk = candidate

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text]


def main():
    print("=" * 60)
    print("  VIDHIVEDA Legal Knowledge Base Ingestion")
    print("=" * 60)

    cache = load_cache()
    new_cache = cache.copy()
    
    files_to_process = []
    
    # Check hashes
    for filename in DATASETS_TO_INGEST:
        file_path = DATASET_DIR / filename
        if not file_path.exists():
            print(f"[Skip] {filename} not found.")
            continue
            
        file_hash = get_file_hash(file_path)
        if cache.get(filename) == file_hash:
            print(f"[Skip] {filename} unchanged (hash matched).")
        else:
            print(f"[Queue] {filename} needs ingestion (hash changed/new).")
            files_to_process.append((file_path, file_hash, filename))

    if not files_to_process:
        print("\nAll datasets are up-to-date. No ingestion needed.")
        sys.exit(0)

    print(f"\n[Ingest] Processing {len(files_to_process)} files...")
    
    all_ids = []
    all_texts = []
    all_metadatas = []

    for file_path, file_hash, filename in files_to_process:
        with open(file_path, "r", encoding="utf-8") as f:
            docs = json.load(f)
            
        for doc in docs:
            doc_id_base = doc.get("doc_id", "unknown_id")
            content = doc.get("content", doc.get("facts", ""))
            
            # Combine multiple fields if needed
            if "holding" in doc:
                content += f" Holding: {doc['holding']}"
                
            chunks = chunk_text(content)
            
            for chunk_idx, chunk in enumerate(chunks):
                chunk_id = f"{filename}_{doc_id_base}__chunk_{chunk_idx}"
                all_ids.append(chunk_id)
                all_texts.append(chunk)
                
                # Metadata filtering fields
                all_metadatas.append({
                    "doc_id": str(doc_id_base),
                    "title": str(doc.get("case_name", "Untitled")),
                    "act_section": str(doc.get("act_section", "")),
                    "document_type": str(doc.get("category", "General")),
                    "law_version_valid_from": str(doc.get("valid_from", "1950-01-26")),
                    "chunk_index": int(chunk_idx),
                    "source_file": filename
                })
        
        # Update cache for this file
        new_cache[filename] = file_hash

    if all_texts:
        print(f"[Ingest] Generated {len(all_ids)} chunks.")
        print("[Ingest] Encoding chunks in batches...")
        
        # ONE BATCHED CALL per all_texts (the underlying function handles batch sizing)
        all_embeddings = encode_batch_to_list(all_texts, batch_size=32)
        
        print("[Ingest] Storing in ChromaDB...")
        add_documents(
            ids=all_ids,
            embeddings=all_embeddings,
            documents=all_texts,
            metadatas=all_metadatas,
        )
        
        # Save cache only after successful ingestion
        save_cache(new_cache)
        
        total = get_document_count()
        print(f"\n[SUCCESS] Ingestion complete!")
        print(f"   Newly embedded chunks: {len(all_ids)}")
        print(f"   Total DB Chunks: {total}")
    else:
        print("\n[WARNING] No text found to ingest in the modified files.")
        
if __name__ == "__main__":
    main()
