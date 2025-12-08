from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.chat_routes import router as chat_router
import os

# Initialize FastAPI application
app = FastAPI(
    title="Vacation Planning Agent API",
    description="Conversational AI agent for planning trips and managing itineraries",
    version="1.0.0"
)

# Configure CORS to allow requests from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://purple-sand-06148da0f.1.azurestaticapps.net",  # Production frontend
        "http://localhost:3000",  # Local development
        "https://vacai-b2gccfdrfde4bdbm.canadacentral-01.azurewebsites.net"  # Azure Web App
    ],
    allow_credentials=True,  # Allow cookies and authorization headers
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Register API routes under /api/chat prefix
app.include_router(chat_router)


@app.get("/")
@app.get("/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
