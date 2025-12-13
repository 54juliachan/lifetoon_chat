import os
import json
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse # 改用 RedirectResponse
from pydantic import BaseModel
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, auth

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

# --- 初始化 Gemini ---
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

class ChatRequest(BaseModel):
    message: str

# --- 🔥 修改：根目錄救援路由 ---
# 不再嘗試讀取檔案，而是直接轉址給靜態網頁
# 這樣就把「顯示網頁」的工作交回給 Vercel 的 CDN，避開了 Python 找不到檔案的問題
@app.get("/")
async def read_root():
    return RedirectResponse(url="/index.html")

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

# 呼叫 Gemini
    try:
        # 使用最新的 Flash 模型
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(request.message)
        return {"message": {"content": response.text}}
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        # 如果是 404 模型找不到，嘗試使用舊版穩定的 gemini-pro 作為備援
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