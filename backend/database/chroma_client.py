import logging
import os
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

def get_chroma_client():
    """
    Initialize ChromaDB persistent client.
    Create or get three collections: posts, graph_facts, topic_summaries.
    """
    try:
        db_path = os.environ.get("CHROMA_DB_PATH", "data/chroma_db")
        if not os.path.exists(db_path):
            os.makedirs(db_path, exist_ok=True)
            
        client = chromadb.PersistentClient(path=db_path, settings=Settings(anonymized_telemetry=False))
        
        # We don't embed natively in chroma, we will pass embeddings computed by sentence-transformers manually
        col_posts = client.get_or_create_collection(name="posts")
        col_graphs = client.get_or_create_collection(name="graph_facts")
        col_topics = client.get_or_create_collection(name="topic_summaries")
        
        return client, col_posts, col_graphs, col_topics
    except Exception as e:
        logger.error(f"Error initializing ChromaDB: {e}")
        return None, None, None, None
