#!/usr/bin/env python3
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

def clean_python_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    cleaned_lines = []
    in_docstring = False
    docstring_delimiter = None
    docstring_indent = 0
    
    for line in lines:
        original_line = line
        stripped = line.strip()
        
        if not stripped:
            cleaned_lines.append('\n')
            continue
        
        if stripped.startswith('#!/'):
            cleaned_lines.append(line)
            continue
        
        if stripped.startswith('"""') or stripped.startswith("'''"):
            if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                continue
            in_docstring = True
            docstring_delimiter = '"""' if '"""' in stripped else "'''"
            docstring_indent = len(line) - len(line.lstrip())
            continue
        
        if in_docstring:
            if docstring_delimiter in line:
                in_docstring = False
                docstring_delimiter = None
            continue
        
        if stripped.startswith('#'):
            continue
        
        if '#' in line and not in_docstring:
            code, comment = line.split('#', 1)
            if code.strip():
                line = code.rstrip() + '\n'
            else:
                continue
        
        line = remove_emojis(line)
        cleaned_lines.append(line)
    
    result = ''.join(cleaned_lines)
    result = re.sub(r'\n{4,}', '\n\n\n', result)
    return result

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
        cleaned = clean_python_file(src_path)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        with open(dst_path, 'w', encoding='utf-8') as f:
            f.write(cleaned)
        print(f"Cleaned: {src} -> {dst}")

shutil.copy(os.path.join(source_dir, 'requirements_dashboard.txt'), 
            os.path.join(dest_dir, 'requirements_dashboard.txt'))
shutil.copy(os.path.join(source_dir, 'README.md'), 
            os.path.join(dest_dir, 'README.md'))

print(f"\nAll files copied to: {dest_dir}")

