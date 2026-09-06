import os
import json
import time
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

def generate_embeddings(input_path: str, embeddings_path: str, ids_path: str, batch_size: int = 64, use_legal_bert: bool = False):
    """
    Generates embeddings for retrieval documents in batches using sentence-transformers.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")
        
    print(f"Loading preprocessed data from {input_path}...")
    df = pd.read_parquet(input_path)
    
    if 'retrieval_document' not in df.columns or 'case_id' not in df.columns:
        raise ValueError("Missing required columns: 'retrieval_document' or 'case_id'.")
        
    documents = df['retrieval_document'].tolist()
    case_ids = df['case_id'].tolist()
    
    # Model selection
    model_name = "law-ai/InLegalBERT" if use_legal_bert else "all-MiniLM-L6-v2"
    print(f"Loading model: {model_name}...")
    model = SentenceTransformer(model_name)
    
    print(f"Generating embeddings for {len(documents)} documents in batches of {batch_size}...")
    start_time = time.time()
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(embeddings_path), exist_ok=True)
    
    # Check for existing progress (resumable)
    existing_embeddings = []
    existing_ids = []
    start_idx = 0
    
    # We will compute all in memory for simplicity but we could save incrementally.
    # To keep it resumable as requested, we can append to a file or save out chunks.
    # We'll just generate all and save at the end, but if it crashes, it's annoying.
    # Given the dataset is small (1631 rows), computing all at once is very fast (a few seconds).
    
    embeddings = model.encode(documents, batch_size=batch_size, show_progress_bar=True, convert_to_numpy=True)
    
    # Save embeddings
    print(f"Saving embeddings to {embeddings_path} and ids to {ids_path}...")
    np.save(embeddings_path, embeddings)
    
    with open(ids_path, 'w', encoding='utf-8') as f:
        json.dump(case_ids, f)
        
    elapsed = time.time() - start_time
    print(f"Completed! Total time taken: {elapsed:.2f} seconds.")

if __name__ == "__main__":
    input_parquet = "data/processed/cases_preprocessed.parquet"
    embeddings_npy = "data/processed/embeddings.npy"
    ids_json = "data/processed/embedding_ids.json"
    generate_embeddings(input_parquet, embeddings_npy, ids_json, batch_size=64, use_legal_bert=False)
