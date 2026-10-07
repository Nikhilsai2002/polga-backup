from fastapi import FastAPI
from app.apis.v1.auth import router as auth_router
from app.apis.v1.chat import router as sql_router
from fastapi.middleware.cors import CORSMiddleware
# from app.core.database import Base, engine

# def init_db():
#     Base.metadata.create_all(bind=engine)

# init_db()

from app.core.database import Base, engine

from app.models.analysis import Analysis
from app.models.conversation import Conversation
from app.models.usersession import UserSession

app = FastAPI(title="PaymatiX NLP")

@app.on_event("startup")
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Tables registered:")
    print(Base.metadata.tables.keys())

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public routes
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])

# Protected routes
app.include_router(sql_router, prefix="/chat", tags=["SQL"])

