from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uuid
from wiki import WikipediaPersonSearch
from gpt_generator import generate_persona
import psycopg2
from psycopg2.extras import DictCursor
from typing import Dict
import json

app = FastAPI()

# Database configuration
DATABASE_CONFIG = {
    "dbname": "postgres",
    "user": "postgres.baeuipvrxxdsidfkwmvn",
    "password": "4CipIRLuLkYavf3X",
    "host": "aws-0-ap-northeast-2.pooler.supabase.com",
    "port": "6543"
}

# Pydantic models for request/response
class PersonaRequest(BaseModel):
    name: str

def get_db_connection():
    return psycopg2.connect(**DATABASE_CONFIG)

async def insert_persona_data(persona_data: Dict, wiki_data: Dict) -> str:
    person_id = str(uuid.uuid4())
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                # Begin transaction
                cur.execute("BEGIN")
                
                # 1. Insert basic info
                cur.execute("""
                    INSERT INTO basic_info (person_id, name, birth_death, era, nationality, gender, image_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    person_id,
                    persona_data["basic_info"]["name"],
                    persona_data["basic_info"]["birth_death"],
                    persona_data["basic_info"]["era"],
                    persona_data["basic_info"]["nationality"],
                    persona_data["basic_info"]["gender"],
                    wiki_data.get("basic_info", {}).get("image_url")
                ))

                # 2. Insert professional info
                cur.execute("""
                    INSERT INTO professional_info (person_id, primary_occupation)
                    VALUES (%s, %s)
                """, (person_id, persona_data["professional"]["primary_occupation"]))

                # 3. Insert other roles
                for role in persona_data["professional"]["other_roles"]:
                    cur.execute("""
                        INSERT INTO other_roles (person_id, role_name)
                        VALUES (%s, %s)
                    """, (person_id, role))

                # 4. Insert major achievements
                for achievement in persona_data["professional"]["major_achievements"]:
                    cur.execute("""
                        INSERT INTO major_achievements (person_id, achievement_name)
                        VALUES (%s, %s)
                    """, (person_id, achievement))

                # 5. Insert personal info
                cur.execute("""
                    INSERT INTO personal_info (person_id, education, background)
                    VALUES (%s, %s, %s)
                """, (
                    person_id,
                    persona_data["personal"]["education"],
                    persona_data["personal"]["background"]
                ))

                # 6. Insert personality traits
                for trait in persona_data["personal"]["personality_traits"]:
                    cur.execute("""
                        INSERT INTO personality_traits (person_id, trait_name)
                        VALUES (%s, %s)
                    """, (person_id, trait))

                # 7. Insert influences
                for influence in persona_data["personal"]["influences"]:
                    cur.execute("""
                        INSERT INTO influences (person_id, influence_name)
                        VALUES (%s, %s)
                    """, (person_id, influence))

                # 8. Insert legacy
                cur.execute("""
                    INSERT INTO legacy (person_id, impact, modern_significance)
                    VALUES (%s, %s, %s)
                """, (
                    person_id,
                    persona_data["legacy"]["impact"],
                    persona_data["legacy"]["modern_significance"]
                ))

                # 9. Insert historical context
                cur.execute("""
                    INSERT INTO historical_context (person_id, period_background)
                    VALUES (%s, %s)
                """, (
                    person_id,
                    persona_data["historical_context"]["period_background"]
                ))

                # 10. Insert key events
                for event in persona_data["historical_context"]["key_events"]:
                    cur.execute("""
                        INSERT INTO key_events (person_id, event_description)
                        VALUES (%s, %s)
                    """, (person_id, event))

                # Commit transaction
                conn.commit()
                return person_id

            except Exception as e:
                conn.rollback()
                raise e

@app.post("/persona_generator")
async def create_persona(request: PersonaRequest):
    try:
        # 1. Wikipedia에서 데이터 가져오기
        wiki_search = WikipediaPersonSearch()
        wiki_data = wiki_search.search_person(request.name, summary_only=False)
        
        if not wiki_data:
            raise HTTPException(status_code=404, detail="Person not found in Wikipedia")

        # 2. GPT를 통해 persona 생성
        persona_data = await generate_persona(wiki_data)
        print(persona_data)
        # 3. DB에 데이터 저장
        person_id = await insert_persona_data(persona_data, wiki_data)
        return {"status": "success", "person_id": person_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)