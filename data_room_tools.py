"""
data_room_tools_v2.py

Updated data room access tools implementing your refined architecture with
separate tools for text and image access.
"""

from langchain.tools import tool
import json
from pathlib import Path
from typing import List, Dict, Optional



class DataRoomStorage:
    """
    Enhanced storage manager that provides access to documents, page summaries,
    page text, and page images through your refined data structure.
    """
    
    def __init__(self, index_path: str, base_directory: str):
        """Initialize by loading the data room index"""
        self.base_directory = Path(base_directory)
        
        with open(index_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.metadata = data.get('metadata', {})
        self.documents = {
            doc['document_id']: doc 
            for doc in data['documents']
        }
        self.document_list = data['documents']
        
        print(f"Loaded data room with {len(self.documents)} documents, "
              f"{self.metadata.get('total_pages', 0)} pages")
    
    def list_all_documents(self) -> List[Dict]:
        """
        Return all documents with IDs and summary descriptions.
        
        This provides the highest-level view that agents use to understand
        what exists in the data room before deciding what to investigate.
        """
        return [
            {
                'doc_id': doc['document_id'],
                'summdesc': doc['summary_description'],
                'title': doc['title'],
                'document_type': doc['document_type'],
                'page_count': doc['page_count']
            }
            for doc in self.document_list
        ]
    
    def get_documents(self, document_ids: List[str]) -> Dict:
        """
        Return the combined page summaries for specified documents.
        
        This provides the medium-fidelity view showing what each page contains
        without retrieving the full text or images. Agents use this to decide
        which specific pages warrant detailed examination.
        """
        result = {}
        for doc_id in document_ids:
            if doc_id in self.documents:
                doc = self.documents[doc_id]
                result[doc_id] = {
                    'title': doc['title'],
                    'document_type': doc['document_type'],
                    'pages': [
                        {
                            'page_num': p['page_number'],
                            'summdesc': p['summary_description']
                        }
                        for p in doc['pages']
                    ]
                }
        return result
    
    def get_page_text(self, document_id: str, page_numbers: List[int]) -> Dict:
        """
        Return the extracted text for specified pages.
        
        This provides lightweight textual access for pages that agents want to
        read but don't need to visually examine. Text is much lighter weight
        than images and can be processed more quickly.
        """
        if document_id not in self.documents:
            return {'error': f'Document {document_id} not found'}
        
        doc = self.documents[document_id]
        pages_dict = {p['page_number']: p for p in doc['pages']}
        
        result = {'document_id': document_id, 'title': doc['title'], 'pages': []}
        
        for page_num in page_numbers:
            if page_num not in pages_dict:
                result['pages'].append({
                    'page_num': page_num,
                    'error': f'Page {page_num} not found'
                })
                continue
            
            page_info = pages_dict[page_num]
            result['pages'].append({
                'page_num': page_num,
                'page_text': page_info['page_text']
            })
        
        return result
    
    def get_page_images(self, document_id: str, page_numbers: List[int]) -> Dict:
        """
        Return base64-encoded images for specified pages.
        
        This provides the highest-fidelity access for visual examination of
        signatures, charts, complex tables, or document structure. Images are
        heavyweight so this should be used strategically.
        """
        if document_id not in self.documents:
            return {'error': f'Document {document_id} not found'}
        
        doc = self.documents[document_id]
        pages_dict = {p['page_number']: p for p in doc['pages']}
        
        result = {'document_id': document_id, 'title': doc['title'], 'pages': []}
        
        for page_num in page_numbers:
            if page_num not in pages_dict:
                result['pages'].append({
                    'page_num': page_num,
                    'error': f'Page {page_num} not found'
                })
                continue
            
            page_info = pages_dict[page_num]
            image_rel_path = page_info['image_path']
            image_full_path = self.base_directory / image_rel_path
            
            if not image_full_path.exists():
                result['pages'].append({
                    'page_num': page_num,
                    'error': f'Image file not found'
                })
                continue
            
            try:
                import base64
                with open(image_full_path, 'rb') as f:
                    image_bytes = f.read()
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                
                result['pages'].append({
                    'page_num': page_num,
                    'summdesc': page_info['summary_description'],
                    'image_data': f"data:image/png;base64,{image_base64}"
                })
            except Exception as e:
                result['pages'].append({
                    'page_num': page_num,
                    'error': f'Error loading image: {str(e)}'
                })
        
        return result


# Initialize storage
data_room_storage = DataRoomStorage(
    index_path="./preprocessed_data_room/data_room_index.json",
    base_directory="./preprocessed_data_room"
)


# Tool definitions matching your refined architecture

@tool
def list_data_room_documents() -> str:
    """
    List all documents in the data room with their IDs and summary descriptions.
    
    This is your starting point for understanding what documents are available.
    Each document summary gives you a high-level overview of the document's
    purpose, parties, key topics, and significance.
    
    Use this tool first when beginning analysis to see the complete landscape
    of what exists in the data room.
    
    Returns all documents as: [doc_id, summdesc]
    
    This tool has no usage limits and does not require approval.
    """
    documents = data_room_storage.list_all_documents()
    
    if not documents:
        return "No documents found in data room."
    
    output_lines = [
        "Available Documents in Data Room:",
        "=" * 70,
        ""
    ]
    
    for doc in documents:
        output_lines.extend([
            f"Document ID: {doc['doc_id']}",
            f"Title: {doc['title']}",
            f"Type: {doc['document_type']}",
            f"Pages: {doc['page_count']}",
            f"Summary: {doc['summdesc']}",
            ""
        ])
    
    return "\n".join(output_lines)


@tool
def get_documents(document_ids: List[str]) -> str:
    """
    Retrieve page-by-page summaries for specified documents.
    
    After reviewing document summaries from list_data_room_documents, use this
    tool to get detailed page-level information for documents that appear relevant.
    
    This returns the combined summary description of all pages for each document,
    structured as: documents(all pages [page_num, summdesc])
    
    This medium-fidelity view helps you understand what each page contains so
    you can decide which specific pages need detailed text or image examination.
    
    This tool requires human approval before execution. You will see the list
    of documents you requested, and you can modify the selection if needed.
    
    Args:
        document_ids: List of document IDs (e.g., ["doc_001", "doc_005"])
    
    Returns:
        Page-by-page summaries for the requested documents
    """
    if not document_ids:
        return "Error: Please provide at least one document ID"
    
    result = data_room_storage.get_documents(document_ids)
    
    if not result:
        return f"Error: None of the requested documents were found: {document_ids}"
    
    output_lines = ["Retrieved Document Details:", "=" * 70, ""]
    
    for doc_id, doc_data in result.items():
        output_lines.extend([
            f"Document: {doc_data['title']} ({doc_id})",
            f"Type: {doc_data['document_type']}",
            "",
            "Page-by-Page Summaries:",
            "-" * 50
        ])
        
        for page in doc_data['pages']:
            output_lines.extend([
                f"  Page {page['page_num']}:",
                f"    {page['summdesc']}",
                ""
            ])
        
        output_lines.extend(["=" * 70, ""])
    
    return "\n".join(output_lines)


# Track page text retrieval (unlimited but tracked for monitoring)
_page_text_count = 0

@tool
def get_page_text(document_id: str, page_numbers: List[int]) -> str:
    """
    Retrieve the extracted text content for specified pages.
    
    After reviewing page summaries, use this tool to get the actual text content
    from pages that contain provisions, terms, or information you need to analyze
    in detail.
    
    Text access is lightweight and efficient - use this when you need to read
    the content but don't need to see the visual layout, signatures, or charts.
    
    This tool has no usage limits and does not require approval. It is the
    preferred way to access page content for textual analysis.
    
    Args:
        document_id: The document ID (e.g., "doc_001")
        page_numbers: List of page numbers (e.g., [1, 5, 12])
    
    Returns:
        Text content for each requested page as: page_text[]
    """
    global _page_text_count
    
    if not page_numbers:
        return "Error: Please specify at least one page number"
    
    result = data_room_storage.get_page_text(document_id, page_numbers)
    
    if 'error' in result:
        return f"Error: {result['error']}"
    
    _page_text_count += len(result['pages'])
    
    output_lines = [
        f"Retrieved text from {result['title']} ({document_id})",
        f"Total pages retrieved this session: {_page_text_count}",
        "=" * 70,
        ""
    ]
    
    for page_data in result['pages']:
        if 'error' in page_data:
            output_lines.extend([
                f"Page {page_data['page_num']}: ERROR - {page_data['error']}",
                ""
            ])
        else:
            output_lines.extend([
                f"Page {page_data['page_num']}:",
                "-" * 50,
                page_data['page_text'],
                "",
                "=" * 70,
                ""
            ])
    
    return "\n".join(output_lines)


# Track page image retrieval with hard limit
_page_image_count = 0
_PAGE_IMAGE_LIMIT = 50

@tool
def get_page_image(document_id: str, page_numbers: List[int]) -> str:
    """
    Retrieve actual page images for visual examination.
    
    Use this tool when you need to see the visual layout, examine signatures,
    understand complex charts or tables, or verify document structure that
    cannot be fully understood from text alone.
    
    IMPORTANT: This tool has a hard limit of 50 total page image retrievals
    per analysis session. Use this strategically only for pages that truly
    require visual examination.
    
    For reading textual content, prefer get_page_text which is unlimited.
    For understanding page contents, rely on page summaries from get_documents.
    Reserve image retrieval for situations where visual inspection is essential.
    
    Args:
        document_id: The document ID (e.g., "doc_001")
        page_numbers: List of page numbers (e.g., [1, 5, 12])
    
    Returns:
        Page images with their summaries as: page_image[]
    """
    global _page_image_count
    
    if not page_numbers:
        return "Error: Please specify at least one page number"
    
    # Check usage limit
    if _page_image_count >= _PAGE_IMAGE_LIMIT:
        return (f"Error: Page image limit reached ({_PAGE_IMAGE_LIMIT} images). "
                f"You have already retrieved the maximum allowed. "
                f"Use get_page_text for textual content instead.")
    
    remaining_quota = _PAGE_IMAGE_LIMIT - _page_image_count
    
    if len(page_numbers) > remaining_quota:
        return (f"Error: Requesting {len(page_numbers)} images would exceed limit. "
                f"You have {remaining_quota} image retrievals remaining.")
    
    result = data_room_storage.get_page_images(document_id, page_numbers)
    
    if 'error' in result:
        return f"Error: {result['error']}"
    
    # Update counter for successful retrievals
    successful = len([p for p in result['pages'] if 'image_data' in p])
    _page_image_count += successful
    
    output_lines = [
        f"Retrieved {successful} images from {result['title']} ({document_id})",
        f"Remaining image quota: {_PAGE_IMAGE_LIMIT - _page_image_count}",
        "=" * 70,
        ""
    ]
    
    for page_data in result['pages']:
        if 'error' in page_data:
            output_lines.extend([
                f"Page {page_data['page_num']}: ERROR - {page_data['error']}",
                ""
            ])
        else:
            output_lines.extend([
                f"Page {page_data['page_num']}:",
                f"Summary: {page_data['summdesc']}",
                f"Image: [Base64 image data available for vision analysis]",
                ""
            ])
    
    return "\n".join(output_lines)