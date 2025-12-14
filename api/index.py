import os
import json
import time
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, auth, firestore

# ... (初始化 Firebase 與 FastAPI 保持不變) ...
app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# --- [新增] 定義 AI 角色設定 ---
SYSTEM_PROMPT = "你是一個溫柔親切的朋友，會主動關懷聊天對象、並適時提供建議，以繁體中文進行對話"

class ChatRequest(BaseModel):
    message: str

# [新增] 歡迎請求的資料結構 (接收前端傳來的時間)
class WelcomeRequest(BaseModel):
    local_time: str

@app.get("/")
async def read_root():
    return RedirectResponse(url="/index.html")

# ... (get_history API 保持不變) ...
@app.get("/api/history")
async def get_history(authorization: str = Header(None)):
    # (原有程式碼保持不變...)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split("Bearer ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
        msgs_ref = db.collection('users').document(uid).collection('messages')
        docs = msgs_ref.order_by('timestamp').stream()
        history = []
        for doc in docs:
            history.append(doc.to_dict())
        return {"history": history}
    except Exception as e:
        print(f"History Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- [新增] 主動歡迎 API ---
@app.post("/api/welcome")
async def welcome(request: WelcomeRequest, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split("Bearer ")[1]
    
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
        
        # 準備 Prompt，告訴 AI 現在時間，請它打招呼
        # 這裡不讀取全部歷史，只給簡單指令，避免歡迎語太長或離題
        prompt = f"使用者剛登入，現在他的時間是 {request.local_time}。請用一句話熱情且自然地向他打招呼（例如問候這時間點過得如何），不要重複之前的對話。"
        
        # [關鍵] 設定 system_instruction
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=SYSTEM_PROMPT)
        response = model.generate_content(prompt)
        welcome_msg = response.text

        # 存入資料庫 (只存 AI 的回應，不存 Prompt)
        msgs_ref = db.collection('users').document(uid).collection('messages')
        ai_doc = msgs_ref.document()
        batch = db.batch()
        
        batch.set(ai_doc, {
            "content": welcome_msg,
            "sender": "ai",
            "timestamp": time.time()
        })
        batch.commit()

        return {"message": {"content": welcome_msg}}

    except Exception as e:
        print(f"Welcome Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- [修改] 核心聊天 API ---
@app.post("/api/chat")
async def chat(request: ChatRequest, authorization: str = Header(None)):
    # ... (Token 驗證部分保持不變) ...
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")
    token = authorization.split("Bearer ")[1]
    uid = ""
    try:
        if firebase_admin._apps:
            decoded_token = auth.verify_id_token(token)
            uid = decoded_token['uid']
        else:
            uid = "test_user"
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    # 準備歷史紀錄
    gemini_history = []
    try:
        msgs_ref = db.collection('users').document(uid).collection('messages')
        recent_docs = msgs_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(20).stream()
        history_data = sorted([d.to_dict() for d in recent_docs], key=lambda x: x['timestamp'])
        
        for msg in history_data:
            role = "user" if msg['sender'] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg['content']]})
    except Exception:
        pass

    try:
        # [修改] 加上 system_instruction
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=SYSTEM_PROMPT)
        chat_session = model.start_chat(history=gemini_history)
        response = chat_session.send_message(request.message)
        ai_reply_text = response.text
        
        # 儲存對話 (保持不變)
        batch = db.batch()
        user_doc = msgs_ref.document()
        ai_doc = msgs_ref.document()
        timestamp = time.time()
        
        batch.set(user_doc, {"content": request.message, "sender": "user", "timestamp": timestamp})
        batch.set(ai_doc, {"content": ai_reply_text, "sender": "ai", "timestamp": timestamp + 0.1})
        batch.commit()

        return {"message": {"content": ai_reply_text}}
        
    except Exception as e:
        # ... (錯誤處理保持不變) ...
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}