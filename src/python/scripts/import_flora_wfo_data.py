#!/usr/bin/env python3
"""
WFO Backbone Import - Normalized Schema Version

Downloads and imports World Flora Online taxonomy data into the
normalized taxonomies/taxonomy_versions/taxonomy_nodes schema.
"""
import os
import zipfile
import requests
import certifi
import pandas as pd
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, text

WFO_URL = "https://files.worldfloraonline.org/files/WFO_Backbone/_WFOCompleteBackbone/WFO_Backbone.zip"
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
ZIP_PATH = DATA_DIR / "WFO_Backbone.zip"

TAXONOMY_NAME = "World Flora Online"
TAXONOMY_SOURCE = "https://www.worldfloraonline.org/"
TAXONOMY_DESC = "WFO Backbone - comprehensive plant taxonomy database"


def get_engine():
    """Get database engine from environment variable."""
    db_uri = os.getenv("HOME_MEDIA_AI_URI")
    if not db_uri:
        raise ValueError("HOME_MEDIA_AI_URI environment variable not set")
    return create_engine(db_uri)


def download_zip(url=WFO_URL, out_path=ZIP_PATH):
    """Download WFO backbone ZIP file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} -> {out_path}")
    r = requests.get(url, stream=True, verify=certifi.where())
    r.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return out_path


def file_checksum(path):
    """Calculate SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def get_or_create_taxonomy(engine):
    """Get or create the WFO taxonomy entry, return taxonomy_id."""
    with engine.begin() as conn:
        # Check if exists
        result = conn.execute(
            text("SELECT id FROM taxonomies WHERE name = :name"),
            {"name": TAXONOMY_NAME}
        )
        row = result.fetchone()
        if row:
            print(f"✓ Found existing taxonomy: {TAXONOMY_NAME} (id={row[0]})")
            return row[0]

        # Create new
        result = conn.execute(
            text("""
                INSERT INTO taxonomies (name, description, source)
                VALUES (:name, :description, :source)
            """),
            {
                "name": TAXONOMY_NAME,
                "description": TAXONOMY_DESC,
                "source": TAXONOMY_SOURCE
            }
        )
        taxonomy_id = result.lastrowid
        print(f"✓ Created new taxonomy: {TAXONOMY_NAME} (id={taxonomy_id})")
        return taxonomy_id


def record_version(engine, taxonomy_id, zip_path):
    """Record this version of the WFO backbone, return version_id."""
    checksum = file_checksum(zip_path)
    file_size = os.path.getsize(zip_path)
    file_name = os.path.basename(zip_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with engine.begin() as conn:
        # Check if this version already exists
        result = conn.execute(
            text("SELECT id FROM taxonomy_versions WHERE checksum = :checksum"),
            {"checksum": checksum}
        )
        row = result.fetchone()
        if row:
            print(f"✓ Version already recorded (checksum {checksum[:12]}..., id={row[0]})")
            return row[0]

        # Insert new version
        result = conn.execute(
            text("""
                INSERT INTO taxonomy_versions
                (taxonomy_id, downloaded_at, file_name, file_size, checksum, notes)
                VALUES (:taxonomy_id, :downloaded_at, :file_name, :file_size, :checksum, :notes)
            """),
            {
                "taxonomy_id": taxonomy_id,
                "downloaded_at": now,
                "file_name": file_name,
                "file_size": file_size,
                "checksum": checksum,
                "notes": "Automated ingestion of WFO Backbone via import_flora_wfo_data_v2.py"
            }
        )
        version_id = result.lastrowid
        print(f"✓ Version recorded: {file_name}, checksum={checksum[:12]}..., id={version_id}")
        return version_id


def extract_csv(zip_path):
    """Extract CSV from WFO ZIP file."""
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(DATA_DIR)
        for f in z.namelist():
            if f.endswith(".csv"):
                csv_path = DATA_DIR / f
                print(f"✓ Extracted: {csv_path}")
                return csv_path
    raise FileNotFoundError("No CSV found in ZIP")


def load_plants(csv_file):
    """Load and filter WFO data, keeping only accepted taxa."""
    print(f"Loading WFO data from {csv_file}...")
    df = pd.read_csv(
        csv_file,
        sep="\t",
        quoting=3,
        dtype=str,
        low_memory=False,
        on_bad_lines="skip",
        encoding="ISO-8859-1"
    )
    print(f"  Raw rows: {len(df)}")

    # Filter to accepted taxa only
    if "taxonomicStatus" in df.columns:
        df = df[df["taxonomicStatus"].str.lower() == "accepted"]
        print(f"  Accepted taxa: {len(df)}")

    return df


def clean_dataframe(df):
    """Clean and normalize dataframe for insertion."""
    # Replace NaN with None
    df = df.where(pd.notnull(df), None)

    # Strip quotes from string columns
    string_cols = ["scientificName", "scientificNameAuthorship", "source", "majorGroup"]
    for col in string_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: x.strip('"') if isinstance(x, str) else x)

    # Convert dates
    for col in ["created", "modified"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")

    return df


def insert_taxonomy_nodes(engine, taxonomy_id, df, limit=None):
    """
    Insert taxonomy nodes into the normalized schema.

    First pass: insert all nodes without parent relationships.
    Second pass: update parent_id based on parentNameUsageID.
    """
    if limit:
        df = df.head(limit)
        print(f"⚠ Limiting import to {limit} rows for testing")

    df = clean_dataframe(df)

    print(f"\nInserting {len(df)} taxonomy nodes...")

    # Prepare metadata JSON for each row
    rows = []
    for _, row in df.iterrows():
        metadata = {
            "authorship": row.get("scientificNameAuthorship"),
            "family": row.get("family"),
            "genus": row.get("genus"),
            "source_references": row.get("references"),
            "source": row.get("source"),
            "major_group": row.get("majorGroup"),
            "created": row.get("created"),
            "modified": row.get("modified")
        }
        # Remove None values from metadata
        metadata = {k: v for k, v in metadata.items() if v is not None}

        rows.append({
            "taxonomy_id": taxonomy_id,
            "external_id": row.get("taxonID"),
            "parent_external_id": row.get("parentNameUsageID"),
            "name": row.get("scientificName"),
            "rank": row.get("taxonRank"),
            "status": row.get("taxonomicStatus"),
            "metadata": str(metadata).replace("'", '"')  # Convert to JSON string
        })

    # First pass: insert all nodes
    insert_sql = """
        INSERT IGNORE INTO taxonomy_nodes
        (taxonomy_id, external_id, name, rank, status, metadata)
        VALUES (:taxonomy_id, :external_id, :name, :rank, :status, :metadata)
    """

    batch_size = 1000
    inserted = 0
    with engine.begin() as conn:
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i+batch_size]
            result = conn.execute(text(insert_sql), batch)
            inserted += result.rowcount
            if (i + batch_size) % 10000 == 0:
                print(f"  Inserted {i + batch_size}/{len(rows)} nodes...")

    print(f"✓ Inserted {inserted} nodes (duplicates skipped)")

    # Second pass: update parent relationships
    print("\nResolving parent relationships...")
    update_sql = """
        UPDATE taxonomy_nodes child
        JOIN taxonomy_nodes parent
          ON parent.external_id = :parent_external_id
          AND parent.taxonomy_id = :taxonomy_id
        SET child.parent_id = parent.id
        WHERE child.external_id = :external_id
          AND child.taxonomy_id = :taxonomy_id
    """

    parent_updates = [
        {
            "taxonomy_id": taxonomy_id,
            "external_id": row["external_id"],
            "parent_external_id": row["parent_external_id"]
        }
        for row in rows if row["parent_external_id"]
    ]

    updated = 0
    with engine.begin() as conn:
        for i in range(0, len(parent_updates), batch_size):
            batch = parent_updates[i:i+batch_size]
            for item in batch:
                result = conn.execute(text(update_sql), item)
                updated += result.rowcount
            if (i + batch_size) % 10000 == 0:
                print(f"  Updated {i + batch_size}/{len(parent_updates)} relationships...")

    print(f"✓ Updated {updated} parent relationships")


def run_diagnostics(engine, taxonomy_id):
    """Run diagnostic queries on imported data."""
    queries = {
        "Total nodes": f"""
            SELECT COUNT(*) AS total
            FROM taxonomy_nodes
            WHERE taxonomy_id = {taxonomy_id}
        """,
        "Nodes by rank": f"""
            SELECT rank, COUNT(*) AS count
            FROM taxonomy_nodes
            WHERE taxonomy_id = {taxonomy_id}
            GROUP BY rank
            ORDER BY count DESC
            LIMIT 10
        """,
        "Top families by genera": f"""
            SELECT
                JSON_UNQUOTE(JSON_EXTRACT(metadata, '$.family')) AS family,
                COUNT(DISTINCT JSON_UNQUOTE(JSON_EXTRACT(metadata, '$.genus'))) AS genera_count,
                COUNT(*) AS taxa_count
            FROM taxonomy_nodes
            WHERE taxonomy_id = {taxonomy_id}
              AND JSON_EXTRACT(metadata, '$.family') IS NOT NULL
            GROUP BY family
            ORDER BY genera_count DESC
            LIMIT 10
        """,
        "Orphaned nodes (no parent)": f"""
            SELECT COUNT(*) AS orphans
            FROM taxonomy_nodes
            WHERE taxonomy_id = {taxonomy_id}
              AND parent_id IS NULL
              AND rank != 'kingdom'
        """
    }

    print("\n" + "="*60)
    print("DIAGNOSTIC REPORT")
    print("="*60)

    with engine.begin() as conn:
        for title, sql in queries.items():
            print(f"\n{title}:")
            result = conn.execute(text(sql))
            for row in result.mappings():
                print(f"  {dict(row)}")


def main():
    """Main execution function."""
    print("="*60)
    print("WFO Backbone Import - Normalized Schema")
    print("="*60)

    engine = get_engine()

    # Ensure ZIP file exists
    if not ZIP_PATH.exists():
        print(f"⚠ {ZIP_PATH} not found. Downloading...")
        download_zip()

    # Get or create taxonomy entry
    taxonomy_id = get_or_create_taxonomy(engine)

    # Record this version
    version_id = record_version(engine, taxonomy_id, ZIP_PATH)

    # Extract and load data
    csv_file = extract_csv(ZIP_PATH)
    df = load_plants(csv_file)

    # Insert into normalized schema
    insert_taxonomy_nodes(engine, taxonomy_id, df)  # Remove limit for full import

    # Run diagnostics
    run_diagnostics(engine, taxonomy_id)

    print("\n" + "="*60)
    print("Import complete!")
    print("="*60)


if __name__ == "__main__":
    main()
