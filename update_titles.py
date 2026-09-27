#!/usr/bin/env python
"""
Batch update all template titles from "Mini POS" to "Mo Mo Pajamas For You"
"""
import os
import re

template_dir = r"C:\Mo Mo Pajamas\app\templates"

# Pattern to match and replace
old_pattern = r"Mini POS"
new_text = "Mo Mo Pajamas For You"

files_updated = 0

for root, dirs, files in os.walk(template_dir):
    for file in files:
        if file.endswith(".html"):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace "Mini POS" with "Mo Mo Pajamas For You" in title blocks
            new_content = content.replace("Mini POS", new_text)
            
            if new_content != content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                files_updated += 1
                print(f"Updated: {os.path.relpath(filepath, template_dir)}")

print(f"\nTotal files updated: {files_updated}")