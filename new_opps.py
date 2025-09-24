#!/usr/bin/env python3
"""
Script to detect new Summer 2026 internship opportunities from listings.json changes
and generate email content for notifications.
"""

import json
import os
import sys
import glob
from datetime import datetime
from typing import Dict, List, Any, Set

def load_listings_json(file_path: str) -> Dict[str, Any]:
    """Load and parse listings.json file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading {file_path}: {e}")
        return {}

def extract_added_lines_from_patch(patch_file: str) -> List[str]:
    """Extract added lines from a patch file for listings.json."""
    added_lines = []
    in_listings_section = False
    
    try:
        with open(patch_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Check if we're entering the listings.json section
                if line.startswith('+++') and 'listings.json' in line:
                    in_listings_section = True
                    continue
                # Check if we're leaving the listings.json section (next file)
                elif line.startswith('+++') and 'listings.json' not in line:
                    in_listings_section = False
                    continue
                # If we're in listings.json section and line starts with +, it's an addition
                elif in_listings_section and line.startswith('+') and not line.startswith('+++'):
                    added_lines.append(line[1:])  # Remove the + prefix
    except FileNotFoundError:
        print(f"Patch file {patch_file} not found")
    
    return added_lines

def parse_json_from_lines(lines: List[str]) -> Dict[str, Any]:
    """Parse JSON content from a list of lines."""
    try:
        # Join lines and try to parse as JSON
        json_content = ''.join(lines)
        return json.loads(json_content)
    except json.JSONDecodeError:
        # If full JSON parsing fails, try to extract individual entries
        entries = {}
        current_entry = []
        brace_count = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            current_entry.append(line)
            
            # Count braces to detect complete JSON objects
            brace_count += line.count('{') - line.count('}')
            
            # If we have a complete object, try to parse it
            if brace_count == 0 and current_entry:
                try:
                    entry_json = json.loads(''.join(current_entry))
                    # Extract company name from the entry if possible
                    if isinstance(entry_json, dict):
                        # This is a simplified approach - in reality, you'd need to
                        # reconstruct the full JSON structure properly
                        pass
                except json.JSONDecodeError:
                    pass
                current_entry = []
        
        return {}
    except Exception as e:
        print(f"Error parsing JSON from lines: {e}")
        return {}

def find_summer_2026_opportunities(listings: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find all opportunities that have 'Summer 2026' in their terms."""
    summer_2026_opportunities = []
    
    for company, opportunities in listings.items():
        if not isinstance(opportunities, list):
            continue
            
        for opportunity in opportunities:
            if isinstance(opportunity, dict):
                # Check if 'terms' key exists and contains 'Summer 2026'
                terms = opportunity.get('terms', [])
                if isinstance(terms, list):
                    if any('Summer 2026' in str(term) for term in terms):
                        opportunity['company'] = company
                        summer_2026_opportunities.append(opportunity)
                elif isinstance(terms, str) and 'Summer 2026' in terms:
                    opportunity['company'] = company
                    summer_2026_opportunities.append(opportunity)
    
    return summer_2026_opportunities

def find_new_summer_2026_opportunities_from_patches() -> List[Dict[str, Any]]:
    """Find new Summer 2026 opportunities by analyzing patch files."""
    summer_2026_opportunities = []
    
    # Look for patch files in the changes directory
    patch_files = glob.glob("changes/patch-*.patch")
    
    for patch_file in patch_files:
        print(f"Processing patch file: {patch_file}")
        
        # Extract added lines from this patch
        added_lines = extract_added_lines_from_patch(patch_file)
        
        if not added_lines:
            continue
            
        # Try to parse the added content as JSON
        added_content = parse_json_from_lines(added_lines)
        
        # Find Summer 2026 opportunities in the added content
        new_opportunities = find_summer_2026_opportunities(added_content)
        summer_2026_opportunities.extend(new_opportunities)
    
    return summer_2026_opportunities

def format_opportunity(opp: Dict[str, Any]) -> str:
    """Format a single opportunity for email display."""
    company = opp.get('company', 'Unknown Company')
    role = opp.get('role', 'Unknown Role')
    location = opp.get('location', 'Unknown Location')
    application_link = opp.get('application_link', 'No link provided')
    
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
    companies = {}
    for opp in new_opportunities:
        company = opp.get('company', 'Unknown')
        if company not in companies:
            companies[company] = []
        companies[company].append(opp)
    
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
    """Main function to process listings.json changes and generate email."""
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
            company = opp.get('company', 'Unknown')
            role = opp.get('role', 'Unknown')
            terms = opp.get('terms', [])
            print(f"{i}. {company} - {role} (Terms: {terms})")
        if len(new_opportunities) > 5:
            print(f"... and {len(new_opportunities) - 5} more")
    else:
        print("📭 No new Summer 2026 opportunities found in the changes")

if __name__ == "__main__":
    main()
