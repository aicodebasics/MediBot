from pydantic_settings import BaseSettings
from typing import Dict, List

class Settings(BaseSettings):
    groq_api_key: str = ""
    qdrant_url: str = ":memory:"
    qdrant_api_key: str = ""
    jwt_secret: str = "medibot-secret-change-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    data_dir: str = "./data"
    db_path: str = "./data/db/mediassist.db"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Role -> allowed collections
ROLE_COLLECTIONS: Dict[str, List[str]] = {
    "doctor":            ["general", "clinical", "nursing"],
    "nurse":             ["general", "nursing"],
    "billing_executive": ["general", "billing"],
    "technician":        ["general", "equipment"],
    "admin":             ["general", "clinical", "nursing", "billing", "equipment"],
}

# Collection -> access roles
COLLECTION_ACCESS: Dict[str, List[str]] = {
    "general":   ["doctor", "nurse", "billing_executive", "technician", "admin"],
    "clinical":  ["doctor", "admin"],
    "nursing":   ["doctor", "nurse", "admin"],
    "billing":   ["billing_executive", "admin"],
    "equipment": ["technician", "admin"],
}

# Roles allowed to use SQL RAG
SQL_RAG_ROLES = {"billing_executive", "admin"}

# Demo users: username -> {password, role}
DEMO_USERS = {
    "dr.mehta":      {"password": "doctor123",   "role": "doctor"},
    "nurse.priya":   {"password": "nurse123",    "role": "nurse"},
    "billing.ravi":  {"password": "billing123",  "role": "billing_executive"},
    "tech.anand":    {"password": "tech123",     "role": "technician"},
    "admin.sys":     {"password": "admin123",    "role": "admin"},
}

QDRANT_COLLECTION = "medibot"
DENSE_MODEL = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL = "Qdrant/bm25"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
HYBRID_TOP_K = 20
RERANK_TOP_N = 5
