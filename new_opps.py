#!/usr/bin/env python3
"""
Script to detect new Summer 2026 internship opportunities from README.md changes
and generate email content for notifications.
"""

import os
import glob
import re
from typing import Dict, List, Any, Set, Tuple


def extract_added_lines_from_patch(patch_file: str) -> List[str]:
    """Extract added lines from a patch file for README.md."""
    added_lines = []
    in_readme_section = False

    try:
        with open(patch_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Check if we're entering README.md section
                if line.startswith('+++') and 'README.md' in line:
                    in_readme_section = True
                    continue
                elif line.startswith('+++') and 'README.md' not in line:
                    in_readme_section = False
                    continue

                # Collect only added lines (ignore diff headers)
                if in_readme_section and line.startswith('+') and not line.startswith('+++'):
                    added_lines.append(line[1:].rstrip())
    except FileNotFoundError:
        print(f"Patch file {patch_file} not found")

    return added_lines

def parse_opportunities_from_readme_lines(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse internship opportunities from README table rows."""
    opportunities = []
    
    # Process lines in groups to capture complete table rows
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Look for table rows that contain internship data
        if '<tr>' in line:
            # Collect the next few lines to get the complete table row
            row_lines = []
            j = i
            while j < len(lines) and '</tr>' not in lines[j]:
                row_lines.append(lines[j])
                j += 1
            if j < len(lines):
                row_lines.append(lines[j])  # Include the closing </tr>
            
            # Join the row lines to analyze the complete row
            row_text = ' '.join(row_lines)
            
            # Check if this row contains an internship opportunity
            if '<td><strong><a href=' in row_text and 'Apply' in row_text:
                opportunity = parse_single_opportunity_from_row(row_text)
                if opportunity:
                    opportunities.append(opportunity)
            
            i = j + 1
        else:
            i += 1
    
    return opportunities

def parse_single_opportunity_from_row(row_text: str) -> Dict[str, Any]:
    """Parse a single opportunity from a complete table row."""
    try:
        # Extract company name from the first <td> with company link
        company_match = re.search(r'<td><strong><a href="[^"]*">([^<]+)</a></strong></td>', row_text)
        company = company_match.group(1) if company_match else "Unknown Company"
        
        # Extract role from the second <td>
        role_match = re.search(r'<td><strong><a href="[^"]*">[^<]+</a></strong></td>\s*<td>([^<]+)</td>', row_text)
        if not role_match:
            # Try alternative pattern for role
            role_match = re.search(r'</td>\s*<td>([^<]+)</td>', row_text)
        role = role_match.group(1).strip() if role_match else "Software Engineering Intern"
        
        # Extract location from the third <td>
        location_match = re.search(r'<td>([^<]+)</td>\s*<td><div align="center">', row_text)
        location = location_match.group(1).strip() if location_match else "Various"
        
        # Extract application URL
        url_match = re.search(r'<a href="([^"]*)"[^>]*><img[^>]*alt="Apply"', row_text)
        url = url_match.group(1) if url_match else "No link provided"
        
        return {
            'company_name': company,
            'title': role,
            'url': url,
            'locations': [location] if location != "Various" else ['Various'],
            'terms': ['Summer 2026']  # Assume Summer 2026 for this repo
        }
    except Exception as e:
        print(f"Error parsing opportunity from row: {e}")
        return None



def find_new_summer_2026_opportunities_from_patches() -> List[Dict[str, Any]]:
    """Find new Summer 2026 opportunities by analyzing README patch files."""
    summer_2026_opportunities = []

    # Look for patch files in the changes directory
    patch_files = glob.glob("changes/*.patch")

    for patch_file in patch_files:
        print(f"Processing patch file: {patch_file}")

        # Extract added lines from this patch
        added_lines = extract_added_lines_from_patch(patch_file)

        # Parse newly added opportunities from README content
        if added_lines:
            new_opportunities = parse_opportunities_from_readme_lines(added_lines)
            summer_2026_opportunities.extend(new_opportunities)

    # De-duplicate by company name and URL
    deduped: List[Dict[str, Any]] = []
    seen_keys: Set[Tuple[str, str]] = set()
    for opp in summer_2026_opportunities:
        key = (str(opp.get('company_name')), str(opp.get('url')))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(opp)

    return deduped

def format_opportunity(opp: Dict[str, Any]) -> str:
    """Format a single opportunity for email display."""
    company = opp.get('company_name', 'Unknown Company')
    role = opp.get('title', 'Unknown Role')
    location = ', '.join(opp.get('locations', [])) if isinstance(opp.get('locations'), list) else opp.get('locations', 'Unknown Location')
    application_link = opp.get('url', 'No link provided')

    return f"""🏢 COMPANY: {company}
💼 ROLE: {role}
📍 LOCATION: {location}
🔗 APPLICATION: {application_link}"""

def generate_email_body(new_opportunities: List[Dict[str, Any]]) -> str:
    """Generate the email body content."""
    if not new_opportunities:
        return """📭 NO NEW SUMMER 2026 INTERNSHIPS DETECTED

No new Summer 2026 internship opportunities were found in the latest sync.
Check back later for new opportunities!"""

    # Header
    email_content = """🚀 NEW SUMMER 2026 INTERNSHIP OPPORTUNITIES DETECTED! 🚀

The following new Summer 2026 internships have been added to the repository:

"""

    # Group by company for better organization
    companies: Dict[str, List[Dict[str, Any]]] = {}
    for opp in new_opportunities:
        company = opp.get('company_name', 'Unknown')
        companies.setdefault(company, []).append(opp)

    # Add opportunities grouped by company
    for company, opps in companies.items():
        email_content += f"📋 COMPANY: {company}\n"
        email_content += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        for opp in opps:
            email_content += format_opportunity(opp) + "\n\n"

        email_content += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # Footer
    email_content += """💡 TIP: Apply early! These Summer 2026 opportunities are fresh and competition is high.

Good luck with your applications! 🎯"""

    return email_content

def main():
    """Main function to process README.md changes and generate email."""
    print("🔍 Analyzing patch files for new Summer 2026 opportunities...")

    # Find new Summer 2026 opportunities from patch files
    new_opportunities = find_new_summer_2026_opportunities_from_patches()

    # Generate email body
    email_body = generate_email_body(new_opportunities)

    # Write email body to file
    os.makedirs("email", exist_ok=True)
    with open("email/body.txt", "w", encoding="utf-8") as f:
        f.write(email_body)

    print(f"✅ Found {len(new_opportunities)} new Summer 2026 opportunities")
    print("📧 Email body written to email/body.txt")

    # Print summary for debugging
    if new_opportunities:
        print("\n🎯 New Summer 2026 opportunities found:")
        for i, opp in enumerate(new_opportunities[:5], 1):  # Show first 5
            company = opp.get('company_name', 'Unknown')
            role = opp.get('title', 'Unknown')
            url = opp.get('url', 'No URL')
            print(f"{i}. {company} - {role} (URL: {url[:50]}...)")
        if len(new_opportunities) > 5:
            print(f"... and {len(new_opportunities) - 5} more")
    else:
        print("📭 No new Summer 2026 opportunities found in the changes")

if __name__ == "__main__":
    main()
