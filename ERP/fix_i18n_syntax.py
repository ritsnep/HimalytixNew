#!/usr/bin/env python
"""
Script to fix invalid i18n syntax in Django templates.
Converts {{ i18n["key"]|default:"value" }} to {% trans "value" %}
"""
import os
import re
import sys
from pathlib import Path

def fix_template_file(file_path):
    """Fix i18n syntax in a single template file."""
    print(f"Processing: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"  Error reading file: {e}")
        return False
    
    original_content = content
    changes = 0
    
    # Pattern to match {{ i18n["..."]|default:"..." }}
    pattern = r'\{\{\s*i18n\["[^"]*"\]\|default:"([^"]*)"\s*\}\}'
    
    # Find all matches to count them
    matches = list(re.finditer(pattern, content))
    if not matches:
        print(f"  No i18n syntax found")
        return False
    
    print(f"  Found {len(matches)} i18n references")
    
    # Replace all occurrences
    content = re.sub(pattern, r'{% trans "\1" %}', content)
    changes = len(matches)
    
    # Check if {% load i18n %} is present
    has_load_i18n = '{% load i18n %}' in content
    
    if not has_load_i18n and changes > 0:
        # Add {% load i18n %} at the top, after {% extends %} if present
        if '{% extends' in content:
            # Add after extends tag
            content = re.sub(
                r'(\{% extends [^\%]*\%\})',
                r'\1\n{% load i18n %}',
                content,
                count=1
            )
        else:
            # Add at the very top
            content = '{% load i18n %}\n' + content
        print("  Added {% load i18n %}")
    
    if content != original_content:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✓ Fixed {changes} references")
            return True
        except Exception as e:
            print(f"  Error writing file: {e}")
            return False
    else:
        print(f"  No changes needed")
        return False

def main():
    """Find and fix all template files."""
    # Get the accounting templates directory
    script_dir = Path(__file__).parent
    templates_dir = script_dir / 'accounting' / 'templates' / 'accounting'
    
    if not templates_dir.exists():
        print(f"Error: Templates directory not found: {templates_dir}")
        return 1
    
    print(f"Scanning templates in: {templates_dir}")
    print("-" * 60)
    
    # Find all .html files
    html_files = list(templates_dir.rglob('*.html'))
    print(f"Found {len(html_files)} HTML template files\n")
    
    fixed_count = 0
    for html_file in html_files:
        if fix_template_file(html_file):
            fixed_count += 1
        print()
    
    print("-" * 60)
    print(f"Summary: Fixed {fixed_count} out of {len(html_files)} files")
    return 0

if __name__ == '__main__':
    sys.exit(main())
