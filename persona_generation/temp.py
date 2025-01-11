from openai import OpenAI
from typing import Dict, Any
import json
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()

async def generate_persona(wiki_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wikipedia 데이터를 기반으로 GPT를 사용하여 상세한 persona 정보를 생성
    
    Args:
        wiki_data (Dict[str, Any]): Wikipedia API에서 가져온 인물 정보
        
    Returns:
        Dict[str, Any]: 생성된 persona 정보
    """
    
    # System prompt 구성
    system_message = {
        "role": "system",
        "content": [
            {
                "type": "text",
                "text": f"""다음 Wikipedia 정보를 기반으로 상세한 인물 프로필을 생성해주세요:

제목: {wiki_data['basic_info']['title']}
생몰년: {wiki_data['basic_info']['birth_death']}
국적: {wiki_data['basic_info']['nationality']}
내용: {wiki_data['content'][:3000]}  # 처음 3000자만 사용

카테고리: {', '.join(wiki_data['categories'][:10])}

다음 구조에 맞춰 프로필을 생성해주세요:
1. 기본 정보 (시대, 성별 포함)
2. 전문적 경력 (주요 직업, 다른 역할들, 주요 업적)
3. 개인적 정보 (교육, 배경, 성격 특성, 영향받은 요소들)
4. 유산/영향력 (역사적 영향, 현대적 의의)
5. 역사적 맥락 (시대적 배경, 주요 사건들)

가능한 한 상세하고 정확하게 작성해주세요."""
            }
        ]
    }

    # GPT API 호출
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
            "role": "system",
            "content": [
                {
                "type": "text",
                "text": f"{system_message}"
                }
            ]
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
            "name": "historical_figure_persona_profile",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                "basic_info": {
                    "type": "object",
                    "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the historical figure or Wikipedia page URL."
                    },
                    "birth_death": {
                        "type": "string",
                        "description": "Birth and death years."
                    },
                    "era": {
                        "type": "string",
                        "description": "Era during which the figure lived."
                    },
                    "nationality": {
                        "type": "string",
                        "description": "Nationality or origin of the historical figure."
                    },
                    "gender": {
                        "type": "string",
                        "description": "Gender of the historical figure."
                    }
                    },
                    "required": [
                    "name",
                    "birth_death",
                    "era",
                    "nationality",
                    "gender"
                    ],
                    "additionalProperties": False
                },
                "professional": {
                    "type": "object",
                    "properties": {
                    "primary_occupation": {
                        "type": "string",
                        "description": "Primary occupation of the historical figure."
                    },
                    "other_roles": {
                        "type": "array",
                        "description": "Other roles the historical figure was involved in.",
                        "items": {
                        "type": "string"
                        }
                    },
                    "major_achievements": {
                        "type": "array",
                        "description": "Significant achievements of the historical figure.",
                        "items": {
                        "type": "string"
                        }
                    }
                    },
                    "required": [
                    "primary_occupation",
                    "other_roles",
                    "major_achievements"
                    ],
                    "additionalProperties": False
                },
                "personal": {
                    "type": "object",
                    "properties": {
                    "education": {
                        "type": "string",
                        "description": "Educational background of the historical figure."
                    },
                    "background": {
                        "type": "string",
                        "description": "Background information about the figure."
                    },
                    "personality_traits": {
                        "type": "array",
                        "description": "Traits or characteristics of the historical figure.",
                        "items": {
                        "type": "string"
                        }
                    },
                    "influences": {
                        "type": "array",
                        "description": "Influences on the historical figure's life.",
                        "items": {
                        "type": "string"
                        }
                    }
                    },
                    "required": [
                    "education",
                    "background",
                    "personality_traits",
                    "influences"
                    ],
                    "additionalProperties": False
                },
                "legacy": {
                    "type": "object",
                    "properties": {
                    "impact": {
                        "type": "string",
                        "description": "The impact the historical figure had on history."
                    },
                    "modern_significance": {
                        "type": "string",
                        "description": "The modern significance of the historical figure."
                    }
                    },
                    "required": [
                    "impact",
                    "modern_significance"
                    ],
                    "additionalProperties": False
                },
                "historical_context": {
                    "type": "object",
                    "properties": {
                    "period_background": {
                        "type": "string",
                        "description": "Socio-cultural background of the period in which the figure lived."
                    },
                    "key_events": {
                        "type": "array",
                        "description": "Key events that were influential during the historical figure's lifetime.",
                        "items": {
                        "type": "string"
                        }
                    }
                    },
                    "required": [
                    "period_background",
                    "key_events"
                    ],
                    "additionalProperties": False
                }
                },
                "required": [
                "basic_info",
                "professional",
                "personal",
                "legacy",
                "historical_context"
                ],
                "additionalProperties": False
            }
            }
        },
        temperature=1,
        max_tokens=8192
    )

    # Wikipedia 데이터에서 가져온 기본 정보 추가
    persona_data = json.loads(response.choices[0].message.content)
    
    # Wikipedia에서 가져온 기본 정보로 업데이트
    persona_data["basic_info"].update({
        "name": wiki_data["basic_info"]["title"],
        "birth_death": wiki_data["basic_info"]["birth_death"],
        "nationality": wiki_data["basic_info"]["nationality"]
    })

    return persona_data