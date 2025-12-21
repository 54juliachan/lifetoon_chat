import os
import json
import time
import numpy as np
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, auth, firestore
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --- 基礎設定 ---
app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 初始化 Firebase ---
if not firebase_admin._apps:
    service_account_info = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if service_account_info:
        try:
            cred = credentials.Certificate(json.loads(service_account_info))
            firebase_admin.initialize_app(cred)
        except Exception as e:
            print(f"Firebase Init Error: {e}")
    else:
        print("Warning: FIREBASE_SERVICE_ACCOUNT_JSON not set.")

db = firestore.client()

# --- 初始化 Gemini ---
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# --- RAG 檔案處理邏輯 ---
def load_and_process_rag_data(file_name="my_data.txt"):
    """讀取 .txt 檔案並切分為小區塊"""
    # 修正路徑處理，確保在不同環境下都能讀到 api 資料夾內的檔案
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, file_name)
    
    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found. RAG disabled.")
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # 增加 log 確認讀取到內容
        print(f"成功讀取檔案: {file_name}, 長度: {len(text)} 字")
        
        # 每 500 字切一塊，重疊 50 字保持上下文連貫
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = splitter.split_text(text)
        print(f"檔案切分完成，共 {len(chunks)} 個區塊")
        return chunks
    except Exception as e:
        print(f"File Loading Error: {e}")
        return []

# 在啟動時載入資料
CHUNKS = load_and_process_rag_data("my_data.txt")

def get_relevant_context(user_query, chunks, top_k=2):
    """檢索與問題最相關的文字片段"""
    if not chunks:
        return ""
    
    try:
        # 1. 將問題向量化
        query_embedding = genai.embed_content(
            model="models/text-embedding-004",
            content=user_query,
            task_type="retrieval_query"
        )["embedding"]

        # 2. 將所有區塊向量化 (修正點：處理列表格式)
        embedding_response = genai.embed_content(
            model="models/text-embedding-004",
            content=chunks,
            task_type="retrieval_document"
        )
        chunk_embeddings = embedding_response["embeddings"]

        # 3. 計算相似度 (內積)
        scores = np.dot(chunk_embeddings, query_embedding)
        # 取得最相關的索引
        top_indices = np.argsort(scores)[-top_k:][::-1]
        
        relevant_text = "\n\n".join([chunks[i] for i in top_indices])
        print(f"RAG 檢索成功，找到相關片段長度: {len(relevant_text)}")
        return relevant_text
    except Exception as e:
        # 這裡會印出具體的 Embedding 錯誤到 Log
        print(f"RAG Retrieval Error: {e}")
        return ""

# --- AI 角色與指令 ---
BASE_SYSTEM_PROMPT = "你是一個溫柔親切的朋友，會主動關懷聊天對象、並適時提供建議，以繁體中文進行對話，每則訊息不超過100字。"

# --- 資料模型 ---
class ChatRequest(BaseModel):
    message: str

class WelcomeRequest(BaseModel):
    local_time: str

# --- 路由實作 ---

@app.get("/")
async def read_root():
    return RedirectResponse(url="/index.html")

@app.post("/api/chat")
async def chat(request: ChatRequest, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")

    token = authorization.split("Bearer ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
    except Exception:
        uid = "test_user"

    # 1. 檢索 RAG 背景知識
    context = get_relevant_context(request.message, CHUNKS)
    
    # 2. 動態生成系統指令 (增強引導 AI 使用背景資料)
    dynamic_system_prompt = BASE_SYSTEM_PROMPT
    if context:
        dynamic_system_prompt += (
            f"\n\n【重要背景資料】：\n---\n{context}\n---\n"
            "如果使用者的問題與上方資料相關，請務必參考該資料回答。"
        )

    # 3. 準備歷史紀錄
    gemini_history = []
    msgs_ref = db.collection('users').document(uid).collection('messages')
    recent_docs = msgs_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10).stream()
    history_data = sorted([d.to_dict() for d in recent_docs], key=lambda x: x['timestamp'])
    
    for msg in history_data:
        role = "user" if msg['sender'] == "user" else "model"
        gemini_history.append({"role": role, "parts": [msg['content']]})

    if gemini_history and gemini_history[0]["role"] == "model":
        gemini_history.insert(0, {"role": "user", "parts": ["你好"]})

    # 4. 呼叫 Gemini 2.5 Flash
    try:
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=dynamic_system_prompt)
        chat_session = model.start_chat(history=gemini_history)
        response = chat_session.send_message(request.message)
        ai_reply_text = response.text
        
        # 5. 存入 Firestore
        now = time.time()
        batch = db.batch()
        batch.set(msgs_ref.document(), {"content": request.message, "sender": "user", "timestamp": now})
        batch.set(msgs_ref.document(), {"content": ai_reply_text, "sender": "ai", "timestamp": now + 0.1})
        batch.commit()

        return {"message": {"content": ai_reply_text}}
    except Exception as e:
        print(f"Gemini API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "rag_chunks": len(CHUNKS)}