import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import re
import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

# CONSTANTS & PATHS
FAQ_FILE_PATH = "atmos_faq.txt"
DEFAULT_GROQ_KEY = os.environ.get("GROQ_API_KEY", "")

# Initialize FastAPI App
app = FastAPI(title="Atmos Support AI")

# Mount Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Static file mappings

# Load documents & corpus
def load_faq_documents(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    parts = content.split("### ")
    docs = []
    for part in parts:
        if not part.strip():
            continue
        lines = part.split("\n")
        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        
        doc = Document(
            page_content=f"Section: {title}\nContent:\n{body}",
            metadata={"source": "atmos_faq.txt", "section": title, "body": body}
        )
        docs.append(doc)
    return docs

faq_docs = load_faq_documents(FAQ_FILE_PATH)

# Local keyword search
def local_keyword_search(query, docs, k=2):
    query_clean = re.sub(r'[^\w\s]', '', query.lower())
    query_words = set(query_clean.split())
    if not query_words:
        return [(doc, 1.0) for doc in docs[:k]]
        
    results = []
    for doc in docs:
        content_clean = re.sub(r'[^\w\s]', '', doc.page_content.lower())
        content_words = content_clean.split()
        
        overlap = len(query_words.intersection(content_words))
        
        title_clean = re.sub(r'[^\w\s]', '', doc.metadata["section"].lower())
        title_words = title_clean.split()
        title_overlap = len(query_words.intersection(title_words))
        
        score = (overlap / len(query_words)) + (title_overlap * 0.5)
        results.append((doc, score))
        
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:k]

# Mock response generator
def generate_mock_response(query, chat_history, retrieved_docs):
    query_lower = query.lower()
    
    prev_country = None
    for msg in reversed(chat_history):
        if msg["role"] == "user":
            content = msg["content"].lower()
            if "india" in content:
                prev_country = "India"
                break
            elif "canada" in content:
                prev_country = "Canada"
                break
            elif "uk" in content or "united kingdom" in content:
                prev_country = "United Kingdom"
                break

    resolved_country = None
    # Check if the query is a continuation or brief follow-up
    continuation_keywords = {"how", "why", "what", "cost", "price", "rate", "there", "speed", "time", "days", "ship", "deliver"}
    is_continuation = any(w in query_lower for w in continuation_keywords) or len(query_lower.split()) <= 2
    
    if is_continuation:
        resolved_country = prev_country

    citations = []
    for doc, score in retrieved_docs:
        sec = doc.metadata["section"]
        citations.append({
            "section": sec,
            "content": doc.metadata["body"],
            "score": score
        })

    if "tier" in query_lower or "service" in query_lower:
        ans = (
            "Atmos offers three distinct customer service tiers [Service Tiers]:\n\n"
            "* **Basic Tier** (Free): Includes standard shipping and email-only support with a 24-48 business hour response time.\n"
            "* **Premium Tier** ($19.99/mo): Offers free 2-day shipping, 24/7 web chat support, and a priority response time under 4 hours.\n"
            "* **Enterprise Tier** (Custom starting at $499/mo): Provides free next-day delivery, 24/7/365 direct phone support, and dedicated support."
        )
    elif "india" in query_lower or resolved_country == "India":
        if "cost" in query_lower or "price" in query_lower or "rate" in query_lower or resolved_country:
            ans = "Shipping to **India** is a flat rate of **$25 USD** [Shipping Policies - International Shipping]. The estimated delivery time is **7 to 10 business days**. Import duties and taxes are collected at delivery."
        else:
            ans = "Yes, Atmos ships to **India** [Shipping Policies - International Shipping]. Delivery typically takes **7 to 10 business days** with a flat rate of **$25 USD**."
    elif "canada" in query_lower or resolved_country == "Canada":
        ans = "Atmos ships to **Canada** for a flat rate of **$15 USD** with a delivery timeline of **5 to 7 business days** [Shipping Policies - International Shipping]."
    elif "uk" in query_lower or "united kingdom" in query_lower or resolved_country == "United Kingdom":
        ans = "Shipping to the **United Kingdom (UK)** costs a flat rate of **$20 USD** and takes **6 to 8 business days** [Shipping Policies - International Shipping]."
    elif "hour" in query_lower or "time" in query_lower or "contact" in query_lower or "phone" in query_lower:
        ans = (
            "Here are the business hours and support contacts for Atmos [Business Hours & Contact Information]:\n\n"
            "* **General Office Hours**: Mon-Fri, 9:00 AM - 6:00 PM EST.\n"
            "* **Technical Support Chat**: Available 24/7/365.\n"
            "* **Phone Line**: Mon-Fri, 8:00 AM - 8:00 PM EST at **1-800-555-ATMOS**."
        )
    elif "return" in query_lower or "refund" in query_lower:
        ans = (
            "Here is the Atmos return policy [Return and Refund Processes]:\n\n"
            "* **Return Window**: 30 days from delivery.\n"
            "* **Condition**: Items must be in original, undamaged packaging.\n"
            "* **Fees**: Return shipping labels are **free** for Premium & Enterprise tiers, and cost a **$4.99 label fee** (deducted from refund) for the Basic tier.\n"
            "* **Refund Timeline**: 5 to 7 business days once received."
        )
    else:
        best_doc = retrieved_docs[0][0]
        sec = best_doc.metadata["section"]
        body = best_doc.metadata["body"]
        ans = (
            f"Based on our **{sec}** policies:\n\n"
            f"{body}\n\n"
            f"If you need further assistance, please reach out to customer support at 1-800-555-ATMOS."
        )
        
    # Only keep citations that are explicitly referenced in the response
    actual_citations = []
    ans_lower = ans.lower()
    for cit in citations:
        sec_name = cit["section"].lower()
        if f"[{sec_name}]" in ans_lower or sec_name in ans_lower:
            actual_citations.append(cit)
            
    return ans, actual_citations

# Custom Embeddings
class SimpleLocalEmbeddings(Embeddings):
    def __init__(self, vocabulary):
        self.vocabulary = list(vocabulary)
        self.dim = len(self.vocabulary)
        
    def _embed(self, text):
        vector = np.zeros(self.dim, dtype=np.float32)
        words = re.findall(r'\w+', text.lower())
        for w in words:
            if w in self.vocabulary:
                idx = self.vocabulary.index(w)
                vector[idx] += 1.0
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        return vector.tolist()

    def embed_documents(self, texts):
        return [self._embed(t) for t in texts]

    def embed_query(self, text):
        return self._embed(text)

# Lazy initialization of FAISS
vector_store = None
def get_vectorstore():
    global vector_store
    if vector_store is None:
        from langchain_community.vectorstores import FAISS
        all_text = " ".join([doc.page_content for doc in faq_docs])
        vocab = set(re.findall(r'\w+', all_text.lower()))
        embeddings = SimpleLocalEmbeddings(vocab)
        vector_store = FAISS.from_documents(faq_docs, embeddings)
    return vector_store

# RAG call
def get_live_response(api_key, query, chat_history):
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    
    vs = get_vectorstore()
    
    search_query = query
    if chat_history:
        history_str = ""
        # Skip the initial greeting message when building context
        history_msgs = chat_history[1:] if len(chat_history) > 1 else []
        for msg in history_msgs[-3:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_str += f"{role}: {msg['content']}\n"
            
        query_lower = query.lower()
        pronouns = {"it", "there", "they", "them", "those", "that", "this", "him", "her", "he", "she"}
        has_pronoun = any(f" {p} " in f" {query_lower} " or query_lower.startswith(f"{p} ") or query_lower.endswith(f" {p}") for p in pronouns)
        is_short = len(query.split()) <= 3
        
        if is_short or has_pronoun:
            rewrite_prompt = f"""Analyze the conversation history and the follow-up question. Rewrite the follow-up question as a standalone search query.
If the follow-up question is extremely brief (like "how", "why", "cost", "speed"), expand it fully using the context of what was just being discussed in the history.
Ensure any pronouns (like "there", "it") are replaced with the correct locations or subjects.

Conversation History:
{history_str}
Follow-up Question: {query}

Standalone search query (output ONLY the rewritten search query, no extra text):"""
            
            try:
                llm_rewriter = ChatOpenAI(
                    model="llama-3.1-8b-instant",
                    openai_api_key=api_key,
                    openai_api_base="https://api.groq.com/openai/v1",
                    temperature=0.0
                )
                search_query = llm_rewriter.invoke(rewrite_prompt).content.strip()
            except Exception:
                search_query = query
            
    retrieved_docs = vs.similarity_search(search_query, k=2)
    
    context_str = ""
    citations = []
    for doc in retrieved_docs:
        sec_title = doc.metadata.get("section", "General")
        context_str += f"\n--- {sec_title} ---\n{doc.page_content}\n"
        citations.append({
            "section": sec_title,
            "content": doc.metadata.get("body", doc.page_content),
            "score": 0.95
        })
        
    system_instruction = f"""You are a professional, helpful, and polite customer support agent for Atmos.
Atmos is a premium smart-home hardware and software provider.

Answer the user's question using ONLY the provided context sections. If the answer cannot be determined from the context, state that you do not have that information in your knowledge base and suggest they contact support at 1-800-555-ATMOS or via web chat. Do not make up or extrapolate facts.

Citations:
In your response, you MUST cite the section where the information was found (e.g. "[Service Tiers]" or "[Shipping Policies - International Shipping]"). Do this inline near the facts you are stating.

Provided Context Sections:
{context_str}
"""
    
    messages = [SystemMessage(content=system_instruction)]
    history_msgs = chat_history[1:] if len(chat_history) > 1 else []
    for msg in history_msgs:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
            
    messages.append(HumanMessage(content=query))
    
    llm = ChatOpenAI(
        model="llama-3.1-8b-instant",
        openai_api_key=api_key,
        openai_api_base="https://api.groq.com/openai/v1",
        temperature=0.2
    )
    
    response = llm.invoke(messages)
    
    # Only keep citations that are explicitly referenced in the response
    actual_citations = []
    response_text = response.content
    response_lower = response_text.lower()
    for cit in citations:
        sec_name = cit["section"].lower()
        if f"[{sec_name}]" in response_lower or sec_name in response_lower:
            actual_citations.append(cit)
            
    return response_text, actual_citations


# Simple Memory state
session_history = [
    {
        "role": "assistant",
        "content": "Hello! Welcome to Atmos Support. I am your virtual customer service assistant. How can I help you today?\n\nYou can click on any of the common topics above, or type your question below. I can answer questions about shipping rates, service tiers, business hours, and return processes.",
        "citations": []
    }
]

# API Schemas
class ChatQuery(BaseModel):
    message: str

# ROUTES
@app.get("/", response_class=FileResponse)
async def get_index():
    return FileResponse("templates/index.html")

@app.post("/chat")
async def chat_endpoint(query: ChatQuery):
    global session_history
    user_msg = query.message
    
    # Append user question to history
    session_history.append({"role": "user", "content": user_msg})
    
    # Process
    try:
        # Check if greeting
        query_clean = re.sub(r'[^\w\s]', '', user_msg.strip().lower())
        greetings = {"hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening", "yo"}
        
        if query_clean in greetings:
            ans = "Hello! I am your Atmos support assistant. How can I help you today? I can answer questions about our service tiers, shipping policies, returns, and business hours."
            citations = []
        else:
            if DEFAULT_GROQ_KEY:
                try:
                    ans, citations = get_live_response(DEFAULT_GROQ_KEY, user_msg, session_history[:-1])
                except Exception as live_err:
                    retrieved = local_keyword_search(user_msg, faq_docs, k=2)
                    ans, citations = generate_mock_response(user_msg, session_history[:-1], retrieved)
                    ans += "\n\n*(Note: Running in offline fallback mode.)*"
            else:
                retrieved = local_keyword_search(user_msg, faq_docs, k=2)
                ans, citations = generate_mock_response(user_msg, session_history[:-1], retrieved)
    except Exception as e:
        ans = f"Error processing message: {str(e)}"
        citations = []
        
    # Append assistant reply to history
    session_history.append({"role": "assistant", "content": ans, "citations": citations})
    return JSONResponse({"answer": ans, "citations": citations})

@app.post("/clear")
async def clear_endpoint():
    global session_history
    session_history = [
        {
            "role": "assistant",
            "content": "Hello! Welcome to Atmos Support. I am your virtual customer service assistant. How can I help you today?\n\nYou can click on any of the common topics above, or type your question below. I can answer questions about shipping rates, service tiers, business hours, and return processes.",
            "citations": []
        }
    ]
    return JSONResponse({"status": "cleared"})

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8501))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
