#!/usr/bin/env python3
"""
Script to detect new Summer 2026 internship opportunities from listings.json changes
and generate email content for notifications.
"""

import json
import os
import glob
import re
from typing import Dict, List, Any, Set, Tuple

def load_listings_json(file_path: str) -> List[Dict[str, Any]]:
    """Load and parse listings.json file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading {file_path}: {e}")
        return []

def extract_added_lines_from_patch(patch_file: str) -> List[str]:
    """Extract added lines from a patch file for listings.json."""
    added_lines = []
    in_listings_section = False

    try:
        with open(patch_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Check if we're entering listings.json section
                if line.startswith('+++') and 'listings.json' in line:
                    in_listings_section = True
                    continue
                elif line.startswith('+++') and 'listings.json' not in line:
                    in_listings_section = False
                    continue

                # Collect only added lines (ignore diff headers)
                if in_listings_section and line.startswith('+') and not line.startswith('+++'):
                    added_lines.append(line[1:].rstrip())
    except FileNotFoundError:
        print(f"Patch file {patch_file} not found")

    return added_lines

def extract_activation_flip_identifiers_from_patch(patch_file: str) -> List[Dict[str, str]]:
    """Detect hunks where an entry flips from "active": false to "active": true
    and extract nearby identifiers (id, url, company_name, title, first location).

    Returns a list of attribute dictionaries per flipped entry with whatever
    identifiers were discoverable from the hunk context.
    """
    flips: List[Dict[str, str]] = []
    in_listings_section = False
    current_hunk: List[str] = []

    try:
        with open(patch_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('+++'):
                    in_listings_section = 'listings.json' in line
                    # Reset any accumulated hunk when switching files
                    current_hunk = []
                    continue

                # Track hunk content only for listings.json
                if not in_listings_section:
                    continue

                # Hunk headers start with @@, reset buffer
                if line.startswith('@@'):
                    if current_hunk:
                        # process previous hunk before starting a new one
                        _maybe_extract_flip(current_hunk, flips)
                    current_hunk = []
                    current_hunk.append(line)
                    continue

                # Accumulate lines within the hunk (context ' ', removals '-', additions '+')
                if line.startswith((' ', '+', '-')):
                    current_hunk.append(line)

            # Process the final hunk at EOF
            if current_hunk:
                _maybe_extract_flip(current_hunk, flips)

    except FileNotFoundError:
        pass

    return flips

def _maybe_extract_flip(hunk_lines: List[str], flips_out: List[Dict[str, str]]) -> None:
    """If the given hunk contains an active false->true flip, extract identifiers."""
    text = ''.join(hunk_lines)
    has_false = re.search(r'\n-\s*"active"\s*:\s*false', text) is not None
    has_true  = re.search(r'\n\+\s*"active"\s*:\s*true', text) is not None
    if has_false and has_true:
        # Try to extract identifiers from the hunk context (any of +, -, or space lines)
        attrs: Dict[str, str] = {}
        joined = '\n'.join(hunk_lines)

        def grab(pattern: str, key: str) -> None:
            if key in attrs:
                return
            m = re.search(pattern, joined)
            if m:
                attrs[key] = m.group(1)

        # Prefer id/url, then company/title/location
        grab(r'"id"\s*:\s*"([^"]+)"', 'id')
        grab(r'"url"\s*:\s*"([^"]+)"', 'url')
        grab(r'"company_name"\s*:\s*"([^"]+)"', 'company_name')
        grab(r'"title"\s*:\s*"([^"]+)"', 'title')
        # First location inside locations array on same or following line
        grab(r'"locations"\s*:\s*\[\s*"([^"]+)"', 'location')

        if attrs:
            flips_out.append(attrs)

def parse_json_from_lines(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse JSON objects from added patch lines."""
    if not lines:
        return []

    # Join lines and try to find JSON objects by braces
    text = "\n".join(lines)

    objects = []
    buffer = []
    brace_count = 0

    for line in text.splitlines():
        if "{" in line:
            brace_count += line.count("{")
        if "}" in line:
            brace_count -= line.count("}")

        buffer.append(line)

        if brace_count == 0 and buffer:
            candidate = "\n".join(buffer).strip().rstrip(",")
            try:
                obj = json.loads(candidate)
                objects.append(obj)
            except json.JSONDecodeError:
                pass
            buffer = []

    return objects

def find_summer_2026_opportunities(listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find all opportunities that have 'Summer 2026' in their terms."""
    summer_2026_opportunities = []

    for opportunity in listings:
        if isinstance(opportunity, dict):
            terms = opportunity.get('terms', [])
            if isinstance(terms, list) and any('Summer 2026' in str(term) for term in terms):
                summer_2026_opportunities.append(opportunity)
            elif isinstance(terms, str) and 'Summer 2026' in terms:
                summer_2026_opportunities.append(opportunity)

    return summer_2026_opportunities

def find_new_summer_2026_opportunities_from_patches() -> List[Dict[str, Any]]:
    """Find new Summer 2026 opportunities by analyzing patch files."""
    summer_2026_opportunities = []

    # Look for patch files in the changes directory
    patch_files = glob.glob("changes/*.patch")

    # Collect IDs/URLs of entries whose active flipped to true
    flipped_attrs: List[Dict[str, str]] = []

    for patch_file in patch_files:
        print(f"Processing patch file: {patch_file}")

        # Extract added lines from this patch
        added_lines = extract_added_lines_from_patch(patch_file)

        # Parse newly added objects (brand-new entries)
        if added_lines:
            added_content = parse_json_from_lines(added_lines)
            new_opportunities = find_summer_2026_opportunities(added_content)
            summer_2026_opportunities.extend(new_opportunities)

        # Also detect active false->true flips in this patch
        flipped_attrs.extend(extract_activation_flip_identifiers_from_patch(patch_file))

    # If we detected flips, load full listings and pull those entries
    if flipped_attrs:
        listings_path = os.path.join('.github', 'scripts', 'listings.json')
        current_listings: List[Dict[str, Any]] = load_listings_json(listings_path)

        def entry_matches_attrs(entry: Dict[str, Any], attrs: Dict[str, str]) -> bool:
            if 'id' in attrs and entry.get('id') == attrs['id']:
                return True
            if 'url' in attrs and entry.get('url') == attrs['url']:
                return True
            # Fallback: match by company, title, and location if available
            company_ok = ('company_name' not in attrs) or (entry.get('company_name') == attrs.get('company_name'))
            title_ok = ('title' not in attrs) or (entry.get('title') == attrs.get('title'))
            if isinstance(entry.get('locations'), list):
                loc_ok = ('location' not in attrs) or (attrs.get('location') in entry.get('locations', []))
            else:
                loc_ok = ('location' not in attrs) or (entry.get('locations') == attrs.get('location'))
            return company_ok and title_ok and loc_ok

        flipped_entries: List[Dict[str, Any]] = []
        for attrs in flipped_attrs:
            match = next((e for e in current_listings if entry_matches_attrs(e, attrs)), None)
            if match:
                flipped_entries.append(match)

        # Filter flipped entries to Summer 2026
        summer_2026_opportunities.extend(find_summer_2026_opportunities(flipped_entries))

    # De-duplicate by id or url
    deduped: List[Dict[str, Any]] = []
    seen_keys: Set[Tuple[str, str]] = set()
    for opp in summer_2026_opportunities:
        key = (str(opp.get('id')), str(opp.get('url')))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(opp)

    return deduped

    return summer_2026_opportunities

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
            company = opp.get('company_name', 'Unknown')
            role = opp.get('title', 'Unknown')
            terms = opp.get('terms', [])
            print(f"{i}. {company} - {role} (Terms: {terms})")
        if len(new_opportunities) > 5:
            print(f"... and {len(new_opportunities) - 5} more")
    else:
        print("📭 No new Summer 2026 opportunities found in the changes")

if __name__ == "__main__":
    main()
