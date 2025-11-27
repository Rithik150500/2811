"""
web_research_tools.py

Implements web search and fetch capabilities that allow agents to research
external legal context, statutes, regulations, and case law.
"""

from langchain.tools import tool
import requests
from typing import Optional
import os

# You would typically use a proper search API like Tavily, Brave, or similar
# This is a simplified example showing the pattern
SEARCH_API_KEY = os.environ.get("SEARCH_API_KEY")
SEARCH_API_URL = "https://api.tavily.com/search"

# Track web fetch usage
_web_fetch_count = 0
_WEB_FETCH_LIMIT = 20


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web for legal information, statutes, regulations, or case law.
    
    Use this tool to find external legal context that helps interpret or
    analyze provisions found in the data room documents. Search for:
    - Applicable statutes and regulations
    - Legal standards and requirements
    - Case law and legal precedents
    - Industry best practices
    - Regulatory guidance
    
    This tool returns search results with titles, URLs, and snippets. Review
    the results to identify authoritative sources, then use web_fetch to
    retrieve full content from the most relevant sources.
    
    This tool has no usage limits and does not require approval.
    
    Args:
        query: Search query (e.g., "Delaware corporate governance requirements")
        max_results: Maximum number of results to return (default 5)
    
    Returns:
        Formatted search results with titles, URLs, and snippets
    """
    if not query.strip():
        return "Error: Please provide a search query"
    
    try:
        # Make the search API call
        # This is a simplified example - in production you would use a real API
        response = requests.post(
            SEARCH_API_URL,
            json={
                "query": query,
                "max_results": max_results,
                "search_depth": "advanced"
            },
            headers={"Authorization": f"Bearer {SEARCH_API_KEY}"},
            timeout=10
        )
        
        if response.status_code != 200:
            return f"Error: Search request failed with status {response.status_code}"
        
        results = response.json().get("results", [])
        
        if not results:
            return f"No results found for query: {query}"
        
        # Format results for the agent
        output_lines = [
            f"Search Results for: {query}",
            "=" * 60,
            ""
        ]
        
        for idx, result in enumerate(results, start=1):
            output_lines.extend([
                f"{idx}. {result.get('title', 'Untitled')}",
                f"   URL: {result.get('url', 'N/A')}",
                f"   Snippet: {result.get('snippet', 'No snippet available')}",
                f"   Source: {result.get('domain', 'Unknown')}",
                ""
            ])
        
        output_lines.append(
            "Use web_fetch with specific URLs to retrieve full content from authoritative sources."
        )
        
        return "\n".join(output_lines)
        
    except requests.Timeout:
        return "Error: Search request timed out. Please try again."
    except Exception as e:
        return f"Error performing web search: {str(e)}"


@tool
def web_fetch(url: str) -> str:
    """
    Fetch the complete content of a specific web page.
    
    After using web_search to identify relevant sources, use this tool to
    retrieve the full content of authoritative pages. Focus on:
    - Government and regulatory websites
    - Official legal databases
    - Court websites and legal repositories
    - Reputable legal analysis and commentary
    
    IMPORTANT: This tool has a usage limit of 20 fetches per analysis session.
    It also requires human approval before execution. Be selective about which
    sources you retrieve - prioritize official and authoritative sources over
    secondary sources or general information sites.
    
    Args:
        url: The complete URL to fetch (e.g., "https://www.sec.gov/rules/...")
    
    Returns:
        The text content of the web page, with HTML stripped for readability
    """
    global _web_fetch_count
    
    if not url.strip():
        return "Error: Please provide a URL to fetch"
    
    # Check usage limit
    if _web_fetch_count >= _WEB_FETCH_LIMIT:
        return (f"Error: Web fetch limit reached ({_WEB_FETCH_LIMIT} fetches). "
                f"You have already retrieved the maximum number of web pages allowed. "
                f"Review the content you have already fetched.")
    
    remaining = _WEB_FETCH_LIMIT - _web_fetch_count
    
    try:
        # Fetch the web page
        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; LegalAnalysisBot/1.0)"
            }
        )
        
        if response.status_code != 200:
            return f"Error: Failed to fetch URL (status {response.status_code}): {url}"
        
        # Extract text content (you would use a proper HTML parser in production)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text and clean it up
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Truncate if extremely long
        max_length = 8000
        if len(text) > max_length:
            text = text[:max_length] + f"\n\n[Content truncated at {max_length} characters]"
        
        # Update usage counter
        _web_fetch_count += 1
        
        output = [
            f"Fetched content from: {url}",
            f"Remaining fetch quota: {remaining - 1}",
            "=" * 60,
            "",
            text
        ]
        
        return "\n".join(output)
        
    except requests.Timeout:
        return f"Error: Request timed out while fetching: {url}"
    except Exception as e:
        return f"Error fetching URL: {str(e)}"