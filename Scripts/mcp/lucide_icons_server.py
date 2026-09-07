"""Lucide Icons MCP Server - 아이콘 검색 API"""
import json
import asyncio
from typing import Any
import httpx
from pathlib import Path


class LucideIconsServer:
    """Lucide Icons 아이콘 검색 MCP 서버"""

    def __init__(self):
        self.icons_cache = None
        self.cache_path = Path(__file__).parent / "lucide_icons_cache.json"

    async def load_icons(self):
        """아이콘 데이터 로드"""
        if self.icons_cache is not None:
            return self.icons_cache

        # 캐시 파일에서 로드
        if self.cache_path.exists():
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                self.icons_cache = json.load(f)
                return self.icons_cache

        # GitHub에서 다운로드
        try:
            url = "https://cdn.jsdelivr.net/npm/lucide@latest/dist/icons.json"
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10)
                if response.status_code == 200:
                    self.icons_cache = response.json()
                    # 캐시 저장
                    self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.cache_path, 'w', encoding='utf-8') as f:
                        json.dump(self.icons_cache, f, ensure_ascii=False, indent=2)
                    return self.icons_cache
        except Exception as e:
            print(f"아이콘 로드 실패: {e}")

        return {}

    async def search_icons(self, query: str, limit: int = 10) -> list[dict]:
        """아이콘 검색

        Args:
            query: 검색어 (아이콘 이름)
            limit: 최대 결과 개수 (기본값: 10)

        Returns:
            검색 결과 리스트
        """
        icons = await self.load_icons()
        query_lower = query.lower()

        results = []
        for icon_name, icon_data in icons.items():
            if query_lower in icon_name.lower():
                results.append({
                    "name": icon_name,
                    "tags": icon_data.get("tags", []),
                    "categories": icon_data.get("categories", [])
                })
                if len(results) >= limit:
                    break

        return results

    async def get_icon_info(self, icon_name: str) -> dict | None:
        """특정 아이콘 정보 조회

        Args:
            icon_name: 아이콘 이름

        Returns:
            아이콘 정보 또는 None
        """
        icons = await self.load_icons()
        icon_name_lower = icon_name.lower()

        for name, data in icons.items():
            if name.lower() == icon_name_lower:
                return {
                    "name": name,
                    "tags": data.get("tags", []),
                    "categories": data.get("categories", []),
                    "description": f"Lucide icon: {name}"
                }

        return None

    async def list_categories(self) -> list[str]:
        """모든 카테고리 목록 조회"""
        icons = await self.load_icons()
        categories = set()

        for icon_data in icons.values():
            categories.update(icon_data.get("categories", []))

        return sorted(list(categories))

    async def list_icons_by_category(self, category: str) -> list[str]:
        """카테고리별 아이콘 목록 조회

        Args:
            category: 카테고리 이름

        Returns:
            아이콘 이름 리스트
        """
        icons = await self.load_icons()
        result = []

        for icon_name, icon_data in icons.items():
            if category in icon_data.get("categories", []):
                result.append(icon_name)

        return sorted(result)


async def main():
    """테스트용 메인 함수"""
    server = LucideIconsServer()

    print("=== Lucide Icons MCP 서버 테스트 ===\n")

    # 검색 테스트
    print("1. 아이콘 검색 (query='arrow'):")
    results = await server.search_icons("arrow", limit=5)
    for icon in results:
        print(f"  - {icon['name']}")

    print("\n2. 카테고리 목록:")
    categories = await server.list_categories()
    print(f"  총 {len(categories)}개 카테고리")
    print(f"  {', '.join(categories[:10])}...")

    print("\n3. 특정 아이콘 정보 (icon_name='search'):")
    icon_info = await server.get_icon_info("search")
    if icon_info:
        print(f"  {json.dumps(icon_info, ensure_ascii=False, indent=2)}")
    else:
        print("  아이콘을 찾을 수 없습니다.")


if __name__ == "__main__":
    asyncio.run(main())
