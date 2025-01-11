import requests
from typing import Dict, Optional
from datetime import datetime

class WikipediaPersonSearch:
    def __init__(self, language: str = 'ko'):
        """
        위키피디아 API를 사용하여 인물을 검색하는 클래스
        
        Args:
            language (str): 위키피디아 언어 설정 (기본값: 'ko' - 한국어)
        """
        self.base_url = f"https://{language}.wikipedia.org/w/api.php"
        self.session = requests.Session()
    
    def extract_birth_death(self, content: str) -> str:
        """
        본문에서 생몰년 정보를 추출
        """
        # 간단한 예시 - 실제로는 더 복잡한 패턴 매칭이 필요할 수 있음
        try:
            first_paragraph = content.split('\n')[0]
            if '년' in first_paragraph and '월' in first_paragraph:
                return first_paragraph.split('(')[1].split(')')[0]
            return "정보 없음"
        except:
            return "정보 없음"

    def extract_nationality(self, categories: list) -> str:
        """
        카테고리에서 국적 정보 추출
        """
        nationality_keywords = ['대한민국', '조선', '한국', '일본', '중국', '미국', '영국']
        for category in categories:
            for keyword in nationality_keywords:
                if keyword in category:
                    return keyword
        return "정보 없음"

    def search_person(self, name: str, summary_only: bool = False) -> Optional[Dict]:
        """
        이름으로 인물을 검색하고 관련 정보를 반환
        
        Args:
            name (str): 검색할 인물 이름
            summary_only (bool): True면 요약만, False면 전체 내용 반환
            
        Returns:
            Dict: 검색된 인물 정보를 담은 딕셔너리
            None: 검색 결과가 없는 경우
        """
        # 1. 검색어와 가장 일치하는 페이지 찾기
        search_params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": name,
            "srprop": "snippet",
            "srlimit": 1
        }
        
        search_response = self.session.get(url=self.base_url, params=search_params)
        search_data = search_response.json()
        
        if not search_data["query"]["search"]:
            return None
            
        page_id = search_data["query"]["search"][0]["pageid"]
        
        # 2. 페이지 상세 정보 가져오기
        detail_params = {
            "action": "query",
            "format": "json",
            "prop": "extracts|pageimages|info|categories|sections|langlinks",
            "exintro": summary_only,
            "explaintext": True,
            "inprop": "url|displaytitle",
            "piprop": "original",
            "pageids": page_id,
            "cllimit": "max",
            "llprop": "url|langname",
            "lllimit": "max"
        }
        
        detail_response = self.session.get(url=self.base_url, params=detail_params)
        detail_data = detail_response.json()
        
        page_data = detail_data["query"]["pages"][str(page_id)]
        
        # 3. 섹션 정보 가져오기
        sections_params = {
            "action": "parse",
            "format": "json",
            "pageid": page_id,
            "prop": "sections"
        }
        
        sections_response = self.session.get(url=self.base_url, params=sections_params)
        sections_data = sections_response.json()
        
        # 4. 결과 데이터 구성
        content = page_data.get("extract", "")
        categories = [cat["title"].replace("Category:", "") for cat in page_data.get("categories", [])]
        
        result = {
            "basic_info": {
                "title": page_data.get("title"),
                "birth_death": self.extract_birth_death(content),
                "nationality": self.extract_nationality(categories),
                "image_url": page_data.get("original", {}).get("source") if "original" in page_data else None,
            },
            "content": content,
            "url": page_data.get("fullurl"),
            "categories": categories,
            "sections": [
                {
                    "title": section["line"],
                    "level": section["level"],
                    "index": section["index"]
                }
                for section in sections_data.get("parse", {}).get("sections", [])
            ],
            "other_languages": [
                {
                    "language": lang["langname"],
                    "url": lang["url"]
                }
                for lang in page_data.get("langlinks", [])
            ]
        }
        
        return result