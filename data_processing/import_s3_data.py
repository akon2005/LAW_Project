import os
import json
import boto3
from botocore import UNSIGNED
from botocore.client import Config

# Initialize S3 client for anonymous access
s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))
bucket_name = 'indian-supreme-court-judgments'

# We'll fetch from year 2024
prefix = 'metadata/json/year=2024/'

print("Fetching list of objects...")
response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix, MaxKeys=50)

cases_added = []
for obj in response.get('Contents', []):
    key = obj['Key']
    if not key.endswith('.json'):
        continue
    
    print(f"Downloading {key}...")
    file_obj = s3.get_object(Bucket=bucket_name, Key=key)
    file_content = file_obj['Body'].read().decode('utf-8')
    data = json.loads(file_content)
    
    # Extract data to match our schema
    case_id = data.get('case_id', '')
    if not case_id:
        case_id = data.get('nc_display', f"SC_2024_{len(cases_added)}")
        
    title = data.get('title', 'Unknown Title')
    year = 2024
    court = "Supreme Court of India"
    
    # Use description or some summary as facts
    facts = data.get('description', '')
    if not facts:
        facts = "Facts not explicitly detailed in metadata."
        
    # Sections (if any)
    sections = []
    
    outcome = data.get('disposal_nature', 'Unknown')
    outcome_label = 1 if 'Allowed' in str(outcome) or 'Conviction' in str(outcome) else 0
    
    reasoning_excerpt = data.get('judgment', '') or data.get('raw_html', '')[:500]
    
    new_case = {
        "case_id": case_id,
        "case_name": title,
        "year": year,
        "court": court,
        "facts": facts,
        "sections": sections,
        "outcome": outcome,
        "outcome_label": outcome_label,
        "reasoning_excerpt": reasoning_excerpt
    }
    cases_added.append(new_case)

print(f"Downloaded {len(cases_added)} cases.")

# Append to cases.json
cases_file = r'd:\All projects\LAW project\backend\data\dataset\cases.json'
with open(cases_file, 'r', encoding='utf-8') as f:
    existing_cases = json.load(f)

existing_cases.extend(cases_added)

with open(cases_file, 'w', encoding='utf-8') as f:
    json.dump(existing_cases, f, indent=2, ensure_ascii=False)
    
print("Successfully appended to cases.json")
