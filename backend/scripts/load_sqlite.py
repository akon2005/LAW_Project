import os
import sys
import pandas as pd
from sqlalchemy.orm import Session

# Add backend to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import SessionLocal, init_db, Case

def load_data_to_sqlite(preprocessed_path: str):
    """
    Loads metadata from preprocessed parquet into SQLite database.
    """
    print("Initializing SQLite Database...")
    init_db()
    
    print(f"Loading preprocessed data from {preprocessed_path}...")
    df = pd.read_parquet(preprocessed_path)
    
    db: Session = SessionLocal()
    
    try:
        # Check if DB is already populated to avoid duplication
        existing_count = db.query(Case).count()
        if existing_count > 0:
            print(f"Database already contains {existing_count} records. Clearing table to reload.")
            db.query(Case).delete()
            db.commit()
            
        metadata_list = df['metadata'].tolist()
        
        cases_to_insert = []
        for meta in metadata_list:
            case = Case(
                case_id=meta.get('case_id'),
                case_name=meta.get('case_name'),
                citation=meta.get('citation'),
                year=meta.get('year'),
                court=meta.get('court'),
                legal_domain=meta.get('legal_domain'),
                section=meta.get('section'),
                source=meta.get('source'),
                record_type=meta.get('record_type'),
                valid_from=meta.get('valid_from'),
                valid_until=meta.get('valid_until'),
                contains_outcome_language=meta.get('contains_outcome_language')
            )
            cases_to_insert.append(case)
            
        print(f"Inserting {len(cases_to_insert)} records into SQLite...")
        db.bulk_save_objects(cases_to_insert)
        db.commit()
        
        count = db.query(Case).count()
        print(f"Successfully loaded {count} records into SQLite metadata store.")
        
    except Exception as e:
        db.rollback()
        print(f"Error loading to SQLite: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    preprocessed_parquet = "data/processed/cases_preprocessed.parquet"
    load_data_to_sqlite(preprocessed_parquet)
