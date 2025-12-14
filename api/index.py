import os
import json
import time # [新增] 用於紀錄時間戳
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, auth, firestore # [修改] 引入 firestore

# 設定 docs_url
app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")

# ... (CORS 設定保持不變) ...
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

# [新增] 初始化 Firestore Client
db = firestore.client()

# --- 初始化 Gemini ---
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

class ChatRequest(BaseModel):
    message: str

# ... (根目錄救援路由保持不變) ...
@app.get("/")
async def read_root():
    return RedirectResponse(url="/index.html")

# --- [新增] 取得歷史紀錄 API ---
@app.get("/api/history")
async def get_history(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split("Bearer ")[1]
    
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
        
        # 從 Firestore 撈取該用戶的歷史訊息，按時間排序
        # 結構: users -> {uid} -> messages
        msgs_ref = db.collection('users').document(uid).collection('messages')
        docs = msgs_ref.order_by('timestamp').stream()
        
        history = []
        for doc in docs:
            history.append(doc.to_dict())
            
        return {"history": history}
        
    except Exception as e:
        print(f"History Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- [修改] 核心聊天功能 ---
@app.post("/api/chat")
async def chat(request: ChatRequest, authorization: str = Header(None)):
    # 1. 檢查 Token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.split("Bearer ")[1]
    uid = ""

    try:
        # 2. 驗證 Firebase Token 並取得 User ID
        if firebase_admin._apps:
            decoded_token = auth.verify_id_token(token)
            uid = decoded_token['uid']
        else:
            # 開發測試用，若無 Firebase 則跳過 (實務上不建議)
            print("Skipping auth verification (Firebase not init)")
            uid = "test_user"
        
    except Exception as e:
        print(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid authentication token: {str(e)}")

    # 3. 準備 Gemini 的歷史上下文 (Context)
    gemini_history = []
    
    try:
        # 撈取最近 20 筆對話，避免 Token 超量，也提供足夠上下文
        msgs_ref = db.collection('users').document(uid).collection('messages')
        recent_docs = msgs_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(20).stream()
        
        # 因為是倒序抓取，抓回來後要轉回正序
        history_data = sorted([d.to_dict() for d in recent_docs], key=lambda x: x['timestamp'])
        
        for msg in history_data:
            role = "user" if msg['sender'] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg['content']]})
            
    except Exception as e:
        print(f"Firestore read error: {e}")
        # 若讀取失敗，就當作沒歷史，繼續執行

    # 4. 呼叫 Gemini
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # [修改] 使用 start_chat 帶入歷史紀錄
        chat_session = model.start_chat(history=gemini_history)
        response = chat_session.send_message(request.message)
        ai_reply_text = response.text
        
        # [新增] 將這次的對話存入 Firestore
        batch = db.batch()
        user_doc = msgs_ref.document()
        ai_doc = msgs_ref.document()
        
        timestamp = time.time()
        
        batch.set(user_doc, {
            "content": request.message,
            "sender": "user",
            "timestamp": timestamp
        })
        
        batch.set(ai_doc, {
            "content": ai_reply_text,
            "sender": "ai", # 前端判斷用 ai，Gemini 歷史用 model，這裡存 ai 方便前端
            "timestamp": timestamp + 0.1 # 確保 AI 回應排在 User 之後
        })
        
        batch.commit()

        return {"message": {"content": ai_reply_text}}
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        # 錯誤處理邏輯保持不變...
        if "404" in str(e) or "not found" in str(e).lower():
            try:
                fallback_model = genai.GenerativeModel("gemini-pro")
                response = fallback_model.generate_content(request.message) # 備援模式暫不支援歷史
                return {"message": {"content": response.text + "\n(備用模型回應)"}}
            except Exception as e2:
                raise HTTPException(status_code=500, detail=f"Model Error: {str(e2)}")
        
        raise HTTPException(status_code=500, detail=str(e))

# ... (健康檢查保持不變) ...
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "Lifetoon API is running"}