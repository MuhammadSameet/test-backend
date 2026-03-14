---
title: 🤖 Robotics Textbook RAG Chatbot
emoji: 🚀
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
---

# Physical AI & Humanoid Robotics RAG Chatbot

Interactive RAG chatbot powered by **3 textbook chapters** on Physical AI, Robotics Fundamentals, and Humanoid Design Principles.

## ✨ Features
- **Gradio Chat UI** (`http://localhost:7860`): Ask questions naturally
- **FastAPI API** (`http://localhost:8000`): `/query`, `/health`, `/docs`
- **Local-First**: Keyword search on 1000+ chunks (no APIs needed)
- **Optional Upgrades**: Gemini/Cohere generation, Qdrant vectors
- **Docker-Optimized**: Multi-stage, secure, healthchecked

## 📚 Loaded Content
- `01-introduction-to-physical-ai.md`
- `02-robotics-fundamentals.md` 
- `03-humanoid-design-principles.md`

**Example Queries**:
- "What is Physical AI stack?"
- "Explain ZMP balance control"
- "Humanoid arm DoF requirements?"

## 🚀 HF Spaces Deployment

### 1. Push to HF
```
git init && git add . && git commit -m "HF ready"
huggingface-cli repo create your-space-name --yes
git remote add origin https://huggingface.co/spaces/YOUR_USERNAME/your-space-name
git push -u origin main
```

### 2. Set Secrets (Settings > Secrets)
| Key | Value | Required? |
|-----|-------|-----------|
| `GEMINI_API_KEY` | `AIza...` (Google AI Studio) | Optional (uses local fallback) |
| `COHERE_API_KEY` | `xco...` (cohere.ai) | Optional (for embeddings) |
| `QDRANT_URL` | `https://...qdrant.io` | Optional (cloud Qdrant) |
| `QDRANT_API_KEY` | `...` | Optional |

### 3. Space Config
- SDK: **Docker** (auto-detected)
- Port: **7860** (Gradio)
- Hardware: CPU Basic (or A10G for faster)

**Space will auto-build and launch!** ~2-5 min.

## 🧪 Local Testing
```bash
# From d:/backend-docker/backend/
docker build -t rag-hf .
docker run -p 7860:7860 -p 8000:8000 --name rag-test rag-hf
```
- UI: http://localhost:7860
- API: http://localhost:8000/docs
- Health: http://localhost:8000/health

## 🔧 API Usage
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is ZMP?", "top_k": 3}' \
  | jq
```

## 📈 Architecture
```
Chapters (.md) → Chunking → Keyword Search (local)
              ↓ (opt)
Qdrant Embed → Cohere → Gemini Answer
```

## 🛠 Built With
- FastAPI + Gradio + Docker
- Python 3.11-slim (secure, optimized)
- Local RAG (no vendor lock-in)

## 🙌 Credits
RAG system by BLACKBOXAI • Textbook chapters included

**Ready for production HF Spaces!** 🎉

