"""
Web Search Tool using DuckDuckGo.
"""

from langchain_core.tools import tool

try:
    from langchain_community.tools import DuckDuckGoSearchRun
    _ddg = DuckDuckGoSearchRun(region="us-en")
except Exception:
    _ddg = None


@tool
def web_search(query: str) -> str:
    """Search the web for real-time information, news, current events, or any topic not in the document."""
    try:
        if _ddg is not None:
            return _ddg.run(query)
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
            if results:
                return "\n\n".join(
                    [f"**{r.get('title', '')}**\n{r.get('body', '')}\nURL: {r.get('href', '')}" for r in results]
                )
            return "No search results found."
    except Exception as e:
        return f"Error executing web search: {e}"
