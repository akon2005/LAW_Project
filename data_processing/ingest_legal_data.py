import sys
import os

# Add backend to path so we can import services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tqdm import tqdm
from app.services.dataset_service import load_and_validate_dataset
from app.rag.embedding_service import embedding_service
from app.db.vector_store import legal_cases_store

def main():
    print("VIDHIVEDA Legal Data Ingestion")
    print("-" * 32)
    
    # 1-3. Load Hugging Face dataset, validate, and extract metadata
    valid_records, report = load_and_validate_dataset()
    
    if not valid_records:
        print("No valid records found. Exiting.")
        return
        
    print(f"Extracted {len(valid_records)} valid records.")
    
    # 4-8. Create stable IDs, generate embeddings, insert into ChromaDB
    batch_size = 100
    total_inserted = 0
    
    print(f"Generating embeddings and inserting into ChromaDB (batch size: {batch_size})...")
    
    for i in tqdm(range(0, len(valid_records), batch_size)):
        batch = valid_records[i:i+batch_size]
        
        texts = [record["text"] for record in batch]
        ids = [record["chunk_id"] for record in batch]
        
        # Build ChromaDB metadata (no None values allowed)
        metadatas = []
        for record in batch:
            meta = {
                "document_id": record["document_id"],
                "chunk_id": record["chunk_id"],
                "source": record["source_file"],
                "chunk_index": record["chunk_index"],
                "total_pages": record["total_pages"],
                "case_name": record["case_name"],
                "court": record["court"],
            }
            if record["year"] is not None:
                meta["year"] = record["year"]
            metadatas.append(meta)
            
        # 5. Generate embeddings
        embeddings = embedding_service.generate_embeddings(texts)
        
        # 7. Insert documents
        legal_cases_store.insert_documents(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
        total_inserted += len(ids)
        
    # 9-10. Final Statistics
    print("\nVIDHIVEDA Legal Data Ingestion")
    print("-" * 32)
    print(f"Dataset: dedol-hf/india-case-legal-rag")
    print(f"Total records: {report.get('Total records (in split)', 0)}")
    print(f"Valid records: {report.get('Valid records', 0)}")
    print(f"Invalid records: {report.get('Invalid records', 0)}")
    print(f"Embedded records: {total_inserted}")
    print(f"ChromaDB records: {legal_cases_store.get_count()}")
    print("\nIngestion completed successfully.")

if __name__ == "__main__":
    main()
