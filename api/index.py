import os
import json
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse # 新增 HTMLResponse
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

# --- 🔥 新增：根目錄救援路由 ---
# 如果 Vercel 把首頁請求丟給 Python，我們就手動回傳 index.html
@app.get("/")
async def read_root():
    # 嘗試尋找 public/index.html 的位置
    # 在 Vercel 環境中，檔案結構通常被保留
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index_path = os.path.join(base_dir, "public", "index.html")

    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    else:
        return {"status": "error", "message": "index.html not found on server"}

# --- 核心聊天功能 ---
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

# --- 健康檢查 ---
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "Lifetoon API is running"}