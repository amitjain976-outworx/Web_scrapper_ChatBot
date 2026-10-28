from typing import List, Dict, Any
import httpx

from utils.logger import get_logger
from config import settings

logger = get_logger(__name__)


class RAGService:
    """
    Retrieval-Augmented Generation service
    (Consumes retrieved contexts only)
    """

    # =====================================================
    # CONTEXT BUILDING
    # =====================================================

    def build_context(
        self,
        search_results: List[Dict[str, Any]],
        max_chars: int = 4000,
    ) -> str:
        context_blocks = []
        total_chars = 0

        for r in search_results:
            text = r.get("text", "").strip()
            payload = r.get("payload", {})

            url = payload.get("url", "unknown source")
            source_type = payload.get("source", "unknown")

            if not text:
                continue

            block = (
                f"Source URL: {url}\n"
                f"Content type: {source_type}\n"
                f"Content:\n{text}"
            )

            if total_chars + len(block) > max_chars:
                break

            context_blocks.append(block)
            total_chars += len(block)

        return "\n\n".join(context_blocks)

    # =====================================================
    # PROMPT
    # =====================================================

    def build_prompt(self, question: str, context: str) -> str:
        return f"""
You are a question-answering assistant.

Rules:
- Use ONLY the provided information.
- Use ONLY the source URLs exactly as provided.
- Do NOT invent, modify, or guess URLs.
- Do NOT use outside knowledge.
- If the answer is not present, reply exactly:
I do not know based on the provided information.

Information:
{context}

Question:
{question}

Answer:
""".strip()

    # =====================================================
    # MAIN ENTRY
    # =====================================================

    async def generate_answer(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        MIN_SCORE = 0.25

        filtered_contexts = [
            c for c in contexts
            if c.get("score", 0) >= MIN_SCORE
        ]

        logger.info("Generating RAG answer")

        if not filtered_contexts:
            return {
                "answer": "I do not know based on the provided information.",
                "sources": [],
            }

        context_text = self.build_context(filtered_contexts)
        prompt = self.build_prompt(query, context_text)

        answer = await self._call_text_llm(prompt)

        sources = list({
            c.get("payload", {}).get("url")
            for c in filtered_contexts
            if c.get("payload", {}).get("url")
        })

        return {
            "answer": answer,
            "sources": sources,
        }

    # =====================================================
    # TEXT LLM
    # =====================================================

    async def _call_text_llm(self, prompt: str) -> str:
        payload = {
            "model": settings.TEXT_LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 256,
            },
        }

        async with httpx.AsyncClient(
            timeout=float(settings.TEXT_LLM_TIMEOUT)
        ) as client:
            response = await client.post(
                f"{settings.TEXT_LLM_BASE_URL}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        return data.get("response", "").strip()
