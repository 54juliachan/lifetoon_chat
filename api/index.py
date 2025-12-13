import os
import json
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, auth

app = FastAPI()

# --- 初始化 Firebase Admin ---
if not firebase_admin._apps:
    # 嘗試讀取環境變數，如果沒有則印出警告
    service_account_info = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if service_account_info:
        try:
            cred = credentials.Certificate(json.loads(service_account_info))
            firebase_admin.initialize_app(cred)
        except Exception as e:
            print(f"Firebase Init Error: {e}")
    else:
        print("Warning: FIREBASE_SERVICE_ACCOUNT_JSON not set.")

# --- 初始化 Gemini ---
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# 定義請求資料模型
class ChatRequest(BaseModel):
    message: str

# --- 核心聊天功能 ---
# 加上 @app.post("/chat") 以防 Vercel 剝離了 /api 前綴
@app.post("/api/chat")
@app.post("/chat") 
async def chat(request: ChatRequest, authorization: str = Header(None)):
    # 1. 檢查 Token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.split("Bearer ")[1]

    try:
        # 2. 驗證 Firebase Token
        # 注意：如果本地開發沒有正確設定 Firebase Admin，這裡可能會失敗
        # 在 Vercel 上確保環境變數正確
        if firebase_admin._apps:
            decoded_token = auth.verify_id_token(token)
        else:
            # 僅供測試：如果沒有 Firebase 設定，暫時跳過驗證 (不建議生產環境使用)
            print("Skipping auth verification (Firebase not init)")
        
    except Exception as e:
        print(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid authentication token: {str(e)}")

    # 3. 呼叫 Gemini API
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(request.message)
        return {"message": {"content": response.text}}
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 測試與除錯路由 ---

# 讓瀏覽器直接訪問 /api/chat 時顯示友善訊息，而不是 404
@app.get("/api/chat")
@app.get("/chat")
async def chat_get():
    return {"status": "ok", "message": "API is running! Please use POST method to chat."}

# 根目錄測試
@app.get("/api")
async def api_root():
    return {"status": "ok", "message": "Welcome to Lifetoon Chat API"}