import logging
import json
import time
import os
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

OPENROUTER_MODEL = "google/gemma-4-26b-a4b-it"

def _get_openrouter_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        default_headers={
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "SimPPL Dashboard",
        }
    )

async def stream_response(query: str, context_results: list):
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    
    if not api_key:
        yield f"data: {json.dumps({'type': 'error', 'content': 'OPENROUTER_API_KEY not set or invalid in .env'})}\n\n"
        return

    try:
        client = _get_openrouter_client()
        
        system = (
            "You are a social media research analyst. Answer questions about Reddit data "
            "using ONLY the provided context. Be precise and cite specific authors, "
            "subreddits, or topics from the context when relevant."
        )
        
        context_str = "\n---CONTEXT---\n"
        for idx, r in enumerate(context_results):
            context_str += (
                f"[{idx+1}] Source: {r.get('source_type', 'unknown')}\n"
                f"Metadata: {json.dumps(r.get('metadata', {}))}\n"
                f"{r.get('text', '')}\n\n"
            )
            
        full_prompt = f"{context_str}\n---USER QUERY---\n{query}"
        
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": full_prompt}
        ]
        
        t0 = time.time()
        
        # 1. Main Streaming Call to OpenRouter
        response = await client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=messages,
            stream=True,
            temperature=0.3,
            max_tokens=600
        )
        
        full_answer = ""
        async for chunk in response:
            token = chunk.choices[0].delta.content or ""
            if token:
                full_answer += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        
        latency = time.time() - t0
        logger.info(f"Chat stream finished. Latency: {latency:.2f}s")
        
        # 2. Sequential Call for Suggestions (Non-streaming)
        suggestions = []
        try:
            sug_prompt = (
                f"Based on the query '{query}' and the analysis just performed:\n"
                f"{full_answer}\n"
                f"Suggest exactly 3 related research questions as a JSON array of strings. "
                f'Return ONLY the raw JSON array: ["Question 1", "Question 2", "Question 3"]'
            )
            
            sug_res = await client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[{"role": "user", "content": sug_prompt}],
                temperature=0.5,
                max_tokens=200
            )
            
            txt = sug_res.choices[0].message.content.strip()

            # Clean JSON formatting
            if txt.startswith("```json"):
                txt = txt[7:]
            if txt.startswith("```"):
                txt = txt[3:]
            if txt.endswith("```"):
                txt = txt[:-3]
            txt = txt.strip()

            start = txt.find("[")
            end = txt.rfind("]") + 1
            if start != -1 and end > start:
                txt = txt[start:end]

            parsed = json.loads(txt)
            suggestions = parsed if isinstance(parsed, list) else []

        except Exception as se:
            logger.error(f"Failed to generate suggestions: {se}")
            suggestions = []

        yield f"data: {json.dumps({'type': 'suggestions', 'content': suggestions})}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Error in stream_response: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': f'An error occurred: {str(e)}'})}\n\n"
