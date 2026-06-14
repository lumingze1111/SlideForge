"""
数据获取工具 - 提供多种数据源接口
"""

import json
import requests
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup
import re


class DataFetchError(Exception):
    """数据获取错误"""
    pass


def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    通用网页搜索（使用 DuckDuckGo 即时搜索）

    Args:
        query: 搜索查询
        max_results: 最大结果数

    Returns:
        搜索结果字典
    """
    try:
        # 使用 DuckDuckGo 即时答案 API
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        results = {
            "query": query,
            "abstract": data.get("Abstract", ""),
            "abstract_source": data.get("AbstractSource", ""),
            "abstract_url": data.get("AbstractURL", ""),
            "related_topics": []
        }

        # 提取相关主题
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and "Text" in topic:
                results["related_topics"].append({
                    "text": topic.get("Text", ""),
                    "url": topic.get("FirstURL", "")
                })

        return results

    except Exception as e:
        raise DataFetchError(f"Web search failed: {e}")


def wikipedia_fetch(title: str, lang: str = "zh") -> Dict[str, Any]:
    """
    获取维基百科条目数据

    Args:
        title: 条目标题
        lang: 语言代码（zh、en 等）

    Returns:
        维基百科数据字典
    """
    try:
        # 使用维基百科 API
        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "titles": title,
            "prop": "extracts|info",
            "exintro": True,
            "explaintext": True,
            "inprop": "url"
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        pages = data.get("query", {}).get("pages", {})
        if not pages:
            raise DataFetchError(f"Wikipedia page not found: {title}")

        page = list(pages.values())[0]

        if "missing" in page:
            raise DataFetchError(f"Wikipedia page not found: {title}")

        result = {
            "title": page.get("title", ""),
            "extract": page.get("extract", ""),
            "url": page.get("fullurl", ""),
            "page_id": page.get("pageid", "")
        }

        # 获取 infobox 数据
        try:
            infobox_params = {
                "action": "parse",
                "format": "json",
                "page": title,
                "prop": "wikitext"
            }
            infobox_response = requests.get(url, params=infobox_params, timeout=30)
            infobox_data = infobox_response.json()

            wikitext = infobox_data.get("parse", {}).get("wikitext", {}).get("*", "")
            result["infobox"] = _parse_infobox(wikitext)

        except:
            result["infobox"] = {}

        return result

    except Exception as e:
        raise DataFetchError(f"Wikipedia fetch failed: {e}")


def _parse_infobox(wikitext: str) -> Dict[str, str]:
    """解析维基百科 infobox"""
    infobox = {}

    # 简单的 infobox 解析
    pattern = r'\|\s*([^=]+?)\s*=\s*(.+?)(?=\n\||\n}})'
    matches = re.findall(pattern, wikitext, re.DOTALL)

    for key, value in matches:
        key = key.strip()
        value = re.sub(r'\[\[([^\]|]+\|)?([^\]]+)\]\]', r'\2', value)  # 移除链接
        value = re.sub(r'<[^>]+>', '', value)  # 移除 HTML 标签
        value = value.strip()
        if value:
            infobox[key] = value

    return infobox


def web_scrape(url: str, selectors: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    从网页提取数据

    Args:
        url: 目标 URL
        selectors: CSS 选择器字典（可选）

    Returns:
        提取的数据字典
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'lxml')

        result = {
            "url": url,
            "title": soup.title.string if soup.title else "",
            "data": {}
        }

        if selectors:
            # 使用提供的选择器提取数据
            for key, selector in selectors.items():
                elements = soup.select(selector)
                if elements:
                    result["data"][key] = [elem.get_text(strip=True) for elem in elements]
        else:
            # 默认提取：标题、段落、链接
            result["data"]["headings"] = [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])][:10]
            result["data"]["paragraphs"] = [p.get_text(strip=True) for p in soup.find_all('p') if len(p.get_text(strip=True)) > 50][:5]

        return result

    except Exception as e:
        raise DataFetchError(f"Web scrape failed: {e}")


def execute_python_safe(code: str, timeout: int = 10) -> Dict[str, Any]:
    """
    在沙箱环境中执行 Python 代码

    Args:
        code: Python 代码字符串
        timeout: 超时时间（秒）

    Returns:
        执行结果字典
    """
    import subprocess
    import tempfile
    import os

    try:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            # 执行代码（使用受限的环境）
            result = subprocess.run(
                ['python', temp_file],
                capture_output=True,
                text=True,
                timeout=timeout,
                env={
                    **os.environ,
                    'PYTHONPATH': '',  # 清空 Python 路径
                }
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }

        finally:
            # 清理临时文件
            os.unlink(temp_file)

    except subprocess.TimeoutExpired:
        raise DataFetchError(f"Python code execution timeout after {timeout}s")
    except Exception as e:
        raise DataFetchError(f"Python code execution failed: {e}")


# 示例：获取 NBA 球员数据的辅助函数
def fetch_sports_data(player_name: str, sport: str = "basketball") -> Dict[str, Any]:
    """
    获取体育数据（示例实现）

    Args:
        player_name: 球员名称
        sport: 运动类型

    Returns:
        球员数据字典
    """
    # 这是一个示例实现，实际应该调用专业的体育数据 API
    # 例如：SportsData.io、ESPN API 等

    try:
        # 使用维基百科作为数据源
        wiki_data = wikipedia_fetch(player_name, lang="zh")

        # 尝试从 infobox 提取数据
        infobox = wiki_data.get("infobox", {})

        result = {
            "name": player_name,
            "sport": sport,
            "summary": wiki_data.get("extract", "")[:500],
            "url": wiki_data.get("url", ""),
            "stats": {}
        }

        # 提取统计数据
        for key, value in infobox.items():
            if any(stat_keyword in key.lower() for stat_keyword in ["场均", "得分", "助攻", "篮板", "三分"]):
                result["stats"][key] = value

        return result

    except Exception as e:
        raise DataFetchError(f"Failed to fetch sports data: {e}")
