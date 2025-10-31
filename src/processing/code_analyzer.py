import ast
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

class CodeAnalyzer:
    """Analyze code files to extract functions, classes, imports, and structure"""
    
    def __init__(self):
        self.supported_languages = {
            '.py': self.analyze_python,
            '.js': self.analyze_javascript, 
            '.ts': self.analyze_javascript,  # TypeScript uses similar syntax
            '.jsx': self.analyze_javascript,
            '.tsx': self.analyze_javascript,
        }
    
    def analyze_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Analyze a code file and extract structural information"""
        extension = Path(file_path).suffix.lower()
        
        if extension in self.supported_languages:
            return self.supported_languages[extension](content, file_path)
        else:
            return self.analyze_generic(content, file_path)
    
    def analyze_python(self, content: str, file_path: str) -> Dict[str, Any]:
        """Analyze Python code using AST"""
        try:
            tree = ast.parse(content)
            
            analysis = {
                "language": "python",
                "file_path": file_path,
                "imports": [],
                "functions": [],
                "classes": [],
                "variables": [],
                "docstrings": [],
                "complexity_score": 0
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis["imports"].append({
                            "type": "import",
                            "name": alias.name,
                            "alias": alias.asname,
                            "line": node.lineno
                        })
                
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        analysis["imports"].append({
                            "type": "from_import", 
                            "module": module,
                            "name": alias.name,
                            "alias": alias.asname,
                            "line": node.lineno
                        })
                
                elif isinstance(node, ast.FunctionDef):
                    func_info = {
                        "name": node.name,
                        "line": node.lineno,
                        "args": [arg.arg for arg in node.args.args],
                        "returns": ast.unparse(node.returns) if node.returns else None,
                        "decorators": [ast.unparse(d) for d in node.decorator_list],
                        "docstring": ast.get_docstring(node),
                        "is_async": False
                    }
                    analysis["functions"].append(func_info)
                    
                    if func_info["docstring"]:
                        analysis["docstrings"].append({
                            "type": "function",
                            "name": node.name,
                            "content": func_info["docstring"],
                            "line": node.lineno
                        })
                
                elif isinstance(node, ast.AsyncFunctionDef):
                    func_info = {
                        "name": node.name,
                        "line": node.lineno, 
                        "args": [arg.arg for arg in node.args.args],
                        "returns": ast.unparse(node.returns) if node.returns else None,
                        "decorators": [ast.unparse(d) for d in node.decorator_list],
                        "docstring": ast.get_docstring(node),
                        "is_async": True
                    }
                    analysis["functions"].append(func_info)
                    
                    if func_info["docstring"]:
                        analysis["docstrings"].append({
                            "type": "async_function",
                            "name": node.name,
                            "content": func_info["docstring"],
                            "line": node.lineno
                        })
                
                elif isinstance(node, ast.ClassDef):
                    class_info = {
                        "name": node.name,
                        "line": node.lineno,
                        "bases": [ast.unparse(base) for base in node.bases],
                        "decorators": [ast.unparse(d) for d in node.decorator_list],
                        "docstring": ast.get_docstring(node),
                        "methods": []
                    }
                    
                    # Find methods in the class
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            class_info["methods"].append({
                                "name": item.name,
                                "line": item.lineno,
                                "is_async": isinstance(item, ast.AsyncFunctionDef)
                            })
                    
                    analysis["classes"].append(class_info)
                    
                    if class_info["docstring"]:
                        analysis["docstrings"].append({
                            "type": "class",
                            "name": node.name,
                            "content": class_info["docstring"],
                            "line": node.lineno
                        })
            
            # Calculate complexity score
            analysis["complexity_score"] = len(analysis["functions"]) + len(analysis["classes"]) * 2
            
            return analysis
            
        except SyntaxError as e:
            return {
                "language": "python",
                "file_path": file_path,
                "error": f"Syntax error: {e}",
                "imports": [],
                "functions": [],
                "classes": []
            }
    
    def analyze_javascript(self, content: str, file_path: str) -> Dict[str, Any]:
        """Analyze JavaScript/TypeScript using regex patterns"""
        analysis = {
            "language": "javascript",
            "file_path": file_path,
            "imports": [],
            "functions": [], 
            "classes": [],
            "exports": [],
            "complexity_score": 0
        }
        
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            
            # Import statements
            if line.startswith('import '):
                import_match = re.search(r'import\s+(.+?)\s+from\s+[\'"](.+?)[\'"]', line)
                if import_match:
                    analysis["imports"].append({
                        "what": import_match.group(1),
                        "from": import_match.group(2),
                        "line": i
                    })
            
            # Function declarations
            func_match = re.search(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)', line)
            if func_match:
                analysis["functions"].append({
                    "name": func_match.group(1),
                    "line": i,
                    "is_async": "async" in line,
                    "is_exported": "export" in line
                })
            
            # Arrow functions
            arrow_match = re.search(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(', line)
            if arrow_match:
                analysis["functions"].append({
                    "name": arrow_match.group(1), 
                    "line": i,
                    "type": "arrow_function",
                    "is_async": "async" in line
                })
            
            # Class declarations
            class_match = re.search(r'(?:export\s+)?class\s+(\w+)', line)
            if class_match:
                analysis["classes"].append({
                    "name": class_match.group(1),
                    "line": i,
                    "is_exported": "export" in line
                })
            
            # Export statements
            if line.startswith('export '):
                export_match = re.search(r'export\s+(?:default\s+)?(.+)', line)
                if export_match:
                    analysis["exports"].append({
                        "what": export_match.group(1),
                        "line": i,
                        "is_default": "default" in line
                    })
        
        analysis["complexity_score"] = len(analysis["functions"]) + len(analysis["classes"]) * 2
        return analysis
    
    def analyze_generic(self, content: str, file_path: str) -> Dict[str, Any]:
        """Generic analysis for unsupported languages"""
        lines = content.split('\n')
        
        return {
            "language": "unknown",
            "file_path": file_path,
            "line_count": len(lines),
            "char_count": len(content),
            "non_empty_lines": len([line for line in lines if line.strip()]),
            "has_comments": any(line.strip().startswith(('#', '//', '/*', '<!--')) for line in lines)
        }
    
    def extract_code_chunks(self, content: str, file_path: str, max_chunk_size: int = 1000) -> List[Dict[str, Any]]:
        """Extract meaningful code chunks based on structure"""
        analysis = self.analyze_file(file_path, content)
        chunks = []
        lines = content.split('\n')
        
        if analysis.get("language") == "python":
            # Chunk by functions and classes
            for func in analysis.get("functions", []):
                start_line = func["line"] - 1
                end_line = self._find_python_block_end(lines, start_line)
                
                chunk_content = '\n'.join(lines[start_line:end_line])
                if len(chunk_content) <= max_chunk_size:
                    chunks.append({
                        "content": chunk_content,
                        "type": "function",
                        "name": func["name"],
                        "start_line": start_line + 1,
                        "end_line": end_line,
                        "metadata": func
                    })
            
            for cls in analysis.get("classes", []):
                start_line = cls["line"] - 1
                end_line = self._find_python_block_end(lines, start_line)
                
                chunk_content = '\n'.join(lines[start_line:end_line])
                if len(chunk_content) <= max_chunk_size:
                    chunks.append({
                        "content": chunk_content,
                        "type": "class",
                        "name": cls["name"],
                        "start_line": start_line + 1,
                        "end_line": end_line,
                        "metadata": cls
                    })
        
        # If no structured chunks or chunks too large, fall back to line-based chunking
        if not chunks:
            chunk_size_lines = max_chunk_size // 50  # Rough estimate
            for i in range(0, len(lines), chunk_size_lines):
                chunk_lines = lines[i:i + chunk_size_lines]
                chunk_content = '\n'.join(chunk_lines)
                
                chunks.append({
                    "content": chunk_content,
                    "type": "section",
                    "start_line": i + 1,
                    "end_line": min(i + chunk_size_lines, len(lines)),
                    "metadata": {"line_based": True}
                })
        
        return chunks
    
    def _find_python_block_end(self, lines: List[str], start_line: int) -> int:
        """Find the end of a Python function/class block"""
        if start_line >= len(lines):
            return len(lines)
        
        # Find the indentation level of the definition
        def_line = lines[start_line]
        base_indent = len(def_line) - len(def_line.lstrip())
        
        # Look for the end of the block
        for i in range(start_line + 1, len(lines)):
            line = lines[i]
            if line.strip() == "":
                continue
            
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= base_indent and line.strip():
                return i
        
        return len(lines)