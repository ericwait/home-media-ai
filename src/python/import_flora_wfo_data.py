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


def get_engine():
    db_uri = os.getenv("HOME_MEDIA_AI_URI")
    return create_engine(db_uri)


def download_zip(url=WFO_URL, out_path=ZIP_PATH):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} -> {out_path}")
    r = requests.get(url, stream=True, verify=certifi.where())
    r.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return out_path


def file_checksum(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def record_version(engine, zip_path):
    checksum = file_checksum(zip_path)
    file_size = os.path.getsize(zip_path)
    file_name = os.path.basename(zip_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    ddl = """
    CREATE TABLE IF NOT EXISTS wfo_versions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        downloaded_at DATETIME NOT NULL,
        file_name VARCHAR(255),
        file_size BIGINT,
        checksum CHAR(64) UNIQUE,
        notes TEXT
    )
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))
        try:
            conn.execute(
                text("""
                INSERT INTO wfo_versions (downloaded_at, file_name, file_size, checksum, notes)
                VALUES (:downloaded_at, :file_name, :file_size, :checksum, :notes)
                """),
                {
                    "downloaded_at": now,
                    "file_name": file_name,
                    "file_size": file_size,
                    "checksum": checksum,
                    "notes": "Automated ingestion of WFO Backbone"
                }
            )
            print(f"Version recorded: {file_name}, checksum={checksum[:12]}...")
        except Exception:
            print(f"Version already recorded (checksum {checksum[:12]}...). Skipping.")


# --- Extract CSV from ZIP ---
def extract_csv(zip_path, extract_dir="data"):
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(extract_dir)
        for f in z.namelist():
            if f.endswith(".csv"):
                return os.path.join(extract_dir, f)
    raise FileNotFoundError("No CSV found in ZIP")


# --- Load and Filter Data ---
def load_plants(csv_file):
    df = pd.read_csv(
        csv_file,
        sep="\t",          # WFO backbone is tab-delimited
        quoting=3,         # QUOTE_NONE
        dtype=str,         # keep IDs/names as strings
        low_memory=False,
        on_bad_lines="skip",
        encoding="ISO-8859-1"
    )
    if "taxonomicStatus" in df.columns:
        df = df[df["taxonomicStatus"].str.lower() == "accepted"]
    return df


def clean_dataframe(df):
    df = df.where(pd.notnull(df), None)
    for col in ["scientificName", "scientificNameAuthorship", "source", "majorGroup"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: x.strip('"') if isinstance(x, str) else x)
    for col in ["created", "modified"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")
    return df


# --- Create Table (pared down) ---
def create_table(engine):
    ddl = """
    CREATE TABLE IF NOT EXISTS plant_taxonomy (
        taxon_id VARCHAR(50) PRIMARY KEY,
        parent_id VARCHAR(50),
        scientific_name VARCHAR(255),
        authorship VARCHAR(255),
        taxon_rank VARCHAR(50),
        family VARCHAR(100),
        genus VARCHAR(100),
        taxonomic_status VARCHAR(50),
        source_references TEXT,
        source VARCHAR(255),
        major_group VARCHAR(100),
        created DATE,
        modified DATE
    )
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


# --- Upsert Data (pared down) ---
def merge_plant_taxonomy_info(engine, df, limit=None):
    if limit:
        df = df.head(limit)

    df = clean_dataframe(df)
    rows = df.to_dict(orient="records")

    upsert_sql = """
    INSERT INTO plant_taxonomy (
        taxon_id, parent_id, scientific_name, authorship, taxon_rank,
        family, genus, taxonomic_status, source_references, source,
        major_group, created, modified
    )
    VALUES (
        :taxonID, :parentNameUsageID, :scientificName, :scientificNameAuthorship, :taxonRank,
        :family, :genus, :taxonomicStatus, :references, :source,
        :majorGroup, :created, :modified
    )
    ON DUPLICATE KEY UPDATE
        parent_id = VALUES(parent_id),
        scientific_name = VALUES(scientific_name),
        authorship = VALUES(authorship),
        taxon_rank = VALUES(taxon_rank),
        family = VALUES(family),
        genus = VALUES(genus),
        taxonomic_status = VALUES(taxonomic_status),
        source_references = VALUES(source_references),
        source = VALUES(source),
        major_group = VALUES(major_group),
        created = VALUES(created),
        modified = VALUES(modified)
    """

    with engine.begin() as conn:
        # batch insert to avoid packet size issues
        batch_size = 1000
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i+batch_size]
            conn.execute(text(upsert_sql), batch)


# --- Mermaid Graph for a Family (Family → Genus only) ---
def make_mermaid_for_family(df, family_name, limit=100):
    sub = df[df["family"] == family_name].head(limit)
    lines = ["graph TD", f'    A["{family_name}"]']
    genus_seen = set()
    for _, row in sub.iterrows():
        genus = row.get("genus")
        if genus and genus not in genus_seen:
            node_id = f'G_{genus}'
            lines.append(f'    A --> {node_id}["{genus}"]')
            genus_seen.add(genus)
    return "\n".join(lines)


def write_family_graphs(engine, families, limit=20):
    with engine.begin() as conn:
        for fam in families:
            df = pd.read_sql(text("SELECT * FROM plant_taxonomy WHERE family=:fam"), conn, params={"fam": fam})
            mermaid = make_mermaid_for_family(df, fam, limit=limit)
            write_mermaid_to_file(mermaid, f"{fam}_taxonomy.mmd")


def make_mermaid_major_groups(engine, limit_families=10):
    sql = """
    SELECT major_group, family, COUNT(*) AS taxa_count
    FROM plant_taxonomy
    WHERE family IS NOT NULL AND family <> ''
    GROUP BY major_group, family
    ORDER BY major_group, taxa_count DESC
    """
    lines = ["graph TD", '    ROOT["Plantae"]']
    with engine.begin() as conn:
        result = conn.execute(text(sql))
        data = result.fetchall()

    # Organize families under each major group
    groups = {}
    for mg, fam, count in data:
        if not mg:
            mg = "Unknown"
        groups.setdefault(mg, []).append((fam, count))

    # Build Mermaid nodes
    for mg, fams in groups.items():
        node_id = f'MG_{mg.replace(" ", "_")}'
        lines.append(f'    ROOT --> {node_id}["{mg}"]')
        # apply limit here
        for fam, count in fams[:limit_families]:
            fam_id = f'F_{fam.replace(" ", "_")}'
            lines.append(f'    {node_id} --> {fam_id}["{fam} ({count})"]')

    return "\n".join(lines)


def write_mermaid_to_file(mermaid_str, filename="flora_family.mmd"):
    doc_dir = Path(__file__).resolve().parents[2] / "doc"
    doc_dir.mkdir(parents=True, exist_ok=True)
    out_path = doc_dir / filename
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(mermaid_str)
    print(f"Mermaid graph written to {out_path}")


# --- Diagnostic Report ---
def run_report(engine):
    queries = {
        "Total taxa": """
            SELECT COUNT(*) AS total_taxa
            FROM plant_taxonomy;
        """,
        "Sample records": """
            SELECT taxon_id, scientific_name, family, genus, taxonomic_status
            FROM plant_taxonomy
            LIMIT 5;
        """,
        "Top families by genera": """
            SELECT family, COUNT(DISTINCT genus) AS genera_count, COUNT(*) AS taxa_count
            FROM plant_taxonomy
            GROUP BY family
            ORDER BY genera_count DESC
            LIMIT 10;
        """,
        "Top genera by taxa": """
            SELECT genus, family, COUNT(*) AS taxa_count
            FROM plant_taxonomy
            GROUP BY genus, family
            ORDER BY taxa_count DESC
            LIMIT 10;
        """,
        "Status distribution": """
            SELECT taxonomic_status, COUNT(*) AS n
            FROM plant_taxonomy
            GROUP BY taxonomic_status;
        """,
        "Major groups": """
            SELECT major_group, COUNT(*) AS n
            FROM plant_taxonomy
            GROUP BY major_group
            ORDER BY n DESC;
        """,
        "Metadata ranges": """
            SELECT MIN(created) AS earliest_created,
                   MAX(created) AS latest_created,
                   MIN(modified) AS earliest_modified,
                   MAX(modified) AS latest_modified
            FROM plant_taxonomy;
        """
    }

    with engine.begin() as conn:
        for title, sql in queries.items():
            print(f"\n--- {title} ---")
            result = conn.execute(text(sql))
            # Print nicely
            for row in result.mappings():
                print(dict(row))


# --- Main ---
if __name__ == "__main__":
    engine = get_engine()

    if not ZIP_PATH.exists():
        raise FileNotFoundError(f"{ZIP_PATH} not found. Please download manually.")

    record_version(engine, ZIP_PATH)
    csv_file = extract_csv(ZIP_PATH)
    df = load_plants(csv_file)
    create_table(engine)
    merge_plant_taxonomy_info(engine, df)  #, limit=10000)

    write_family_graphs(engine, ["Cyperaceae"], limit=50)
    mermaid_major = make_mermaid_major_groups(engine, limit_families=10)
    write_mermaid_to_file(mermaid_major, "flora_taxonomy.mmd")/

    # Run diagnostics
    run_report(engine)

