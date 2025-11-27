"""
approval_workflow.py

Implements the human-in-the-loop approval workflow that presents
pending tool calls to reviewers and processes their decisions.
"""

from typing import Dict, List, Any
from langgraph.types import Command


class ApprovalHandler:
    """
    Handles the approval workflow for agent tool calls.
    
    This class provides methods to check for interrupts, present them to
    users, collect decisions, and resume execution with those decisions.
    """
    
    def check_for_interrupt(self, result: Dict) -> bool:
        """
        Check if the agent result contains an interrupt requiring approval.
        
        Args:
            result: The result from agent.invoke()
        
        Returns:
            True if there is an interrupt, False otherwise
        """
        return bool(result.get("__interrupt__"))
    
    def extract_pending_actions(self, result: Dict) -> List[Dict]:
        """
        Extract the pending tool calls from an interrupt.
        
        Args:
            result: The result containing an interrupt
        
        Returns:
            List of action request dictionaries
        """
        if not self.check_for_interrupt(result):
            return []
        
        interrupt_data = result["__interrupt__"][0].value
        return interrupt_data.get("action_requests", [])
    
    def extract_review_configs(self, result: Dict) -> List[Dict]:
        """
        Extract the review configuration for each pending action.
        
        Args:
            result: The result containing an interrupt
        
        Returns:
            List of review configuration dictionaries
        """
        if not self.check_for_interrupt(result):
            return []
        
        interrupt_data = result["__interrupt__"][0].value
        return interrupt_data.get("review_configs", [])
    
    def format_action_for_display(
        self,
        action: Dict,
        review_config: Dict
    ) -> str:
        """
        Format a pending action for display to the user.
        
        This creates a human-readable representation of what the agent
        wants to do, making it easy for reviewers to understand and decide.
        
        Args:
            action: The action request dictionary
            review_config: The review configuration for this action
        
        Returns:
            Formatted string describing the pending action
        """
        tool_name = action.get("name", "Unknown Tool")
        tool_args = action.get("args", {})
        allowed_decisions = review_config.get("allowed_decisions", [])
        
        # Create a clear description
        lines = [
            "=" * 70,
            f"PENDING ACTION: {tool_name}",
            "=" * 70,
            ""
        ]
        
        # Format arguments nicely
        if tool_args:
            lines.append("Arguments:")
            for key, value in tool_args.items():
                # Truncate long values for display
                value_str = str(value)
                # if len(value_str) > 200:
                #     value_str = value_str[:200] + "..."
                lines.append(f"  {key}: {value_str}")
            lines.append("")
        
        # Show what decisions are allowed
        lines.append("Allowed Decisions:")
        for decision in allowed_decisions:
            lines.append(f"  - {decision}")
        lines.append("")
        
        # Add guidance based on tool
        if tool_name == "get_documents":
            lines.extend([
                "This will retrieve page-by-page summaries for the specified documents.",
                "Review the document IDs and consider if you want to add or remove any.",
                ""
            ])
        elif tool_name == "web_fetch":
            lines.extend([
                "This will fetch the complete content of this web page.",
                "Verify this is an authoritative source worth retrieving.",
                ""
            ])
        elif tool_name == "write_file" or tool_name == "edit_file":
            lines.extend([
                "This will save analysis findings to the filesystem.",
                "Review the content to ensure it meets quality standards.",
                ""
            ])
        elif tool_name == "task":
            lines.extend([
                "This will delegate work to a specialized subagent.",
                "Review the task description to ensure it's clear and appropriate.",
                ""
            ])
        
        return "\n".join(lines)
    
    def prompt_for_decision(
        self,
        action: Dict,
        review_config: Dict
    ) -> Dict:
        """
        Prompt the user for a decision about a pending action.
        
        In a production system, this would integrate with your web interface.
        For now, it uses command-line interaction as an example.
        
        Args:
            action: The action request
            review_config: The review configuration
        
        Returns:
            A decision dictionary with type and potentially edited arguments
        """
        allowed = review_config.get("allowed_decisions", [])
        tool_name = action.get("name")
        
        # Display the action
        print(self.format_action_for_display(action, review_config))
        
        # Prompt for decision
        while True:
            print("Your decision:")
            for idx, decision in enumerate(allowed, start=1):
                print(f"  {idx}. {decision}")
            
            choice = input(f"\nEnter your choice (1-{len(allowed)}): ").strip()
            
            try:
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(allowed):
                    decision_type = allowed[choice_idx]
                    break
                else:
                    print("Invalid choice. Please try again.\n")
            except ValueError:
                print("Invalid input. Please enter a number.\n")
        
        # Handle edit decisions
        if decision_type == "edit" and "edit" in allowed:
            print("\nYou chose to edit the arguments.")
            print("Current arguments:")
            import json
            print(json.dumps(action.get("args", {}), indent=2))
            
            print("\nProvide edited arguments as JSON:")
            edited_args_str = input().strip()
            
            try:
                edited_args = json.loads(edited_args_str)
                return {
                    "type": "edit",
                    "edited_action": {
                        "name": tool_name,
                        "args": edited_args
                    }
                }
            except json.JSONDecodeError:
                print("Invalid JSON. Using original arguments.")
                return {"type": "approve"}
        
        return {"type": decision_type}
    
    def process_interrupt(self, result: Dict) -> List[Dict]:
        """
        Process an interrupt by prompting for decisions on all pending actions.
        
        Args:
            result: The result containing an interrupt
        
        Returns:
            List of decision dictionaries, one per pending action
        """
        actions = self.extract_pending_actions(result)
        configs = self.extract_review_configs(result)
        
        if not actions:
            return []
        
        # Create a lookup map
        config_map = {cfg["action_name"]: cfg for cfg in configs}
        
        # Collect decisions for each action
        decisions = []
        for action in actions:
            review_config = config_map.get(action["name"], {})
            decision = self.prompt_for_decision(action, review_config)
            decisions.append(decision)
        
        return decisions
    
    def create_resume_command(self, decisions: List[Dict]) -> Command:
        """
        Create a Command object to resume execution with decisions.
        
        Args:
            decisions: List of decision dictionaries
        
        Returns:
            Command object for resuming
        """
        return Command(resume={"decisions": decisions})


# Create a global approval handler instance
approval_handler = ApprovalHandler()