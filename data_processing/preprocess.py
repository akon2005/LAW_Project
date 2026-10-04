import os
import json
import pandas as pd
import numpy as np

def preprocess_for_retrieval(input_path: str, output_path: str, stats_path: str):
    """
    Builds retrieval document, metadata dicts, and computes basic stats.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")
        
    print(f"Loading cleaned data from {input_path}...")
    df = pd.read_parquet(input_path)
    
    # 1. Build a single retrieval document text per row
    def build_retrieval_doc(row):
        parts = []
        if pd.notna(row.get('Case Name')): parts.append(f"Case Name: {row['Case Name']}")
        if pd.notna(row.get('Legal Domain')): parts.append(f"Legal Domain: {row['Legal Domain']}")
        if pd.notna(row.get('Applicable Section(s) / Article(s)')): parts.append(f"Applicable Sections/Articles: {row['Applicable Section(s) / Article(s)']}")
        if pd.notna(row.get('Key Legal Principle / Outcome')): parts.append(f"Key Principle/Outcome: {row['Key Legal Principle / Outcome']}")
        return "\n".join(parts)
        
    df['retrieval_document'] = df.apply(build_retrieval_doc, axis=1)
    
    # 2. Flag outcome-revealing language
    outcome_keywords = ['convicted', 'acquitted', 'sentenced to', 'conviction upheld', 'sentence reduced']
    def check_outcome_language(text):
        if pd.isna(text): return False
        text_lower = str(text).lower()
        return any(keyword in text_lower for keyword in outcome_keywords)
        
    df['contains_outcome_language'] = df['Key Legal Principle / Outcome'].apply(check_outcome_language)
    
    # 3. Build metadata dict per row
    def build_metadata(row):
        # valid_until = null unless overruled. 
        # TODO: update valid_until logic when real full-text judgments + citator data is ingested.
        return {
            'case_id': str(row.get('case_id')),
            'case_name': str(row.get('Case Name', '')),
            'citation': str(row.get('Citation', '')),
            'year': int(row.get('Year', 0)) if pd.notna(row.get('Year')) else 0,
            'court': str(row.get('Court', '')),
            'legal_domain': str(row.get('Legal Domain', '')),
            'section': str(row.get('Applicable Section(s) / Article(s)', '')),
            'source': str(row.get('Data Source', '')),
            'record_type': str(row.get('Record Type', '')),
            'valid_from': int(row.get('Year', 0)) if pd.notna(row.get('Year')) else 0,
            'valid_until': None, 
            'contains_outcome_language': bool(row.get('contains_outcome_language', False))
        }
        
    # We will serialize metadata to JSON strings in the dataframe to easily save back to parquet,
    # or keep as dicts if it's fine. We'll keep as dict objects in a column.
    df['metadata'] = df.apply(build_metadata, axis=1)
    
    # Save the dataframe with new columns
    df.to_parquet(output_path, index=False)
    print(f"Saved preprocessed data to {output_path}")
    
    # 4. Compute basic dataset stats
    stats = {
        'total_rows': len(df),
        'by_legal_domain': df['Legal Domain'].fillna('Unknown').value_counts().to_dict(),
        'by_court': df['Court'].fillna('Unknown').value_counts().to_dict(),
        'by_record_type': df['Record Type'].fillna('Unknown').value_counts().to_dict(),
        'rows_with_outcome_language': int(df['contains_outcome_language'].sum())
    }
    
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=4)
    print(f"Saved dataset stats to {stats_path}")
    
if __name__ == "__main__":
    input_parquet = "data/processed/cases_clean.parquet"
    output_parquet = "data/processed/cases_preprocessed.parquet"
    stats_json = "data/processed/dataset_stats.json"
    preprocess_for_retrieval(input_parquet, output_parquet, stats_json)
