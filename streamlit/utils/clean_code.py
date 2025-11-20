#!/usr/bin/env python3
import re
import ast
import sys

def remove_emojis_from_string(text):
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

def clean_file_content(content):
    lines = content.split('\n')
    cleaned_lines = []
    skip_next = False
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        if skip_next:
            skip_next = False
            continue
        
        if stripped.startswith('"""') or stripped.startswith("'''"):
            if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                continue
            if '"""' in stripped[3:] or "'''" in stripped[3:]:
                continue
            skip_next = True
            continue
        
        if stripped.startswith('#'):
            continue
        
        if '#' in line:
            code_part = line.split('#')[0]
            if code_part.strip():
                line = code_part.rstrip()
            else:
                continue
        
        line = remove_emojis_from_string(line)
        
        cleaned_lines.append(line)
    
    result = '\n'.join(cleaned_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result

if __name__ == "__main__":
    files = ['streamlit_app.py', 'pages/1_Multi_Question_Dashboard.py', 'pages/2_Single_Question_Analysis.py']
    
    for filepath in files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            cleaned = clean_file_content(content)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(cleaned)
            
            print(f"Cleaned: {filepath}")
        except Exception as e:
            print(f"Error cleaning {filepath}: {e}")

