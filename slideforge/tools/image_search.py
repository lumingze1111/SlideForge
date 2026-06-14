"""
图片搜索工具 - 集成 Unsplash 和 Pexels API
"""

import os
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import requests
from enum import Enum


class ImageSource(str, Enum):
    """图片来源"""
    UNSPLASH = "unsplash"
    PEXELS = "pexels"


@dataclass
class ImageResult:
    """图片搜索结果"""
    url: str
    description: str
    author: str
    source: ImageSource
    width: int
    height: int
    download_url: str  # 用于实际下载的 URL


class ImageSearchError(Exception):
    """图片搜索错误"""
    pass


class ImageSearchTool:
    """图片搜索工具"""

    def __init__(self):
        self.unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")
        self.pexels_key = os.getenv("PEXELS_API_KEY")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SlideForge/1.0"
        })

    def search(
        self,
        query: str,
        limit: int = 5,
        orientation: Optional[str] = None,
        preferred_source: Optional[ImageSource] = None
    ) -> List[ImageResult]:
        """
        搜索图片

        Args:
            query: 搜索关键词
            limit: 返回结果数量
            orientation: 图片方向 ('landscape', 'portrait', 'squarish')
            preferred_source: 优先使用的图片源

        Returns:
            图片结果列表

        Raises:
            ImageSearchError: 搜索失败时抛出
        """
        # 确定搜索顺序
        sources = []
        if preferred_source:
            sources.append(preferred_source)
            # 添加其他源作为备选
            if preferred_source == ImageSource.UNSPLASH and self.pexels_key:
                sources.append(ImageSource.PEXELS)
            elif preferred_source == ImageSource.PEXELS and self.unsplash_key:
                sources.append(ImageSource.UNSPLASH)
        else:
            # 默认优先 Unsplash
            if self.unsplash_key:
                sources.append(ImageSource.UNSPLASH)
            if self.pexels_key:
                sources.append(ImageSource.PEXELS)

        if not sources:
            raise ImageSearchError(
                "No image search API keys configured. "
                "Please set UNSPLASH_ACCESS_KEY or PEXELS_API_KEY"
            )

        # 依次尝试各个源
        last_error = None
        for source in sources:
            try:
                if source == ImageSource.UNSPLASH:
                    return self._search_unsplash(query, limit, orientation)
                elif source == ImageSource.PEXELS:
                    return self._search_pexels(query, limit, orientation)
            except Exception as e:
                last_error = e
                continue

        # 所有源都失败
        raise ImageSearchError(f"All image sources failed. Last error: {last_error}")

    def _search_unsplash(
        self,
        query: str,
        limit: int,
        orientation: Optional[str]
    ) -> List[ImageResult]:
        """搜索 Unsplash"""
        if not self.unsplash_key:
            raise ImageSearchError("UNSPLASH_ACCESS_KEY not configured")

        url = "https://api.unsplash.com/search/photos"
        params = {
            "query": query,
            "per_page": limit,
            "client_id": self.unsplash_key
        }
        if orientation:
            params["orientation"] = orientation

        # 重试机制
        for attempt in range(3):
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                results = []
                for item in data.get("results", []):
                    results.append(ImageResult(
                        url=item["urls"]["regular"],
                        description=item.get("description") or item.get("alt_description") or query,
                        author=item["user"]["name"],
                        source=ImageSource.UNSPLASH,
                        width=item["width"],
                        height=item["height"],
                        download_url=item["urls"]["raw"]
                    ))

                return results

            except requests.Timeout:
                if attempt == 2:
                    raise ImageSearchError("Unsplash API timeout after 3 attempts")
                time.sleep(2 ** attempt)  # 指数退避

            except requests.HTTPError as e:
                if e.response.status_code == 429:
                    raise ImageSearchError("Unsplash API rate limit exceeded")
                elif e.response.status_code == 401:
                    raise ImageSearchError("Invalid Unsplash API key")
                else:
                    raise ImageSearchError(f"Unsplash API error: {e}")

            except Exception as e:
                raise ImageSearchError(f"Unsplash search failed: {e}")

        return []

    def _search_pexels(
        self,
        query: str,
        limit: int,
        orientation: Optional[str]
    ) -> List[ImageResult]:
        """搜索 Pexels"""
        if not self.pexels_key:
            raise ImageSearchError("PEXELS_API_KEY not configured")

        url = "https://api.pexels.com/v1/search"
        params = {
            "query": query,
            "per_page": limit
        }
        if orientation:
            params["orientation"] = orientation

        headers = {
            "Authorization": self.pexels_key
        }

        # 重试机制
        for attempt in range(3):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()

                results = []
                for item in data.get("photos", []):
                    results.append(ImageResult(
                        url=item["src"]["large"],
                        description=item.get("alt") or query,
                        author=item["photographer"],
                        source=ImageSource.PEXELS,
                        width=item["width"],
                        height=item["height"],
                        download_url=item["src"]["original"]
                    ))

                return results

            except requests.Timeout:
                if attempt == 2:
                    raise ImageSearchError("Pexels API timeout after 3 attempts")
                time.sleep(2 ** attempt)

            except requests.HTTPError as e:
                if e.response.status_code == 429:
                    raise ImageSearchError("Pexels API rate limit exceeded")
                elif e.response.status_code == 401:
                    raise ImageSearchError("Invalid Pexels API key")
                else:
                    raise ImageSearchError(f"Pexels API error: {e}")

            except Exception as e:
                raise ImageSearchError(f"Pexels search failed: {e}")

        return []

    def download_image(self, image: ImageResult, save_path: str) -> str:
        """
        下载图片到本地

        Args:
            image: 图片结果
            save_path: 保存路径

        Returns:
            保存的文件路径
        """
        try:
            response = self.session.get(image.download_url, timeout=30, stream=True)
            response.raise_for_status()

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return save_path

        except Exception as e:
            raise ImageSearchError(f"Failed to download image: {e}")


# 创建全局实例
_image_search_tool = None


def get_image_search_tool() -> ImageSearchTool:
    """获取图片搜索工具单例"""
    global _image_search_tool
    if _image_search_tool is None:
        _image_search_tool = ImageSearchTool()
    return _image_search_tool
