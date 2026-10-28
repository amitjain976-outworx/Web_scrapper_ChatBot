from typing import List, Dict, Any, Optional
import uuid
import chromadb
from pathlib import Path
from chromadb.config import Settings

from utils.logger import get_logger
from config import settings

logger = get_logger(__name__)

persist_path = Path(settings.CHROMA_PERSIST_PATH).expanduser().resolve()
persist_path.mkdir(parents=True, exist_ok=True)

logger.info(f"[VectorService] Chroma persist directory: {persist_path}")

class VectorService:
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=Settings(
                anonymized_telemetry=False,
            )
        )

        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION
        )

    def upsert_text(
        self,
        text: str,
        # embedding: List[float],
        payload: Dict[str, Any],
        point_id: Optional[str] = None,
    ) -> str:
        pid = point_id or str(uuid.uuid4())

        clean_payload = {
            k: str(v) if not isinstance(v, (str, int, float, bool)) else v
            for k, v in payload.items()
            if v is not None
        }

        clean_payload.setdefault("source", "vision")
        clean_payload.setdefault("content_type", "screenshot")

        try:
            self.collection.upsert(
                ids=[pid],
                # embeddings=[embedding],
                documents=[text],
                metadatas=[clean_payload],
            )

            logger.info(f"[VectorService] Vector inserted | id={pid} | collection={settings.CHROMA_COLLECTION}")

            logger.info(f"[VectorService] Vector count: {self.collection.count()}")

        except Exception as e:
            logger.error(f"Chroma upsert failed: {e}")
            raise

        return pid

    def search(
        self,
        query_text: str,
        limit: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:

        results = self.collection.query(
            query_texts=[query_text],
            n_results=limit,
            where=metadata_filter,
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        response = []
        for doc, meta, distance in zip(documents, metadatas, distances):
            response.append(
                {
                    "text": doc,
                    "payload": meta,
                    "score": 1 / (1 + distance),
                }
            )

        return response

