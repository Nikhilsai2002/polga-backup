from pydantic import BaseModel
 
# class ChatRequest(BaseModel):
#     question: str
 

class ChatResultStatus(BaseModel):
    prompt: str
    query: str


class ChatRequest(BaseModel):
    question: str
    user: str
    analysis_id: int

class AnalysisRequest(BaseModel):
    user: str
    analysis_name: str

class EngagementRequest(BaseModel):
    user_query: str

    