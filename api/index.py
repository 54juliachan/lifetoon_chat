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

# --- 1. 必加：CORS 設定 ---
# 這能解決許多莫名其妙的 "Not Found" 或 Network Error
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生產環境建議改成你的 Vercel 網域
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

# --- 2. 核心聊天功能 (多重路徑保險) ---
# Vercel 有時會剝離路徑，有時會保留。
# 加上 "/" 是為了防止 Vercel 把 /api/chat rewrite 到腳本後，腳本只收到空路徑的情況。
@app.post("/api/chat")
@app.post("/chat")
@app.post("/") 
async def chat(request: ChatRequest, authorization: str = Header(None)):
    # 檢查 Token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.split("Bearer ")[1]

    try:
        if firebase_admin._apps:
            decoded_token = auth.verify_id_token(token)
        else:
            print("Skipping auth verification (Firebase not init)")
        
    except Exception as e:
        print(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid authentication token: {str(e)}")

    # 呼叫 Gemini
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(request.message)
        return {"message": {"content": response.text}}
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 3. 測試路由 ---
@app.get("/api/chat")
@app.get("/chat")
@app.get("/")
async def chat_get():
    return {"status": "ok", "message": "API is running! (POST to chat)"}

# 萬用路由：捕捉所有漏網之魚並回傳路徑，這對除錯非常有幫助
# 如果還是出現 404，這個路由會告訴你 FastAPI 到底收到了什麼路徑
@app.api_route("/{path_name:path}", methods=["GET", "POST", "OPTIONS"])
async def catch_all(path_name: str, request: Request):
    return {
        "status": "error", 
        "message": "Path not match", 
        "received_path": path_name,
        "method": request.method
    }