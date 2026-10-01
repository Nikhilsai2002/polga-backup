from fastapi import FastAPI
from app.apis.v1.auth import router as auth_router
from app.apis.v1.chat import router as sql_router
from fastapi.middleware.cors import CORSMiddleware
# from app.db import Base, engine

# def init_db():
#     Base.metadata.create_all(bind=engine)

# init_db()
app = FastAPI(title="PaymatiX NLP")

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

