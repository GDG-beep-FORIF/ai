import json
import os
from datetime import datetime
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class Persona:
    def __init__(self, persona_data: Dict):
        """
        페르소나 데이터 초기화
        """
        self.basic_info = persona_data.get("basic_info", {})
        self.professional = persona_data.get("professional", {})
        self.personal = persona_data.get("personal", {})
        self.legacy = persona_data.get("legacy", {})
        self.historical_context = persona_data.get("historical_context", {})

    def get_prompt_context(self) -> str:
        """페르소나의 전체적인 컨텍스트 정보 생성"""
        achievements = "\n        - ".join(
            self.professional.get("major_achievements", [])
        )
        personality = "\n        - ".join(self.personal.get("personality_traits", []))
        key_events = "\n        - ".join(self.historical_context.get("key_events", []))

        return f"""
        === 페르소나 프로필 ===
        
        1. 기본 정보
        - 이름: {self.basic_info.get('name')}
        - 시대: {self.basic_info.get('era')}
        - 생몰년: {self.basic_info.get('birth_death')}
        - 국적: {self.basic_info.get('nationality')}
        - 성별: {self.basic_info.get('gender')}

        2. 전문적 경력
        - 주요 직업: {self.professional.get('primary_occupation')}
        - 주요 업적:
        - {achievements}
        
        3. 개인적 배경
        - 교육: {self.personal.get('education')}
        - 배경: {self.personal.get('background')}
        - 성격 특성:
        - {personality}
        
        4. 영향력과 유산
        - 역사적 영향: {self.legacy.get('impact')}
        - 현대적 의의: {self.legacy.get('modern_significance')}
        
        5. 시대적 배경
        - 시대 상황: {self.historical_context.get('period_background')}
        - 주요 사건:
        - {key_events}
        """


class DialogueSystem:
    def __init__(self, persona1: Persona, persona2: Persona):
        """
        대화 시스템 초기화
        """
        self.persona1 = persona1
        self.persona2 = persona2

    def generate_dialogue(
        self, user_concern: str, num_turns: int = 3
    ) -> Tuple[List[Dict], str]:
        """
        페르소나 간 대화 생성 및 요약
        """

        system_prompt = f"""당신은 두 역사적 인물 간의 대화를 생성해야 합니다.
        
첫 번째 페르소나:
{self.persona1.get_prompt_context()}

두 번째 페르소나:
{self.persona2.get_prompt_context()}

사용자의 고민: {user_concern}

다음 지침을 따라 대화를 생성하세요:
1. 각 페르소나는 자신의 경험과 관점에서 사용자의 고민에 대해 조언해야 합니다.
2. 대화는 자연스럽게 이어져야 하며, 각자의 시대적 배경과 가치관이 반영되어야 합니다.
3. 페르소나의 성격 특성과 말투를 반영하여 대화를 생성하세요.
4. 역사적 맥락과 개인적 경험을 연결지어 조언하도록 합니다.
5. 서로의 의견에 대해 건설적으로 토론하고 보완하는 방식으로 대화를 진행하세요."""

        dialogue_messages = [{"role": "system", "content": system_prompt}]

        dialogue = []
        current_persona = self.persona1  # 첫 번째 페르소나부터 시작
        other_persona = self.persona2

        for turn in range(num_turns * 2):
            prompt = f"""현재 말하는 페르소나는 {current_persona.basic_info.get('name')}입니다.
상대 페르소나는 {other_persona.basic_info.get('name')}입니다.

이전 대화를 고려하여, {current_persona.basic_info.get('name')}의 관점에서 대화를 이어가세요.
페르소나의 시대적 배경, 경험, 성격을 반영한 자연스러운 대화를 생성해주세요.
현재 턴이 {turn + 1}/{num_turns * 2}입니다. 마지막 턴에 가까워질수록 대화를 자연스럽게 마무리해주세요."""

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=dialogue_messages + [{"role": "user", "content": prompt}],
            )

            dialogue_turn = {
                "speaker": current_persona.basic_info.get("name"),
                "content": response.choices[0].message.content,
            }
            dialogue.append(dialogue_turn)

            dialogue_messages.append(
                {"role": "assistant", "content": response.choices[0].message.content}
            )

            # 다음 턴을 위해 페르소나 교체
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
간단한 결론 정리"""

        summary_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": summary_prompt},
                {"role": "user", "content": str(dialogue)},
            ],
        )

        summary = summary_response.choices[0].message.content

        return dialogue, summary


def format_dialogue(dialogue: List[Dict]) -> str:
    """
    대화 내용을 마크다운 형식으로 포맷팅
    """
    formatted = "# 페르소나 간 대화\n\n"
    for turn in dialogue:
        formatted += f"### {turn['speaker']}\n{turn['content']}\n\n"
    return formatted


def main():
    persona1_data = {
        "basic_info": {
            "name": "퇴계 이황",
            "birth_death": "1501-1570",
            "era": "조선 중기",
            "nationality": "조선",
            "gender": "남성",
        },
        "professional": {
            "primary_occupation": "성리학자, 교육자",
            "other_roles": ["정치인", "시인", "문인"],
            "major_achievements": [
                "주자학의 심도 있는 연구와 발전",
                "『성학십도』 저술",
                "도산서원 설립",
                "사단칠정론 확립",
            ],
        },
        "personal": {
            "education": "성균관에서 수학",
            "background": "어려서부터 학문에 전념하였으며, 29세에 과거에 급제",
            "personality_traits": [
                "신중하고 사려깊은 성격",
                "학문에 대한 진지한 태도",
                "검소하고 겸손한 생활",
                "자연과의 조화를 중시",
            ],
            "influences": [
                "주자학",
                "불교와 도교의 영향",
                "자연과의 교감",
                "시대적 혼란",
            ],
        },
        "legacy": {
            "impact": "조선 성리학의 이론적 체계를 확립하고, 교육의 중요성을 강조하여 많은 제자를 양성함",
            "modern_significance": "현대 한국의 교육 철학과 자기수양 방법론에 큰 영향을 미침",
        },
        "historical_context": {
            "period_background": "조선 중기의 정치적 안정기와 성리학의 발전기",
            "key_events": [
                "중종대의 정치적 변동",
                "사화와 훈구파의 몰락",
                "성리학의 심화 발전",
                "서원 교육의 확대",
            ],
        },
    }

    persona2_data = {
        "basic_info": {
            "name": "버지니아 울프",
            "birth_death": "1882-1941",
            "era": "빅토리아 후기-모더니즘",
            "nationality": "영국",
            "gender": "여성",
        },
        "professional": {
            "primary_occupation": "소설가, 에세이스트",
            "other_roles": ["페미니스트", "출판인", "문학 비평가"],
            "major_achievements": [
                "『댈러웨이 부인』 집필",
                "『자기만의 방』 출간",
                "호가스 출판사 설립",
                "모더니즘 문학의 혁신",
            ],
        },
        "personal": {
            "education": "킹스 칼리지 런던에서 그리스어와 역사 학습",
            "background": "지적인 중산층 가정에서 성장, 블룸즈버리 그룹의 중심인물",
            "personality_traits": [
                "예민하고 섬세한 감수성",
                "진보적 사고방식",
                "실험적이고 혁신적인 성향",
                "내면의 갈등과 우울",
            ],
            "influences": [
                "빅토리아 시대의 사회적 제약",
                "여성의 권리 신장 운동",
                "심리학의 발전",
                "1차 세계대전",
            ],
        },
        "legacy": {
            "impact": "현대 소설의 기법을 혁신하고 페미니즘 문학의 기반을 마련",
            "modern_significance": "현대 여성 문학과 실험적 서사 기법에 지속적인 영향을 미침",
        },
        "historical_context": {
            "period_background": "빅토리아 시대 말기부터 모더니즘 시대까지의 급격한 사회 변화기",
            "key_events": [
                "여성 참정권 운동",
                "제1차 세계대전",
                "모더니즘 운동의 발전",
                "정신의학의 발전",
            ],
        },
    }

    # 페르소나 인스턴스 생성
    persona1 = Persona(persona1_data)
    persona2 = Persona(persona2_data)

    dialogue_system = DialogueSystem(persona1, persona2)

    user_concern = "직장에서의 스트레스 해소 방법에 대해 고민이 있습니다."
    dialogue, summary = dialogue_system.generate_dialogue(user_concern)

    print(format_dialogue(dialogue))
    print(summary)


if __name__ == "__main__":
    main()
