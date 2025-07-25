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

# Register router
app.include_router(router, prefix="/api")


