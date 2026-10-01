from fastapi import APIRouter, HTTPException, Depends
# from app.agents.auth.auth_service_instance import auth_service
from app.utils.redshift_connection import redshift_connection
from app.utils.auth import *
from app.core.auth import get_current_user,token_blacklist

# from app.agents.auth.auth_dependency import get_current_user
from app.schemas.auth import LoginRequest 
router = APIRouter()
  
@router.post("/login")
# def login(request: LoginRequest):
def login(req: LoginRequest): #, db: Session = Depends(get_db)):
    # user = db.query(User).filter(User.username == req.username).first()
    
    if not redshift_connection(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid Redshift credentials")
        
    token = create_access_token(data={"sub": req.username})
    return {"access_token": token, "token_type": "bearer"}
 
@router.get("/validate-token")
def validate_token(user: dict = Depends(get_current_user)):
    return {"valid": True, "username": user["username"], "token": user["token"]}
 
@router.post("/logout")
def logout(user: dict = Depends(get_current_user)):
    token_blacklist.add(user["token"])
    return {"message": f"User {user['username']} logged out successfully"}