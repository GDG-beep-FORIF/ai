import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import httpx
import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from psycopg2.extras import RealDictCursor, register_uuid
from pydantic import BaseModel

from main import DialogueSystem, Persona

# 환경 변수 로드
load_dotenv()

# FastAPI 앱 초기화
app = FastAPI(title="페르소나 토론 채팅 API")

# UUID 타입 등록
register_uuid()

# API 기본 URL 설정
PERSONA_API_BASE = os.getenv("PERSONA_API_BASE")

# 데이터베이스 설정
DATABASE_CONFIG = {
    "dbname": "postgres",
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_URL"),
    "port": "6543",
}


# 데이터베이스 연결 함수
def get_db_connection():
    return psycopg2.connect(
        dbname=DATABASE_CONFIG["dbname"],
        user=DATABASE_CONFIG["user"],
        password=DATABASE_CONFIG["password"],
        host=DATABASE_CONFIG["host"],
        port=DATABASE_CONFIG["port"],
        cursor_factory=RealDictCursor,
    )


# Pydantic 모델 정의
class ChatRoomCreate(BaseModel):
    """채팅방 생성을 위한 모델"""

    title: str
    person_ids: List[uuid.UUID]  # 토론에 참여할 두 인물의 ID
    user_id: uuid.UUID


class MessageCreate(BaseModel):
    """메시지 생성을 위한 모델"""

    content: str


# 페르소나 API 호출 함수
async def fetch_persona_data(person_id: uuid.UUID) -> Dict:
    """외부 API에서 페르소나 정보 조회"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{PERSONA_API_BASE}/persons/{person_id}")
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail="페르소나 정보를 가져오는데 실패했습니다",
            )
        return response.json()


async def fetch_persona_id_by_name(name: str) -> uuid.UUID:
    """외부 API에서 페르소나 ID 조회"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{PERSONA_API_BASE}/persons", params={"name": name}
        )
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail="페르소나 ID를 가져오는데 실패했습니다",
            )
        data = response.json()
        return data["person_id"]


# API 엔드포인트
@app.post("/chat-rooms/")
async def create_chat_room(room_data: ChatRoomCreate):
    """새로운 토론 채팅방 생성"""
    if len(room_data.person_ids) != 2:
        raise HTTPException(
            status_code=400, detail="토론을 위해 정확히 2명의 인물이 필요합니다"
        )

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO chat_rooms (user_id, title, status)
            VALUES (%s, %s, 'ACTIVE')
            RETURNING room_id
            """,
            (room_data.user_id, room_data.title),
        )

        room_id = cur.fetchone()["room_id"]

        for person_id in room_data.person_ids:
            cur.execute(
                """
                INSERT INTO chat_room_persons (room_id, person_id)
                VALUES (%s, %s)
                """,
                (room_id, person_id),
            )

        conn.commit()
        return {"room_id": room_id, "status": "created"}

    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=400, detail=f"채팅방 생성에 실패했습니다: {str(e)}"
        )
    finally:
        conn.close()


@app.post("/chat-rooms/{room_id}/messages/")
async def create_message(
    room_id: uuid.UUID, message: MessageCreate, user_id: uuid.UUID
):
    """토론 채팅방에 메시지 전송 및 AI 응답 생성"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # 채팅방 상태 확인
        cur.execute(
            """
            SELECT * FROM chat_rooms 
            WHERE room_id = %s 
            AND user_id = %s 
            AND status = 'ACTIVE'
            """,
            (room_id, user_id),
        )

        room = cur.fetchone()
        if not room:
            raise HTTPException(
                status_code=404, detail="채팅방을 찾을 수 없거나 비활성 상태입니다"
            )

        # 사용자 메시지 저장
        cur.execute(
            """
            INSERT INTO chat_messages (room_id, sender_type, sender_id, content)
            VALUES (%s, 'USER', %s, %s)
            RETURNING message_id, content, sender_type, created_at
            """,
            (room_id, user_id, message.content),
        )

        user_message = cur.fetchone()

        # 채팅방의 페르소나 정보 조회
        cur.execute(
            """
            SELECT p.* FROM chat_room_persons crp
            JOIN basic_info p ON crp.person_id = p.person_id
            WHERE crp.room_id = %s
            """,
            (room_id,),
        )

        personas = cur.fetchall()

        # API에서 페르소나 정보 조회
        persona1_data = await fetch_persona_data(personas[0]["person_id"])
        persona2_data = await fetch_persona_data(personas[1]["person_id"])

        # DialogueSystem을 사용하여 토론 응답 생성
        dialogue_system = DialogueSystem(Persona(persona1_data), Persona(persona2_data))

        dialogue, summary = dialogue_system.generate_dialogue(
            message.content, num_turns=1
        )

        # AI 응답들 저장
        for turn in dialogue:
            sender_id = await fetch_persona_id_by_name(turn["speaker"])
            cur.execute(
                """
                INSERT INTO chat_messages (room_id, sender_type, sender_id, content)
                VALUES (%s, 'AI', %s, %s)
                """,
                (room_id, sender_id, turn["content"]),
            )

        conn.commit()
        return {
            "message_id": user_message["message_id"],
            "content": user_message["content"],
            "sender_type": user_message["sender_type"],
            "created_at": user_message["created_at"],
            "ai_responses": dialogue,
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=400, detail=f"메시지 처리에 실패했습니다: {str(e)}"
        )
    finally:
        conn.close()


@app.get("/chat-rooms/")
async def get_chat_rooms(user_id: uuid.UUID):
    """사용자의 토론 채팅방 목록 조회"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT cr.room_id, cr.title, cr.status, cr.created_at,
                   array_agg(bi.name) as person_names
            FROM chat_rooms cr
            JOIN chat_room_persons crp ON cr.room_id = crp.room_id
            JOIN basic_info bi ON crp.person_id = bi.person_id
            WHERE cr.user_id = %s
            GROUP BY cr.room_id, cr.title, cr.status, cr.created_at
            ORDER BY cr.created_at DESC
            """,
            (user_id,),
        )

        return cur.fetchall()
    finally:
        conn.close()


@app.get("/chat-rooms/{room_id}/messages/")
async def get_messages(room_id: uuid.UUID, user_id: uuid.UUID):
    """토론 채팅방의 메시지 목록 조회"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT m.message_id, m.content, m.sender_type, m.created_at,
                   CASE 
                       WHEN m.sender_type = 'USER' THEN u.username
                       WHEN m.sender_type = 'AI' THEN bi.name
                   END as sender_name
            FROM chat_messages m
            LEFT JOIN users u ON m.sender_id = u.user_id AND m.sender_type = 'USER'
            LEFT JOIN basic_info bi ON m.sender_id = bi.person_id AND m.sender_type = 'AI'
            WHERE m.room_id = %s
            ORDER BY m.created_at ASC
            """,
            (room_id,),
        )

        messages = cur.fetchall()
        if not messages:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다")

        return messages
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
