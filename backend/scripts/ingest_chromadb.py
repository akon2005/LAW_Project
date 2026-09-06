import os
import json
import chromadb
import pandas as pd
import numpy as np
from tqdm import tqdm

def ingest_to_chroma(preprocessed_path: str, embeddings_path: str, ids_path: str, chroma_path: str):
    """
    Ingests embeddings, texts, and metadata into a ChromaDB persistent collection.
    """
    print(f"Initializing ChromaDB client at {chroma_path}...")
    client = chromadb.PersistentClient(path=chroma_path)
    
    collection = client.get_or_create_collection(
        name="vidhiveda_cases",
        metadata={"hnsw:space": "cosine"} # Use cosine similarity
    )
    
    print("Loading data...")
    df = pd.read_parquet(preprocessed_path)
    
    # Check if embeddings and ids exist
    if not os.path.exists(embeddings_path) or not os.path.exists(ids_path):
        raise FileNotFoundError("Embeddings or IDs not found. Run embed.py first.")
        
    embeddings = np.load(embeddings_path)
    with open(ids_path, 'r', encoding='utf-8') as f:
        case_ids = json.load(f)
        
    if len(df) != len(embeddings) or len(df) != len(case_ids):
        raise ValueError("Mismatch in number of documents and embeddings.")
        
    # Prepare data for ChromaDB
    # Chroma requires metadata values to be str, int, float, or bool.
    # We built metadata as dicts, let's pull them out
    metadata_list = df['metadata'].tolist()
    
    # Ensure all metadata values are valid for Chroma (no None values, replace with empty string or default)
    cleaned_metadata = []
    for meta in metadata_list:
        clean_meta = {}
        for k, v in meta.items():
            if v is None:
                # Chroma doesn't accept None, replace valid_until null with a distinct marker or omit
                if k == 'valid_until':
                    # Omit valid_until if None, or set a dummy large year like 9999
                    continue
                else:
                    clean_meta[k] = ""
            else:
                clean_meta[k] = v
        cleaned_metadata.append(clean_meta)

    documents_list = df['retrieval_document'].tolist()
    
    print(f"Upserting {len(case_ids)} documents to ChromaDB in batches...")
    
    batch_size = 500
    for i in tqdm(range(0, len(case_ids), batch_size)):
        end = min(i + batch_size, len(case_ids))
        collection.upsert(
            ids=case_ids[i:end],
            embeddings=embeddings[i:end].tolist(),
            documents=documents_list[i:end],
            metadatas=cleaned_metadata[i:end]
        )
        
    print("Ingestion complete.")
    
    # Final count breakdown
    # Since Chroma doesn't have aggregate group by built-in, we just print the df counts or query all.
    # To truly verify Chroma ingestion, we check collection count.
    collection_count = collection.count()
    print(f"\nFinal count in ChromaDB collection 'vidhiveda_cases': {collection_count}")
    
    print("Breakdown by Record Type (from loaded data):")
    record_counts = df['Record Type'].fillna('Unknown').value_counts()
    for record_type, count in record_counts.items():
        print(f" - {record_type}: {count}")

if __name__ == "__main__":
    preprocessed_parquet = "data/processed/cases_preprocessed.parquet"
    embeddings_npy = "data/processed/embeddings.npy"
    ids_json = "data/processed/embedding_ids.json"
    chroma_store_path = "data/chroma_store"
    
    ingest_to_chroma(preprocessed_parquet, embeddings_npy, ids_json, chroma_store_path)
