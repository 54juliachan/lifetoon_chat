import os
import json
import time
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, auth, firestore

# 設定 docs_url
app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")

# --- CORS 設定 ---
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

# 初始化 Firestore
db = firestore.client()

# --- 初始化 Gemini ---
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# --- AI 角色設定 ---
SYSTEM_PROMPT = "你是一個溫柔親切的朋友，會主動關懷聊天對象、並適時提供建議，以繁體中文進行對話，每則訊息不超過100字"

# --- 資料模型 ---
class ChatRequest(BaseModel):
    message: str

class WelcomeRequest(BaseModel):
    local_time: str

# --- 根目錄救援路由 ---
@app.get("/")
async def read_root():
    return RedirectResponse(url="/index.html")

# --- 取得歷史紀錄 API ---
@app.get("/api/history")
async def get_history(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split("Bearer ")[1]
    
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
        
        # 從 Firestore 撈取該用戶的歷史訊息，按時間排序
        msgs_ref = db.collection('users').document(uid).collection('messages')
        docs = msgs_ref.order_by('timestamp').stream()
        
        history = []
        for doc in docs:
            history.append(doc.to_dict())
            
        return {"history": history}
        
    except Exception as e:
        print(f"History Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- [新增] 歷史紀錄清洗函式 ---
def sanitize_history(history):
    """
    確保歷史紀錄符合 Gemini API 規範：
    1. 必須以 'user' 開頭。
    2. 角色必須嚴格交替 (user -> model -> user -> model)。
    3. 傳給 start_chat 的歷史紀錄，最後一則必須是 'model' (因為接下來要發送的是 user 訊息)。
    """
    if not history:
        return []
    
    sanitized = []
    
    # 1. 處理第一則訊息：如果是 model，前面補一個 user
    if history[0]['role'] == 'model':
        sanitized.append({'role': 'user', 'parts': ["(系統自動插入：使用者加入對話)"]})
    
    # 2. 處理連續角色與合併
    for msg in history:
        if not sanitized:
            sanitized.append(msg)
            continue
            
        last_msg = sanitized[-1]
        
        # 如果當前訊息角色與上一則相同，則合併內容 (避免連續相同角色)
        if msg['role'] == last_msg['role']:
            last_msg['parts'].extend(msg['parts'])
        else:
            sanitized.append(msg)
            
    # 3. 處理最後一則訊息：如果是 user，必須移除
    # 因為 start_chat 後我們會呼叫 send_message (user)，如果歷史結尾是 user，會變成 user->user 導致錯誤
    if sanitized and sanitized[-1]['role'] == 'user':
        # 移除最後一則沒有 AI 回應的 User 訊息，避免衝突
        sanitized.pop()
        
    return sanitized

# --- 主動歡迎 API (不報時版本) ---
@app.post("/api/welcome")
async def welcome(request: WelcomeRequest, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split("Bearer ")[1]
    
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
        
        # Prompt 指令：給予時間作為判斷依據，但禁止直接報時
        prompt = f"""
        使用者剛登入，現在他的當地時間是 {request.local_time}。
        請依照時間給予溫暖的問候。
        
        【指令要求】：
        1. 根據時間選用自然的開頭（例如：「早安」、「午安」、「晚安」或「嗨嗨」）。
        2. 嚴格禁止提及具體的「日期」、「年份」或「幾點幾分」。
        3. 接一句像朋友般的簡單關懷或是閒聊問句，引導對方答覆（例如：「今天過得怎麼樣？」、「吃飯了嗎？」、「這時間還沒睡呀？」）。
        4. 總長度保持在兩句以內，語氣要親切自然。
        """
        
        # 設定 system_instruction
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=SYSTEM_PROMPT)
        response = model.generate_content(prompt)
        welcome_msg = response.text

        # 存入資料庫 (只存 AI 的回應)
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

# --- 核心聊天功能 (具備記憶) ---
@app.post("/api/chat")
async def chat(request: ChatRequest, authorization: str = Header(None)):
    # 1. 檢查 Token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.split("Bearer ")[1]
    uid = ""

    try:
        # 2. 驗證 Firebase Token
        if firebase_admin._apps:
            decoded_token = auth.verify_id_token(token)
            uid = decoded_token['uid']
        else:
            # 僅供本地測試 fallback
            print("Skipping auth verification (Firebase not init)")
            uid = "test_user"
        
    except Exception as e:
        print(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid authentication token: {str(e)}")

    # 3. 準備 Gemini 的歷史上下文
    gemini_history = []
    msgs_ref = db.collection('users').document(uid).collection('messages')

    try:
        # 撈取最近 20 筆對話作為 Context
        recent_docs = msgs_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(20).stream()
        # 轉回正序
        history_data = sorted([d.to_dict() for d in recent_docs], key=lambda x: x['timestamp'])
        
        for msg in history_data:
            role = "user" if msg['sender'] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg['content']]})

        # ================= [新增修正程式碼開始] =================
        # 修正：Gemini API 規定 history 必須以 user 開頭
        # 如果第一則訊息是 model (例如歡迎詞)，則在前面插入一個假的 user 訊息
        if gemini_history and gemini_history[0]["role"] == "model":
            gemini_history.insert(0, {
                "role": "user", 
                "parts": ["(系統自動插入：使用者加入對話)"] 
            })
        # ================= [新增修正程式碼結束] =================
            
    except Exception as e:
        print(f"Firestore read error: {e}")
        # 若讀取失敗，就當作沒歷史，繼續執行

    # 4. 呼叫 Gemini
    try:
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=SYSTEM_PROMPT)
        
        # 帶入歷史紀錄
        chat_session = model.start_chat(history=gemini_history)
        response = chat_session.send_message(request.message)
        ai_reply_text = response.text
        
        # 5. 將這次的對話存入 Firestore
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
            "sender": "ai",
            "timestamp": timestamp + 0.1 # 確保 AI 回應排在 User 之後
        })
        
        batch.commit()

        return {"message": {"content": ai_reply_text}}
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        # 備援機制
        if "404" in str(e) or "not found" in str(e).lower():
            try:
                print("Fallback to gemini-pro")
                fallback_model = genai.GenerativeModel("gemini-pro")
                response = fallback_model.generate_content(request.message)
                return {"message": {"content": response.text + "\n(備用模型回應)"}}
            except Exception as e2:
                raise HTTPException(status_code=500, detail=f"Model Error: {str(e2)}")
        
        raise HTTPException(status_code=500, detail=str(e))

# --- 健康檢查 ---
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "Lifetoon API is running"}