"""
MediBot FastAPI backend.
Endpoints: /login, /chat, /collections/{role}, /health
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from groq import Groq

from config import (
    settings,
    DEMO_USERS,
    ROLE_COLLECTIONS,
    SQL_RAG_ROLES,
    QDRANT_COLLECTION,
)
from retrieval import retrieve_and_rerank
from sql_rag import sql_rag_chain

# ── App bootstrap ─────────────────────────────────────────────────────────────
app = FastAPI(title="MediBot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

# ── Qdrant client (loaded at startup) ─────────────────────────────────────────
from qdrant_client import QdrantClient

_qdrant_client: Optional[QdrantClient] = None


def get_qdrant() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        raise HTTPException(status_code=503, detail="Vector store not initialised. Run ingest.py first.")
    return _qdrant_client


@app.on_event("startup")
async def startup():
    global _qdrant_client
    if settings.qdrant_url == ":memory:":
        qdrant_path = "./qdrant_storage"
        if os.path.exists(qdrant_path):
            _qdrant_client = QdrantClient(path=qdrant_path)
            print("Loaded Qdrant from disk storage.")
        else:
            # Auto-run ingestion on first start
            print("No Qdrant storage found. Running ingestion pipeline...")
            from ingest import ingest_all
            _qdrant_client = ingest_all()
    else:
        _qdrant_client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
        print(f"Connected to Qdrant at {settings.qdrant_url}")


# ── Auth helpers ──────────────────────────────────────────────────────────────
def create_token(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": username, "role": role, "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return {"username": payload["sub"], "role": payload["role"]}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ── Pydantic models ────────────────────────────────────────────────────────────
class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str


class ChatRequest(BaseModel):
    question: str


class SourceItem(BaseModel):
    source_document: str
    section_title: str
    collection: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    retrieval_type: str
    role: str


# ── Analytical question detection ─────────────────────────────────────────────
ANALYTICAL_KEYWORDS = {
    "how many", "count", "total", "sum", "average", "list all",
    "which department", "most open", "least", "escalated", "statistics",
    "breakdown", "number of", "percentage", "status of claims",
    "maintenance tickets", "billing claims",
}


def is_analytical(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in ANALYTICAL_KEYWORDS)


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/login", response_model=LoginResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = DEMO_USERS.get(form_data.username)
    if not user or user["password"] != form_data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(form_data.username, user["role"])
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        role=user["role"],
        username=form_data.username,
    )


@app.get("/collections/{role}")
def get_collections(role: str):
    collections = ROLE_COLLECTIONS.get(role)
    if collections is None:
        raise HTTPException(status_code=404, detail=f"Unknown role: {role}")
    return {"role": role, "collections": collections}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    role = user["role"]
    question = req.question.strip()

    # SQL RAG branch
    if is_analytical(question) and role in SQL_RAG_ROLES:
        answer = sql_rag_chain(question)
        return ChatResponse(
            answer=answer,
            sources=[],
            retrieval_type="sql_rag",
            role=role,
        )

    # Check if SQL RAG was intended but role is not permitted
    if is_analytical(question) and role not in SQL_RAG_ROLES:
        return ChatResponse(
            answer=f"As a {role}, you don't have access to analytical database queries. I can only answer questions from your permitted document collections: {', '.join(ROLE_COLLECTIONS[role])}.",
            sources=[],
            retrieval_type="hybrid_rag",
            role=role,
        )

    # Hybrid RAG branch
    client = get_qdrant()
    chunks = retrieve_and_rerank(client, question, role)

    if not chunks:
        allowed = ROLE_COLLECTIONS.get(role, [])
        return ChatResponse(
            answer=f"I couldn't find relevant information in your permitted collections ({', '.join(allowed)}). Please rephrase your question or check if the topic is within your access scope.",
            sources=[],
            retrieval_type="hybrid_rag",
            role=role,
        )

    context = "\n\n---\n\n".join(
        f"[Source: {c['source_document']} | {c['section_title']}]\n{c['text']}"
        for c in chunks
    )

    allowed_collections = ROLE_COLLECTIONS.get(role, [])
    system_prompt = f"""You are MediBot, an intelligent assistant for MediAssist Health Network.
The user is authenticated as role: {role}.
They have access to these document collections: {', '.join(allowed_collections)}.

Answer the question using the provided context. Extract and present ALL relevant details including:
- Drug names, dosages, and administration instructions
- Step-by-step procedures
- Tables with dosage/treatment information (reproduce them clearly)
- Monitoring requirements and referral criteria
- ICD-10 codes where relevant

Be thorough and specific. Always cite the source document and section.
If the context truly lacks information, say so — but first check carefully as the answer is often in a table or list within the context."""

    groq_client = Groq(api_key=settings.groq_api_key)
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )

    answer = response.choices[0].message.content
    sources = [
        SourceItem(
            source_document=c["source_document"],
            section_title=c["section_title"],
            collection=c["collection"],
        )
        for c in chunks
    ]

    return ChatResponse(answer=answer, sources=sources, retrieval_type="hybrid_rag", role=role)
