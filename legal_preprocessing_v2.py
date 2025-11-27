"""
legal_preprocessing_v2.py

Enhanced preprocessing pipeline that extracts both images and text from PDFs,
then uses dual-modal input (image + text) to GPT-5-nano for page summarization.
"""

import os
import json
import base64
import time
import math
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from pdf2image import convert_from_path
from io import BytesIO
import fitz  # PyMuPDF for text extraction
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


@dataclass
class PageData:
    """Represents a single page with all its information"""
    page_number: int
    summary_description: str
    page_text: str
    image_path: str
    tokens_used: int


@dataclass
class DocumentData:
    """Represents a complete document with all its pages"""
    document_id: str
    title: str
    document_type: str
    summary_description: str
    page_count: int
    pages: List[Dict]  # Serialized PageData objects
    pdf_path: str
    total_tokens: int


@dataclass
class DataRoom:
    """Represents the complete preprocessed data room"""
    documents: List[Dict]  # Serialized DocumentData objects
    total_documents: int
    total_pages: int
    total_tokens: int
    
    def to_json(self, output_path: str):
        """Save the complete data room structure to JSON"""
        data = {
            "metadata": {
                "total_documents": self.total_documents,
                "total_pages": self.total_pages,
                "total_tokens": self.total_tokens
            },
            "documents": self.documents
        }
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Data room index saved to {output_path}")


def extract_pages_from_pdf(pdf_path: str, dpi: int = 200) -> List[bytes]:
    """
    Extract all pages from a PDF as individual PNG images.
    
    This creates the visual representation of each page that agents can examine
    when they need to see the actual document layout, formatting, signatures,
    charts, or other visual elements that are difficult to capture in text.
    
    Args:
        pdf_path: Path to the PDF file
        dpi: Resolution for image extraction (200 works well for legal docs)
    
    Returns:
        List of PNG image data as bytes
    """
    print(f"  Extracting page images at {dpi} DPI...")
    
    try:
        images = convert_from_path(pdf_path, dpi=dpi, fmt='png')
        
        page_images = []
        for image in images:
            buffer = BytesIO()
            image.save(buffer, format='PNG')
            page_images.append(buffer.getvalue())
        
        return page_images
        
    except Exception as e:
        print(f"  ✗ Error extracting page images: {e}")
        return []


def extract_text_from_pdf(pdf_path: str) -> List[str]:
    """
    Extract text content from all pages of a PDF.
    
    This extracts the actual textual content that can be searched, analyzed,
    and processed without needing to use vision models. Text extraction is
    fast, cheap, and provides searchable content that complements the visual
    representation from page images.
    
    Using PyMuPDF (fitz) because it handles legal PDFs well, preserving
    structure and handling multi-column layouts appropriately.
    
    Args:
        pdf_path: Path to the PDF file
    
    Returns:
        List of text strings, one per page
    """
    print(f"  Extracting page text...")
    
    try:
        doc = fitz.open(pdf_path)
        page_texts = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Extract text with layout preservation
            text = page.get_text("text")
            
            # Clean up the text slightly
            # Remove excessive whitespace but preserve paragraph structure
            lines = [line.strip() for line in text.split('\n')]
            text = '\n'.join(line for line in lines if line)
            
            page_texts.append(text)
        
        doc.close()
        return page_texts
        
    except Exception as e:
        print(f"  ✗ Error extracting text: {e}")
        return []


def summarize_page_with_dual_input(
    page_image_bytes: bytes,
    page_text: str,
    page_number: int,
    document_name: str,
    model: str = "gpt-5-nano"
) -> Tuple[str, int]:
    """
    Use GPT-5-nano with both image and text to create an accurate page summary.
    
    This is the key innovation in your refined architecture. By providing both
    the visual representation and the textual content to the model, we get the
    best of both worlds. The model can see the layout, structure, and visual
    elements while also reading the actual text content.
    
    This dual-modal approach produces much more accurate summaries than either
    modality alone because the model can cross-reference what it sees with what
    it reads, catching details that might be missed in a single-modality approach.
    
    For legal documents, this means capturing signature blocks, organizational
    charts, and complex tables visually while also understanding dense textual
    provisions, defined terms, and numerical data accurately.
    
    Args:
        page_image_bytes: The page rendered as a PNG image
        page_text: The text content extracted from the page
        page_number: Page number for context
        document_name: Document name for context
        model: Which model to use (gpt-5-nano for cost efficiency)
    
    Returns:
        Tuple of (summary_text, tokens_used)
    """
    # Convert image to base64 for API
    base64_image = base64.b64encode(page_image_bytes).decode('utf-8')
    
    # Truncate text if extremely long to stay within reasonable token limits
    if len(page_text) > 4000:
        page_text = page_text[:4000] + "\n\n[Text truncated for length]"
    
    # Create a prompt that leverages both modalities
    prompt = f"""You are analyzing page {page_number} of a legal document titled "{document_name}".

You have been provided with both the page image and the extracted text content. Use both sources to create an accurate summary.

EXTRACTED TEXT CONTENT:
{page_text}

Your summary should be single sentence that would enable a legal analyst to quickly understand what this page contains and whether it requires detailed examination.

Be specific about legally significant content."""

    try:
        # Call OpenAI's Responses API with both image and text
        response = client.responses.create(
            model=model,
            input=[{
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{base64_image}",
                        "detail": "high"
                    }
                ]
            }],
            reasoning={"effort": "minimal"},  # No deep reasoning needed for description
            text={"verbosity": "low"}  # Keep summaries concise
        )
        
        summary = response.output_text
        
        # Approximate tokens (in production, extract from response.usage)
        tokens_used = len(page_text.split()) + 500  # Rough estimate
        
        return summary, tokens_used
        
    except Exception as e:
        print(f"  ✗ Error summarizing page {page_number}: {e}")
        return f"Page {page_number} (summary unavailable: {str(e)})", 0


def summarize_document_from_pages(
    page_summaries: List[Tuple[int, str]],
    document_name: str,
    document_type: str,
    model: str = "gpt-5-nano"
) -> Tuple[str, int]:
    """
    Create a document-level summary by synthesizing all page summaries.
    
    This step takes the detailed page-level summaries you created with dual-modal
    input and distills them into a single coherent characterization of what the
    entire document is, why it matters, and what key information it contains.
    
    This document summary becomes the high-level view that agents see first when
    deciding which documents to examine in detail. It needs to be comprehensive
    enough to support good filtering decisions but concise enough to fit many
    document summaries into the context window.
    
    Args:
        page_summaries: List of (page_number, summary) tuples
        document_name: Name of the document
        document_type: Category of the document
        model: Which model to use
    
    Returns:
        Tuple of (summary_text, tokens_used)
    """
    # Format all page summaries into readable structure
    combined_summaries = "\n\n".join([
        f"Page {page_num}: {summary}"
        for page_num, summary in page_summaries
    ])
    
    prompt = f"""You are analyzing a legal document titled "{document_name}".

Below are summaries of each page in the document:

{combined_summaries}

Your summary should be one to two sentences that give a legal analyst a clear understanding of what this document is and why it might be important. This summary helps analysts decide which documents to examine in detail.

Be specific and highlight what makes this document legally significant."""

    try:
        response = client.responses.create(
            model=model,
            input=prompt,
            reasoning={"effort": "minimal"},
            text={"verbosity": "low"}
        )
        
        summary = response.output_text
        tokens_used = len(combined_summaries.split()) * 2  # Rough estimate
        
        return summary, int(tokens_used)
        
    except Exception as e:
        print(f"  ✗ Error creating document summary: {e}")
        return f"Document {document_name} containing {len(page_summaries)} pages", 0


def process_data_room(
    pdf_directory: str,
    output_directory: str,
    document_type_mapping: Optional[Dict[str, str]] = None,
    model: str = "gpt-5-nano",
    rate_limit_delay: float = 0.1
) -> DataRoom:
    """
    Process all PDFs in a directory to create a structured data room.
    
    This is the main orchestration function that implements your refined
    preprocessing architecture. It extracts both images and text from each page,
    uses dual-modal input to GPT-5-nano for page summarization, and builds the
    complete hierarchical data structure.
    
    The resulting structure enables efficient progressive disclosure where agents
    start with document summaries, narrow to relevant documents, review page
    summaries, and then strategically access page text or images as needed.
    
    Args:
        pdf_directory: Directory containing PDF files
        output_directory: Where to save processed data and index
        document_type_mapping: Maps document names to categories
        model: Which model to use for summarization
        rate_limit_delay: Seconds to wait between API calls
    
    Returns:
        Complete DataRoom object with all processed documents
    """
    pdf_dir = Path(pdf_directory)
    output_dir = Path(output_directory)
    output_dir.mkdir(exist_ok=True)
    
    # Create subdirectory for page images
    images_dir = output_dir / "page_images"
    images_dir.mkdir(exist_ok=True)
    
    # Create subdirectory for page text
    text_dir = output_dir / "page_text"
    text_dir.mkdir(exist_ok=True)
    
    documents = []
    total_pages = 0
    total_tokens = 0
    
    if document_type_mapping is None:
        document_type_mapping = {}
    
    pdf_files = list(pdf_dir.glob("*.pdf"))
    print(f"\nFound {len(pdf_files)} PDF documents to process\n")
    
    for idx, pdf_path in enumerate(pdf_files, start=1):
        print(f"[{idx}/{len(pdf_files)}] Processing {pdf_path.name}")
        
        # Generate document metadata
        doc_id = f"doc_{idx:03d}"
        doc_name = pdf_path.stem
        doc_type = document_type_mapping.get(doc_name, "General")
        
        # Create directories for this document's data
        doc_images_dir = images_dir / doc_id
        doc_images_dir.mkdir(exist_ok=True)
        
        doc_text_dir = text_dir / doc_id
        doc_text_dir.mkdir(exist_ok=True)
        
        # Extract both images and text
        page_images = extract_pages_from_pdf(str(pdf_path))
        page_texts = extract_text_from_pdf(str(pdf_path))
        
        if not page_images or not page_texts:
            print(f"  ✗ Skipping document due to extraction failure\n")
            continue
        
        if len(page_images) != len(page_texts):
            print(f"  ⚠ Warning: Image count ({len(page_images)}) != text count ({len(page_texts)})")
            # Use the minimum length to avoid index errors
            page_count = min(len(page_images), len(page_texts))
        else:
            page_count = len(page_images)
        
        print(f"  Extracted {page_count} pages (images + text)")
        
        # Process each page with dual-modal input
        page_data_objects = []
        doc_tokens = 0
        
        for page_num in range(1, page_count + 1):
            print(f"  Analyzing page {page_num}/{page_count}...", end=" ")
            
            # Get the corresponding image and text (0-indexed in lists)
            page_image_bytes = page_images[page_num - 1]
            page_text = page_texts[page_num - 1]
            
            # Save the page image
            image_filename = f"page_{page_num:03d}.png"
            image_path = doc_images_dir / image_filename
            with open(image_path, 'wb') as f:
                f.write(page_image_bytes)
            
            # Save the page text
            text_filename = f"page_{page_num:03d}.txt"
            text_path = doc_text_dir / text_filename
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(page_text)
            
            # Get page summary using both image and text
            summary, tokens = summarize_page_with_dual_input(
                page_image_bytes,
                page_text,
                page_num,
                doc_name,
                model
            )
            
            print(f"✓ ({tokens} tokens)")
            
            # Store all page data
            page_data_objects.append(PageData(
                page_number=page_num,
                summary_description=summary,
                page_text=page_text,  # Store text in the index for easy access
                image_path=str(image_path.relative_to(output_dir)),
                tokens_used=tokens
            ))
            
            doc_tokens += tokens
            
            # Rate limiting
            time.sleep(rate_limit_delay)
        
        # Create document-level summary
        print(f"  Creating document summary...")
        doc_summary, summary_tokens = summarize_document_from_pages(
            [(p.page_number, p.summary_description) for p in page_data_objects],
            doc_name,
            doc_type,
            model
        )
        doc_tokens += summary_tokens
        
        # Create document object
        document = DocumentData(
            document_id=doc_id,
            title=doc_name,
            document_type=doc_type,
            summary_description=doc_summary,
            page_count=len(page_data_objects),
            pages=[asdict(p) for p in page_data_objects],
            pdf_path=str(pdf_path),
            total_tokens=doc_tokens
        )
        
        documents.append(asdict(document))
        total_pages += len(page_data_objects)
        total_tokens += doc_tokens
        
        print(f"  ✓ Completed {doc_name} ({doc_tokens} total tokens)\n")
    
    # Create complete data room
    data_room = DataRoom(
        documents=documents,
        total_documents=len(documents),
        total_pages=total_pages,
        total_tokens=total_tokens
    )
    
    # Save to JSON
    index_path = output_dir / "data_room_index.json"
    data_room.to_json(str(index_path))
    
    print(f"\n{'='*60}")
    print(f"Preprocessing Complete!")
    print(f"{'='*60}")
    print(f"Documents processed: {len(documents)}")
    print(f"Total pages analyzed: {total_pages}")
    print(f"Total tokens used: {total_tokens:,}")
    print(f"Output directory: {output_dir}")
    print(f"{'='*60}\n")
    
    return data_room


if __name__ == "__main__":
    # Example usage
    document_types = {
        "Articles_of_Incorporation": "Corporate Governance",
        "Bylaws": "Corporate Governance",
        "Master_Services_Agreement": "Contracts",
        "Employment_Agreement_CEO": "Employment",
        "Patent_Portfolio": "Intellectual Property",
        "Financial_Statements_2023": "Financial",
        "Regulatory_Compliance_Report": "Regulatory"
    }
    
    data_room = process_data_room(
        pdf_directory="./data_room_pdfs",
        output_directory="./preprocessed_data_room",
        document_type_mapping=document_types,
        model="gpt-5-nano"
    )