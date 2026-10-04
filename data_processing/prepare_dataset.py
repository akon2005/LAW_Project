"""
Dataset preparation script for LexRAG.
Loads cases.json (+ statutes, notifications) → validates → populates SQLite.
"""
import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import DATASET_DIR
from app.db.database import init_db, SessionLocal, Case


def load_and_insert(db, file_path: Path, document_type: str):
    """Load a JSON dataset file and insert records into the database."""
    if not file_path.exists():
        print(f"  [Skip] {file_path.name} not found")
        return 0

    with open(file_path, "r", encoding="utf-8") as f:
        docs = json.load(f)

    count = 0
    for doc in docs:
        record = Case(
            case_id=doc.get("doc_id", doc.get("case_id", f"unknown_{count}")),
            case_name=doc.get("title", doc.get("case_name", "Untitled")),
            legal_domain=document_type,
            court=doc.get("court", ""),
            year=doc.get("year", 0),
            citation=doc.get("citation", ""),
            section=", ".join(doc.get("sections", [])) if doc.get("sections") else None,
            source=doc.get("source_url", ""),
            record_type=document_type,
        )
        db.add(record)
        count += 1

    db.commit()
    return count


def main():
    print("=" * 60)
    print("  LexRAG — Dataset Preparation")
    print("=" * 60)

    # Initialize database
    init_db()
    db = SessionLocal()

    # Clear existing records
    db.query(Case).delete()
    db.commit()
    print("[Database] Cleared existing records.")

    total = 0

    # Load case laws
    cases_path = DATASET_DIR / "cases.json"
    count = load_and_insert(db, cases_path, "case_law")
    print(f"[Dataset] Case laws: {count} records from {cases_path.name}")
    total += count

    # Load statutes
    statutes_path = DATASET_DIR / "statutes.json"
    count = load_and_insert(db, statutes_path, "statute")
    print(f"[Dataset] Statutes: {count} records from {statutes_path.name}")
    total += count

    # Load notifications
    notifications_path = DATASET_DIR / "notifications.json"
    count = load_and_insert(db, notifications_path, "notification")
    print(f"[Dataset] Notifications: {count} records from {notifications_path.name}")
    total += count

    # Load regulations
    regulations_path = DATASET_DIR / "regulations.json"
    count = load_and_insert(db, regulations_path, "regulation")
    print(f"[Dataset] Regulations: {count} records from {regulations_path.name}")
    total += count

    # Print statistics
    print(f"\n[Stats] Total documents: {total}")

    # Count by type
    for doc_type in ["case_law", "statute", "notification", "regulation"]:
        type_count = db.query(Case).filter(Case.legal_domain == doc_type).count()
        if type_count > 0:
            print(f"  {doc_type}: {type_count}")

    # Count by jurisdiction
    courts = db.query(Case.court).distinct().all()
    print(f"\n[Stats] Courts: {len(courts)}")
    for c in courts:
        ccount = db.query(Case).filter(Case.court == c[0]).count()
        print(f"  {c[0]}: {ccount}")

    print(f"\n[SUCCESS] Dataset preparation complete! {total} documents loaded.")
    db.close()


if __name__ == "__main__":
    main()
