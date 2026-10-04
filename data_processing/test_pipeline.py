import os
import sys

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.pipeline import retrieve

def run_sanity_tests():
    sample_queries = [
        # Criminal
        "What is the rarest of rare doctrine for death penalty?",
        "When is registration of an FIR mandatory for cognizable offences?",
        
        # Constitutional
        "What is the basic structure doctrine of the Constitution?",
        "Is the right to privacy considered a fundamental right under Article 21?",
        
        # Commercial
        "What are the grounds for setting aside an arbitral award?",
        "Does a unilateral appointment of an arbitrator invalidate the proceedings?",
        
        # Cyber
        "What are the intermediary liability guidelines under Section 79 of the IT Act?",
        "Is Section 66A of the IT Act constitutional?",
        
        # Family
        "What is the right of a Muslim woman to maintenance after the iddat period?",
        "Can a spouse be forced to undergo a medical examination in a matrimonial dispute?"
    ]
    
    print("Running Sanity Tests on Retrieval Pipeline\n" + "="*50)
    
    for idx, query in enumerate(sample_queries, 1):
        print(f"\n[Query {idx}] {query}")
        
        # Retrieve top 3
        try:
            results, is_low_confidence = retrieve(query, top_k=3)
            
            print(f"Low Confidence Triggered: {is_low_confidence}")
            for i, res in enumerate(results, 1):
                print(f"  {i}. {res['case_name']} | Score: {res['similarity_score']:.4f}")
                print(f"     Domain: {res['legal_domain']} | Record Type: {res['record_type']}")
        except Exception as e:
            print(f"Error during retrieval: {e}")

if __name__ == "__main__":
    run_sanity_tests()
