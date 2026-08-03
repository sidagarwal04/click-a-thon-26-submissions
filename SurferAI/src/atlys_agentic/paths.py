from pathlib import Path

ATLYS_AGENTIC_DIR = Path(__file__).resolve().parent
REPO_ROOT = ATLYS_AGENTIC_DIR.parent.parent if ATLYS_AGENTIC_DIR.parent.name == "src" else ATLYS_AGENTIC_DIR.parent
PROBLEM_STATEMENT_DIR = REPO_ROOT / "problem statment"
DATA_DIR = PROBLEM_STATEMENT_DIR / "data"
SPECS_DIR = PROBLEM_STATEMENT_DIR / "specs"
BASE_CONTEXT_MD = PROBLEM_STATEMENT_DIR / "base_context.md"
DDL_SQL = DATA_DIR / "ddl.sql"
LOAD_SH = DATA_DIR / "load.sh"

ATLYS_AGENTIC_DIR = Path(__file__).resolve().parent
CHDB_PATH = ATLYS_AGENTIC_DIR / "chdb_data"
OUTPUTS_DIR = ATLYS_AGENTIC_DIR / "outputs"
SCHEMAS_DIR = OUTPUTS_DIR / "schemas"
INSIGHTS_DIR = OUTPUTS_DIR / "insights"
TRACES_DIR = OUTPUTS_DIR / "traces"
SUBMISSION_DIR = ATLYS_AGENTIC_DIR / "submission"
UNSEEN_SPECS_DIR = ATLYS_AGENTIC_DIR / "specs" / "06_unseen"
AGENTS_CONFIG_YAML = ATLYS_AGENTIC_DIR / "config" / "agents.yaml"

for _d in (OUTPUTS_DIR, SCHEMAS_DIR, INSIGHTS_DIR, TRACES_DIR, SUBMISSION_DIR, UNSEEN_SPECS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def spec_dir(spec_id: str) -> Path:
    """Resolve spec directory generically across problem statement and agentic specs."""
    # 1. Direct path check under problem statment/specs
    candidate = SPECS_DIR / spec_id
    if candidate.exists():
        return candidate
    # 2. Check under src/atlys_agentic/specs
    candidate = ATLYS_AGENTIC_DIR / "specs" / spec_id
    if candidate.exists():
        return candidate
    # 3. Check directly under problem statment/
    candidate = PROBLEM_STATEMENT_DIR / spec_id
    if candidate.exists():
        return candidate
    # 4. Check for partial name match across known locations
    for root in (SPECS_DIR, ATLYS_AGENTIC_DIR / "specs", PROBLEM_STATEMENT_DIR):
        if root.exists():
            for item in root.iterdir():
                if item.is_dir() and (item / "spec.md").exists():
                    if spec_id in item.name or item.name in spec_id:
                        return item
    return SPECS_DIR / spec_id


def spec_md(spec_id: str) -> Path:
    return spec_dir(spec_id) / "spec.md"


def events_ndjson(spec_id: str) -> Path:
    return spec_dir(spec_id) / "events.ndjson"


def available_spec_ids() -> list[str]:
    """Discover all available feature spec IDs generically across spec folders."""
    seen = set()
    specs = []
    for root in (SPECS_DIR, ATLYS_AGENTIC_DIR / "specs", PROBLEM_STATEMENT_DIR):
        if root.exists():
            for item in sorted(root.iterdir()):
                if item.is_dir() and (item / "spec.md").exists():
                    if item.name not in seen:
                        seen.add(item.name)
                        specs.append(item.name)
    return specs or ["01_express_checkout", "02_group_family", "03_status_sharing", "04_abandoned_checkout_recovery", "05_instant_forex"]



def normalize_spec_id(spec_id: str) -> str:
    if not spec_id:
        return "01_express_checkout"
    for sid in available_spec_ids():
        if spec_id == sid:
            return sid
        clean_spec = spec_id.replace("spec_", "").replace("0", "").strip("_")
        clean_sid = sid.replace("0", "").strip("_")
        if spec_id in sid or clean_spec in clean_sid:
            return sid
    return spec_id


def parse_ddl_tables(ddl_path: Path | None = None) -> dict[str, dict]:
    """Parse table names, column lists, and types from ddl.sql."""
    import re
    path = ddl_path or DDL_SQL
    if not path.exists():
        fallback = REPO_ROOT / "problem statment" / "data" / "ddl.sql"
        if fallback.exists():
            path = fallback
        else:
            return {}
    content = path.read_text(encoding="utf-8")
    tables = {}
    table_blocks = re.findall(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_]+)\s*\((.*?)\)\s*ENGINE",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    for tname, body in table_blocks:
        cols = []
        col_types = {}
        for line in body.splitlines():
            line = line.strip().rstrip(",")
            if line and not line.startswith("--"):
                parts = line.split(None, 1)
                if parts:
                    col_name = parts[0]
                    col_type = parts[1] if len(parts) > 1 else "String"
                    cols.append(col_name)
                    col_types[col_name] = col_type
        tables[tname] = {
            "table_name": tname,
            "columns": cols,
            "column_types": col_types,
        }
    return tables


