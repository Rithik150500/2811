"""
file_extraction.py

Extracts files from deepagents StateBackend after analysis completes.
This bridges the gap between ephemeral state storage and persistent disk storage.
"""

from pathlib import Path
from typing import Dict, List
import json


def extract_files_from_checkpoint(
    config: Dict,
    checkpointer,
    output_directory: str = "./analysis_results"
) -> List[str]:
    """
    Extract all files from the deepagents StateBackend and save them to disk.
    
    When deepagents uses StateBackend (the default), files are stored in the
    LangGraph checkpoint state. This function navigates the checkpoint structure,
    extracts file contents, and writes them to a real filesystem so users can
    access their results.
    
    Args:
        config: The thread configuration dict with thread_id
        checkpointer: The MemorySaver or other checkpointer instance
        output_directory: Where to save extracted files
    
    Returns:
        List of file paths that were saved
    """
    output_dir = Path(output_directory)
    output_dir.mkdir(exist_ok=True, parents=True)
    
    print("\nExtracting files from agent state...")
    print("=" * 70)
    
    # Get the final checkpoint for this thread
    # The checkpointer stores the complete conversation state
    checkpoint = checkpointer.get(config)
    
    if not checkpoint:
        print("Warning: No checkpoint found for this thread")
        print("This may mean the thread_id is incorrect or no state was saved")
        return []
    
    # The checkpoint contains a 'channel_values' dict with all state
    channel_values = checkpoint.get("channel_values", {})
    
    if not channel_values:
        print("Warning: Checkpoint exists but has no channel values")
        return []
    
    # DeepAgents stores filesystem data in the 'files' channel
    # This is where StateBackend keeps file contents
    files_state = channel_values.get("files", {})
    
    if not files_state:
        print("No files found in state")
        print("This may mean agents didn't write any files, or files are")
        print("stored under a different key in your deepagents version")
        print("\nAvailable state keys:", list(channel_values.keys()))
        return []
    
    saved_files = []
    
    # Iterate through all files in the state
    for file_path, file_content in files_state.items():
        # Clean up the file path for disk storage
        # Remove leading slashes and common prefixes
        clean_path = file_path.lstrip('/')
        
        # Remove 'dataroom/' prefix if present (agent working directory)
        if clean_path.startswith('dataroom/'):
            clean_path = clean_path[9:]  # len('dataroom/') = 9
        
        # Create the full output path
        output_path = output_dir / clean_path
        
        # Ensure parent directories exist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Write the file content to disk
            # Handle both text and binary content appropriately
            if isinstance(file_content, bytes):
                with open(output_path, 'wb') as f:
                    f.write(file_content)
            else:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(file_content)
            
            saved_files.append(str(output_path))
            
            # Show progress with file sizes for user feedback
            file_size = len(file_content) if isinstance(file_content, (str, bytes)) else 0
            size_kb = file_size / 1024
            print(f"  ✓ Saved: {output_path.name} ({size_kb:.1f} KB)")
            
        except Exception as e:
            print(f"  ✗ Error saving {output_path}: {e}")
    
    print("=" * 70)
    print(f"Successfully extracted {len(saved_files)} files")
    
    return saved_files


def organize_extracted_files(
    saved_files: List[str],
    output_directory: str
) -> Dict[str, List[str]]:
    """
    Organize extracted files by type for easy navigation.
    
    After extraction, this categorizes files to help users quickly find
    what they're looking for: the final report, individual findings, etc.
    
    Args:
        saved_files: List of file paths that were saved
        output_directory: The output directory root
    
    Returns:
        Dictionary categorizing files by type
    """
    output_dir = Path(output_directory)
    
    categorized = {
        'final_report': [],
        'risk_findings': [],
        'other_files': []
    }
    
    for file_path in saved_files:
        file_name = Path(file_path).name.lower()
        
        # Categorize based on file name patterns
        if 'report.docx' in file_name or 'report.doc' in file_name:
            categorized['final_report'].append(file_path)
        elif '_risks.txt' in file_name or 'risk' in file_name:
            categorized['risk_findings'].append(file_path)
        else:
            categorized['other_files'].append(file_path)
    
    return categorized


def print_extraction_summary(
    categorized: Dict[str, List[str]],
    output_directory: str
):
    """
    Print a helpful summary of what was extracted and where to find it.
    
    This gives users clear guidance about accessing their analysis results,
    highlighting the most important files like the final report.
    """
    output_dir = Path(output_directory)
    
    print("\n" + "=" * 70)
    print("ANALYSIS RESULTS SUMMARY")
    print("=" * 70)
    
    # Highlight the final report prominently
    if categorized['final_report']:
        print("\n📄 FINAL REPORT:")
        for report_path in categorized['final_report']:
            rel_path = Path(report_path).relative_to(output_dir)
            print(f"   {rel_path}")
        print("\n   This is your main deliverable - a comprehensive legal risk")
        print("   analysis report suitable for decision-makers.")
    
    # Show risk findings files
    if categorized['risk_findings']:
        print("\n📋 DETAILED FINDINGS FILES:")
        for finding_path in categorized['risk_findings']:
            rel_path = Path(finding_path).relative_to(output_dir)
            print(f"   {rel_path}")
        print("\n   These contain the detailed analysis that was synthesized")
        print("   into the final report. Review these for supporting evidence")
        print("   and specific document citations.")
    
    # Show any other files
    if categorized['other_files']:
        print("\n📁 OTHER FILES:")
        for other_path in categorized['other_files']:
            rel_path = Path(other_path).relative_to(output_dir)
            print(f"   {rel_path}")
    
    print("\n" + "=" * 70)
    print(f"All files are located in: {output_dir.absolute()}")
    print("=" * 70)