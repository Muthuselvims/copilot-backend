from fastapi import FastAPI
from dotenv import load_dotenv
load_dotenv()

from app.routes.agent_routes import router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow all CORS for dev purposes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# This is the correct placement for non-prefixed routes
# They are added directly to the main app instance
@app.get("/")
async def read_root():
    return {"message": "Welcome to my API! 🎉"}

# Add an additional, optional endpoint to check the service status
@app.get("/health")
async def health_check():
    return {"status": "ok"}


# Register router AFTER the app-level routes
# The prefix is applied here, so all routes in 'router'
# will be available at /api/...
app.include_router(router, prefix="/api")