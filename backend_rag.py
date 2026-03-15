"""
Production RAG Chatbot Backend with Cohere + Qdrant + Gemini for HF Spaces
Docker-ready with Gradio UI on port 7860 + FastAPI API on 8000
Local chapters-only loading for HF compatibility
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import os
import re
from dotenv import load_dotenv
import threading
import time

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Robotics Textbook RAG API - HF Spaces Ready")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5

class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    confidence: float

# Initialize API clients
class RAGSystem:
    def __init__(self):
        self.cohere_api_key = os.getenv('COHERE_API_KEY')
        self.qdrant_url = os.getenv('QDRANT_URL')
        self.qdrant_api_key = os.getenv('QDRANT_API_KEY')
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        
        self.documents = {}
        self.chunks = []
        
        # Initialize Qdrant client if credentials available
        self.qdrant_client = None
        if self.qdrant_url and self.qdrant_api_key:
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.http import models
                self.qdrant_client = QdrantClient(
                    url=self.qdrant_url,
                    api_key=self.qdrant_api_key
                )
                print("[OK] Qdrant client initialized")
            except Exception as e:
                print(f"[WARN] Qdrant initialization failed: {e}")
        
        # Load documents - HF Spaces: ONLY chapters/
        self._load_chapters_content()
    
    def _load_chapters_content(self):
        """Load ONLY chapters/*.md files - HF Spaces safe"""
        chapters_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chapters")
        
        if not os.path.exists(chapters_dir):
            print(f"[WARN] Chapters dir not found: {chapters_dir}")
            return
        
        files_loaded = 0
        total_chars = 0
        
        # Explicitly load known chapters (avoid os.walk for HF safety)
        chapter_files = [
            "01-introduction-to-physical-ai.md",
            "02-robotics-fundamentals.md", 
            "03-humanoid-design-principles.md"
        ]
        
        for filename in chapter_files:
            filepath = os.path.join(chapters_dir, filename)
            rel_path = f"chapters/{filename}"
            
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    self.documents[rel_path] = content
                    files_loaded += 1
                    total_chars += len(content)
                    
                    # Create chunks
                    self._create_chunks(content, rel_path)
                    
                except Exception as e:
                    print(f"[WARN] Failed to load {filepath}: {e}")
            else:
                print(f"[WARN] Chapter not found: {filepath}")
        
        print(f"[OK] Loaded {files_loaded} chapters ({total_chars:,} chars), {len(self.chunks)} chunks")
    
    def _create_chunks(self, content: str, source: str, chunk_size: int = 500):
        """Create smart chunks based on headings"""
        heading_pattern = r'^(#{1,3})\s+(.+)$'
        lines = content.split('\n')
        
        current_section = []
        current_heading = "Content"
        
        for line in lines:
            match = re.match(heading_pattern, line, re.MULTILINE)
            if match:
                # Save previous section
                if current_section:
                    section_text = '\n'.join(current_section).strip()
                    if len(section_text) > 50:
                        self.chunks.append({
                            "content": section_text,
                            "source": source,
                            "section": current_heading,
                            "title": self._extract_title(source)
                        })
                
                current_heading = match.group(2)
                current_section = [line]
            else:
                current_section.append(line)
        
        # Last section
        if current_section:
            section_text = '\n'.join(current_section).strip()
            if len(section_text) > 50:
                self.chunks.append({
                    "content": section_text,
                    "source": source,
                    "section": current_heading,
                    "title": self._extract_title(source)
                })
    
    def _extract_title(self, source: str):
        """Extract title from file path"""
        filename = os.path.basename(source).replace('.md', '')
        return filename.replace('-', ' ').replace('_', ' ').title()
    
    def _keyword_search(self, query: str, top_k: int = 5):
        """Enhanced keyword search with scoring - prioritizes chapter content"""
        query_words = query.lower().split()
        query_phrases = [query.lower()]
        
        if len(query_words) > 1:
            for i in range(len(query_words) - 1):
                query_phrases.append(f"{query_words[i]} {query_words[i+1]}")
        
        results = []
        
        for chunk in self.chunks:
            content_lower = chunk["content"].lower()
            section_lower = chunk.get("section", "").lower()
            title_lower = chunk.get("title", "").lower()
            source_lower = chunk.get("source", "").lower()
            score = 0
            
            # Chapter bonus (all are chapters)
            chapter_bonus = 100
            
            # Topic bonuses
            topic_bonus = 0
            if any(w in query_words for w in ['sensor', 'perception']) or '02' in source_lower:
                topic_bonus += 50
            if any(w in ['humanoid', 'balance', 'locomotion']) or '03' in source_lower:
                topic_bonus += 50
            if any(w in ['physical ai', 'embodied']) or '01' in source_lower:
                topic_bonus += 50
            
            for phrase in query_phrases:
                if phrase in content_lower:
                    score += 20
                if phrase in section_lower:
                    score += 30
                if phrase in title_lower:
                    score += 40
            
            for word in query_words:
                if len(word) < 3:
                    continue
                word_count = content_lower.count(word)
                if word_count > 0:
                    score += word_count * 3
                if word in section_lower:
                    score += 10
                if word in title_lower:
                    score += 15
            
            content_words_set = set(w for w in content_lower.split() if len(w) >= 3)
            matched_words = sum(1 for word in query_words if len(word) >= 3 and word in content_words_set)
            if matched_words >= 2:
                score += matched_words * 5
            
            score += chapter_bonus + topic_bonus
            
            if score > 0:
                results.append({**chunk, "score": score})
        
        results.sort(key=lambda x: x["score"], reverse=True)
        final_results = []
        for r in results[:top_k]:
            del r['score']
            final_results.append(r)
        
        return final_results
    
    def search(self, query: str, top_k: int = 5):
        """Search using Qdrant or keyword fallback"""
        if self.qdrant_client and self.cohere_api_key:
            try:
                import requests
                cohere_response = requests.post(
                    "https://api.cohere.ai/v1/embed",
                    headers={"Authorization": f"Bearer {self.cohere_api_key}", "Content-Type": "application/json"},
                    json={"texts": [query], "model": "embed-english-v3.0", "input_type": "search_query"}
                )
                
                if cohere_response.status_code == 200:
                    embedding = cohere_response.json()["embeddings"][0]
                    
                    from qdrant_client.http import models
                    search_result = self.qdrant_client.search(
                        collection_name="book_content",
                        query_vector=embedding,
                        limit=top_k,
                        with_payload=True
                    )
                    
                    if search_result:
                        return [{"content": r.payload.get("content", ""), "source": r.payload.get("source", ""), 
                                "section": r.payload.get("section", ""), "title": r.payload.get("title", ""), "score": r.score} 
                                for r in search_result]
            except Exception as e:
                print(f"[HF] Qdrant search failed: {e}")
        
        return self._keyword_search(query, top_k)
    
    def generate_answer(self, query: str, context: str):
        """Generate using Gemini or fallback"""
        if self.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                
                query_length = len(query.split())
                if query_length <= 3:
                    length_instruction = "concise (2-3 paragraphs)."
                elif query_length <= 6:
                    length_instruction = "moderate (3-4 paragraphs)."
                else:
                    length_instruction = "comprehensive (4-5 paragraphs)."
                
                full_prompt = f"""Friendly AI tutor for Physical AI/Robotics textbook. Natural conversational style.

TEXTBOOK: {context}

Q: {query}

RULES:
- Conversational tone like human tutor
- NO markdown headings or 'Based on textbook'
- Explain in own words
- {length_instruction}
- Simple examples, no repetition
- Friendly/educational

Response:"""
                
                response = model.generate_content(full_prompt)
                answer = response.text.strip()
                # Clean headings
                answer = re.sub(r'#{1,3}\s+', '', answer)
                return answer
            except Exception as e:
                print(f"[HF] Gemini failed: {e}")
        
        return self._generate_fallback_answer(query, context)
    
    def _generate_fallback_answer(self, query: str, context: str):
        sections = re.split(r'###\s+', context)
        relevant = []
        for sec in sections:
            lines = [l for l in sec.split('\n') if not l.strip().startswith('(') and not 'details' in l.lower()]
            clean = '\n'.join(lines).strip()
            if clean:
                relevant.append(clean[:400] + "..." if len(clean) > 400 else clean)
        
        if not relevant:
            return "No matching textbook info. Ask about Physical AI, robotics fundamentals, or humanoid design!"
        
        query_len = len(query.split())
        if query_len <= 3:
            intro = "Good question! "
        else:
            intro = "Great question! From the textbook: "
        
        body = '\n\n'.join(relevant[:2])
        body = re.sub(r'\n{3,}', '\n\n', body)
        return intro + body

# Global RAG system
print("=" * 70)
print("🤖 Robotics Textbook RAG - HF Spaces Ready")
print("=" * 70)
rag_system = RAGSystem()

@app.get("/")
def root():
    return {"message": "HF Spaces RAG API", "status": "running", "docs": "/docs", "ui": "http://localhost:7860", 
            "chapters": len(rag_system.documents), "chunks": len(rag_system.chunks)}

@app.get("/health")
def health():
    return {"status": "healthy", "chapters": len(rag_system.documents), "chunks": len(rag_system.chunks),
            "qdrant": rag_system.qdrant_client is not None, "gemini": bool(rag_system.gemini_api_key),
            "cohere": bool(rag_system.cohere_api_key)}

@app.post("/query", response_model=QueryResponse)
def query_endpoint(request: QueryRequest):
    try:
        results = rag_system.search(request.query, request.top_k)
        if not results:
            return QueryResponse(answer="No info found. Try robotics, humanoids, Physical AI!", sources=[], confidence=0.0)
        
        context_parts = []
        sources = []
        for r in results:
            section_info = f"### {r.get('section', 'Content')} ({r.get('title', 'Unknown')})\n{r['content'][:600]}..."
            context_parts.append(section_info)
            if r["source"] not in sources:
                sources.append(r["source"])
        
        context = "\n\n".join(context_parts)
        answer = rag_system.generate_answer(request.query, context)
        confidence = min(0.5 + (results[0].get("score", 0) * 0.02), 0.95)
        
        return QueryResponse(answer=answer, sources=sources[:5], confidence=confidence)
    except Exception as e:
        raise HTTPException(500, str(e))

# Gradio UI for HF Spaces (port 7860)
def create_gradio_ui():
    try:
        import gradio as gr
        import requests
        import json
        
        def chat_fn(message, history):
            response = requests.post("http://127.0.0.1:8000/query", 
                                   json={"query": message, "top_k": 3},
                                   headers={"Content-Type": "application/json"})
            if response.status_code == 200:
                data = response.json()
                return data["answer"]
            return "API error - check logs."
        
        iface = gr.ChatInterface(
            chat_fn,
            title="🤖 Robotics Textbook RAG Chatbot",
            description="Ask about Physical AI, Robotics Fundamentals, Humanoid Design. Supports local keyword search + optional Gemini/Cohere/Qdrant.",
            theme=gr.themes.Soft()
        )
        
        print("[HF] Starting Gradio UI on http://0.0.0.0:7860")
        iface.launch(server_name="0.0.0.0", server_port=7860, share=False)
    except Exception as e:
        print(f"[HF] Gradio failed: {e}")

if __name__ == "__main__":
    import uvicorn
    
    print("[HF] FastAPI on 8000, Gradio on 7860")
    print("Set Secrets: GEMINI_API_KEY (opt), COHERE_API_KEY (opt), QDRANT_* (opt)")
    
    # Start Gradio in background thread
    gradio_thread = threading.Thread(target=create_gradio_ui, daemon=True)
    gradio_thread.start()
    
    # Give Gradio time to start
    time.sleep(2)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)

