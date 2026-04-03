import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

def web_search(query: str) -> str:
    """Search the web using DuckDuckGo."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
            if not results:
                return "No search results found."
            
            output = ""
            for r in results:
                output += f"- {r['title']} ({r['href']})\n  {r['body']}\n\n"
            return output
    except Exception as e:
        return f"Error during web search: {str(e)}"

def fetch_url(url: str) -> str:
    """Read and clean text content from a given URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]):
            script.decompose()
            
        text = soup.get_text(separator='\n')
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return clean_text[:5000] 
    except Exception as e:
        return f"Error fetching URL: {str(e)}"

# Export tools for dynamic discovery by the UI and Agent
TOOL_DISPATCH = {
    "web_search": web_search,
    "fetch_url": fetch_url
}
