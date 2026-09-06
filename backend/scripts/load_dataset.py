import os
import hashlib
import pandas as pd
import numpy as np

def load_and_clean_data(file_path: str, output_path: str):
    """
    Loads dataset, finds header programmatically, validates columns, drops duplicates,
    cleans text, coerces Year, generates case_id, and saves to parquet.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset not found at {file_path}")

    print(f"Loading data from {file_path}...")
    
    # Read the first few lines to find the header programmatically
    # We look for a line containing 'Case Name' and 'Citation'
    skip_rows = 0
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if 'Case Name' in line and 'Citation' in line:
                skip_rows = i
                break
                
    df = pd.read_csv(file_path, skiprows=skip_rows)
    print(f"Found header at row {skip_rows}. Initial row count: {len(df)}")
    
    # Required columns based on the dataset schema
    required_cols = [
        'Case Name', 'Citation', 'Year', 'Court', 'Legal Domain', 
        'Applicable Section(s) / Article(s)', 'Key Legal Principle / Outcome', 
        'Data Source', 'Record Type'
    ]
    
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in dataset: {missing_cols}")
        
    # Drop exact duplicate rows based on Case Name and Citation
    initial_count = len(df)
    df = df.drop_duplicates(subset=['Case Name', 'Citation'], keep='first')
    print(f"Dropped {initial_count - len(df)} duplicate rows.")
    
    # Normalize whitespace and smart-quote characters in text fields
    text_cols = df.select_dtypes(include=['object', 'string']).columns
    for col in text_cols:
        # replace smart quotes with regular quotes, and normalize whitespace
        df[col] = df[col].astype(str).str.replace(r'[\u2018\u2019]', "'", regex=True) \
                                     .str.replace(r'[\u201C\u201D]', '"', regex=True) \
                                     .str.replace(r'\s+', ' ', regex=True) \
                                     .str.strip()
        # replace 'nan' or 'None' strings that might have been created
        df[col] = df[col].replace({'nan': np.nan, 'None': np.nan})
        
    # Cast Year to integer, coercing errors to NaN
    df['Year'] = pd.to_numeric(df['Year'], errors='coerce')
    missing_year_count = df['Year'].isna().sum()
    if missing_year_count > 0:
        print(f"Warning: {missing_year_count} rows have invalid or missing Year. Dropping them.")
        df = df.dropna(subset=['Year'])
    df['Year'] = df['Year'].astype(int)
    
    # Add a stable case_id per row (hash of Case Name + Citation)
    def generate_id(row):
        unique_string = f"{row['Case Name']}_{row['Citation']}".encode('utf-8')
        return hashlib.sha256(unique_string).hexdigest()[:16] # 16 chars is enough
        
    df['case_id'] = df.apply(generate_id, axis=1)
    
    # Ensure processed directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save to parquet
    df.to_parquet(output_path, index=False)
    print(f"Successfully processed and saved {len(df)} rows to {output_path}")

if __name__ == "__main__":
    input_csv = "../VIDHIVEDA_Sample_Dataset.csv"
    output_parquet = "data/processed/cases_clean.parquet"
    load_and_clean_data(input_csv, output_parquet)
