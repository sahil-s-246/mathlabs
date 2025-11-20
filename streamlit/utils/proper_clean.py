#!/usr/bin/env python3
import ast
import re
import os
import shutil

def remove_emojis(text):
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE
    )
    return emoji_pattern.sub('', text)

class CodeCleaner(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        node.body = [self.visit(stmt) for stmt in node.body if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Str)]
        return node
    
    def visit_Module(self, node):
        node.body = [self.visit(stmt) for stmt in node.body if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, (ast.Str, ast.Constant))]
        return node

def clean_file_ast(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        cleaned_lines = []
        skip_docstring = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            if stripped.startswith('#!/'):
                cleaned_lines.append(line)
                continue
            
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                    continue
                if '"""' in stripped[3:] or "'''" in stripped[3:]:
                    continue
                skip_docstring = True
                continue
            
            if skip_docstring:
                if '"""' in line or "'''" in line:
                    skip_docstring = False
                continue
            
            if stripped.startswith('#'):
                continue
            
            if '#' in line and not skip_docstring:
                parts = line.split('#', 1)
                if parts[0].strip():
                    line = parts[0].rstrip()
                else:
                    continue
            
            line = remove_emojis(line)
            cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines)
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        try:
            ast.parse(result)
        except:
            return content
        
        return result
    except:
        return content

source_dir = '/Users/akhileshvangala/dataset_project/sahil_smart/model_eval/send_bruce'
dest_dir = '/Users/akhileshvangala/Desktop/send_bruce'

files_to_process = [
    ('streamlit_app.py', 'streamlit_app.py'),
    ('pages/1_📊_Multi_Question_Dashboard.py', 'pages/1_Multi_Question_Dashboard.py'),
    ('pages/2_🔍_Single_Question_Analysis.py', 'pages/2_Single_Question_Analysis.py'),
]

for src, dst in files_to_process:
    src_path = os.path.join(source_dir, src)
    dst_path = os.path.join(dest_dir, dst)
    
    if os.path.exists(src_path):
        with open(src_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        cleaned = []
        in_docstring = False
        docstring_quote = None
        
        for line in lines:
            stripped = line.strip()
            
            if stripped.startswith('#!/'):
                cleaned.append(line)
                continue
            
            if not in_docstring and (stripped.startswith('"""') or stripped.startswith("'''")):
                if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                    continue
                in_docstring = True
                docstring_quote = '"""' if '"""' in stripped else "'''"
                continue
            
            if in_docstring:
                if docstring_quote in line:
                    in_docstring = False
                continue
            
            if stripped.startswith('#'):
                continue
            
            if '#' in line and not in_docstring:
                code_part = line.split('#')[0]
                if code_part.strip():
                    line = code_part.rstrip()
                else:
                    continue
            
            line = remove_emojis(line)
            cleaned.append(line)
        
        result = '\n'.join(cleaned)
        result = re.sub(r'\n{4,}', '\n\n\n', result)
        
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        with open(dst_path, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"Processed: {src} -> {dst}")

shutil.copy(os.path.join(source_dir, 'requirements_dashboard.txt'), 
            os.path.join(dest_dir, 'requirements_dashboard.txt'))
shutil.copy(os.path.join(source_dir, 'README.md'), 
            os.path.join(dest_dir, 'README.md'))

print(f"\nFiles ready at: {dest_dir}")

