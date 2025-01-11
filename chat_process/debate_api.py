import asyncio
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set

import httpx
import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from openai import OpenAI
from psycopg2.extras import RealDictCursor, register_uuid
from pydantic import BaseModel

from main import DialogueSystem, Persona

# 환경 변수 로드
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# FastAPI 앱 초기화
app = FastAPI(title="페르소나 토론 채팅 API")

# UUID 타입 등록
register_uuid()

PERSONA_API_BASE = "https://port-0-back-m1ung2x3f53d462a.sel4.cloudtype.app"

# Database configuration
DATABASE_CONFIG = {
    "dbname": "postgres",
    "user": "postgres.baeuipvrxxdsidfkwmvn",
    "password": "4CipIRLuLkYavf3X",
    "host": "aws-0-ap-northeast-2.pooler.supabase.com",
    "port": "6543"
}


class DialogueSystem:
    def __init__(
        self,
        persona1_data: Dict,
        persona2_data: Dict,
        connection_manager=None,
        room_id=None,
    ):
        self.persona1_data = persona1_data
        self.persona2_data = persona2_data
        self.connection_manager = connection_manager
        self.room_id = room_id

    async def send_dialogue_message(self, message: dict):
        """웹소켓을 통해 대화 메시지 전송"""
        if self.connection_manager and self.room_id:
            await self.connection_manager.broadcast_to_room(message, self.room_id)

    def _get_persona_prompt(self, persona_data: Dict) -> str:
        """페르소나의 전체적인 컨텍스트 정보 생성"""
        basic_info = persona_data.get("basic_info", {})
        professional = persona_data.get("professional", {})
        personal = persona_data.get("personal", {})
        legacy = persona_data.get("legacy", {})
        historical = persona_data.get("historical_context", {})

        return f"""
    === 페르소나 상세 프로필 ===

    1. 인물 정보
    - 이름: {basic_info.get('name', '')}
    - 생애: {basic_info.get('birth_death', '')}
    - 시대: {basic_info.get('era', '')}
    - 국적: {basic_info.get('nationality', '')}

    2. 직업과 업적
    - 주요 직책: {professional.get('primary_occupation', '')}
    - 관련 역할: {', '.join(role['roleName'] for role in professional.get('other_roles', []))}
    - 주요 업적:
        {self._format_list([ach['achievementName'] for ach in professional.get('major_achievements', [])])}

    3. 개인 배경과 성향
    - 교육 배경: {personal.get('education', '')}
    - 개인 이력: {personal.get('background', '')}
    - 성격 특성:
        {self._format_list([trait['traitName'] for trait in personal.get('personality_traits', [])])}
    - 영향 받은 요소:
        {self._format_list([inf['influenceName'] for inf in personal.get('influences', [])])}

    4. 역사적 맥락
    - 시대적 배경: {historical.get('period_background', '')}
    - 주요 사건:
        {self._format_list([event['eventDescription'] for event in historical.get('key_events', [])])}

    5. 역사적 의의
    - 역사적 영향: {legacy.get('impact', '')}
    - 현대적 의미: {legacy.get('modern_significance', '')}"""

    def _format_list(self, items: List[str]) -> str:
        return "\n        - ".join(items) if items else ""

    async def generate_dialogue(
        self, user_concern: str, num_turns: int = 3
    ) -> tuple[list[dict], str]:
        """페르소나 간 대화 생성 및 요약"""
        system_prompt = f"""당신은 두 인물 간의 대화를 생성해야 합니다.
        
첫 번째 페르소나:
{self._get_persona_prompt(self.persona1_data)}

두 번째 페르소나:
{self._get_persona_prompt(self.persona2_data)}

사용자의 질문: {user_concern}

다음 지침을 따라 대화를 생성하세요:
1. 각 페르소나는 자신의 경험과 관점에서 사용자의 질문에 대해 답변해야 합니다.
2. 대화는 자연스럽게 이어져야 하며, 각자의 시대적 배경과 가치관이 반영되어야 합니다.
3. 페르소나의 성격 특성과 말투를 반영하여 대화를 생성하세요.
4. 역사적 맥락과 개인적 경험을 연결지어 답변하도록 합니다.
5. 서로의 의견에 대해 건설적으로 토론하고 보완하는 방식으로 대화를 진행하세요.
6. 최종적으로 두 사람의 관점을 종합하여 유익한 조언을 제공하세요

반드시 사용자의 고민에 대한 올바른 조언을 포함해야 합니다."""

        dialogue_messages = [{"role": "system", "content": system_prompt}]
        dialogue = []
        current_persona = self.persona1_data
        other_persona = self.persona2_data

        for turn in range(num_turns * 2):
            prompt = f"""현재 말하는 페르소나는 {current_persona['basic_info'].get('name')}입니다.
상대 페르소나는 {other_persona['basic_info'].get('name')}입니다.

이전 대화를 고려하여, {current_persona['basic_info'].get('name')}의 관점에서 대화를 이어가세요.
반드시 {current_persona['basic_info'].get('name')}의 대화만 생성해야 합니다.

페르소나의 시대적 배경, 경험, 성격을 반영한 자연스러운 대화를 생성해주세요.
현재 턴이 {turn + 1}/{num_turns * 2}입니다. 마지막 턴에 가까워질수록 대화를 자연스럽게 마무리해주세요."""

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=dialogue_messages + [{"role": "user", "content": prompt}],
            )

            content = response.choices[0].message.content
            speaker_name = current_persona["basic_info"].get("name")
            content = content.replace(f"{speaker_name}: ", "").strip('"')

            dialogue_turn = {
                "speaker": speaker_name,
                "content": content,
                "timestamp": datetime.now().isoformat(),
            }
            dialogue.append(dialogue_turn)

            if self.connection_manager and self.room_id:
                await self.send_dialogue_message(dialogue_turn)

            dialogue_messages.append({"role": "assistant", "content": content})
            current_persona, other_persona = other_persona, current_persona

        summary_prompt = """지금까지의 대화를 다음 형식으로 마크다운 요약을 작성해주세요:

# 대화 요약

## 주요 논점
- 각 페르소나가 제시한 핵심 주장

## 공통점과 차이점
- 두 페르소나의 관점 비교

## 핵심 조언
- 사용자에게 도움이 될 만한 주요 조언들

## 결론
사용자의 고민에 대한 최종 조언 요약"""

        summary_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": summary_prompt},
                {"role": "user", "content": str(dialogue)},
            ],
        )

        summary = summary_response.choices[0].message.content
        return dialogue, summary


# 웹소켓 연결 관리자
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[uuid.UUID, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: uuid.UUID):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = set()
        self.active_connections[room_id].add(websocket)

    def disconnect(self, websocket: WebSocket, room_id: uuid.UUID):
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast_to_room(self, message: dict, room_id: uuid.UUID):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_json(message)


manager = ConnectionManager()


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
    """외부 API에서 페르소나 정보 조회 및 데이터 구조 변환"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{PERSONA_API_BASE}/persons/{person_id}")
            response.raise_for_status()
            data = response.json()
            
            # API 응답을 DialogueSystem이 기대하는 형식으로 변환
            return {
                "basic_info": {
                    "id": data["id"],
                    "name": data["name"],
                    "birth_death": data["birthDeath"],
                    "era": data["era"],
                    "nationality": data["nationality"],
                    "gender": data["gender"],
                },
                "professional": {
                    "primary_occupation": data["professionalInfo"][0]["primaryOccupation"] if data["professionalInfo"] else "",
                    "other_roles": data["otherRoles"],
                    "major_achievements": data["achievements"],
                },
                "personal": {
                    "education": data["personalInfo"]["education"],
                    "background": data["personalInfo"]["background"],
                    "personality_traits": data["personalityTraits"],
                    "influences": data["influences"],
                },
                "legacy": data["legacy"],
                "historical_context": {
                    "period_background": data["historicalContext"]["periodBackground"],
                    "key_events": data["keyEvents"],
                }
            }
            
        except httpx.HTTPError as e:
            print(f"HTTP Error: {e}")
            raise HTTPException(status_code=500, detail=f"페르소나 정보를 가져오는데 실패했습니다: {str(e)}")
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다")


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


# 웹소켓 엔드포인트
@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: uuid.UUID):
    print(f"Attempting to connect to room: {room_id}")
    await manager.connect(websocket, room_id)
    try:
        while True:
            # 클라이언트로부터 메시지 수신
            data = await websocket.receive_json()  # JSON 형태로 메시지 수신
            
            # 필요한 데이터 추출
            content = data.get("content")
            user_id = uuid.UUID(data.get("user_id"))
            
            conn = get_db_connection()
            try:
                # 사용자 메시지 저장 및 브로드캐스트
                await save_and_broadcast_message(
                    conn, room_id, "USER", user_id, content
                )

                # 채팅방의 페르소나 정보 조회
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT p.* FROM chat_room_persons crp
                    JOIN basic_info p ON crp.person_id = p.person_id
                    WHERE crp.room_id = %s
                    """,
                    (room_id,)
                )
                personas = cur.fetchall()
                print("personas cur")
                # API에서 페르소나 정보 조회
                persona1_data = await fetch_persona_data(personas[0]["person_id"])
                print(persona1_data)
                persona2_data = await fetch_persona_data(personas[1]["person_id"])
                print(persona2_data)

                # DialogueSystem을 사용하여 토론 응답 생성
                dialogue_system = DialogueSystem(
                    persona1_data,
                    persona2_data,
                    connection_manager=manager,
                    room_id=room_id,
                )

                # 대화 생성 - websocket을 통해 자동으로 브로드캐스트됨
                dialogue, summary = await dialogue_system.generate_dialogue(
                    content, num_turns=3
                )

                # 요약 메시지 전송
                await manager.broadcast_to_room(
                    {
                        "type": "summary",
                        "content": summary,
                        "timestamp": datetime.now().isoformat()
                    },
                    room_id
                )

                conn.commit()

            except Exception as e:
                conn.rollback()
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
            finally:
                conn.close()

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)


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


async def save_and_broadcast_message(
    conn, room_id: uuid.UUID, sender_type: str, sender_id: uuid.UUID, content: str
):
    """메시지 저장 및 브로드캐스트"""
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO chat_messages (room_id, sender_type, sender_id, content)
        VALUES (%s, %s, %s, %s)
        RETURNING message_id, content, sender_type, created_at
        """,
        (room_id, sender_type, sender_id, content),
    )

    message = cur.fetchone()

    # 웹소켓으로 메시지 전송
    await manager.broadcast_to_room(
        {
            "message_id": str(message["message_id"]),
            "content": message["content"],
            "sender_type": message["sender_type"],
            "created_at": message["created_at"].isoformat(),
        },
        room_id,
    )

    return message


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

        # 사용자 메시지 저장 및 브로드캐스트
        await save_and_broadcast_message(
            conn, room_id, "USER", user_id, message.content
        )

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
        print("persona1_data")
        persona2_data = await fetch_persona_data(personas[1]["person_id"])
        print("persona2_data")
        # DialogueSystem을 사용하여 토론 응답 생성
        dialogue_system = DialogueSystem(
            Persona(persona1_data),
            Persona(persona2_data),
            connection_manager=manager,
            room_id=room_id,
        )
        print("dialogue_system")

        # main.py의 generate_dialogue 사용 - 이미 내부적으로 웹소켓 통신 구현되어 있음
        dialogue, summary = await dialogue_system.generate_dialogue(
            message.content, num_turns=3
        )

        conn.commit()
        return {"status": "success", "message": "메시지가 성공적으로 처리되었습니다"}

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
