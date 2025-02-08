import os
import requests
from typing import Dict, Any
from langsmith import traceable
import arxiv
from PyPDF2 import PdfReader

directory = './data/papers'
data_dir = os.path.join(os.curdir, "data", "papers")

# Check if the directory already exists
if not os.path.exists(directory):
    # If the directory doesn't exist, create it and any necessary intermediate directories
    os.makedirs(directory)
    print(f"Directory '{directory}' created successfully.")


def deduplicate_and_format_sources(search_response, max_tokens_per_source, include_raw_content=False):
    """
    Takes either a single search response or list of responses from search APIs and formats them.
    Limits the raw_content to approximately max_tokens_per_source.
    include_raw_content specifies whether to include the raw_content from arxiv.org in the formatted string.
    
    Args:
        search_response: Either:
            - A dict with a 'results' key containing a list of search results
            - A list of dicts, each containing search results
            
    Returns:
        str: Formatted string with deduplicated sources
    """
    # Convert input to list of results
    if isinstance(search_response, dict):
        sources_list = search_response['results']
    elif isinstance(search_response, list):
        sources_list = []
        for response in search_response:
            if isinstance(response, dict) and 'results' in response:
                sources_list.extend(response['results'])
            else:
                sources_list.extend(response)
    else:
        raise ValueError("Input must be either a dict with 'results' or a list of search results")
    
    # Deduplicate by URL
    unique_sources = {}
    for source in sources_list:
        if source['url'] not in unique_sources:
            unique_sources[source['url']] = source
    
    # Format output
    formatted_text = "Sources:\n\n"
    for i, source in enumerate(unique_sources.values(), 1):
        formatted_text += f"Source {source['title']}:\n===\n"
        formatted_text += f"URL: {source['url']}\n===\n"
        formatted_text += f"Most relevant content from source: {source['content']}\n===\n"
        if include_raw_content:
            # Using rough estimate of 4 characters per token
            char_limit = max_tokens_per_source * 4
            # Handle None raw_content
            raw_content = source.get('raw_content', '')
            if raw_content is None:
                raw_content = ''
                print(f"Warning: No raw_content found for source {source['url']}")
            if len(raw_content) > char_limit:
                raw_content = raw_content[:char_limit] + "... [truncated]"
            formatted_text += f"Full source content limited to {max_tokens_per_source} tokens: {raw_content}\n\n"
                
    return formatted_text.strip()

def format_sources(search_results):
    """Format search results into a bullet-point list of sources.
    
    Args:
        search_results (dict): Research response containing results
        
    Returns:
        str: Formatted string with sources and their URLs
    """
    return '\n'.join(
        f"* {source['title']} : {source['url']}"
        for source in search_results['results']
    )


def read_pdf(filepath):
    """Takes a filepath to a PDF and returns a string of the PDF's contents"""
    # creating a pdf reader object
    reader = PdfReader(filepath)
    pdf_text = ""
    page_number = 0
    for page in reader.pages:
        page_number += 1
        pdf_text += page.extract_text() + f"\nPage Number: {page_number}"
    return pdf_text


@traceable
def arxiv_search(query: str, max_results: int = 3) -> Dict[str, Any]:
    """Search academic papers on arXiv.org.
    
    Args:
        query (str): The search query to execute
        max_results (int): Maximum number of results to return (default: 3)
        
    Returns:
        dict: Search response containing:
            - results (list): List of search result dictionaries, each containing:
                - title (str): Title of the paper
                - url (str): URL of the paper
                - content (str): Abstract of the paper
                - raw_content (str): Full paper details including authors, categories, etc.
    """
    # Configure the client
    client = arxiv.Client()
    
    # Create the search query
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance
    )
    
    # Execute search and format results
    results = []
    for paper in client.results(search):
        # Download PDF first
        filename = paper.download_pdf(data_dir)
        
        # Then create the result dictionary
        result = {
            "title": paper.title,
            "url": paper.pdf_url,
            "content": paper.summary,
            "raw_content": (
                f"Title: {paper.title}\n"
                f"Authors: {', '.join(str(author) for author in paper.authors)}\n"
                f"Published: {paper.published}\n"
                f"Updated: {paper.updated}\n"
                f"Categories: {', '.join(paper.categories)}\n"
                f"Abstract: {paper.summary}\n"
                f"PDF URL: {paper.pdf_url}\n"
                f"ArXiv ID: {paper.entry_id}\n"
                f"Content: {read_pdf(filename)}"
            )
        }
        
        results.append(result)
    
    return {"results": results}
