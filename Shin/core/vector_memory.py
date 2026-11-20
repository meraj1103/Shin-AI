"""
vector_memory.py — Advanced Vector Memory System for Shin
==========================================================
Implements:
- Semantic memory with vector embeddings (local via Ollama/LM Studio)
- Episodic memory (conversation history with timestamps)
- Procedural memory (skills, workflows, patterns)
- Memory consolidation and importance scoring
- Cross-session learning and retrieval
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import deque

import numpy as np

# Project imports
import sys
from pathlib import Path as P
_ROOT = P(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_CORE = _ROOT / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from core.shin_agent import DualModeLLMRouter, HardwareProfile

logger = logging.getLogger("shin.vector_memory")


# ═══════════════════════════════════════════════════════════════════════════════
# Memory Types & Data Structures
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryType(Enum):
    SEMANTIC = "semantic"      # Facts, knowledge, concepts
    EPISODIC = "episodic"      # Conversations, experiences, events
    PROCEDURAL = "procedural"  # Skills, workflows, how-to patterns


class MemoryImportance(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class MemoryEntry:
    """A single memory entry with vector embedding."""
    id: str
    type: MemoryType
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance: MemoryImportance = MemoryImportance.MEDIUM
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    tags: List[str] = field(default_factory=list)
    source: str = "user"  # user, system, inferred
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "importance": self.importance.value,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "tags": self.tags,
            "source": self.source,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        return cls(
            id=data["id"],
            type=MemoryType(data["type"]),
            content=data["content"],
            embedding=data.get("embedding"),
            metadata=data.get("metadata", {}),
            importance=MemoryImportance(data.get("importance", 2)),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            access_count=data.get("access_count", 0),
            tags=data.get("tags", []),
            source=data.get("source", "user"),
        )


@dataclass
class RetrievalResult:
    """Result from memory retrieval."""
    memory: MemoryEntry
    score: float  # Similarity score (0-1)
    retrieval_method: str  # vector, keyword, hybrid


# ═══════════════════════════════════════════════════════════════════════════════
# Embedding Provider
# ═══════════════════════════════════════════════════════════════════════════════

class EmbeddingProvider:
    """Abstract embedding provider with multiple backends."""
    
    def __init__(self, router: DualModeLLMRouter):
        self.router = router
        self._embedding_cache: Dict[str, List[float]] = {}
        self._cache_lock = threading.Lock()
        self._init_provider()
    
    def _init_provider(self):
        """Initialize the best available embedding provider."""
        # Try Ollama first (local, privacy-first)
        self.provider_type = "ollama"
        self.ollama_url = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        self.embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
        
        # Try LM Studio as fallback
        self.lm_studio_url = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1").rstrip("/")
        self.lm_studio_model = os.getenv("LM_STUDIO_EMBEDDING_MODEL", "text-embedding-nomic-embed-text-v1.5")
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for text, using cache if available."""
        # Check cache
        cache_key = hashlib.md5(text.encode()).hexdigest()
        with self._cache_lock:
            if cache_key in self._embedding_cache:
                return self._embedding_cache[cache_key]
        
        # Generate embedding
        embedding = self._generate_embedding(text)
        
        # Cache it
        with self._cache_lock:
            self._embedding_cache[cache_key] = embedding
        
        return embedding
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using available provider."""
        # Try Ollama
        try:
            import requests
            resp = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": self.embedding_model, "prompt": text},
                timeout=10.0,
            )
            if resp.status_code == 200:
                return resp.json().get("embedding", [])
        except Exception as e:
            logger.debug(f"Ollama embedding failed: {e}")
        
        # Try LM Studio (OpenAI-compatible)
        try:
            import requests
            resp = requests.post(
                f"{self.lm_studio_url}/embeddings",
                json={"model": self.lm_studio_model, "input": text},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", [{}])[0].get("embedding", [])
        except Exception as e:
            logger.debug(f"LM Studio embedding failed: {e}")
        
        # Fallback: Use router's LLM to generate pseudo-embedding via hashing
        # This is a last resort - not semantically meaningful but consistent
        return self._hash_embedding(text)
    
    def _hash_embedding(self, text: str, dim: int = 384) -> List[float]:
        """Generate deterministic pseudo-embedding from text hash."""
        # Use multiple hash functions for better distribution
        hashes = []
        for seed in range(4):
            h = hashlib.blake2b(f"{seed}{text}".encode(), digest_size=dim//8).digest()
            hashes.extend([b / 255.0 for b in h])
        return hashes[:dim]


# ═══════════════════════════════════════════════════════════════════════════════
# Vector Memory Store
# ═══════════════════════════════════════════════════════════════════════════════

class VectorMemoryStore:
    """
    SQLite-backed vector memory store with semantic search.
    Supports multiple memory types with importance-based retention.
    """
    
    def __init__(self, router: DualModeLLMRouter, db_path: Optional[Path] = None):
        self.router = router
        self.embedding_provider = EmbeddingProvider(router)
        
        if db_path is None:
            db_path = _ROOT / "data" / "vector_memory.db"
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def _init_db(self):
        """Initialize database schema."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # Main memories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding BLOB,
                    metadata TEXT,
                    importance INTEGER DEFAULT 2,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    tags TEXT,
                    source TEXT DEFAULT 'user'
                )
            """)
            
            # Index for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_tags ON memories(tags)
            """)
            
            # Conversation turns table (episodic memory)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    user_message TEXT,
                    assistant_response TEXT,
                    timestamp TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversation_session ON conversation_turns(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversation_time ON conversation_turns(timestamp)
            """)
            
            # Procedural patterns table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS procedural_patterns (
                    id TEXT PRIMARY KEY,
                    pattern_name TEXT,
                    description TEXT,
                    steps TEXT,  -- JSON array of steps
                    trigger_conditions TEXT,  -- JSON
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    last_used TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            conn.commit()
    
    def add_memory(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.SEMANTIC,
        metadata: Optional[Dict[str, Any]] = None,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        tags: Optional[List[str]] = None,
        source: str = "user",
        memory_id: Optional[str] = None,
    ) -> MemoryEntry:
        """Add a new memory entry with automatic embedding generation."""
        with self._lock:
            mem_id = memory_id or str(uuid.uuid4())[:12]
            now = datetime.now().isoformat()
            
            # Generate embedding
            embedding = self.embedding_provider.get_embedding(content)
            embedding_blob = np.array(embedding, dtype=np.float32).tobytes() if embedding else None
            
            entry = MemoryEntry(
                id=mem_id,
                type=memory_type,
                content=content,
                embedding=embedding,
                metadata=metadata or {},
                importance=importance,
                created_at=datetime.fromisoformat(now),
                last_accessed=datetime.fromisoformat(now),
                tags=tags or [],
                source=source,
            )
            
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO memories (id, type, content, embedding, metadata, importance, 
                                     created_at, last_accessed, access_count, tags, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.id,
                entry.type.value,
                entry.content,
                embedding_blob,
                json.dumps(entry.metadata),
                entry.importance.value,
                entry.created_at.isoformat(),
                entry.last_accessed.isoformat(),
                entry.access_count,
                json.dumps(entry.tags),
                entry.source,
            ))
            conn.commit()
            
            logger.debug(f"Added memory {mem_id} ({memory_type.value}): {content[:50]}...")
            return entry
    
    def get_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        """Retrieve a memory by ID."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
            row = cursor.fetchone()
            
            if row:
                self._update_access(row["id"])
                return self._row_to_entry(row)
            return None
    
    def _update_access(self, memory_id: str):
        """Update last_accessed and access_count."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE memories 
            SET last_accessed = ?, access_count = access_count + 1
            WHERE id = ?
        """, (datetime.now().isoformat(), memory_id))
        conn.commit()
    
    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        """Convert database row to MemoryEntry."""
        embedding = None
        if row["embedding"]:
            embedding = np.frombuffer(row["embedding"], dtype=np.float32).tolist()
        
        return MemoryEntry(
            id=row["id"],
            type=MemoryType(row["type"]),
            content=row["content"],
            embedding=embedding,
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            importance=MemoryImportance(row["importance"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            last_accessed=datetime.fromisoformat(row["last_accessed"]),
            access_count=row["access_count"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            source=row["source"],
        )
    
    def search(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        top_k: int = 5,
        min_similarity: float = 0.3,
        tags: Optional[List[str]] = None,
    ) -> List[RetrievalResult]:
        """Search memories using vector similarity."""
        with self._lock:
            query_embedding = self.embedding_provider.get_embedding(query)
            if not query_embedding:
                return self._keyword_search(query, memory_type, top_k, tags)
            
            query_vec = np.array(query_embedding, dtype=np.float32)
            
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # Build query
            sql = "SELECT * FROM memories WHERE 1=1"
            params = []
            
            if memory_type:
                sql += " AND type = ?"
                params.append(memory_type.value)
            
            if tags:
                for tag in tags:
                    sql += " AND tags LIKE ?"
                    params.append(f'%"{tag}"%')
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            # Compute similarities
            results = []
            for row in rows:
                entry = self._row_to_entry(row)
                if entry.embedding:
                    entry_vec = np.array(entry.embedding, dtype=np.float32)
                    # Cosine similarity
                    sim = np.dot(query_vec, entry_vec) / (
                        np.linalg.norm(query_vec) * np.linalg.norm(entry_vec) + 1e-8
                    )
                    if sim >= min_similarity:
                        results.append(RetrievalResult(
                            memory=entry,
                            score=float(sim),
                            retrieval_method="vector",
                        ))
            
            # Sort by similarity
            results.sort(key=lambda r: r.score, reverse=True)
            return results[:top_k]
    
    def _keyword_search(
        self,
        query: str,
        memory_type: Optional[MemoryType],
        top_k: int,
        tags: Optional[List[str]],
    ) -> List[RetrievalResult]:
        """Fallback keyword-based search."""
        query_words = set(query.lower().split())
        
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            sql = "SELECT * FROM memories WHERE 1=1"
            params = []
            
            if memory_type:
                sql += " AND type = ?"
                params.append(memory_type.value)
            
            if tags:
                for tag in tags:
                    sql += " AND tags LIKE ?"
                    params.append(f'%"{tag}"%')
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                entry = self._row_to_entry(row)
                content_words = set(entry.content.lower().split())
                overlap = len(query_words & content_words)
                if overlap > 0:
                    score = overlap / max(len(query_words), len(content_words))
                    results.append(RetrievalResult(
                        memory=entry,
                        score=score,
                        retrieval_method="keyword",
                    ))
            
            results.sort(key=lambda r: r.score, reverse=True)
            return results[:top_k]
    
    def get_recent(
        self,
        memory_type: Optional[MemoryType] = None,
        limit: int = 20,
        since: Optional[datetime] = None,
    ) -> List[MemoryEntry]:
        """Get recent memories by creation time."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            sql = "SELECT * FROM memories WHERE 1=1"
            params = []
            
            if memory_type:
                sql += " AND type = ?"
                params.append(memory_type.value)
            
            if since:
                sql += " AND created_at >= ?"
                params.append(since.isoformat())
            
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(sql, params)
            return [self._row_to_entry(row) for row in cursor.fetchall()]
    
    def add_conversation_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record a conversation turn for episodic memory."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversation_turns (id, session_id, user_message, assistant_response, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4())[:12],
                session_id,
                user_message,
                assistant_response,
                datetime.now().isoformat(),
                json.dumps(metadata or {}),
            ))
            conn.commit()
    
    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a session."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM conversation_turns 
                WHERE session_id = ? 
                ORDER BY timestamp DESC LIMIT ?
            """, (session_id, limit))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def add_procedural_pattern(
        self,
        pattern_name: str,
        description: str,
        steps: List[Dict[str, Any]],
        trigger_conditions: Dict[str, Any],
    ) -> str:
        """Store a learned procedural pattern."""
        with self._lock:
            pattern_id = str(uuid.uuid4())[:12]
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO procedural_patterns (id, pattern_name, description, steps, trigger_conditions, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                pattern_id,
                pattern_name,
                description,
                json.dumps(steps),
                json.dumps(trigger_conditions),
                datetime.now().isoformat(),
            ))
            conn.commit()
            return pattern_id
    
    def get_procedural_patterns(
        self,
        trigger: Optional[Dict[str, Any]] = None,
        min_success_rate: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant procedural patterns."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM procedural_patterns")
            
            patterns = []
            for row in cursor.fetchall():
                total = row["success_count"] + row["failure_count"]
                success_rate = row["success_count"] / total if total > 0 else 0
                
                if success_rate >= min_success_rate:
                    patterns.append({
                        "id": row["id"],
                        "name": row["pattern_name"],
                        "description": row["description"],
                        "steps": json.loads(row["steps"]),
                        "trigger_conditions": json.loads(row["trigger_conditions"]),
                        "success_rate": success_rate,
                        "last_used": row["last_used"],
                    })
            
            return patterns
    
    def consolidate_memories(self, max_age_days: int = 30) -> Dict[str, int]:
        """
        Consolidate memories: promote important ones, archive old low-importance ones.
        Returns stats about consolidation.
        """
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat()
            
            # Find old, low-importance memories with low access
            cursor.execute("""
                SELECT id, importance, access_count FROM memories
                WHERE created_at < ? AND importance <= 2 AND access_count < 3
            """, (cutoff,))
            
            archived = 0
            for row in cursor.fetchall():
                # Could move to archive table or just mark
                cursor.execute("UPDATE memories SET importance = 0 WHERE id = ?", (row["id"],))
                archived += 1
            
            # Promote frequently accessed memories
            cursor.execute("""
                UPDATE memories 
                SET importance = CASE 
                    WHEN importance < 4 AND access_count >= 10 THEN importance + 1
                    ELSE importance
                END
            """)
            
            promoted = cursor.rowcount
            conn.commit()
            
            return {"archived": archived, "promoted": promoted}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory store statistics."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute("SELECT type, COUNT(*) as count FROM memories GROUP BY type")
            type_counts = {row["type"]: row["count"] for row in cursor.fetchall()}
            
            cursor.execute("SELECT AVG(importance) as avg_imp, SUM(access_count) as total_access FROM memories")
            row = cursor.fetchone()
            
            cursor.execute("SELECT COUNT(*) as count FROM conversation_turns")
            conv_count = cursor.fetchone()["count"]
            
            cursor.execute("SELECT COUNT(*) as count FROM procedural_patterns")
            pattern_count = cursor.fetchone()["count"]
            
            return {
                "memory_types": type_counts,
                "total_memories": sum(type_counts.values()),
                "avg_importance": row["avg_imp"] or 0,
                "total_accesses": row["total_access"] or 0,
                "conversation_turns": conv_count,
                "procedural_patterns": pattern_count,
                "cache_size": len(self.embedding_provider._embedding_cache),
            }


# ═══════════════════════════════════════════════════════════════════════════════
# Vector Memory Manager (High-level Interface)
# ═══════════════════════════════════════════════════════════════════════════════

class VectorMemoryManager:
    """
    High-level interface for Shin's vector memory system.
    Integrates with existing memory.py and provides semantic search.
    """
    
    def __init__(self, router: Optional[DualModeLLMRouter] = None):
        self.router = router or DualModeLLMRouter(HardwareProfile())
        self.store = VectorMemoryStore(self.router)
        self.session_id = str(uuid.uuid4())[:8]
        
        # Sync with legacy memory.json
        self._sync_legacy_memories()
    
    def _sync_legacy_memories(self):
        """Import memories from legacy memory.json."""
        try:
            from core import memory as legacy_memory
            memories = legacy_memory.load_memories()
            
            for mem in memories:
                content = mem.get("content", "")
                if content:
                    # Check if already imported
                    existing = self.store.search(content, top_k=1, min_similarity=0.95)
                    if not existing:
                        self.store.add_memory(
                            content=content,
                            memory_type=MemoryType.SEMANTIC,
                            metadata={"legacy_timestamp": mem.get("timestamp")},
                            importance=MemoryImportance.MEDIUM,
                            tags=["legacy"],
                            source="legacy_import",
                        )
            
            logger.info(f"Synced {len(memories)} legacy memories")
        except Exception as e:
            logger.debug(f"Legacy memory sync skipped: {e}")
    
    def remember(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.SEMANTIC,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Store a new memory."""
        entry = self.store.add_memory(
            content=content,
            memory_type=memory_type,
            importance=importance,
            tags=tags,
        )
        return entry.id
    
    def recall(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search and retrieve relevant memories."""
        results = self.store.search(query, memory_type, top_k=limit)
        
        return [
            {
                "id": r.memory.id,
                "content": r.memory.content,
                "type": r.memory.type.value,
                "score": r.score,
                "metadata": r.memory.metadata,
                "tags": r.memory.tags,
                "created_at": r.memory.created_at.isoformat(),
            }
            for r in results
        ]
    
    def get_context_for_prompt(self, query: str, max_items: int = 10) -> str:
        """Get formatted memory context for LLM prompts."""
        results = self.recall(query, limit=max_items)
        
        if not results:
            return ""
        
        lines = ["\nRelevant Memories:"]
        for i, r in enumerate(results, 1):
            lines.append(f"  {i}. [{r['type']}] {r['content']} (relevance: {r['score']:.2f})")
        
        return "\n".join(lines)
    
    def record_conversation(self, user_msg: str, assistant_response: str):
        """Record a conversation turn."""
        self.store.add_conversation_turn(
            session_id=self.session_id,
            user_message=user_msg,
            assistant_response=assistant_response,
        )
        
        # Also extract implicit memories
        self._extract_implicit_memories(user_msg)
        self._extract_implicit_memories(assistant_response)
    
    def _extract_implicit_memories(self, text: str):
        """Extract facts and tasks from text using LLM."""
        # This would use the existing extract_and_store_implicit_knowledge from memory.py
        try:
            from core import memory as legacy_memory
            legacy_memory.extract_and_store_implicit_knowledge(text)
        except Exception:
            pass
    
    def learn_pattern(
        self,
        name: str,
        description: str,
        steps: List[Dict[str, Any]],
        triggers: Dict[str, Any],
    ):
        """Learn a procedural pattern."""
        self.store.add_procedural_pattern(name, description, steps, triggers)
    
    def suggest_patterns(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Suggest relevant procedural patterns."""
        return self.store.get_procedural_patterns(trigger=context)
    
    def consolidate(self) -> Dict[str, int]:
        """Run memory consolidation."""
        return self.store.consolidate_memories()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return self.store.get_stats()


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance & Entry Points
# ═══════════════════════════════════════════════════════════════════════════════

_GLOBAL_VECTOR_MEMORY: Optional[VectorMemoryManager] = None


def get_vector_memory() -> VectorMemoryManager:
    global _GLOBAL_VECTOR_MEMORY
    if _GLOBAL_VECTOR_MEMORY is None:
        _GLOBAL_VECTOR_MEMORY = VectorMemoryManager()
    return _GLOBAL_VECTOR_MEMORY


# Backward compatibility with memory.py interface
def add_memory(content: str) -> str:
    return get_vector_memory().remember(content)


def search_memories(query: str = None) -> List[Dict[str, Any]]:
    if not query:
        vm = get_vector_memory()
        recent = vm.store.get_recent(limit=20)
        return [{"content": m.content, "timestamp": m.created_at.isoformat()} for m in recent]
    return get_vector_memory().recall(query)


def build_memories_prompt_context() -> str:
    """Enhanced version for LLM prompts."""
    vm = get_vector_memory()
    # Get recent memories across all types
    recent = vm.store.get_recent(limit=20)
    
    if not recent:
        return ""
    
    lines = ["\nUser's saved personal facts & memories (Shin's persistent memory):"]
    for i, mem in enumerate(recent, 1):
        lines.append(f"  {i}. [{mem.created_at.strftime('%Y-%m-%d %H:%M')}] {mem.content}")
    lines.append("Use this memory context to answer any questions about the user's past, tasks, details, preferences, or belongings.\n")
    
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Testing
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    vm = VectorMemoryManager()
    
    # Test adding memories
    vm.remember("MJ loves coding in Python and uses VS Code", MemoryType.SEMANTIC, MemoryImportance.HIGH, ["preference", "coding"])
    vm.remember("MJ's sister is named Priya", MemoryType.SEMANTIC, MemoryImportance.HIGH, ["family"])
    vm.remember("Had a great coding session yesterday building a React app", MemoryType.EPISODIC, MemoryImportance.MEDIUM, ["coding", "session"])
    
    # Test recall
    results = vm.recall("What does MJ like to code in?")
    for r in results:
        print(f"  [{r['score']:.2f}] {r['content']}")
    
    # Test context
    print(vm.get_context_for_prompt("coding preferences"))
    
    # Stats
    print(json.dumps(vm.get_stats(), indent=2, default=str))