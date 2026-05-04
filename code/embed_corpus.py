#!/usr/bin/env python3
"""CLI to embed all documents and store in local SQLite database.

Usage:
    python embed_corpus.py
"""

import sys
from pathlib import Path
from embeddings.db import EmbeddingDB

# Path to data folder
DATA_DIR = Path(__file__).parent.parent / "data"

def embed_corpus():
    """Scan all .md files and embed them into the database."""

    print("\n" + "="*70)
    print("📚 CORPUS EMBEDDER - Local Vector Database")
    print("="*70 + "\n")

    # Initialize database
    print("🔧 Initializing database...")
    db = EmbeddingDB()
    db.clear()  # Clear previous embeddings
    print("✅ Database ready\n")

    # Scan all companies
    companies = {}
    for company_dir in DATA_DIR.iterdir():
        if not company_dir.is_dir():
            continue

        company = company_dir.name.replace("_", " ").title()
        companies[company] = company_dir

    if not companies:
        print(f"❌ No company folders found in {DATA_DIR}")
        sys.exit(1)

    total_embedded = 0

    # Embed documents for each company
    for company, company_path in sorted(companies.items()):
        print(f"📖 Processing {company}...")

        md_files = list(company_path.glob("**/*.md"))
        if not md_files:
            print(f"   ⚠️  No .md files found\n")
            continue

        company_count = 0

        for md_file in sorted(md_files):
            try:
                # Skip index.md files
                if md_file.name == "index.md":
                    continue

                # Read file
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()

                if not content or not content.strip():
                    continue

                # Get relative path for storage
                rel_path = str(md_file.relative_to(company_path))

                # Use first heading or filename as title
                title = md_file.stem.replace("-", " ").title()
                for line in content.split("\n"):
                    if line.startswith("#"):
                        title = line.lstrip("#").strip()
                        break

                # Add to database
                if db.add_document(company, rel_path, title, content):
                    company_count += 1
                    if company_count % 10 == 0:
                        print(f"   ✓ {company_count} documents...")

            except Exception as e:
                print(f"   ⚠️  Failed to process {md_file.name}: {str(e)}")

        print(f"   ✅ {company_count} documents embedded\n")
        total_embedded += company_count

    # Print summary
    print("="*70)
    stats = db.get_stats()
    print(f"✅ EMBEDDING COMPLETE")
    print("="*70)
    print(f"📊 Total documents: {stats['total_documents']}")
    for company, count in sorted(stats['by_company'].items()):
        print(f"   • {company}: {count} docs")
    print(f"\n💾 Database: {stats['db_path']}")
    print("="*70 + "\n")

    db.close()

if __name__ == "__main__":
    embed_corpus()
