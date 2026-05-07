from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from pathlib import Path
import shutil, uuid
from app.services import db_loader

router = APIRouter()
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/file")
async def upload_file(file: UploadFile = File(...), session_id: str = Form(None)):
    session_id = session_id or str(uuid.uuid4())
    ext = Path(file.filename).suffix.lower()
    if ext not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(400, f"Format non supporté: {ext}")
    dest = UPLOAD_DIR / f"{session_id}_{file.filename}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    if ext == ".csv":
        meta = db_loader.load_csv(session_id, str(dest))
    elif ext in {".xlsx", ".xls"}:
        meta = db_loader.load_excel(session_id, str(dest))
    return {"session_id": session_id, "metadata": meta}


class SQLConnection(BaseModel):
    db_type: str        # postgres | mysql | sqlite | mssql
    host: str = ""
    port: int = 5432
    database: str = ""
    username: str = ""
    password: str = ""
    query: str = ""
    table: str = ""
    name: str = "sql_database"
    session_id: str = ""


@router.post("/sql")
async def connect_sql(conn: SQLConnection):
    session_id = conn.session_id or str(uuid.uuid4())

    # Build connection string
    if conn.db_type == "postgres":
        cs = f"postgresql://{conn.username}:{conn.password}@{conn.host}:{conn.port}/{conn.database}"
    elif conn.db_type == "mysql":
        cs = f"mysql+pymysql://{conn.username}:{conn.password}@{conn.host}:{conn.port}/{conn.database}"
    elif conn.db_type == "sqlite":
        cs = f"sqlite:///{conn.database}"
    elif conn.db_type == "mssql":
        cs = f"mssql+pyodbc://{conn.username}:{conn.password}@{conn.host}:{conn.port}/{conn.database}?driver=ODBC+Driver+17+for+SQL+Server"
    else:
        raise HTTPException(400, f"Type non supporté: {conn.db_type}")

    query = conn.query or (f"SELECT * FROM {conn.table} LIMIT 100000" if conn.table else "")
    if not query:
        raise HTTPException(400, "Fournissez une table ou une requête SQL")

    try:
        meta = db_loader.load_sql(session_id, cs, query, conn.name or conn.database)
        return {"session_id": session_id, "metadata": meta}
    except Exception as e:
        raise HTTPException(500, f"Erreur connexion: {str(e)}")


@router.post("/sql/tables")
async def list_tables(conn: SQLConnection):
    """Liste les tables disponibles dans la base"""
    if conn.db_type == "postgres":
        cs = f"postgresql://{conn.username}:{conn.password}@{conn.host}:{conn.port}/{conn.database}"
        q = "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
    elif conn.db_type == "mysql":
        cs = f"mysql+pymysql://{conn.username}:{conn.password}@{conn.host}:{conn.port}/{conn.database}"
        q = "SHOW TABLES"
    elif conn.db_type == "sqlite":
        cs = f"sqlite:///{conn.database}"
        q = "SELECT name FROM sqlite_master WHERE type='table'"
    else:
        raise HTTPException(400, "Type non supporté")

    try:
        import sqlalchemy, pandas as pd
        engine = sqlalchemy.create_engine(cs)
        df = pd.read_sql(q, engine)
        return {"tables": df.iloc[:, 0].tolist()}
    except Exception as e:
        raise HTTPException(500, f"Erreur: {str(e)}")


@router.get("/sessions")
def list_sessions():
    return {"sessions": db_loader.list_sessions()}

@router.get("/{session_id}/metadata")
def get_metadata(session_id: str):
    meta = db_loader.get_metadata(session_id)
    if not meta:
        raise HTTPException(404, "Session introuvable")
    return meta
