import logging
import json
import time
import google.generativeai as genai
from config import get_gemini_api_key, mark_gemini_key_exhausted, increment_gemini_key_usage

logger = logging.getLogger(__name__)

async def stream_response(query: str, context_results: list):
    api_key = get_gemini_api_key()
    
    if not api_key:
        yield f"data: {json.dumps({'type': 'error', 'content': 'GEMINI_API_KEY not set or all keys exhausted'})}\n\n"
        return

    try:
        genai.configure(api_key=api_key)
        
        system = (
            "You are a social media research analyst. Answer questions about Reddit data "
            "using ONLY the provided context. Be precise and cite specific authors, "
            "subreddits, or topics from the context when relevant."
        )
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system
        )
        
        context_str = "\n---CONTEXT---\n"
        for idx, r in enumerate(context_results):
            context_str += (
                f"[{idx+1}] Source: {r['source_type']}\n"
                f"Metadata: {json.dumps(r['metadata'])}\n"
                f"{r['text']}\n\n"
            )
            
        full_prompt = f"{context_str}\n---USER QUERY---\n{query}"
        
        t0 = time.time()
        increment_gemini_key_usage(api_key)
        
        response = await model.generate_content_async(
            full_prompt,
            stream=True,
            generation_config=genai.types.GenerationConfig(temperature=0.3)
        )
        
        full_answer = ""
        async for chunk in response:
            token = chunk.text
            if token:
                full_answer += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        
        latency = time.time() - t0
        logger.info(f"Chat stream finished. Latency: {latency:.2f}s")
        
        # --- Suggestions call ---
        suggestions = []
        try:
            api_key_sug = get_gemini_api_key()
            if not api_key_sug:
                raise ValueError("No API key available for suggestions")

            genai.configure(api_key=api_key_sug)
            sug_model = genai.GenerativeModel("gemini-2.5-flash")
            increment_gemini_key_usage(api_key_sug)

            sug_prompt = (
                f"Based on the query '{query}' and the analysis just performed:\n"
                f"{full_answer}\n"
                f"Suggest exactly 3 related research questions as a JSON array of strings. "
                f'Return ONLY the raw JSON array: ["Question 1", "Question 2", "Question 3"]'
            )

            sug_res = await sug_model.generate_content_async(
                sug_prompt,
                generation_config=genai.types.GenerationConfig(temperature=0.5)
            )
            
            txt = sug_res.text.strip()

            # Strip markdown fences if present
            if txt.startswith("```json"):
                txt = txt[7:]
            if txt.startswith("```"):
                txt = txt[3:]
            if txt.endswith("```"):
                txt = txt[:-3]
            txt = txt.strip()

            # Extract just the JSON array
            start = txt.find("[")
            end = txt.rfind("]") + 1
            if start != -1 and end > start:
                txt = txt[start:end]

            parsed = json.loads(txt)
            # FIX: was "if not list: [] else: []" — both branches cleared suggestions!
            suggestions = parsed if isinstance(parsed, list) else []

        except Exception as se:
            err_str = str(se)
            if (
                "GenerateRequestsPerDay" in err_str
                or ("429" in err_str and "limit: 20" in err_str)
                or "Quota exceeded" in err_str
            ):
                if 'api_key_sug' in locals() and api_key_sug:
                    mark_gemini_key_exhausted(api_key_sug)
            logger.error(f"Failed to generate suggestions: {se}")
            suggestions = []

        yield f"data: {json.dumps({'type': 'suggestions', 'content': suggestions})}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        err_str = str(e)
        if (
            "GenerateRequestsPerDay" in err_str
            or ("429" in err_str and "limit: 20" in err_str)
            or "Quota exceeded" in err_str
        ):
            mark_gemini_key_exhausted(api_key)
        logger.error(f"Error in stream_response: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': 'An error occurred during response generation.'})}\n\n"
# ══════════════════════════════════════════════════════════════════════════════
# NEW: LangGraph-powered chatbot using HuggingFace Inference API (free models)
# Architecture: synthesize_node → suggest_node
#   - synthesize_node streams tokens from HF model token-by-token
#   - suggest_node generates 3 follow-up research questions
#   - Both nodes write custom events picked up by LangGraph's stream_mode="custom"
#   - stream_response() yields each event as an SSE chunk (same interface as before)
# ══════════════════════════════════════════════════════════════════════════════

# import logging
# import os
# import json
# import time
# from typing import TypedDict
# import asyncio

# from langgraph.graph import StateGraph, END
# from openai import AsyncOpenAI

# logger = logging.getLogger(__name__)

# # Global registry for cross-node async streaming free of contextvar bugs
# _chat_queues = {}

# # OpenRouter model
# OPENROUTER_MODEL = "google/gemma-4-26b-a4b-it"


# # ── State ─────────────────────────────────────────────────────────────────────

# class ChatState(TypedDict):
#     run_id: str           # Unique identifier to map to _chat_queues
#     query: str
#     context_results: list
#     answer: str           # populated by synthesize_node
#     suggestions: list     # populated by suggest_node


# # ── Helpers ───────────────────────────────────────────────────────────────────

# def _build_context_str(context_results: list) -> str:
#     """Format retrieved ChromaDB chunks into a numbered context block."""
#     ctx = "\n---CONTEXT---\n"
#     for idx, r in enumerate(context_results):
#         ctx += (
#             f"[{idx+1}] Source: {r['source_type']}\n"
#             f"Metadata: {json.dumps(r['metadata'])}\n"
#             f"{r['text']}\n\n"
#         )
#     return ctx


# def _get_openrouter_client() -> AsyncOpenAI:
#     return AsyncOpenAI(
#         base_url="https://openrouter.ai/api/v1",
#         api_key=os.environ.get("OPENROUTER_API_KEY", ""),
#         default_headers={
#             "HTTP-Referer": "http://localhost:3000",
#             "X-Title": "SimPPL Dashboard",
#         }
#     )


# # ── Node 1: Synthesize ────────────────────────────────────────────────────────

# async def synthesize_node(state: ChatState) -> dict:
#     """
#     Calls the OpenRouter API (streaming) and puts each token onto
#     the native asyncio.Queue mapped to this run_id for flawless SSE streaming.
#     """
#     client = _get_openrouter_client()
#     q = _chat_queues.get(state["run_id"])

#     context_str = _build_context_str(state["context_results"])
#     system_msg = (
#         "You are a social media research analyst. "
#         "Answer questions about Reddit data using ONLY the provided context. "
#         "Be precise and cite specific authors, subreddits, or topics from the context when relevant."
#     )
#     full_prompt = f"{system_msg}\n{context_str}\n---USER QUERY---\n{state['query']}"
#     messages = [{"role": "user", "content": full_prompt}]

#     full_answer = ""
#     t0 = time.time()

#     try:
#         stream = await client.chat.completions.create(
#             model=OPENROUTER_MODEL,
#             messages=messages,
#             stream=True,
#             max_tokens=600,
#             temperature=0.3,
#         )
#         async for chunk in stream:
#             token = chunk.choices[0].delta.content or ""
#             if token and q:
#                 full_answer += token
#                 await q.put({"type": "token", "content": token})

#         latency = time.time() - t0
#         logger.info(f"[LangGraph] synthesize_node done. Latency: {latency:.2f}s")
#     except Exception as e:
#         logger.error(f"[LangGraph] synthesize_node error: {e}")
#         if q:
#             await q.put({"type": "error", "content": f"LLM error: {str(e)}"})

#     return {"answer": full_answer}


# # ── Node 2: Suggest ───────────────────────────────────────────────────────────

# async def suggest_node(state: ChatState) -> dict:
#     """
#     Makes a single non-streaming call to generate 3 follow-up research questions.
#     Puts the result onto the asyncio.Queue.
#     """
#     client = _get_openrouter_client()
#     q = _chat_queues.get(state["run_id"])

#     sug_prompt = (
#         f"Based on this query: '{state['query']}'\n"
#         f"And this analysis:\n{state['answer']}\n\n"
#         f"Suggest exactly 3 related research questions as a JSON array of strings. "
#         f"Return ONLY the raw JSON array — no explanation, no markdown:\n"
#         f'["Question 1", "Question 2", "Question 3"]'
#     )
#     messages = [{"role": "user", "content": sug_prompt}]

#     suggestions = []
#     try:
#         res = await client.chat.completions.create(
#             model=OPENROUTER_MODEL,
#             messages=messages,
#             max_tokens=200,
#             temperature=0.5,
#         )
#         txt = res.choices[0].message.content.strip()

#         # Strip markdown code fences if the model added them
#         if txt.startswith("```json"): txt = txt[7:]
#         if txt.startswith("```"):     txt = txt[3:]
#         if txt.endswith("```"):       txt = txt[:-3]
#         txt = txt.strip()

#         # Extract just the JSON array portion
#         start = txt.find("[")
#         end   = txt.rfind("]") + 1
#         if start != -1 and end > start:
#             txt = txt[start:end]

#         suggestions = json.loads(txt)
#         if not isinstance(suggestions, list):
#             suggestions = []
#     except Exception as se:
#         logger.error(f"[LangGraph] suggest_node failed: {se}")
#         suggestions = []

#     # Emit suggestions to the queue
#     if q:
#         await q.put({"type": "suggestions", "content": suggestions})
#     return {"suggestions": suggestions}


# # ── Graph Assembly ────────────────────────────────────────────────────────────

# def _build_chat_graph():
#     graph = StateGraph(ChatState)
#     graph.add_node("synthesize", synthesize_node)
#     graph.add_node("suggest",    suggest_node)
#     graph.set_entry_point("synthesize")
#     graph.add_edge("synthesize", "suggest")
#     graph.add_edge("suggest",    END)
#     return graph.compile()

# # Lazily compiled once per process lifetime
# _chat_graph = None

# def _get_chat_graph():
#     global _chat_graph
#     if _chat_graph is None:
#         _chat_graph = _build_chat_graph()
#     return _chat_graph


# # ── Public Interface ────────────────────────────────────────────────────────────

# import uuid

# async def stream_response(query: str, context_results: list):
#     """
#     LangGraph-powered SSE streamer.

#     Uses an asyncio.Queue injected into a global registry so streaming is immune
#     to contextvar loss inside HTTP client async generators.
#     """
#     run_id = uuid.uuid4().hex
#     q = asyncio.Queue()
#     _chat_queues[run_id] = q

#     try:
#         api_key = os.environ.get("OPENROUTER_API_KEY", "")
#         if not api_key:
#             yield f"data: {json.dumps({'type': 'error', 'content': 'OPENROUTER_API_KEY not set. Add it to .env'})}\n\n"
#             return

#         graph = _get_chat_graph()
#         initial_state: ChatState = {
#             "run_id":          run_id,
#             "query":           query,
#             "context_results": context_results,
#             "answer":          "",
#             "suggestions":     [],
#         }

#         # Run the graph entirely in a background task
#         task = asyncio.create_task(graph.ainvoke(initial_state))

#         # Continuously monitor the queue for chunks and yield them natively
#         while True:
#             # We wait either for the queue to have an item, or for the task to finish
#             done, pending = await asyncio.wait(
#                 [task, asyncio.create_task(q.get())],
#                 return_when=asyncio.FIRST_COMPLETED
#             )

#             for d in done:
#                 res = d.result()
#                 if isinstance(res, dict) and "type" in res:
#                     # Item pulled from queue -> yield it to the frontend!
#                     yield f"data: {json.dumps(res)}" + "\n\n"

#             # Check if all events pushed AND task is complete
#             if q.empty() and task.done():
#                 if task.exception():
#                     err = task.exception()
#                     logger.error(f"Graph execution failed: {err}")
#                     yield f"data: {json.dumps({'type': 'error', 'content': 'Graph internal error'})}\n\n"
#                 break

#         yield "data: [DONE]\n\n"

#     except Exception as e:
#         logger.error(f"[LangGraph] stream_response error: {e}")
#         yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
#     finally:
#         # Cleanup memory
#         _chat_queues.pop(run_id, None)
