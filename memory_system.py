"""
Memory management system for Dementia Chatbot
Handles vector embeddings, storage, and retrieval
"""
import numpy as np
import faiss
import json
from typing import List, Dict, Optional, Tuple
from sentence_transformers import SentenceTransformer
from pathlib import Path
import pickle
import logging
from datetime import datetime
import re

from config import FAISS_INDEX_PATH, EMBEDDING_MODEL, MAX_MEMORY_CHUNKS, TOP_K_RESULTS, SIMILARITY_THRESHOLD
from database import MemoryDatabase

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MemorySystem:
    def __init__(self):
        self.db = MemoryDatabase()
        self.embedding_model = None
        self.embedding_dim = None
        self.index = None
        self.memory_id_map = {}  # Maps index position to memory ID
        try:
            self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
            self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
            self.load_or_create_index()
        except Exception as e:
            logger.error(f"Embedding model initialization failed: {e}")
            self.embedding_model = None
            self.embedding_dim = None
            self.index = None
            self.memory_id_map = {}
    
    def load_or_create_index(self):
        """Load existing FAISS index or create new one"""
        index_file = FAISS_INDEX_PATH / "memory_index.faiss"
        id_map_file = FAISS_INDEX_PATH / "memory_id_map.pkl"
        
        if index_file.exists() and id_map_file.exists():
            try:
                self.index = faiss.read_index(str(index_file))
                with open(id_map_file, 'rb') as f:
                    self.memory_id_map = pickle.load(f)
                logger.info(f"Loaded FAISS index with {self.index.ntotal} memories")
            except Exception as e:
                logger.error(f"Error loading index: {e}")
                self._create_new_index()
        else:
            self._create_new_index()
    
    def _create_new_index(self):
        """Create a new FAISS index"""
        self.index = faiss.IndexFlatIP(self.embedding_dim)  # Inner product for cosine similarity
        self.memory_id_map = {}
        FAISS_INDEX_PATH.mkdir(exist_ok=True)
        logger.info("Created new FAISS index")
    
    def save_index(self):
        """Save FAISS index and ID mapping to disk"""
        try:
            FAISS_INDEX_PATH.mkdir(exist_ok=True)
            index_file = FAISS_INDEX_PATH / "memory_index.faiss"
            id_map_file = FAISS_INDEX_PATH / "memory_id_map.pkl"
            
            faiss.write_index(self.index, str(index_file))
            with open(id_map_file, 'wb') as f:
                pickle.dump(self.memory_id_map, f)
            logger.info("Saved FAISS index to disk")
        except Exception as e:
            logger.error(f"Error saving index: {e}")
    
    def add_memory(self, text: str, source: str, tags: List[str] = None, 
                   language: str = "en") -> str:
        """Add a new memory with embedding"""
        # Add to database
        memory_id = self.db.add_memory(text, source, tags, language)

        # Best-effort vector index update; database write remains source of truth
        if self.embedding_model is not None and self.index is not None:
            try:
                embedding = self.embedding_model.encode([text])
                embedding = embedding.astype('float32')
                faiss.normalize_L2(embedding)
                self.index.add(embedding)
                index_position = self.index.ntotal - 1
                self.memory_id_map[index_position] = memory_id
                self.save_index()
            except Exception as e:
                logger.error(f"Could not add memory to vector index: {e}")
        
        logger.info(f"Added memory {memory_id} to index")
        return memory_id
    
    def search_memories(self, query: str, k: int = TOP_K_RESULTS, 
                       language: str = None) -> List[Dict]:
        """Search for relevant memories using vector similarity with date awareness"""
        if self.index is None or self.embedding_model is None or self.index.ntotal == 0:
            return self._keyword_search_memories(query, k, language)
        
        # Check for date-based queries first
        from date_utils import date_extractor
        modified_query, date_filter = date_extractor.parse_query_dates(query)
        
        # If we found a date filter, search by date first
        if date_filter:
            date_results = self.db.search_memories_by_date(date_filter, language)
            if date_results:
                
                # Sort by relevance (caregiver confirmed first, then recency)
                def date_rank_key(m):
                    caregiver_priority = 1 if m.get('caregiver_confirmed') else 0
                    return (caregiver_priority, m.get('created_at', ''))
                
                date_results.sort(key=date_rank_key, reverse=True)
                return date_results[:k]
        
        # Fall back to vector similarity search with modified query
        search_query = modified_query if modified_query != query else query
        
        try:
            query_embedding = self.embedding_model.encode([search_query])
            query_embedding = query_embedding.astype('float32')
            faiss.normalize_L2(query_embedding)
            scores, indices = self.index.search(query_embedding, min(max(k * 3, k), self.index.ntotal))
        except Exception as e:
            logger.error(f"Vector search failed, using keyword fallback: {e}")
            return self._keyword_search_memories(query, k, language)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # No more results
                break
                
            memory_id = self.memory_id_map.get(idx)
            if memory_id:
                memory = self.db.get_memory(memory_id)
                if memory:
                    # Apply filters
                    if language and memory['language'] != language:
                        continue
                    # Apply similarity threshold (cosine similarity on normalized vectors)
                    if score < SIMILARITY_THRESHOLD:
                        continue

                    memory['similarity_score'] = float(score)
                    results.append(memory)
        
        # Prefer caregiver-confirmed memories, then sort by similarity desc
        def rank_key(m):
            caregiver_priority = 1 if m.get('caregiver_confirmed') else 0
            return (caregiver_priority, m.get('similarity_score', 0.0))

        results.sort(key=rank_key, reverse=True)
        if results:
            return results[:k]

        # Threshold may be too strict for short/plain-language queries.
        # Fall back to deterministic keyword retrieval from decrypted texts.
        return self._keyword_search_memories(query, k, language)

    def _keyword_search_memories(self, query: str, k: int, language: str = None) -> List[Dict]:
        """Keyword-based fallback search over decrypted memory text and tags."""
        memories = self.db.get_all_memories(language=language)
        if not memories:
            return []

        raw_tokens = re.findall(r"\b[a-zA-Z]+\b", (query or "").lower())
        stop_words = {
            "the", "and", "for", "with", "from", "that", "this", "what", "when", "where",
            "who", "how", "does", "did", "have", "has", "had", "are", "was", "were", "you",
            "your", "our", "their", "about", "into", "than", "then", "them", "they"
        }
        tokens = [t for t in raw_tokens if len(t) > 2 and t not in stop_words]

        # Simple intent synonyms to improve retrieval for common health queries.
        expanded_tokens = set(tokens)
        synonym_groups = {
            "medicine": {"medicine", "medicines", "medication", "medications", "drug", "drugs", "tablet", "tablets", "pill", "pills", "metformin"},
            "appointment": {"appointment", "appointments", "doctor", "dentist", "visit", "meeting", "checkup"},
            "family": {"family", "daughter", "son", "mother", "father", "parents", "wife", "husband", "sister", "brother"},
            "sunday": {"sunday", "weekend"}
        }
        for group in synonym_groups.values():
            if expanded_tokens.intersection(group):
                expanded_tokens.update(group)

        tokens = list(expanded_tokens)
        if not tokens:
            return memories[:k]

        scored = []
        for m in memories:
            text = (m.get("text") or "").lower()
            tags = " ".join(m.get("tags") or []).lower()
            combined = f"{text} {tags}"
            overlap = sum(1 for t in tokens if t in combined)
            if overlap > 0:
                m["similarity_score"] = float(overlap) / float(max(len(tokens), 1))
                scored.append(m)

        if not scored:
            return []

        scored.sort(
            key=lambda m: (
                1 if m.get("caregiver_confirmed") else 0,
                m.get("similarity_score", 0.0),
                m.get("created_at", "")
            ),
            reverse=True,
        )
        return scored[:k]
    
    def get_related_memories(self, memory_id: str, k: int = 3) -> List[Dict]:
        """Get memories related to a specific memory"""
        memory = self.db.get_memory(memory_id)
        if not memory:
            return []
        
        # Use the memory text as query
        return self.search_memories(memory['text'], k=k)
    
    def rebuild_index(self):
        """Rebuild the entire FAISS index from database"""
        logger.info("Rebuilding FAISS index from database")
        
        # Create new index
        self._create_new_index()
        
        # Get all memories from database
        memories = self.db.get_all_memories()
        
        if not memories:
            logger.info("No memories found in database")
            return
        
        # Process in batches
        batch_size = 100
        texts = []
        memory_ids = []
        
        for memory in memories:
            texts.append(memory['text'])
            memory_ids.append(memory['id'])
            
            if len(texts) >= batch_size:
                self._add_batch_to_index(texts, memory_ids)
                texts = []
                memory_ids = []
        
        # Add remaining texts
        if texts:
            self._add_batch_to_index(texts, memory_ids)
        
        # Save index
        self.save_index()
        logger.info(f"Rebuilt index with {self.index.ntotal} memories")
    
    def _add_batch_to_index(self, texts: List[str], memory_ids: List[str]):
        """Add a batch of texts to the FAISS index"""
        embeddings = self.embedding_model.encode(texts)
        embeddings = embeddings.astype('float32')
        faiss.normalize_L2(embeddings)
        
        self.index.add(embeddings)
        
        # Update ID mapping
        start_idx = self.index.ntotal - len(texts)
        for i, memory_id in enumerate(memory_ids):
            self.memory_id_map[start_idx + i] = memory_id
    
    def delete_memory(self, memory_id: str):
        """Delete a memory from both database and index"""
        # Delete from database
        self.db.delete_memory(memory_id)
        
        # Rebuild index (FAISS doesn't support deletion efficiently)
        self.rebuild_index()
        
        logger.info(f"Deleted memory {memory_id}")
    
    def get_memory_stats(self) -> Dict:
        """Get statistics about stored memories"""
        memories = self.db.get_all_memories()
        
        stats = {
            'total_memories': len(memories),
            'faiss_index_size': self.index.ntotal,
            'languages': {},
            'sources': {}
        }
        
        for memory in memories:
            # Count by language
            lang = memory['language']
            stats['languages'][lang] = stats['languages'].get(lang, 0) + 1
            
            
            # Count by source
            source = memory['source']
            stats['sources'][source] = stats['sources'].get(source, 0) + 1
        
        return stats
