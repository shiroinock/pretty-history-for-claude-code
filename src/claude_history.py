#!/usr/bin/env python3
"""
Claude Code History Colored Formatter
Recreates Claude Code appearance with ANSI colors exactly like the actual UI
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import argparse
import textwrap
import re
import difflib
import termios
import tty


# Theme definitions
THEMES = {
    'default': {
        'name': 'Default',
        'description': 'Clean and simple display',
        'symbols': {
            'bullet': '▶',
            'user_prompt': '>',
            'tool_result': '│',
            'todo_complete': '✓',
            'todo_pending': '○',
            'banner_top': '┌─',
            'banner_bottom': '└─',
            'banner_side': '│',
            'banner_corner_tr': '─┐',
            'banner_corner_br': '─┘'
        }
    },
    'minimal': {
        'name': 'Minimal',
        'description': 'Minimal formatting with basic ASCII',
        'symbols': {
            'bullet': '-',
            'user_prompt': '>',
            'tool_result': ' ',
            'todo_complete': '[x]',
            'todo_pending': '[ ]',
            'banner_top': '-',
            'banner_bottom': '-',
            'banner_side': '|',
            'banner_corner_tr': '-',
            'banner_corner_br': '-'
        }
    },
    'classic': {
        'name': 'Classic',
        'description': 'Classic style with Unicode characters',
        'symbols': {
            'bullet': '●',
            'user_prompt': '>',
            'tool_result': '⎿',
            'todo_complete': '✓',
            'todo_pending': '○',
            'banner_top': '╭─',
            'banner_bottom': '╰─',
            'banner_side': '│',
            'banner_corner_tr': '─╮',
            'banner_corner_br': '─╯'
        }
    },
    'plain': {
        'name': 'Plain',
        'description': 'Plain text with minimal formatting',
        'symbols': {
            'bullet': '*',
            'user_prompt': '>',
            'tool_result': '  ',
            'todo_complete': '- [x]',
            'todo_pending': '- [ ]',
            'banner_top': '',
            'banner_bottom': '',
            'banner_side': '',
            'banner_corner_tr': '',
            'banner_corner_br': ''
        }
    }
}

# ANSI Color Codes
class Colors:
    # Basic colors
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Text colors
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    YELLOW = '\033[93m'
    ORANGE = '\033[38;5;208m'
    
    # Background colors
    BG_GRAY = '\033[48;5;236m'
    BG_GREEN = '\033[48;5;22m'  # Dark green for additions
    BG_RED = '\033[48;5;88m'  # Dark rose for deletions
    BG_BRIGHT_GREEN = '\033[48;5;34m'  # Lighter green for inline additions
    BG_BRIGHT_RED = '\033[48;5;167m'  # Lighter rose for inline deletions
    
    # Special formatting for different elements
    FILE_NAME = CYAN
    COST_INFO = GRAY
    BANNER = GRAY
    
    # Theme-specific elements (will be set based on selected theme)
    BULLET = None
    USER_PROMPT = None
    TOOL_RESULT = None
    

def sanitize_ansi(text: str) -> str:
    """Remove potentially dangerous ANSI escape sequences while preserving safe color codes."""
    if not text:
        return text
    
    # List of safe ANSI sequences (basic colors and formatting)
    safe_patterns = [
        r'\033\[0m',  # Reset
        r'\033\[[0-9]{1,2}m',  # Basic colors (30-37, 90-97)
        r'\033\[[0-9]{1,2};[0-9]{1,2}m',  # Combined formatting
        r'\033\[1m', r'\033\[2m',  # Bold, Dim
        r'\033\[48;5;[0-9]{1,3}m',  # Background colors
        r'\033\[38;5;[0-9]{1,3}m',  # Foreground colors
    ]
    
    # First, validate that only safe sequences are present
    import re
    temp_text = text
    for pattern in safe_patterns:
        temp_text = re.sub(pattern, '', temp_text)
    
    # Check if any ANSI sequences remain
    if re.search(r'\033\[', temp_text):
        # Remove ALL ANSI sequences if unsafe ones are found
        return re.sub(r'\033\[[^m]*m', '', text)
    
    return text


def validate_path(path: Path, base_dir: Path = None) -> bool:
    """Validate that a path is safe to access."""
    try:
        # Resolve to absolute path
        resolved_path = path.resolve()
        
        # If base_dir is provided, ensure path is within it
        if base_dir:
            base_resolved = base_dir.resolve()
            # Check if the resolved path is under the base directory
            try:
                resolved_path.relative_to(base_resolved)
                return True
            except ValueError:
                return False
        
        # Basic validation - ensure it's not accessing system files
        forbidden_paths = ['/etc', '/sys', '/proc', '/dev', '/root']
        path_str = str(resolved_path)
        for forbidden in forbidden_paths:
            if path_str.startswith(forbidden):
                return False
        
        return True
    except Exception:
        return False


class ClaudeHistoryColoredFormatter:
    def __init__(self, history_file: Path, theme: str = 'default'):
        self.history_file = history_file
        self.entries: List[Dict[str, Any]] = []
        self.conversation_pairs: List[Dict[str, Any]] = []
        self.theme = THEMES.get(theme, THEMES['default'])
        self._setup_theme_colors()
        
    def _setup_theme_colors(self):
        """Setup color formatting based on selected theme."""
        # Set theme-specific color combinations
        Colors.BULLET = Colors.GREEN + self.theme['symbols']['bullet'] + Colors.RESET
        Colors.USER_PROMPT = Colors.WHITE + self.theme['symbols']['user_prompt'] + Colors.RESET
        Colors.TOOL_RESULT = Colors.GRAY + self.theme['symbols']['tool_result'] + Colors.RESET
        
    def parse(self) -> None:
        """Parse the JSONL history file."""
        with open(self.history_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line)
                        # Skip summary entries
                        if entry.get('type') not in ['summary']:
                            self.entries.append(entry)
                    except json.JSONDecodeError:
                        print(f"Error: Invalid JSON format in history file", file=sys.stderr)
                        
        self._build_conversation_pairs()
                        
    def _build_conversation_pairs(self) -> None:
        """Build conversation pairs from raw entries."""
        i = 0
        while i < len(self.entries):
            entry = self.entries[i]
            
            if entry.get('type') == 'user' and 'toolUseResult' not in entry:
                # This is a user message - collect all assistant responses and tool results until next user message
                j = i + 1
                last_processed_index = i
                
                # Process all assistant responses and tool results until next user message
                while j < len(self.entries):
                    next_entry = self.entries[j]
                    
                    # If we hit another user message (non-tool-result), stop
                    if next_entry.get('type') == 'user' and 'toolUseResult' not in next_entry:
                        break
                        
                    # If this is an assistant response, create a pair for it
                    if next_entry.get('type') == 'assistant':
                        pair = {
                            'user_message': entry,
                            'assistant_response': next_entry,
                            'tool_results': []
                        }
                        
                        # Collect tool results that follow this assistant response
                        k = j + 1
                        while k < len(self.entries):
                            result_entry = self.entries[k]
                            if (result_entry.get('type') == 'user' and 
                                'toolUseResult' in result_entry):
                                pair['tool_results'].append(result_entry)
                                k += 1
                            else:
                                break
                        
                        self.conversation_pairs.append(pair)
                        last_processed_index = k - 1
                        j = k
                    else:
                        j += 1
                
                # Skip to the next unprocessed entry
                i = last_processed_index + 1
            else:
                i += 1
                        
    def format_timestamp(self, timestamp_str: str) -> str:
        """Format ISO timestamp to readable format."""
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime('%H:%M:%S')
        except:
            return timestamp_str
            
    def format_user_message(self, entry: Dict[str, Any]) -> str:
        """Format user message with colors like Claude Code."""
        content = entry['message'].get('content', '')
        
        # Handle different content types
        if isinstance(content, str):
            message_text = sanitize_ansi(content)
        elif isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    text = item.get('text', '')
                    if '<command-message>' not in text:
                        text_parts.append(sanitize_ansi(text))
            message_text = '\n'.join(text_parts)
        else:
            message_text = sanitize_ansi(str(content))
            
        if entry.get('isMeta') or not message_text.strip():
            return ""
            
        # Format like Claude Code with proper wrapping and colors
        lines = []
        for line in message_text.strip().split('\n'):
            if len(line) <= 76:
                lines.append(f"{Colors.USER_PROMPT} {Colors.WHITE}{line}{Colors.RESET}")
            else:
                # Wrap at word boundaries when possible
                wrapped = textwrap.fill(line, width=76, 
                                      break_long_words=False, break_on_hyphens=False)
                first_line = True
                for wrapped_line in wrapped.split('\n'):
                    if first_line:
                        lines.append(f"{Colors.USER_PROMPT} {Colors.WHITE}{wrapped_line}{Colors.RESET}")
                        first_line = False
                    else:
                        lines.append(f"  {Colors.WHITE}{wrapped_line}{Colors.RESET}")
        
        return '\n' + '\n'.join(lines) + '\n'
        
    def format_assistant_response(self, entry: Dict[str, Any], tool_results: List[Dict[str, Any]]) -> str:
        """Format assistant response with tools in colorized Claude Code style."""
        if not entry:
            return ""
            
        message = entry.get('message', {})
        cost = entry.get('costUSD', 0)
        duration_ms = entry.get('durationMs', 0)
        duration_s = duration_ms / 1000.0
        
        lines = []
        
        # Add cost info once at the beginning
        if cost >= 0.01:
            cost_info = f"{Colors.COST_INFO}Cost: ${cost:.4f} ({duration_s:.1f}s){Colors.RESET}"
        else:
            cost_info = f"{Colors.COST_INFO}Cost: ${cost:.6f} ({duration_s:.1f}s){Colors.RESET}"
        lines.append(cost_info)
        
        # Extract content
        content = message.get('content', [])
        text_parts = []
        tool_uses = []
        
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    if item.get('type') == 'text':
                        text = item.get('text', '').strip()
                        if text:
                            text_parts.append(sanitize_ansi(text))
                    elif item.get('type') == 'tool_use':
                        tool_uses.append(item)
                        
        # Format text response without cost (since it's already shown)
        if text_parts:
            full_text = '\n\n'.join(text_parts)
            
            # Preserve original line structure to maintain markdown formatting
            original_lines = full_text.split('\n')
            
            # Format with colored bullet point (cost already shown at top)
            if original_lines:
                first_line = original_lines[0]
                lines.append(f"{Colors.BULLET} {Colors.WHITE}{first_line}{Colors.RESET}")
                for line in original_lines[1:]:
                    # Preserve empty lines and indentation
                    if line:
                        lines.append(f"  {Colors.WHITE}{line}{Colors.RESET}")
                    else:
                        lines.append("")
                        
        # Format tool uses with colors
        for i, tool in enumerate(tool_uses):
            if lines:
                lines.append("")
                
            tool_name = tool.get('name', 'Unknown')
            tool_input = tool.get('input', {})
            
            # Format tool display with colors (only bullet is colored)
            if tool_name == 'Bash':
                command = sanitize_ansi(tool_input.get('command', ''))
                # For Bash, we'll show cost first, then full command on next line
                tool_line = f"{Colors.BULLET} Bash…"
            elif tool_name == 'Write':
                file_path = tool_input.get('file_path', '')
                file_name = Path(file_path).name if file_path else 'Unknown'
                tool_line = f"{Colors.BULLET} Write({Colors.FILE_NAME}{file_name}{Colors.RESET})…"
            elif tool_name in ['Edit', 'MultiEdit']:
                file_path = tool_input.get('file_path', '')
                file_name = Path(file_path).name if file_path else 'Unknown'
                tool_line = f"{Colors.BULLET} Edit({Colors.FILE_NAME}{file_name}{Colors.RESET})…"
            elif tool_name == 'Read':
                file_path = tool_input.get('file_path', '')
                file_name = Path(file_path).name if file_path else 'Unknown'
                tool_line = f"{Colors.BULLET} Read({Colors.FILE_NAME}{file_name}{Colors.RESET})…"
            elif tool_name == 'Glob':
                pattern = tool_input.get('pattern', '')
                tool_line = f"{Colors.BULLET} Glob({pattern})…"
            elif tool_name == 'Grep':
                pattern = tool_input.get('pattern', '')
                tool_line = f"{Colors.BULLET} Grep({pattern})…"
            elif tool_name == 'TodoRead':
                tool_line = f"{Colors.BULLET} TodoRead…"
            elif tool_name == 'TodoWrite':
                todos = tool_input.get('todos', [])
                todo_count = len(todos)
                tool_line = f"{Colors.BULLET} TodoWrite({todo_count} items)…"
            else:
                tool_line = f"{Colors.BULLET} {tool_name}…"
                
            # Add cost info aligned to the right (match Claude Code format)
            if cost >= 0.01:
                cost_info = f"{Colors.COST_INFO}Cost: ${cost:.4f} ({duration_s:.1f}s){Colors.RESET}"
            else:
                cost_info = f"{Colors.COST_INFO}Cost: ${cost:.6f} ({duration_s:.1f}s){Colors.RESET}"
            
            # Add tool-specific display (cost already shown at top of response)
            if tool_name == 'Bash':
                # Add tool line
                lines.append(tool_line)
                # Add command on next line
                command = tool_input.get('command', '')
                if command:
                    lines.append(f"    {Colors.GRAY}$ {command}{Colors.RESET}")
            else:
                # Add tool line for other tools
                lines.append(tool_line)
            
            # Add tool result
            tool_result = self._find_tool_result(tool, tool_results)
            if tool_result:
                result_text = self._format_tool_result(tool_result, tool_name, tool)
                if result_text:
                    lines.append(result_text)
            else:
                # No tool result found - this might be the issue!
                # For Edit/MultiEdit, try to generate diff anyway
                if tool_name in ['Edit', 'MultiEdit']:
                    diff_lines = self._generate_diff_from_tool_input(tool)
                    if diff_lines:
                        file_path = tool.get('input', {}).get('file_path', '')
                        file_name = Path(file_path).name if file_path else 'Unknown'
                        
                        # Count additions and deletions
                        additions = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
                        deletions = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))
                        
                        output_lines = []
                        output_lines.append(f"  {Colors.TOOL_RESULT}  {Colors.WHITE}Modified {Colors.FILE_NAME}{file_name}{Colors.RESET} {Colors.GRAY}({Colors.GREEN}+{additions}{Colors.GRAY}/{Colors.ORANGE}-{deletions}{Colors.GRAY}){Colors.RESET}")
                        
                        # Parse and show generated diff with line numbers
                        line_num = 1  # Start with line 1 if we don't have context
                        for i, line in enumerate(diff_lines):
                            formatted_line = self._format_diff_line_with_inline_highlight(line, diff_lines, i)
                            
                            if line.startswith('@@'):
                                # Parse hunk header to get line numbers
                                match = re.search(r'\+(\d+)', line)
                                if match:
                                    line_num = int(match.group(1))
                                output_lines.append(f"       {Colors.BLUE}{line}{Colors.RESET}")
                            elif line.startswith('+'):
                                output_lines.append(f"       {line_num:>10} {formatted_line}")
                                line_num += 1
                            elif line.startswith('-'):
                                output_lines.append(f"       {' ':>10} {formatted_line}")
                            else:
                                output_lines.append(f"       {line_num:>10} {line[1:]}")
                                line_num += 1
                        
                        lines.append('\n'.join(output_lines))
                    
        return '\n'.join(lines)
        
    def _find_tool_result(self, tool: Dict[str, Any], tool_results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find the result for a specific tool use."""
        tool_id = tool.get('id')
        if not tool_id:
            return None
            
        for result in tool_results:
            if (result.get('message', {}).get('content', [{}])[0].get('tool_use_id') == tool_id):
                return result
        return None
    
    def _format_diff_line_with_inline_highlight(self, line: str, all_lines: List[str], line_idx: int) -> str:
        """Format a diff line with inline highlighting for changed parts.
        
        For paired delete/add lines, highlight the parts that actually changed.
        """
        if not line:
            return line
            
        # Check if this is a delete line followed by an add line (a modification)
        if line.startswith('-') and line_idx + 1 < len(all_lines) and all_lines[line_idx + 1].startswith('+'):
            old_line = line
            new_line = all_lines[line_idx + 1]
            
            # Get the content without the +/- prefix
            old_content = old_line[1:]
            new_content = new_line[1:]
            
            # Use SequenceMatcher to find differences
            import difflib
            matcher = difflib.SequenceMatcher(None, old_content, new_content)
            
            # Build the highlighted old line
            result = []
            last_end = 0
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == 'equal':
                    result.append(old_content[i1:i2])
                elif tag in ['delete', 'replace']:
                    # Highlight deleted/changed parts
                    result.append(f"{Colors.BG_BRIGHT_RED}{old_content[i1:i2]}{Colors.RESET}{Colors.BG_RED}")
                last_end = i2
            
            return f"{Colors.BG_RED}-{''.join(result)}{Colors.RESET}"
            
        # Check if this is an add line preceded by a delete line (second part of modification)
        elif line.startswith('+') and line_idx > 0 and all_lines[line_idx - 1].startswith('-'):
            old_line = all_lines[line_idx - 1]
            new_line = line
            
            # Get the content without the +/- prefix
            old_content = old_line[1:]
            new_content = new_line[1:]
            
            # Use SequenceMatcher to find differences
            import difflib
            matcher = difflib.SequenceMatcher(None, old_content, new_content)
            
            # Build the highlighted new line
            result = []
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == 'equal':
                    result.append(new_content[j1:j2])
                elif tag in ['insert', 'replace']:
                    # Highlight added/changed parts
                    result.append(f"{Colors.BG_BRIGHT_GREEN}{new_content[j1:j2]}{Colors.RESET}{Colors.BG_GREEN}")
            
            return f"{Colors.BG_GREEN}+{''.join(result)}{Colors.RESET}"
            
        # For standalone additions or deletions, just use solid background
        elif line.startswith('-'):
            return f"{Colors.BG_RED}{line}{Colors.RESET}"
        elif line.startswith('+'):
            return f"{Colors.BG_GREEN}{line}{Colors.RESET}"
        else:
            # Context line or other
            return line
    
    def _generate_diff_from_tool_input(self, tool: Dict[str, Any]) -> List[str]:
        """Generate diff lines from Edit/MultiEdit tool input."""
        tool_input = tool.get('input', {})
        old_string = tool_input.get('old_string', '')
        new_string = tool_input.get('new_string', '')
        
        if not old_string and not new_string:
            return []
            
        # Split into lines for difflib
        old_lines = old_string.splitlines(keepends=True) if old_string else []
        new_lines = new_string.splitlines(keepends=True) if new_string else []
        
        # Generate unified diff
        diff_lines = list(difflib.unified_diff(
            old_lines, new_lines, 
            fromfile='old', tofile='new', 
            lineterm='', n=3
        ))
        
        # Skip the file headers (first 2 lines) and return the actual diff content
        return diff_lines[2:] if len(diff_lines) > 2 else []
        
    def _format_tool_result(self, result_entry: Dict[str, Any], tool_name: str, tool: Optional[Dict[str, Any]] = None) -> str:
        """Format tool result in colorized Claude Code style."""
        if 'toolUseResult' not in result_entry:
            return ""
            
        result = result_entry['toolUseResult']
        
        # Handle TodoRead first since it can return a list
        if tool_name == 'TodoRead':
            # TodoRead result might be in different formats
            todos = []
            if isinstance(result, dict):
                todos = result.get('todos', [])
            elif isinstance(result, list):
                todos = result
            else:
                # Check if it's nested in the entry structure
                todos = []
                
            if todos:
                output_lines = []
                output_lines.append(f"  {Colors.TOOL_RESULT}  {Colors.WHITE}Current TODO list:{Colors.RESET}")
                for todo in todos:  # Show all todos
                    status_color = Colors.GREEN if todo.get('status') == 'completed' else Colors.YELLOW
                    status_symbol = self.theme['symbols']['todo_complete'] if todo.get('status') == 'completed' else self.theme['symbols']['todo_pending']
                    content = todo.get('content', '')
                    # Don't truncate content, but wrap long lines
                    if len(content) > 70:
                        # Wrap long content to multiple lines
                        import textwrap
                        wrapped = textwrap.wrap(content, width=70, subsequent_indent='         ')
                        output_lines.append(f"       {status_color}{status_symbol}{Colors.RESET} {Colors.GRAY}{wrapped[0]}{Colors.RESET}")
                        for wrapped_line in wrapped[1:]:
                            output_lines.append(f"       {Colors.GRAY}{wrapped_line}{Colors.RESET}")
                    else:
                        output_lines.append(f"       {status_color}{status_symbol}{Colors.RESET} {Colors.GRAY}{content}{Colors.RESET}")
                return '\n'.join(output_lines)
            else:
                return f"  {Colors.TOOL_RESULT}  {Colors.GRAY}No TODO items{Colors.RESET}"
        
        elif isinstance(result, dict):
            if tool_name == 'Bash':
                stdout = result.get('stdout', '').strip()
                stderr = result.get('stderr', '').strip()
                
                if stdout or stderr:
                    content = sanitize_ansi(stdout if stdout else stderr)
                    lines = content.split('\n')
                    
                    output_lines = []
                    if lines:
                        # Show first line with proper formatting and colors
                        output_lines.append(f"  {Colors.TOOL_RESULT}  {Colors.WHITE}{lines[0]}{Colors.RESET}")
                        
                        # Show remaining lines with continuation
                        for line in lines[1:]:
                            output_lines.append(f"     {Colors.GRAY}{line}{Colors.RESET}")
                            
                        # Limit output length for readability
                        if len(output_lines) > 8:
                            output_lines = output_lines[:6]
                            output_lines.append(f"     {Colors.DIM}... ({len(lines) - 5} more lines){Colors.RESET}")
                            output_lines.append(f"     {Colors.GRAY}{lines[-1]}{Colors.RESET}")  # Show last line
                            
                    return '\n'.join(output_lines)
                else:
                    return f"  {Colors.TOOL_RESULT}  {Colors.GRAY}(No output){Colors.RESET}"
                    
            elif tool_name == 'Write':
                file_path = result.get('filePath', '')
                content = result.get('content', '')
                
                if content:
                    line_count = len(content.split('\n'))
                    file_name = Path(file_path).name if file_path else 'Unknown'
                    return f"  {Colors.TOOL_RESULT}  {Colors.WHITE}Created {Colors.FILE_NAME}{file_name}{Colors.RESET} {Colors.GRAY}({line_count} lines){Colors.RESET}"
                else:
                    return f"  {Colors.TOOL_RESULT}  {Colors.WHITE}Created file{Colors.RESET}"
                    
            elif tool_name in ['Edit', 'MultiEdit']:
                file_path = result.get('filePath', '')
                patches = result.get('structuredPatch', [])
                
                output_lines = []
                if patches:
                    # Calculate additions/deletions from actual patch data
                    additions = 0
                    deletions = 0
                    for patch in patches:
                        # If patch has explicit counts, use them
                        if 'additions' in patch and 'deletions' in patch:
                            additions += patch.get('additions', 0)
                            deletions += patch.get('deletions', 0)
                        else:
                            # Calculate from lines directly (Claude Code format)
                            for line in patch.get('lines', []):
                                if line.startswith('+') and not line.startswith('+++'):
                                    additions += 1
                                elif line.startswith('-') and not line.startswith('---'):
                                    deletions += 1
                    file_name = Path(file_path).name if file_path else 'Unknown'
                    output_lines.append(f"  {Colors.TOOL_RESULT}  {Colors.WHITE}Modified {Colors.FILE_NAME}{file_name}{Colors.RESET} {Colors.GRAY}({Colors.GREEN}+{additions}{Colors.GRAY}/{Colors.ORANGE}-{deletions}{Colors.GRAY}){Colors.RESET}")
                    
                    # Show changes with line numbers (Claude Code format)
                    for patch in patches:
                        old_start = patch.get('oldStart', 0)
                        new_start = patch.get('newStart', 0)
                        lines = patch.get('lines', [])
                        
                        # Track line numbers
                        old_line_num = old_start
                        new_line_num = new_start
                        
                        # Process lines with inline diff highlighting
                        for i, line in enumerate(lines):
                            formatted_line = self._format_diff_line_with_inline_highlight(line, lines, i)
                            
                            if line.startswith('-'):
                                # Deleted line
                                output_lines.append(f"       {old_line_num:>10} {formatted_line}")
                                old_line_num += 1
                            elif line.startswith('+'):
                                # Added line
                                output_lines.append(f"       {new_line_num:>10} {formatted_line}")
                                new_line_num += 1
                            else:
                                # Context line
                                output_lines.append(f"       {new_line_num:>10} {line[1:]}")
                                old_line_num += 1
                                new_line_num += 1
                                
                    return '\n'.join(output_lines)
                else:
                    # No structuredPatch, try to generate diff from tool input
                    file_name = Path(file_path).name if file_path else 'Unknown'
                    
                    if tool:
                        diff_lines = self._generate_diff_from_tool_input(tool)
                        if diff_lines:
                            # Count additions and deletions
                            additions = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
                            deletions = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))
                            
                            output_lines.append(f"  {Colors.TOOL_RESULT}  {Colors.WHITE}Modified {Colors.FILE_NAME}{file_name}{Colors.RESET} {Colors.GRAY}({Colors.GREEN}+{additions}{Colors.GRAY}/{Colors.ORANGE}-{deletions}{Colors.GRAY}){Colors.RESET}")
                            
                            # Parse and show generated diff with line numbers
                            line_num = 1  # Start with line 1 if we don't have context
                            for i, line in enumerate(diff_lines):
                                formatted_line = self._format_diff_line_with_inline_highlight(line, diff_lines, i)
                                
                                if line.startswith('@@'):
                                    # Parse hunk header to get line numbers
                                    match = re.search(r'\+(\d+)', line)
                                    if match:
                                        line_num = int(match.group(1))
                                    output_lines.append(f"       {Colors.BLUE}{line}{Colors.RESET}")
                                elif line.startswith('+'):
                                    output_lines.append(f"       {line_num:>10} {formatted_line}")
                                    line_num += 1
                                elif line.startswith('-'):
                                    output_lines.append(f"       {' ':>10} {formatted_line}")
                                else:
                                    output_lines.append(f"       {line_num:>10} {line[1:]}")
                                    line_num += 1
                            
                            return '\n'.join(output_lines)
                    
                    return f"  {Colors.TOOL_RESULT}  {Colors.WHITE}Modified {Colors.FILE_NAME}{file_name}{Colors.RESET}"
                    
            elif tool_name == 'Read':
                file_info = result.get('file', {})
                num_lines = file_info.get('numLines', 0)
                file_path = file_info.get('filePath', '')
                file_name = Path(file_path).name if file_path else 'Unknown'
                return f"  {Colors.TOOL_RESULT}  {Colors.WHITE}Read {Colors.FILE_NAME}{file_name}{Colors.RESET} {Colors.GRAY}({num_lines} lines){Colors.RESET}"
                
            elif tool_name == 'TodoWrite':
                # TodoWrite returns oldTodos and newTodos
                new_todos = result.get('newTodos', [])
                old_todos = result.get('oldTodos', [])
                
                if new_todos:
                    output_lines = []
                    output_lines.append(f"  {Colors.TOOL_RESULT}  {Colors.WHITE}Updated TODO list:{Colors.RESET}")
                    
                    # Show all todos from the new list
                    for todo in new_todos:  # Show all todos
                        status_color = Colors.GREEN if todo.get('status') == 'completed' else Colors.YELLOW
                        status_symbol = self.theme['symbols']['todo_complete'] if todo.get('status') == 'completed' else self.theme['symbols']['todo_pending']
                        content = todo.get('content', '')
                        # Don't truncate content, but wrap long lines
                        if len(content) > 70:
                            # Wrap long content to multiple lines
                            import textwrap
                            wrapped = textwrap.wrap(content, width=70, subsequent_indent='         ')
                            output_lines.append(f"       {status_color}{status_symbol}{Colors.RESET} {Colors.GRAY}{wrapped[0]}{Colors.RESET}")
                            for wrapped_line in wrapped[1:]:
                                output_lines.append(f"       {Colors.GRAY}{wrapped_line}{Colors.RESET}")
                        else:
                            output_lines.append(f"       {status_color}{status_symbol}{Colors.RESET} {Colors.GRAY}{content}{Colors.RESET}")
                    
                    return '\n'.join(output_lines)
                else:
                    return f"  {Colors.TOOL_RESULT}  {Colors.WHITE}Updated TODO list{Colors.RESET}"
                
        return f"  {Colors.TOOL_RESULT}  {Colors.WHITE}Completed{Colors.RESET}"
        
    def format_welcome_banner(self) -> str:
        """Format the welcome banner with colors like Claude Code."""
        if not self.entries:
            return ""
            
        # Find first user entry to get cwd
        cwd = None
        for entry in self.entries:
            if entry.get('type') == 'user' and entry.get('cwd'):
                cwd = entry['cwd']
                break
        
        if not cwd:
            cwd = 'Unknown'
        
        # Format banner with colors
        # Calculate banner width based on cwd length
        min_width = 53  # Minimum width for the banner
        cwd_line_content = f"cwd: {cwd}"
        banner_width = max(min_width, len(cwd_line_content) + 8)  # 8 = spaces and padding
        
        # Create horizontal lines based on theme
        if self.theme['symbols']['banner_top']:  # Only show banner if theme has banner symbols
            # Handle different banner formats
            if len(self.theme['symbols']['banner_top']) >= 2:
                # Multi-character format like "╭─"
                top_line = self.theme['symbols']['banner_top'][0] + self.theme['symbols']['banner_top'][1] * (banner_width - 2) + self.theme['symbols']['banner_corner_tr']
                bottom_line = self.theme['symbols']['banner_bottom'][0] + self.theme['symbols']['banner_bottom'][1] * (banner_width - 2) + self.theme['symbols']['banner_corner_br']
            else:
                # Single character format like "-"
                char = self.theme['symbols']['banner_top']
                top_line = char * banner_width
                bottom_line = char * banner_width
            
            empty_line = self.theme['symbols']['banner_side'] + " " * (banner_width - 2) + self.theme['symbols']['banner_side']
        else:
            # For themes without banners (like plain)
            return f"\n{'=' * 50}\nSession: {cwd}\n{'=' * 50}\n"
        
        # Helper function to pad line content
        def pad_line(content_length):
            return " " * (banner_width - content_length - 2)  # -2 for the border characters
        
        banner = []
        banner.append(f"{Colors.BANNER}{top_line}{Colors.RESET}")
        
        # Line 1: Welcome message (visible length: 27)
        side = self.theme['symbols']['banner_side']
        banner.append(f"{Colors.BANNER}{side}{Colors.RESET} {Colors.WHITE}✻ JSONL History Formatter {Colors.RESET}{pad_line(27)}{Colors.BANNER}{side}{Colors.RESET}")
        
        # Line 2: Empty
        banner.append(f"{Colors.BANNER}{empty_line}{Colors.RESET}")
        
        # Line 3: Help text (visible length: 50 text + 3 leading spaces = 53)
        help_text = "Independent tool - not affiliated with any service"
        help_visible_length = len(f"   {help_text}")
        banner.append(f"{Colors.BANNER}{side}{Colors.RESET}   {Colors.GRAY}{help_text}{Colors.RESET}{pad_line(help_visible_length)}{Colors.BANNER}{side}{Colors.RESET}")
        
        # Line 4: Empty
        banner.append(f"{Colors.BANNER}{empty_line}{Colors.RESET}")
        
        # Line 5: CWD (visible length varies)
        cwd_visible_length = len(f"   cwd: {cwd}")
        banner.append(f"{Colors.BANNER}{side}{Colors.RESET}   {Colors.GRAY}cwd: {Colors.FILE_NAME}{cwd}{Colors.RESET}{pad_line(cwd_visible_length)}{Colors.BANNER}{side}{Colors.RESET}")
        
        banner.append(f"{Colors.BANNER}{bottom_line}{Colors.RESET}")
        banner.append("")
        
        return '\n'.join(banner)
        
    def format_entries(self) -> str:
        """Format all entries in colorized Claude Code style."""
        output = []
        
        # Add welcome banner
        output.append(self.format_welcome_banner())
        
        # Format conversation pairs
        last_user_message = None
        for i, pair in enumerate(self.conversation_pairs):
            # Only show user message if it's different from the previous one
            current_user_message = pair['user_message']
            if current_user_message != last_user_message:
                user_formatted = self.format_user_message(current_user_message)
                if user_formatted:
                    output.append(user_formatted)
                last_user_message = current_user_message
                
            # Format assistant response
            assistant_formatted = self.format_assistant_response(
                pair['assistant_response'], 
                pair['tool_results']
            )
            if assistant_formatted:
                output.append(assistant_formatted)
                
            # Add spacing after each conversation pair
            if i < len(self.conversation_pairs) - 1:
                output.append("")
                
        return '\n'.join(output)


def get_key():
    """Get a single keypress from terminal."""
    try:
        # Check if we're in an interactive terminal
        if not sys.stdin.isatty():
            # Non-interactive mode, use simple input
            return input().strip()[:1]
            
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)  # Use cbreak instead of raw mode
            key = sys.stdin.read(1)
            return key
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except (termios.error, OSError):
        # Fallback for non-interactive environments
        return input().strip()[:1]

def interactive_menu(items: List[str], title: str) -> int:
    """Interactive menu with arrow key navigation.
    
    Returns:
        Selected index (0-based), or -1 if cancelled
    """
    # Check if we're in an interactive terminal
    try:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            # Fallback to number selection for non-interactive environments
            return numbered_menu(items, title)
    except:
        return numbered_menu(items, title)
    
    selected = 0
    window_size = 10  # Display 10 items at a time
    window_start = 0  # Start of the display window
    
    while True:
        # Calculate scrolling window
        if selected < window_start:
            # Scroll up
            window_start = selected
        elif selected >= window_start + window_size:
            # Scroll down
            window_start = selected - window_size + 1
        
        window_end = min(window_start + window_size, len(items))
        
        # Clear screen and show menu
        print('\033[2J\033[H', end='')  # Clear screen and move cursor to top
        print(f"{Colors.GREEN}{title}{Colors.RESET}")
        print("=" * len(title))
        
        # Always show scroll indicator area (even if empty) for consistent layout
        if window_start > 0:
            print(f"   {Colors.DIM}↑ {window_start} more items above{Colors.RESET}")
        else:
            print()  # Empty line to maintain layout
        
        # Display items in the current window
        for idx, i in enumerate(range(window_start, window_end)):
            item = items[i]
            # Show number shortcut based on position in visible window (1-9, then 0 for 10th item)
            if idx < 9:
                shortcut = str(idx + 1)
            elif idx == 9:
                shortcut = "0"
            else:
                shortcut = " "  # No shortcut for items beyond 10 (shouldn't happen with window_size=10)
            
            if i == selected:
                print(f"{Colors.BG_GRAY} > {Colors.YELLOW}{shortcut}{Colors.WHITE} {item}{Colors.RESET}")
            else:
                print(f"   {Colors.YELLOW}{shortcut}{Colors.GRAY} {item}{Colors.RESET}")
        
        # Always show scroll indicator area (even if empty) for consistent layout
        if window_end < len(items):
            remaining = len(items) - window_end
            print(f"   {Colors.DIM}↓ {remaining} more items below{Colors.RESET}")
        else:
            print()  # Empty line to maintain layout
        
        print(f"{Colors.YELLOW}Use W/S/arrows or numbers to navigate, Enter to select, L for less, X to go back, Q to quit{Colors.RESET}")
        
        # Get user input
        key = get_key()
        
        if key.lower() == 'w':  # Up
            selected = (selected - 1) % len(items)
        elif key.lower() == 's':  # Down
            selected = (selected + 1) % len(items)
        elif key == '\r' or key == '\n':  # Enter
            return selected
        elif key.lower() == 'l':  # Less mode
            return (selected, 'less')  # Return tuple to indicate less mode
        elif key.lower() == 'x':  # Back
            return -2  # Special return code for "go back"
        elif key.lower() == 'q':  # Quit
            return -1
        elif key.isdigit():  # Number shortcut
            if key == '0':
                # 0 key selects 10th visible item
                target_idx = window_start + 9
                if target_idx < window_end:
                    return target_idx
            else:
                # 1-9 keys select items 1-9 in visible window
                visible_idx = int(key) - 1
                target_idx = window_start + visible_idx
                if target_idx < window_end:
                    return target_idx
        elif ord(key) == 27:  # ESC key or start of escape sequence
            # Only process arrow key sequences, ignore standalone ESC
            try:
                next1 = sys.stdin.read(1)
                if next1 == '[':
                    # This is an arrow key sequence
                    next2 = sys.stdin.read(1)
                    if next2 == 'A':  # Up arrow
                        selected = (selected - 1) % len(items)
                    elif next2 == 'B':  # Down arrow
                        selected = (selected + 1) % len(items)
                    # Ignore other escape sequences (like left/right arrows)
                # Ignore all other ESC sequences
            except:
                # Ignore standalone ESC or any read errors
                pass

def numbered_menu(items: List[str], title: str) -> int:
    """Fallback numbered menu for non-interactive environments."""
    print(f"\n{Colors.GREEN}{title}{Colors.RESET}")
    print("=" * len(title))
    print()
    
    for i, item in enumerate(items, 1):
        print(f"{Colors.WHITE}{i:2d}.{Colors.RESET} {Colors.GRAY}{item}{Colors.RESET}")
    
    try:
        print(f"\n{Colors.YELLOW}Select number (1-{len(items)}), 'x' to go back, or 0 to quit:{Colors.RESET} ", end='')
        user_input = input().strip()
        
        if user_input.lower() == 'x':
            return -2  # Go back
        elif user_input == '0':
            return -1  # Quit
        else:
            choice = int(user_input)
            if 1 <= choice <= len(items):
                return choice - 1
            else:
                print(f"{Colors.ORANGE}Invalid selection.{Colors.RESET}")
                return -1
    except (ValueError, KeyboardInterrupt, EOFError):
        print(f"\n{Colors.ORANGE}Cancelled.{Colors.RESET}")
        return -1


def get_default_projects_dir() -> Path:
    """Get the default projects directory from environment or fallback."""
    # Check environment variable first
    env_dir = os.environ.get('CLAUDE_HISTORY_DIR')
    if env_dir:
        return Path(env_dir)
    
    # Check if ~/.claude/projects exists (for backward compatibility)
    claude_dir = Path.home() / '.claude' / 'projects'
    if claude_dir.exists():
        return claude_dir
    
    # Default to user's home directory
    return Path.home()


def find_history_files(projects_dir: Path) -> List[Path]:
    """Find all JSONL history files in the projects directory."""
    history_files = []
    
    if not projects_dir.exists():
        return history_files
        
    for project_dir in projects_dir.iterdir():
        if project_dir.is_dir():
            for file in project_dir.glob('*.jsonl'):
                history_files.append(file)
                
    return sorted(history_files, key=lambda x: x.stat().st_mtime, reverse=True)


class InteractiveSession:
    def __init__(self):
        self.settings = {
            'theme': 'default',
            'output_file': None,
            'no_color': False,
            'force_color': False,
            'base_dir': None,
            'use_less': False
        }
        self.projects_dir = None
        
    def show_main_menu(self) -> str:
        """Show main menu and return selected action."""
        menu_items = [
            "📁 Select and View History File",
            "🎨 Change Display Theme",
            "⚙️  Configure Output Options", 
            "📂 Change Base Directory",
            "ℹ️  Show Current Settings",
            "❓ Show Help"
        ]
        
        choice = interactive_menu(menu_items, "🚀 JSONL History Formatter - Main Menu")
        
        if choice == -1:  # Quit
            return 'quit'
        elif choice == 0:  # Select and view file
            return 'select_file'
        elif choice == 1:  # Change theme
            return 'change_theme'
        elif choice == 2:  # Configure output
            return 'configure_output'
        elif choice == 3:  # Change base dir
            return 'change_base_dir'
        elif choice == 4:  # Show settings
            return 'show_settings'
        elif choice == 5:  # Help
            return 'show_help'
        else:
            return 'main_menu'
    
    def select_theme(self) -> bool:
        """Theme selection submenu. Returns True if changed."""
        theme_items = []
        for theme_id, theme_info in THEMES.items():
            current_marker = " ← Current" if theme_id == self.settings['theme'] else ""
            preview = f"{theme_info['symbols']['bullet']} Example"
            theme_items.append(f"{theme_info['name']} - {theme_info['description']}{current_marker}")
        
        choice = interactive_menu(theme_items, "🎨 Select Display Theme")
        
        if choice == -1 or choice == -2:  # Quit or back
            return False
        
        theme_keys = list(THEMES.keys())
        if 0 <= choice < len(theme_keys):
            old_theme = self.settings['theme']
            self.settings['theme'] = theme_keys[choice]
            if old_theme != self.settings['theme']:
                print(f"\n{Colors.GREEN}✓ Theme changed to: {THEMES[self.settings['theme']]['name']}{Colors.RESET}")
                return True
        return False
    
    def configure_output(self) -> bool:
        """Output configuration submenu. Returns True if changed."""
        output_items = [
            f"💾 Output to file: {'Yes' if self.settings['output_file'] else 'No'}",
            f"🌈 Colors: {'Disabled' if self.settings['no_color'] else 'Enabled'}",
            f"🔍 Force colors: {'Yes' if self.settings['force_color'] else 'No'}",
            f"📖 Use less viewer: {'Yes' if self.settings['use_less'] else 'No'}"
        ]
        
        choice = interactive_menu(output_items, "⚙️  Configure Output Options")
        
        if choice == -1 or choice == -2:  # Quit or back
            return False
        elif choice == 0:  # Output file
            return self._configure_output_file()
        elif choice == 1:  # Colors
            self.settings['no_color'] = not self.settings['no_color']
            if self.settings['no_color']:
                self.settings['force_color'] = False
            print(f"\n{Colors.GREEN}✓ Colors {'disabled' if self.settings['no_color'] else 'enabled'}{Colors.RESET}")
            return True
        elif choice == 2:  # Force colors
            if not self.settings['no_color']:
                self.settings['force_color'] = not self.settings['force_color']
                print(f"\n{Colors.GREEN}✓ Force colors {'enabled' if self.settings['force_color'] else 'disabled'}{Colors.RESET}")
                return True
            else:
                print(f"\n{Colors.ORANGE}Colors are disabled. Enable colors first.{Colors.RESET}")
        elif choice == 3:  # Less viewer
            self.settings['use_less'] = not self.settings['use_less']
            print(f"\n{Colors.GREEN}✓ Less viewer {'enabled' if self.settings['use_less'] else 'disabled'}{Colors.RESET}")
            return True
        return False
    
    def _configure_output_file(self) -> bool:
        """Configure output file setting."""
        try:
            if self.settings['output_file']:
                # Currently has output file, offer to disable
                choice_items = [
                    f"📝 Current: {self.settings['output_file']}",
                    "🗑️  Disable file output (use stdout)",
                    "📝 Change output file"
                ]
                choice = interactive_menu(choice_items, "💾 Output File Configuration")
                
                if choice == 1:  # Disable
                    self.settings['output_file'] = None
                    print(f"\n{Colors.GREEN}✓ Output file disabled. Will use stdout.{Colors.RESET}")
                    return True
                elif choice == 2:  # Change
                    return self._prompt_output_file()
            else:
                # No output file, offer to set one
                return self._prompt_output_file()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.ORANGE}Cancelled.{Colors.RESET}")
        return False
    
    def _prompt_output_file(self) -> bool:
        """Prompt for output file path."""
        try:
            print(f"\n{Colors.YELLOW}Enter output file path (or press Enter to cancel):{Colors.RESET}")
            file_path = input("📁 File path: ").strip()
            if file_path:
                self.settings['output_file'] = Path(file_path)
                print(f"\n{Colors.GREEN}✓ Output file set to: {file_path}{Colors.RESET}")
                return True
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.ORANGE}Cancelled.{Colors.RESET}")
        return False
    
    def show_settings(self):
        """Display current settings."""
        print(f"\n{Colors.GREEN}📋 Current Settings:{Colors.RESET}")
        print("=" * 50)
        print(f"🎨 Theme: {Colors.CYAN}{THEMES[self.settings['theme']]['name']}{Colors.RESET}")
        print(f"📂 Base directory: {Colors.CYAN}{self.projects_dir or 'Auto-detect'}{Colors.RESET}")
        print(f"💾 Output file: {Colors.CYAN}{self.settings['output_file'] or 'stdout'}{Colors.RESET}")
        print(f"🌈 Colors: {Colors.CYAN}{'Disabled' if self.settings['no_color'] else 'Enabled'}{Colors.RESET}")
        print(f"🔍 Force colors: {Colors.CYAN}{'Yes' if self.settings['force_color'] else 'No'}{Colors.RESET}")
        print(f"📖 Use less: {Colors.CYAN}{'Yes' if self.settings['use_less'] else 'No'}{Colors.RESET}")
        
        print(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            pass
    
    def show_help(self):
        """Display help information."""
        help_text = f"""
{Colors.GREEN}📖 JSONL History Formatter Help{Colors.RESET}

{Colors.YELLOW}Main Features:{Colors.RESET}
• 📁 View conversation history files in various themes
• 🎨 Choose from 4 different display themes
• ⚙️  Configure output options (file, colors, viewer)
• 📂 Set custom base directories for history files

{Colors.YELLOW}Navigation:{Colors.RESET}
• Use W/S or arrow keys to navigate
• Press Enter to select
• Press X to go back
• Press Q to quit
• Use number keys (1-9, 0) for quick selection

{Colors.YELLOW}Themes Available:{Colors.RESET}
• default: Clean modern style (▶)
• minimal: Simple ASCII characters (-)
• classic: Unicode decorative style (●)
• plain: Plain text formatting (*)

{Colors.YELLOW}About:{Colors.RESET}
This is an independent open-source tool for viewing conversation
logs. Not affiliated with any specific service or platform.

{Colors.YELLOW}Press Enter to continue...{Colors.RESET}
"""
        print(help_text)
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            pass
    
    def run_interactive_session(self):
        """Main interactive session loop."""
        self.projects_dir = get_default_projects_dir()
        
        print(f"\n{Colors.GREEN}🚀 Welcome to JSONL History Formatter{Colors.RESET}")
        print(f"{Colors.GRAY}Independent tool - not affiliated with any service{Colors.RESET}\n")
        
        while True:
            action = self.show_main_menu()
            
            if action == 'quit':
                print(f"\n{Colors.BLUE}👋 Goodbye!{Colors.RESET}")
                break
            elif action == 'select_file':
                if self._handle_file_selection():
                    break  # File was processed, exit
            elif action == 'change_theme':
                self.select_theme()
            elif action == 'configure_output':
                self.configure_output()
            elif action == 'change_base_dir':
                self._configure_base_dir()
            elif action == 'show_settings':
                self.show_settings()
            elif action == 'show_help':
                self.show_help()
    
    def _configure_base_dir(self):
        """Configure base directory."""
        try:
            print(f"\n{Colors.YELLOW}Current base directory: {Colors.CYAN}{self.projects_dir}{Colors.RESET}")
            print(f"{Colors.YELLOW}Enter new base directory (or press Enter to keep current):{Colors.RESET}")
            new_dir = input("📂 Directory path: ").strip()
            if new_dir:
                new_path = Path(new_dir)
                if new_path.exists() and new_path.is_dir():
                    self.projects_dir = new_path
                    print(f"\n{Colors.GREEN}✓ Base directory changed to: {new_path}{Colors.RESET}")
                else:
                    print(f"\n{Colors.ORANGE}❌ Directory does not exist: {new_path}{Colors.RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.ORANGE}Cancelled.{Colors.RESET}")
    
    def _handle_file_selection(self) -> bool:
        """Handle file selection and processing. Returns True if file was processed."""
        history_files = find_history_files(self.projects_dir)
        if not history_files:
            print(f"\n{Colors.ORANGE}📭 No history files found in {self.projects_dir}{Colors.RESET}")
            print(f"{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
            try:
                input()
            except (KeyboardInterrupt, EOFError):
                pass
            return False
        
        selected_file = interactive_file_selection(history_files)
        if not selected_file:
            return False
        
        # Handle less mode
        use_less = self.settings['use_less']
        if isinstance(selected_file, tuple) and selected_file[1] == 'less':
            selected_file = selected_file[0]
            use_less = True
        
        # Process the file
        return self._process_selected_file(selected_file, use_less)
    
    def _process_selected_file(self, history_file: Path, use_less: bool) -> bool:
        """Process the selected file with current settings. Returns True if successful."""
        try:
            print(f"\n{Colors.BLUE}📖 Processing: {history_file.name}{Colors.RESET}")
            
            # Apply color settings
            if self.settings['no_color']:
                self._disable_colors()
            
            # Create formatter with current theme
            formatter = ClaudeHistoryColoredFormatter(history_file, theme=self.settings['theme'])
            formatter.parse()
            formatted_output = formatter.format_entries()
            
            if use_less:
                self._display_in_less(formatted_output)
            elif self.settings['output_file']:
                self._save_to_file(formatted_output)
                print(f"{Colors.GREEN}✓ Saved to: {self.settings['output_file']}{Colors.RESET}")
            else:
                print(formatted_output)
            
            return True
            
        except Exception as e:
            print(f"\n{Colors.ORANGE}❌ Error processing file: {e}{Colors.RESET}")
            print(f"{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
            try:
                input()
            except (KeyboardInterrupt, EOFError):
                pass
            return False
    
    def _disable_colors(self):
        """Disable color output."""
        for attr_name in dir(Colors):
            if not attr_name.startswith('_'):
                setattr(Colors, attr_name, '')
    
    def _display_in_less(self, content: str):
        """Display content in less viewer."""
        import subprocess
        import tempfile
        import stat
        
        fd, tmp_path = tempfile.mkstemp(suffix='.txt', prefix='jsonl_history_')
        try:
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)
            with os.fdopen(fd, 'w') as tmp:
                tmp.write(content)
            subprocess.run(['less', '-R', tmp_path])
        finally:
            os.unlink(tmp_path)
    
    def _save_to_file(self, content: str):
        """Save content to output file."""
        with open(self.settings['output_file'], 'w', encoding='utf-8') as f:
            f.write(content)


def interactive_file_selection(history_files: List[Path]) -> Optional[Path]:
    """Interactive file selection with project grouping and arrow key navigation."""
    if not history_files:
        return None
        
    # Group files by project
    projects = {}
    for file in history_files:
        project_name = file.parent.name
        if project_name not in projects:
            projects[project_name] = []
        projects[project_name].append(file)
    
    while True:  # Main loop to handle "go back" functionality
        # Create project menu items
        project_list = list(projects.keys())
        project_menu_items = []
        
        # Add "All Files" option
        project_menu_items.append(f"📄 All Files ({len(history_files)} total)")
        
        # Add project options
        for project_name in project_list:
            file_count = len(projects[project_name])
            latest_file = max(projects[project_name], key=lambda x: x.stat().st_mtime)
            mod_time = datetime.fromtimestamp(latest_file.stat().st_mtime)
            project_menu_items.append(f"📁 {project_name} ({file_count} files, latest: {mod_time.strftime('%m-%d %H:%M')})")
        
        # Show project selection menu
        choice = interactive_menu(project_menu_items, "📁 Select Project")
        
        # Handle less mode tuple (not applicable at project level, so ignore)
        if isinstance(choice, tuple) and choice[1] == 'less':
            continue  # Ignore less mode at project selection level
        elif choice == -1:  # Cancelled (q)
            return None
        elif choice == -2:  # Go back - but this is top level, so quit
            return None
        elif choice == 0:  # All files
            while True:  # File selection loop for all files
                # Create file menu for all files
                file_menu_items = []
                for file in history_files:
                    project_name = file.parent.name
                    mod_time = datetime.fromtimestamp(file.stat().st_mtime)
                    file_size = file.stat().st_size / 1024  # KB
                    file_menu_items.append(f"{project_name}/{file.name} ({mod_time.strftime('%m-%d %H:%M')}, {file_size:.1f} KB)")
                
                file_choice = interactive_menu(file_menu_items, "📄 Select History File")
                
                if file_choice == -1:  # Cancelled (q)
                    return None
                elif file_choice == -2:  # Go back
                    break  # Return to project selection
                elif isinstance(file_choice, tuple) and file_choice[1] == 'less':
                    # Less mode requested
                    selected_file = history_files[file_choice[0]]
                    return (selected_file, 'less')
                else:
                    return history_files[file_choice]
        else:
            # Selected a specific project
            selected_project = project_list[choice - 1]
            project_files = sorted(projects[selected_project], key=lambda x: x.stat().st_mtime, reverse=True)
            
            while True:  # File selection loop for project files
                    # Create file menu for project files
                    file_menu_items = []
                    for file in project_files:
                        mod_time = datetime.fromtimestamp(file.stat().st_mtime)
                        file_size = file.stat().st_size / 1024  # KB
                        file_menu_items.append(f"{file.name} ({mod_time.strftime('%m-%d %H:%M')}, {file_size:.1f} KB)")
                    
                    file_choice = interactive_menu(file_menu_items, f"📄 Files in {selected_project}")
                    
                    if file_choice == -1:  # Cancelled (q)
                        return None
                    elif file_choice == -2:  # Go back
                        break  # Return to project selection
                    elif isinstance(file_choice, tuple) and file_choice[1] == 'less':
                        # Less mode requested
                        selected_file = project_files[file_choice[0]]
                        return (selected_file, 'less')
                    else:
                        return project_files[file_choice]


def main():
    parser = argparse.ArgumentParser(
        description='JSONL History Formatter - Independent tool for formatting conversation logs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent('''
        NOTICE: This is an independent open-source tool. Not affiliated with 
        Anthropic, Claude, or any related services. Use responsibly and ensure 
        compliance with applicable terms of service.
        
        Examples:
          # Interactive menu mode (recommended)
          %(prog)s --menu
          
          # Interactive file selection only
          %(prog)s --select
          
          # List available themes
          %(prog)s --list-themes
          
          # Format with specific theme
          %(prog)s --theme default
          
          # List all available history files
          %(prog)s --list
          
          # Format a specific history file
          %(prog)s /path/to/history.jsonl
          
          # Format history from a specific project
          %(prog)s --project my-project
          
          # Save to file (colors preserved)
          %(prog)s --output formatted_history.txt
          
          # Disable colors for plain text output
          %(prog)s --no-color
        ''')
    )
    
    parser.add_argument('history_file', nargs='?', type=Path,
                       help='Path to history JSONL file (defaults to most recent)')
    parser.add_argument('--list', '-l', action='store_true',
                       help='List all available history files')
    parser.add_argument('--project', '-p', type=str,
                       help='Select history from specific project directory')
    parser.add_argument('--output', '-o', type=Path,
                       help='Output to file instead of stdout')
    parser.add_argument('--no-color', action='store_true',
                       help='Disable colors for plain text output')
    parser.add_argument('--force-color', action='store_true',
                       help='Force colors even when output is redirected')
    parser.add_argument('--select', '-s', action='store_true',
                       help='Interactive file selection mode')
    parser.add_argument('--base-dir', '-b', type=Path,
                       help='Base directory for Claude history files (default: $CLAUDE_HISTORY_DIR or ~/.claude/projects)')
    parser.add_argument('--theme', '-t', type=str, choices=list(THEMES.keys()), default='default',
                       help='Display theme (default: %(default)s)')
    parser.add_argument('--list-themes', action='store_true',
                       help='List available themes')
    parser.add_argument('--menu', '-m', action='store_true',
                       help='Start interactive menu mode')
    
    args = parser.parse_args()
    
    # Handle --menu mode first (no other args needed)
    if args.menu:
        session = InteractiveSession()
        if args.base_dir:
            session.projects_dir = args.base_dir
        if args.theme != 'default':
            session.settings['theme'] = args.theme
        if args.no_color:
            session.settings['no_color'] = True
        if args.force_color:
            session.settings['force_color'] = True
        if args.output:
            session.settings['output_file'] = args.output
        
        session.run_interactive_session()
        return
    
    # Handle --list-themes
    if args.list_themes:
        print(f"{Colors.GREEN}Available Themes:{Colors.RESET}")
        print("=" * 60)
        for theme_id, theme in THEMES.items():
            print(f"{Colors.WHITE}{theme_id:12}{Colors.RESET} - {theme['description']}")
            print(f"              Preview: {Colors.GREEN}{theme['symbols']['bullet']}{Colors.RESET} Command")
            print(f"                      {Colors.GRAY}{theme['symbols']['tool_result']}{Colors.RESET}  Result")
        return
    
    # Disable colors if requested or output is redirected (unless force-color is used)
    if args.no_color or (not args.force_color and args.output is None and not sys.stdout.isatty()):
        for attr_name in dir(Colors):
            if not attr_name.startswith('_'):
                setattr(Colors, attr_name, '')
    
    # Get projects directory
    if args.base_dir:
        projects_dir = args.base_dir
    else:
        projects_dir = get_default_projects_dir()
    
    # If no specific args, start menu mode
    if not any([args.history_file, args.list, args.project, args.select, args.output]):
        session = InteractiveSession()
        session.projects_dir = projects_dir
        session.run_interactive_session()
        return
    
    if args.select:
        # Interactive selection mode
        history_files = find_history_files(projects_dir)
        if not history_files:
            print(f"{Colors.ORANGE}📭 No history files found.{Colors.RESET}")
            return
            
        selected_file = interactive_file_selection(history_files)
        if not selected_file:
            return
        
        # Check if less mode was requested
        if isinstance(selected_file, tuple) and selected_file[1] == 'less':
            history_file = selected_file[0]
            print(f"{Colors.BLUE}📖 Opening in less: {history_file.name}{Colors.RESET}", file=sys.stderr)
            
            # Format the content first
            formatter = ClaudeHistoryColoredFormatter(history_file, theme=args.theme)
            formatter.parse()
            formatted_output = formatter.format_entries()
            
            # Open in less using subprocess
            import subprocess
            import tempfile
            import stat
            
            # Write formatted output to a temporary file with secure permissions
            fd, tmp_path = tempfile.mkstemp(suffix='.txt', prefix='claude_history_')
            try:
                # Set secure permissions (readable only by owner)
                os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)
                
                # Write content
                with os.fdopen(fd, 'w') as tmp:
                    tmp.write(formatted_output)
                
                # Use less with color support
                subprocess.run(['less', '-R', tmp_path])
            finally:
                # Clean up temporary file
                os.unlink(tmp_path)
        else:
            # Normal mode - parse and format the selected history
            print(f"{Colors.BLUE}📖 Reading: {selected_file.name}{Colors.RESET}", file=sys.stderr)
            
            formatter = ClaudeHistoryColoredFormatter(selected_file, theme=args.theme)
            formatter.parse()
            formatted_output = formatter.format_entries()
            
            # Output results
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(formatted_output)
                print(f"{Colors.GREEN}✅ Output written to: {args.output}{Colors.RESET}", file=sys.stderr)
            else:
                print(formatted_output)
        return
    
    if args.list:
        # List available history files with colors
        history_files = find_history_files(projects_dir)
        if not history_files:
            print("📭 No history files found.")
            return
            
        print(f"{Colors.GREEN}📚 Available Claude Code History Files:{Colors.RESET}")
        print("=" * 60)
        
        for i, file in enumerate(history_files, 1):
            project_name = file.parent.name
            mod_time = datetime.fromtimestamp(file.stat().st_mtime)
            file_size = file.stat().st_size / 1024  # KB
            
            print(f"{Colors.WHITE}{i:2d}.{Colors.RESET} {Colors.CYAN}📁 {project_name}{Colors.RESET}")
            print(f"    {Colors.BLUE}📄 {file.name}{Colors.RESET}")
            print(f"    {Colors.GRAY}🕐 {mod_time.strftime('%Y-%m-%d %H:%M:%S')}{Colors.RESET}")
            print(f"    {Colors.YELLOW}📊 {file_size:.1f} KB{Colors.RESET}")
            print()
        return
        
    # Determine which history file to parse
    if args.history_file:
        history_file = args.history_file
        # Validate the provided file path
        if not validate_path(history_file):
            print(f"{Colors.ORANGE}❌ Invalid file path{Colors.RESET}")
            return
    elif args.project:
        # Find history in specific project
        project_dir = projects_dir / args.project.replace('/', '-')
        if not project_dir.exists():
            project_dir = projects_dir / args.project
            
        if not project_dir.exists():
            print(f"{Colors.ORANGE}❌ Project not found{Colors.RESET}")
            return
            
        history_files = list(project_dir.glob('*.jsonl'))
        if not history_files:
            print(f"{Colors.ORANGE}📭 No history files found in project{Colors.RESET}")
            return
            
        history_file = sorted(history_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
    else:
        # Use most recent history file
        history_files = find_history_files(projects_dir)
        if not history_files:
            print(f"{Colors.ORANGE}📭 No history files found.{Colors.RESET}")
            return
            
        history_file = history_files[0]
        
    # Validate the final history file path
    if not validate_path(history_file, projects_dir.parent if projects_dir else None):
        print(f"{Colors.ORANGE}❌ Access denied to file{Colors.RESET}")
        return
        
    # Parse and format the history
    print(f"{Colors.BLUE}📖 Reading: {history_file.name}{Colors.RESET}", file=sys.stderr)
    
    formatter = ClaudeHistoryColoredFormatter(history_file, theme=args.theme)
    formatter.parse()
    formatted_output = formatter.format_entries()
    
    # Output results
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(formatted_output)
        print(f"{Colors.GREEN}✅ Output written to: {args.output}{Colors.RESET}", file=sys.stderr)
    else:
        print(formatted_output)


if __name__ == '__main__':
    main()