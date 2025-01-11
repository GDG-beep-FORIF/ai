import json
import os
from datetime import datetime
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.markdown import Markdown

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
        self.console = Console()  # 임시 마크다운 출력용

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
5. 서로의 의견에 대해 건설적으로 토론하고 보완하는 방식으로 대화를 진행하세요.
6. 최종적으로 두 사람의 관점을 종합하여 유익한 조언을 제공하세요."""

        dialogue_messages = [{"role": "system", "content": system_prompt}]

        dialogue = []
        current_persona = self.persona1  # 첫 번째 페르소나부터 시작
        other_persona = self.persona2

        self.console.print(
            Markdown("\n# 대화 시작\n"), style="bold green"
        )  # 임시 마크다운 출력용

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

            # GPT 응답에서 화자 이름 제거
            content = response.choices[0].message.content
            speaker_name = current_persona.basic_info.get("name")
            content = content.replace(f"{speaker_name}: ", "")

            dialogue_turn = {
                "speaker": speaker_name,
                "content": content,
            }
            dialogue.append(dialogue_turn)

            # 임시 마크다운 출력용
            self.console.print(
                Markdown(f"\n## {dialogue_turn['speaker']}"), style="bold blue"
            )
            self.console.print(Markdown(content))
            self.console.print(Markdown("\n"))

            dialogue_messages.append({"role": "assistant", "content": content})

            # 다음 턴을 위해 페르소나 교체
            current_persona, other_persona = other_persona, current_persona

        self.console.print(
            Markdown("\n# 대화 종료\n\n"), style="bold red"
        )  # 임시 마크다운 출력용

        summary_prompt = """지금까지의 대화를 다음 형식으로 마크다운 요약을 작성해주세요:

# 대화 요약

## 주요 논점
- 각 페르소나가 제시한 핵심 주장

## 공통점과 차이점
- 두 페르소나의 관점 비교

## 핵심 조언
- 사용자에게 도움이 될 만한 주요 조언들

## 결론
사용자의 고민이나 질문에 대한 최종 조언 요약"""

        summary_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": summary_prompt},
                {"role": "user", "content": str(dialogue)},
            ],
        )

        summary = summary_response.choices[0].message.content

        self.console.print(Markdown(summary))  # 임시 마크다운 출력용

        return dialogue, summary


def format_dialogue(dialogue: List[Dict]) -> str:
    """
    대화 내용을 마크다운 형식으로 포맷팅
    """
    formatted = "# 페르소나 간 대화\n\n"
    for turn in dialogue:
        formatted += f"## {turn['speaker']}\n{turn['content']}\n\n"
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
            "name": "고죠 사토루",
            "birth_death": "1989-현재",
            "era": "현대",
            "nationality": "일본",
            "gender": "남성",
        },
        "professional": {
            "primary_occupation": "주술사, 교사",
            "other_roles": ["스승", "강사"],
            "major_achievements": [
                "무한을 다루는 주술사",
                "사상 최강의 주술사로 인정받음",
                "특급 주령 다수 봉인 및 제압",
                "도쿄 주술고등전문학교 교사로 활동하며 뛰어난 제자를 양성",
            ],
        },
        "personal": {
            "education": "도쿄 주술고등전문학교 졸업",
            "background": "천부적인 재능을 타고난 주술사로, 고죠 가문의 계승자",
            "personality_traits": [
                "자신감 넘치는 태도",
                "냉철하면서도 유머러스한 성격",
                "정의감이 강하고 동료를 소중히 여김",
                "위험에도 두려움 없이 행동",
            ],
            "influences": [
                "고죠 가문의 전통과 유산",
                "무한의 주술 기술",
                "주술 세계의 갈등과 불의",
                "제자들과 동료들에 대한 책임감",
            ],
        },
        "legacy": {
            "impact": "주술 세계의 균형을 유지하며 강력한 힘으로 악을 억제함",
            "modern_significance": "미래 주술사들에게 큰 영향을 끼치며, 정의와 강함의 상징이 됨",
        },
        "historical_context": {
            "period_background": "주령과의 싸움이 지속되는 현대 일본",
            "key_events": [
                "수많은 특급 주령과의 전투",
                "교토와 도쿄 주술사들의 대립 완화에 기여",
                "숙명의 적과의 대립",
                "특급 주령 '스쿠나'와 관련된 사건에 깊게 관여",
            ],
        },
    }

    # 페르소나 인스턴스 생성
    persona1 = Persona(persona1_data)
    persona2 = Persona(persona2_data)

    dialogue_system = DialogueSystem(persona1, persona2)

    # 임시 사용자 고민
    user_concern = "회사 상사에게 받는 스트레스를 어떻게 해결해야 할까요?"
    dialogue_system.generate_dialogue(user_concern)


if __name__ == "__main__":
    main()
