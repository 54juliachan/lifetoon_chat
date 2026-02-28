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

db = firestore.client()

# --- 初始化 Gemini ---
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# --- RAG 檔案處理邏輯 ---
def load_and_process_rag_data(file_name="my_data.txt"):
    file_path = os.path.join(os.path.dirname(__file__), file_name)
    if not os.path.exists(file_path): 
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    return splitter.split_text(text)

CHUNKS = load_and_process_rag_data("my_data.txt")

def get_relevant_context(user_query, chunks, top_k=3):
    if not chunks: return ""
    try:
        query_embedding = genai.embed_content(model="models/text-embedding-004", content=user_query, task_type="retrieval_query")["embedding"]
        chunk_embeddings = genai.embed_content(model="models/text-embedding-004", content=chunks, task_type="retrieval_document")["embeddings"]
        scores = np.dot(chunk_embeddings, query_embedding)
        top_indices = np.argsort(scores)[-top_k:][::-1]
        return "\n\n".join([chunks[i] for i in top_indices])
    except: return ""

BASE_SYSTEM_PROMPT = """你是一位溫和、具同理心的傾聽者。
你的目標是透過自然的對話，引導使用者分享生活中的經歷與內在感受。
行為指南：
- 傾聽勝於表達：回應時先確認使用者的情緒，展現理解。
- 鼓勵探索：若使用者提到一個事件，請鼓勵他們描述細節或當下的心情。
- 保持中立：不評判、不預設立場，避免給予說教式的建議。
- 節奏控制：一次只問一個問題，讓對話保持像朋友般流暢的節奏。
- 若使用者陷入負面情緒，請先給予溫暖的回應，再轉向開放式的引導。"""

class ChatRequest(BaseModel):
    message: str

class WelcomeRequest(BaseModel):
    local_time: str

@app.get("/")
async def read_root():
    return RedirectResponse(url="/index.html")

@app.get("/api/history")
async def get_history(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split("Bearer ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
        msgs_ref = db.collection('users').document(uid).collection('messages')
        docs = msgs_ref.order_by('timestamp').stream()
        return {"history": [doc.to_dict() for doc in docs]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/welcome")
async def welcome(request: WelcomeRequest, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split("Bearer ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
        prompt = f"使用者剛登入，當地時間是 {request.local_time}。請給予自然的問候。總長兩句內。"
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=BASE_SYSTEM_PROMPT)
        response = model.generate_content(prompt)
        welcome_msg = response.text
        msgs_ref = db.collection('users').document(uid).collection('messages')
        msgs_ref.add({"content": welcome_msg, "sender": "ai", "timestamp": time.time()})
        return {"message": {"content": welcome_msg}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat(request: ChatRequest, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    token = authorization.split("Bearer ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
    except: uid = "test_user"
    
    context = get_relevant_context(request.message, CHUNKS)
    dynamic_prompt = BASE_SYSTEM_PROMPT
    if context: dynamic_prompt += f"\n背景資料：\n{context}"
    
    msgs_ref = db.collection('users').document(uid).collection('messages')
    recent_docs = msgs_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10).stream()
    history_data = sorted([d.to_dict() for d in recent_docs], key=lambda x: x['timestamp'])
    
    gemini_history = []
    for msg in history_data:
        role = "user" if msg['sender'] == "user" else "model"
        gemini_history.append({"role": role, "parts": [msg['content']]})
    
    if gemini_history and gemini_history[0]["role"] == "model":
        gemini_history.insert(0, {"role": "user", "parts": ["你好"]})

    try:
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=dynamic_prompt)
        chat_session = model.start_chat(history=gemini_history)
        response = chat_session.send_message(request.message)
        ai_reply = response.text
        now = time.time()
        batch = db.batch()
        batch.set(msgs_ref.document(), {"content": request.message, "sender": "user", "timestamp": now})
        batch.set(msgs_ref.document(), {"content": ai_reply, "sender": "ai", "timestamp": now + 0.1})
        batch.commit()
        return {"message": {"content": ai_reply}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/summarize")
async def summarize(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    token = authorization.split("Bearer ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
        msgs_ref = db.collection('users').document(uid).collection('messages')
        
        # 1. 抓取內容進行分析
        all_docs = msgs_ref.order_by('timestamp').stream()
        docs_list = [d for d in all_docs]
        chat_text = "\n".join([f"{d.to_dict()['sender']}: {d.to_dict()['content']}" for d in docs_list])
        
        prompt = f"""
        請根據聊天內容分析並回傳 JSON：
        {chat_text}
        
        1. mood: 10字內形容心情。
        2. events: 1~3件紀錄(15字內/件)。
        3. oneLiner: 15字內描述今天。
        4. messageToSelf: 50字內模擬語氣寫給自己。
        """
        
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        summary_result = json.loads(response.text)
        
        # 2. 批次刪除該使用者的所有對話紀錄
        batch = db.batch()
        for d in docs_list:
            batch.delete(d.reference)
        batch.commit()
        
        return summary_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}