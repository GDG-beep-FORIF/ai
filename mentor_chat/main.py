from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor, register_uuid
import uuid
from contextlib import contextmanager
from openai import OpenAI
import os
import httpx
import json
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
PERSONA_API_BASE = "https://port-0-back-m1ung2x3f53d462a.sel4.cloudtype.app"

# Database configuration
DATABASE_CONFIG = {
    "dbname": "postgres",
    "user": "postgres.baeuipvrxxdsidfkwmvn",
    "password": "4CipIRLuLkYavf3X",
    "host": "aws-0-ap-northeast-2.pooler.supabase.com",
    "port": "6543"
}

# Pydantic models
class MessageCreate(BaseModel):
    content: str

class ChatRoomCreate(BaseModel):
    title: str
    person_ids: List[uuid.UUID]

class Message(BaseModel):
    message_id: uuid.UUID
    content: str
    sender_type: str
    created_at: datetime

    class Config:
        from_attributes = True

# Helper functions
async def get_current_user():
    # JWT 토큰 검증 로직 구현
    # 임시로 테스트용 사용자 ID 반환
    return uuid.UUID("bc430308-def0-4203-9971-437fdba5283a")

@contextmanager
def get_db_cursor():
    conn = psycopg2.connect(**DATABASE_CONFIG)
    register_uuid()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

async def fetch_persona_info(name: str) -> Dict:
    """외부 API에서 페르소나 정보 조회"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{PERSONA_API_BASE}/persons", params={"name": name})
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="페르소나 정보를 가져오는데 실패했습니다.")
        return response.json()

def create_persona_prompt(persona_data: Dict) -> str:
    """페르소나 데이터를 기반으로 시스템 프롬프트 생성"""
    prompt = f"""당신은 {persona_data['name']}입니다. 
생애: {persona_data['birthDeath']}
시대: {persona_data['era']}
국적: {persona_data['nationality']}

직업: {', '.join(p['primaryOccupation'] for p in persona_data['professionalInfo'])}
다른 역할: {', '.join(r['roleName'] for r in persona_data['otherRoles'])}

주요 업적:
{chr(10).join('- ' + a['achievementName'] for a in persona_data['achievements'])}

개인 배경:
교육: {persona_data['personalInfo']['education']}
배경: {persona_data['personalInfo']['background']}

성격 특성:
{chr(10).join('- ' + t['traitName'] for t in persona_data['personalityTraits'])}

영향받은 요소:
{chr(10).join('- ' + i['influenceName'] for i in persona_data['influences'])}

역사적 맥락:
{persona_data['historicalContext']['periodBackground']}

주요 사건:
{chr(10).join('- ' + e['eventDescription'] for e in persona_data['keyEvents'])}

유산:
영향력: {persona_data['legacy']['impact']}
현대적 의의: {persona_data['legacy']['modernSignificance']}

당신은 위 정보를 바탕으로 해당 인물의 성격, 사고방식, 말투를 완벽히 재현해야 합니다. 
대화할 때는 당신의 시대와 맥락에 맞는 적절한 언어를 사용하되, 현대인과 소통이 가능한 수준을 유지하세요.
당신의 모든 발언과 행동은 위의 역사적 사실과 인물의 성격에 부합해야 합니다."""

    return prompt

def format_chat_history(history: List[dict]) -> List[dict]:
    """채팅 히스토리를 OpenAI API 형식으로 변환"""
    formatted_messages = []
    for msg in history:
        role = "assistant" if msg['sender_type'] == 'AI' else "user"
        formatted_messages.append({
            "role": role,
            "content": [{
                "type": "text",
                "text": msg['content']
            }]
        })
    return formatted_messages

async def get_ai_response(history: List[dict], current_message: str, persona_name: str) -> str:
    """AI 응답 생성"""
    try:
        # 페르소나 정보 조회
        persona_data = await fetch_persona_info(persona_name)
        
        # 시스템 프롬프트 생성
        system_prompt = create_persona_prompt(persona_data)
        
        # 시스템 메시지 구성
        system_message = {
            "role": "system",
            "content": [{
                "type": "text",
                "text": system_prompt
            }]
        }
        
        # 채팅 히스토리 포맷팅
        chat_history = format_chat_history(history)
        
        # 현재 메시지 추가
        current_message = {
            "role": "user",
            "content": [{
                "type": "text",
                "text": current_message
            }]
        }
        
        # API 요청 메시지 구성
        messages = [system_message] + chat_history + [current_message]
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "text"},
            temperature=1,
            max_tokens=4096,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI Response Error: {str(e)}")
        raise HTTPException(status_code=500, detail="AI 응답 생성 중 오류가 발생했습니다.")

# API Endpoints
@app.get("/")
async def read_root():
    return {"status": "running", "message": "Chat API is running"}

@app.post("/chat-rooms/")
async def create_chat_room(
    chat_room: ChatRoomCreate,
    current_user_id: uuid.UUID = Depends(get_current_user)
):
    with get_db_cursor() as cur:
        try:
            # 채팅방 생성
            cur.execute("""
                INSERT INTO chat_rooms (user_id, title, status)
                VALUES (%s, %s, 'ACTIVE')
                RETURNING room_id
            """, (current_user_id, chat_room.title))
            
            room_id = cur.fetchone()['room_id']
            
            # 페르소나 연결
            for person_id in chat_room.person_ids:
                cur.execute("""
                    INSERT INTO chat_room_persons (room_id, person_id)
                    VALUES (%s, %s)
                """, (room_id, person_id))
                
            return {"room_id": room_id, "status": "created"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"채팅방 생성 중 오류 발생: {str(e)}")

@app.get("/chat-rooms/")
async def list_chat_rooms(current_user_id: uuid.UUID = Depends(get_current_user)):
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT r.room_id, r.title, r.status, r.created_at,
                   array_agg(p.name) as person_names
            FROM chat_rooms r
            LEFT JOIN chat_room_persons crp ON r.room_id = crp.room_id
            LEFT JOIN basic_info p ON crp.person_id = p.person_id
            WHERE r.user_id = %s
            GROUP BY r.room_id, r.title, r.status, r.created_at
            ORDER BY r.created_at DESC
        """, (current_user_id,))
        
        return cur.fetchall()

@app.get("/chat-rooms/{room_id}")
async def get_chat_room(
    room_id: uuid.UUID,
    current_user_id: uuid.UUID = Depends(get_current_user)
):
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT r.*, 
                   array_agg(json_build_object(
                       'person_id', p.person_id,
                       'name', p.name
                   )) as persons
            FROM chat_rooms r
            LEFT JOIN chat_room_persons crp ON r.room_id = crp.room_id
            LEFT JOIN basic_info p ON crp.person_id = p.person_id
            WHERE r.room_id = %s AND r.user_id = %s
            GROUP BY r.room_id
        """, (room_id, current_user_id))
        
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
            
        return result

@app.get("/chat-rooms/{room_id}/messages/")
async def get_chat_messages(
    room_id: uuid.UUID,
    current_user_id: uuid.UUID = Depends(get_current_user)
):
    with get_db_cursor() as cur:
        # 채팅방 접근 권한 확인
        cur.execute("""
            SELECT 1 FROM chat_rooms 
            WHERE room_id = %s AND user_id = %s
        """, (room_id, current_user_id))
        
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
            
        # 메시지 조회
        cur.execute("""
            SELECT message_id, content, sender_type, created_at
            FROM chat_messages
            WHERE room_id = %s
            ORDER BY created_at ASC
        """, (room_id,))
        
        return cur.fetchall()

@app.post("/chat-rooms/{room_id}/messages/")
async def create_message(
    room_id: uuid.UUID,
    message: MessageCreate,
    current_user_id: uuid.UUID = Depends(get_current_user)
):
    with get_db_cursor() as cur:
        try:
            # 사용자 메시지 저장
            cur.execute("""
                INSERT INTO chat_messages (room_id, sender_type, sender_id, content)
                VALUES (%s, 'USER', %s, %s)
                RETURNING message_id, created_at
            """, (room_id, current_user_id, message.content))
            
            user_message = cur.fetchone()
            
            # 대화 히스토리 조회
            cur.execute("""
                SELECT m.content, m.sender_type, m.created_at
                FROM chat_messages m
                WHERE m.room_id = %s
                ORDER BY m.created_at DESC
                LIMIT 10
            """, (room_id,))
            
            history = cur.fetchall()
            
            # 페르소나 정보 조회
            cur.execute("""
                SELECT p.name
                FROM chat_room_persons crp
                JOIN basic_info p ON crp.person_id = p.person_id
                WHERE crp.room_id = %s
                LIMIT 1
            """, (room_id,))
            
            person_info = cur.fetchone()
            if not person_info:
                raise HTTPException(status_code=404, detail="페르소나 정보를 찾을 수 없습니다.")
            
            # AI 응답 생성
            ai_response = await get_ai_response(history, message.content, person_info['name'])
            
            # AI 응답 저장
            cur.execute("""
                INSERT INTO chat_messages (room_id, sender_type, sender_id, content)
                VALUES (%s, 'AI', %s, %s)
                RETURNING message_id, created_at
            """, (room_id, current_user_id, ai_response))
            
            return {
                "message_id": user_message['message_id'],
                "content": message.content,
                "sender_type": "USER",
                "created_at": user_message['created_at'],
                "ai_response": {
                    "content": ai_response,
                    "sender_type": "AI"
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"메시지 처리 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)