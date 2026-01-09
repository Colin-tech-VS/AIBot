from fastapi import APIRouter, HTTPException, Depends, status, Response, Request, Body
from backend.auth.database import get_db_connection
from backend.auth.security import get_password_hash, verify_password, create_access_token, decode_access_token
from backend.auth.models import UserCreate, UserLogin, Token, UserResponse, ChangePassword, UserDetailResponse, ConversationSync
from typing import List
import sqlite3
import json

router = APIRouter(prefix="/auth", tags=["auth"])

def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        # Check Authorization header as fallback
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        return None
        
    payload = decode_access_token(token)
    if not payload:
        return None
        
    return {"username": payload.get("sub"), "user_id": payload.get("user_id")}

@router.get("/me", response_model=UserDetailResponse)
def get_me(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Non connecté")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, created_at FROM users WHERE id = ?", (user["user_id"],))
    db_user = cursor.fetchone()
    conn.close()
    
    if not db_user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        
    return {
        "id": db_user["id"],
        "username": db_user["username"],
        "email": db_user["email"],
        "created_at": db_user["created_at"]
    }

@router.post("/change-password")
def change_password(data: ChangePassword, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Non connecté")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user["user_id"],))
    db_user = cursor.fetchone()
    
    if not db_user or not verify_password(data.old_password, db_user["password_hash"]):
        conn.close()
        raise HTTPException(status_code=400, detail="Ancien mot de passe incorrect")
    
    new_password_hash = get_password_hash(data.new_password)
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_password_hash, user["user_id"]))
    conn.commit()
    conn.close()
    
    return {"message": "Mot de passe modifié avec succès"}

@router.delete("/delete-account")
def delete_account(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Non connecté")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Supprimer les conversations de l'utilisateur
        cursor.execute("DELETE FROM user_conversations WHERE user_id = ?", (user["user_id"],))
        # Supprimer l'utilisateur
        cursor.execute("DELETE FROM users WHERE id = ?", (user["user_id"],))
        conn.commit()
        return {"message": "Compte et données supprimés avec succès"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression: {str(e)}")
    finally:
        conn.close()

@router.post("/register", response_model=UserResponse)
def register(user: UserCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    password_hash = get_password_hash(user.password)
    
    try:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (user.username, user.email, password_hash)
        )
        user_id = cursor.lastrowid
        conn.commit()
        return {"id": user_id, "username": user.username, "email": user.email}
    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            raise HTTPException(status_code=400, detail="Nom d'utilisateur déjà utilisé")
        if "email" in str(e):
            raise HTTPException(status_code=400, detail="Email déjà utilisé")
        raise HTTPException(status_code=400, detail="Erreur lors de l'inscription")
    finally:
        conn.close()

@router.post("/login", response_model=Token)
def login(user_data: UserLogin, response: Response):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE username = ?", (user_data.username,))
    user = cursor.fetchone()
    conn.close()
    
    if not user or not verify_password(user_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect",
        )
    
    access_token = create_access_token(data={"sub": user["username"], "user_id": user["id"]})
    
    # On peut aussi mettre le token dans un cookie pour plus de sécurité côté navigateur
    response.set_cookie(key="access_token", value=access_token, httponly=True, max_age=3600*24*7)
    
    return {"access_token": access_token, "token_type": "bearer", "username": user["username"]}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Déconnexion réussie"}

@router.post("/sync_conversations")
def sync_conversations(request_data: List[ConversationSync] = Body(...), user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Non connecté")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        for conv in request_data:
            # Pydantic a déjà validé la structure
            # Utilisation de model_dump() pour Pydantic v2, fallback sur dict() si v1
            messages_list = []
            for m in conv.messages:
                if hasattr(m, "model_dump"):
                    messages_list.append(m.model_dump())
                else:
                    messages_list.append(m.dict())
                    
            cursor.execute(
                """
                INSERT INTO user_conversations (id, user_id, title, messages_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                messages_json = excluded.messages_json,
                updated_at = CURRENT_TIMESTAMP
                """,
                (conv.id, user["user_id"], conv.title, json.dumps(messages_list))
            )
        conn.commit()
        return {"status": "success", "synced": len(request_data)}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/conversations")
def get_user_conversations(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Non connecté")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM user_conversations WHERE user_id = ? ORDER BY updated_at DESC", (user["user_id"],))
    rows = cursor.fetchall()
    conn.close()
    
    conversations = []
    for row in rows:
        conversations.append({
            "id": row["id"],
            "title": row["title"],
            "messages": json.loads(row["messages_json"]),
            "updated_at": row["updated_at"]
        })
    return conversations
