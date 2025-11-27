"""
main_application.py

Main application that orchestrates the complete legal risk analysis workflow
from initial request through preprocessing, analysis, and report generation.
"""

import uuid
from pathlib import Path
from typing import Dict
from agent_configuration import legal_analysis_agent, checkpointer
from approval_workflow import approval_handler
from storage_and_tools import data_room_storage
# Add this import at the top
from file_extraction import (
    extract_files_from_checkpoint,
    organize_extracted_files,
    print_extraction_summary
)


def run_legal_risk_analysis(
    data_room_path: str,
    output_directory: str = "./analysis_output"
) -> Dict:
    """
    Run a complete legal risk analysis on a preprocessed data room.
    
    This is the main entry point that coordinates the entire workflow from
    receiving a data room through producing a final report.
    
    Args:
        data_room_path: Path to the preprocessed data room directory
        output_directory: Where to save analysis outputs
    
    Returns:
        Dictionary with analysis results and final report path
    """
    
    # Create output directory
    output_dir = Path(output_directory)
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Generate a unique thread ID for this analysis session
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print("=" * 70)
    print("LEGAL RISK ANALYSIS SYSTEM")
    print("=" * 70)
    print(f"Analysis Session ID: {thread_id}")
    print(f"Output Directory: {output_dir}")
    print("=" * 70)
    print()
    
    # Load document summaries to provide as initial context
    documents = data_room_storage.list_all_documents()
    
    # Format document summaries for the main agent
    doc_summary_text = "\n\n".join([
        f"Document {doc['id']}: {doc['title']}\n"
        f"Type: {doc['document_type']}\n"
        f"Pages: {doc['page_count']}\n"
        f"Summary: {doc['summary_description']}"
        for doc in documents
    ])
    
    # Create the initial request
    initial_request = f"""Please analyze this corporate data room for legal risks and produce a comprehensive risk analysis report.

DATA ROOM CONTENTS:

{doc_summary_text}

ANALYSIS SCOPE:

Conduct thorough legal due diligence across all relevant risk categories including but not limited to:
- Corporate governance structure and compliance
- Commercial contracts and obligations
- Intellectual property assets and protections
- Regulatory compliance status
- Employment matters
- Litigation and disputes
- Financial arrangements and liabilities
- Real estate holdings
- Environmental compliance
- Any other material legal risks

DELIVERABLE:

Produce a professional legal risk analysis report in Word format that:
- Provides an executive summary of key findings
- Details specific risks identified in each category
- Cites supporting evidence from documents
- Assesses severity of each risk
- Offers recommendations for risk mitigation
- Maintains professional quality suitable for decision-makers

Please create your analysis plan, conduct the investigation, and deliver the final report."""

    print("Initiating analysis with main coordinating agent...")
    print()
    
    # Invoke the main agent with initial request
    result = legal_analysis_agent.invoke(
        {"messages": [{"role": "user", "content": initial_request}]},
        config=config
    )
    
    # Enter the approval loop
    iteration = 0
    max_iterations = 50  # Safety limit
    
    while iteration < max_iterations:
        iteration += 1
        
        # Check if execution was interrupted for approval
        if approval_handler.check_for_interrupt(result):
            print(f"\n{'='*70}")
            print(f"APPROVAL REQUIRED (Iteration {iteration})")
            print(f"{'='*70}\n")
            
            # Process the interrupt and get decisions
            decisions = approval_handler.process_interrupt(result)
            
            if not decisions:
                print("No decisions collected. Aborting.")
                break
            
            print(f"\nResuming execution with {len(decisions)} decision(s)...")
            print()
            
            # Resume execution with the decisions
            resume_command = approval_handler.create_resume_command(decisions)
            result = legal_analysis_agent.invoke(resume_command, config=config)
            
        else:
            # No interrupt - execution is complete
            print("\n" + "=" * 70)
            print("ANALYSIS COMPLETE")
            print("=" * 70)
            break
    
    if iteration >= max_iterations:
        print("\nWarning: Maximum iterations reached. Analysis may be incomplete.")
    
    # Extract final messages and look for completion indicators
    messages = result.get("messages", [])
    if messages:
        final_message = messages[-1]
        print("\nFinal Agent Message:")
        print("-" * 70)
        # Fix: Use attribute access instead of .get()
        content = getattr(final_message, 'content', 'No content')
        print(content)
        print("-" * 70)
    
    # The report should now exist in the filesystem
    # In a production system, you would extract it from the state
    # and provide a download link
    
    print("\nAnalysis session completed.")
    print(f"Session ID: {thread_id}")
    print(f"Total iterations: {iteration}")
    
    return {
        "session_id": thread_id,
        "status": "complete",
        "iterations": iteration,
        "final_result": result
    }


if __name__ == "__main__":
    # Example usage
    result = run_legal_risk_analysis(
        data_room_path="./preprocessed_data_room",
        output_directory="./analysis_results"
    )
    
    # Extract files from state to disk
    print("\n" + "=" * 70)
    print("EXTRACTING ANALYSIS OUTPUTS")
    print("=" * 70)
    
    try:
        # Extract all files from the checkpoint state
        saved_files = extract_files_from_checkpoint(
            config={"configurable": {"thread_id": result['session_id']}},
            checkpointer=checkpointer,
            output_directory="./analysis_results"
        )
        
        if saved_files:
            # Organize files by category
            categorized = organize_extracted_files(
                saved_files,
                "./analysis_results"
            )
            
            # Print helpful summary
            print_extraction_summary(
                categorized,
                "./analysis_results"
            )
        else:
            print("\n⚠️  No files were extracted from state.")
            print("This may indicate an issue with how files are stored.")
            print("\nDebugging tips:")
            print("1. Check that agents successfully wrote files during analysis")
            print("2. Verify the checkpoint state structure matches expectations")
            print("3. Examine checkpoint.channel_values keys to find file storage")
            
    except Exception as e:
        print(f"\n✗ Error during file extraction: {e}")
        print("\nYou may need to examine the checkpoint structure directly:")
        print(f"  config = {{'configurable': {{'thread_id': '{result['session_id']}'}}}}")
        print("  checkpoint = checkpointer.get(config)")
        print("  print(checkpoint.keys())")
        print("  print(checkpoint['channel_values'].keys())")
    
    # Final summary
    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"Session ID: {result['session_id']}")
    print(f"Status: {result['status']}")
    print(f"Iterations: {result['iterations']}")
    print("=" * 70)