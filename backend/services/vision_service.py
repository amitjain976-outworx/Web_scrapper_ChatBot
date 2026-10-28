import os
import base64
import io
from typing import Optional
import asyncio
import json
import shutil

import httpx
from PIL import Image, ImageOps

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

VISION_SEMAPHORE = asyncio.Semaphore(1)

max_tokens = int(settings.OLLAMA_MAX_TOKENS)

# =====================================================
# IMAGE PREPROCESSING
# =====================================================

def image_to_base64(image_path: str) -> str:
    """
    Load image from disk, normalize orientation, resize,
    and convert to base64 JPEG for vision model input.
    """
    try:
        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img)

            max_size = settings.VISION_MAX_IMAGE_SIZE
            img.thumbnail((max_size, max_size), Image.BICUBIC)

            buffer = io.BytesIO()
            img.convert("RGB").save(buffer, format="JPEG", quality=80, optimize=True,)
            data = buffer.getvalue()

            encoded = base64.b64encode(data).decode()

            # HARD STOP — prevents Ollama GPU OOM crashes
            if len(encoded) > 4_000_000:
                raise RuntimeError("Encoded image too large for vision model")

            return encoded

    except Exception as e:
        logger.exception(f"Invalid image file: {image_path}")
        raise RuntimeError("Failed to process image") from e

# =====================================================
# PROMPT ENGINEERING
# =====================================================

def build_prompt() -> str:
    """
    Strict vision prompt to avoid hallucination and formatting noise.
    Optimized for vector DB ingestion.
    """
    return """
You are an extremely detailed and precise visual analysis assistant.
You are extracting factual information from a webpage screenshot for use in a knowledge base.

Your task is to extract and describe ALL information that is clearly visible in the image.
Your goal is to capture ONLY meaningful, queryable information.
Do not omit any visible element, even if it seems minor or unimportant.

Output formatting rules (strict):
- Use plain text only.
- Do NOT use markdown, symbols, bullet points, headings, or emojis.
- Do NOT include internal reasoning, step-by-step thought process, or self-dialogue.
- Only provide the final factual description of what is visible in the image.
- Do NOT include phrases like "Wait, no", "Let's check", "I think", "Got it", "Let's start", or any other commentary on your own analysis.
- Use complete sentences.
- Paragraphs are allowed only to separate clearly distinct sections of description.
- Use a single blank line between paragraphs.

Core analysis rules:
- Base your response ONLY on what is directly visible in the image.
- Do NOT guess, infer, assume, or use external knowledge.
- Do NOT describe intent, purpose, or functionality unless it is explicitly indicated by visible text, labels, icons, or UI elements.
- If something appears familiar but cannot be confirmed with certainty, state that it cannot be confirmed from the image.
- If any part of the image is blurred, cut off, obstructed, or too small to read, explicitly say so.

Required analysis steps (must all be reflected in the answer):
- Identify and describe every visible UI element, object, text block, icon, image, button, input field, menu, link, or control.
- Describe layout and structure, including alignment, grouping, spacing, and relative positioning of elements.
- Transcribe all readable text exactly as it appears, including headings, labels, buttons, navigation items, and small UI text.
- Describe colors, fonts (if distinguishable), contrast, and visual styling where visible.
- Describe images, illustrations, logos, and icons, including their position and appearance.
- Describe visible states such as selected items, active elements, disabled controls, hover states if shown, or error/success indicators.
- Note any repeated elements, patterns, or sections.
- If the image does not contain enough clearly visible information, explicitly state that no reliable description can be produced.

Website-specific analysis:
- If the image appears to be a website or web application, describe:
  - The overall page layout and sections
  - Navigation elements and their labels
  - Forms, inputs, and interactive controls visible
  - Any indicators of functionality only when directly supported by visible UI text or symbols
- If the purpose of the website is suggested by visible text or imagery, describe what is suggested and cite the exact visual evidence.
- If the purpose cannot be determined with certainty, state that explicitly.

Uncertainty handling:
- Clearly distinguish between what is fully visible, partially visible, and not visible.
- If the image does not contain enough information to determine a specific detail, say:
  I cannot determine this from the image.

Response style:
- Be exhaustive, precise, and factual.
- Do not summarize or shorten.
- Do not add interpretations or opinions.
- Do not repeat these instructions in the response.

""".strip()

def save_vision_response(
    image_path: str,
    response_text: str,
    output_dir: str = "vision_outputs",
) -> None:
    """
    Save vision model response to a text file.
    """
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(image_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.txt")

    with open(output_path, "a", encoding="utf-8") as f:
        # Separator between responses
        f.write("\n\n" + "=" * 80 + "\n")
        f.write("VISION MODEL RESPONSE\n")
        f.write("=" * 80 + "\n\n")
        f.write(response_text)
        f.write("\n")

    logger.info(f"[VisionService] Saved vision response to {output_path}")


# =====================================================
# OLLAMA VISION INFERENCE
# =====================================================

async def run_ollama_vision(image_path: str) -> str:
    image_b64 = image_to_base64(image_path)

    payload = {
        "model": settings.OLLAMA_MODEL,
        "stream": True,
        "messages": [
            {
                "role": "user",
                "content": build_prompt(),
                "images": [image_b64],
            }
        ],
        "options": {
            "temperature": 0.3,
            "top_p": 0.9,
            "num_predict": min(max_tokens, 2048),
        },
    }

    timeout = httpx.Timeout(
        connect=10.0,
        read=float(settings.OLLAMA_TIMEOUT),
        write=10.0,
        pool=10.0,
    )

    for attempt in range(2):
        try:
            async with VISION_SEMAPHORE:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream(
                        "POST",
                        f"{settings.OLLAMA_BASE_URL}/api/chat",
                        json=payload,
                    ) as response:

                        response.raise_for_status()
                        full_response = ""
                        raw_lines = []

                        async for line in response.aiter_lines():
                            if not line.strip():
                                continue

                            raw_lines.append(line)

                            try:
                                data = json.loads(line)

                            except json.JSONDecodeError:
                                logger.debug(f"Skipping non-JSON line: {line}")
                                continue

                            if "message" in data:
                                msg = data["message"]
                                if "content" in msg and msg["content"]:
                                    full_response += msg["content"]
                                elif "thinking" in msg and msg["thinking"]:
                                    full_response += msg["thinking"]
                                    logger.debug(f"[VisionService] Incremental thinking: {msg['thinking']}")

            full_response = full_response.strip()

            # DEBUG: log all raw lines
            # logger.info(f"[VisionService] Raw streamed lines from Ollama:\n" + "\n".join(raw_lines))
            logger.info(f"[VisionService] Combined model response:\n{full_response}")

            if not full_response:
                # Save image for debugging if response is empty
                debug_path = f"debug_images/{os.path.basename(image_path)}"
                os.makedirs(os.path.dirname(debug_path), exist_ok=True)
                shutil.copy(image_path, debug_path)
                logger.warning(f"Vision model returned empty response. Saved image to {debug_path}")
                raise RuntimeError("Empty response from vision model")

            save_vision_response(image_path, full_response)    

            if full_response[-1] not in ".!?":
                logger.warning("Vision model response may be truncated")

            return full_response

        except httpx.TimeoutException:
            logger.exception("Ollama vision request timed out")
            if attempt < 2:
                await asyncio.sleep(4 * (attempt + 1))
                continue
            raise RuntimeError("Vision model timeout")

        except httpx.HTTPStatusError:
            logger.exception("HTTP error from Ollama vision model")
            if attempt < 2:
                await asyncio.sleep(1)
                continue
            raise RuntimeError("Vision model communication error")

        except Exception as e:
            logger.exception("Unexpected vision inference failure")
            raise RuntimeError("Vision inference failed") from e


# =====================================================
# PUBLIC SERVICE API
# =====================================================

async def image_to_text(image_path: str) -> str:
    """
    High-level vision API used by:
    - crawl_service
    - vision_worker
    """
    logger.debug(f"Running vision analysis for {image_path}")
    return await run_ollama_vision(image_path)
