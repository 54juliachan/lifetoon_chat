import os
import json
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, auth

# 設定 docs_url 以便在 /api/docs 查看文件
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

# --- 初始化 Gemini ---
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

class ChatRequest(BaseModel):
    message: str

# --- 核心聊天功能 ---
# 因為 vercel.json 現在只轉發 /api/...，所以這裡的路徑設定要包含 /api
@app.post("/api/chat")
async def chat(request: ChatRequest, authorization: str = Header(None)):
    # 1. 檢查 Token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.split("Bearer ")[1]

    try:
        # 2. 驗證 Firebase Token
        if firebase_admin._apps:
            decoded_token = auth.verify_id_token(token)
        else:
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

# --- 健康檢查路由 ---
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "Lifetoon API is running"}