#!/usr/bin/env python3
"""
Script to detect new Summer 2026 internship opportunities from README.md changes
and generate email content for notifications.
"""

import os
import glob
import re
import html
from typing import Dict, List, Any, Set, Tuple

# --- Email theme (summer internships = warm orange) ----------------------
ACCENT = "#ea580c"
EMOJI = "☀️"
LABEL_SHORT = "Summer 2026 internship"


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
                if opportunity and opportunity.get('age') == '0d':
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
        
        # Extract age from the last <td>
        age_match = re.search(r'<td>(\d+d)</td>\s*</tr>', row_text)
        age = age_match.group(1) if age_match else "Unknown"
        
        return {
            'company_name': company,
            'title': role,
            'url': url,
            'locations': [location] if location != "Various" else ['Various'],
            'terms': ['Summer 2026'],  # Assume Summer 2026 for this repo
            'age': age
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

def _opp_fields(opp: Dict[str, Any]) -> Dict[str, str]:
    """Normalize a single opportunity's fields for rendering."""
    locs = opp.get('locations', [])
    location = ', '.join(locs) if isinstance(locs, list) else str(locs)
    url = opp.get('url', '') or ''
    return {
        'company': opp.get('company_name', 'Unknown Company'),
        'role': opp.get('title', 'Unknown Role'),
        'location': location or 'Various',
        'url': url,
        'age': opp.get('age', 'Unknown'),
    }


# =============================================================================
# Plain-text email (send-gate marker + fallback for non-HTML clients)
# =============================================================================

def format_opportunity(opp: Dict[str, Any]) -> str:
    """Format a single opportunity for the plain-text email."""
    f = _opp_fields(opp)
    link = f['url'] if f['url'] else 'No link provided'
    return f"""🏢 COMPANY: {f['company']}
💼 ROLE: {f['role']}
📍 LOCATION: {f['location']}
🔗 APPLICATION: {link}
⏰ AGE: {f['age']}"""


def generate_email_text(new_opportunities: List[Dict[str, Any]]) -> str:
    """Generate the plain-text email body. Keeps the '🏢 COMPANY:' send gate."""
    if not new_opportunities:
        return """📭 NO NEW SUMMER 2026 INTERNSHIPS DETECTED

No new Summer 2026 internship opportunities (0d age) were found in the latest sync.
Check back later for new opportunities!"""

    count = len(new_opportunities)
    noun = "internship" if count == 1 else "internships"
    lines = [f"☀️ {count} new Summer 2026 {noun} just posted (added today).", ""]
    for opp in new_opportunities:
        lines.append(format_opportunity(opp))
        lines.append("")
        lines.append("─" * 48)
        lines.append("")
    lines.append("💡 These went up today — apply early, they move fast. Good luck! 🎯")
    return "\n".join(lines)


# =============================================================================
# HTML email (engaging, card-based, clickable Apply buttons)
# =============================================================================

def _render_card(opp: Dict[str, Any]) -> str:
    """Render one opportunity as an email-safe HTML card."""
    f = _opp_fields(opp)
    company = html.escape(f['company'])
    role = html.escape(f['role'])
    location = html.escape(f['location'])
    url = html.escape(f['url'], quote=True)

    if f['url']:
        action = (
            f'<a href="{url}" style="display:inline-block;background:{ACCENT};color:#ffffff;'
            'font-weight:600;font-size:14px;text-decoration:none;padding:10px 22px;'
            'border-radius:8px;">Apply now →</a>'
        )
    else:
        action = '<span style="color:#94a3b8;font-size:13px;">No application link provided</span>'

    return f"""
          <tr><td style="padding:8px 0;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                   style="background:#ffffff;border:1px solid #e5e9f0;border-radius:12px;">
              <tr><td style="padding:18px 20px;">
                <div style="font-size:12px;font-weight:600;letter-spacing:.04em;
                            text-transform:uppercase;color:{ACCENT};">{company}</div>
                <div style="font-size:17px;font-weight:700;color:#0f172a;margin:4px 0 8px;">{role}</div>
                <div style="font-size:14px;color:#475569;margin-bottom:16px;">
                  📍 {location} &nbsp;·&nbsp; 🆕 Added today</div>
                {action}
              </td></tr>
            </table>
          </td></tr>"""


def generate_email_html(new_opportunities: List[Dict[str, Any]]) -> str:
    """Generate the engaging HTML email body."""
    count = len(new_opportunities)
    noun = "internship" if count == 1 else "internships"
    if not new_opportunities:
        header = "No new Summer 2026 internships right now"
        sub = "Nothing new in the latest sync — check back soon."
        cards = ""
    else:
        header = f"{EMOJI} {count} new Summer 2026 {noun} just posted"
        sub = f"Fresh {LABEL_SHORT} listings added today. These move fast — apply early."
        cards = "".join(_render_card(o) for o in new_opportunities)

    return f"""<!doctype html>
<html>
<body style="margin:0;padding:0;background:#f1f5f9;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background:#f1f5f9;padding:24px 12px;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0"
             style="max-width:600px;width:100%;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
        <tr><td style="padding:4px 4px 18px;">
          <div style="font-size:22px;font-weight:800;color:#0f172a;">{header}</div>
          <div style="font-size:14px;color:#64748b;margin-top:6px;">{sub}</div>
        </td></tr>
        {cards}
        <tr><td style="padding:20px 4px 4px;">
          <div style="font-size:13px;color:#94a3b8;border-top:1px solid #e2e8f0;padding-top:14px;">
            You're getting this because your {LABEL_SHORT} tracker spotted new postings
            in the SimplifyJobs list. Good luck! 🎯
          </div>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def main():
    """Main function to process README.md changes and generate email."""
    print("🔍 Analyzing patch files for new Summer 2026 opportunities (0d age only)...")

    # Find new Summer 2026 opportunities from patch files
    new_opportunities = find_new_summer_2026_opportunities_from_patches()

    # Generate plain-text (gate + fallback) and HTML (engaging) bodies
    email_text = generate_email_text(new_opportunities)
    email_html = generate_email_html(new_opportunities)

    # Write email bodies to files
    os.makedirs("email", exist_ok=True)
    with open("email/body.txt", "w", encoding="utf-8") as f:
        f.write(email_text)
    with open("email/body.html", "w", encoding="utf-8") as f:
        f.write(email_html)

    print(f"✅ Found {len(new_opportunities)} new Summer 2026 opportunities (0d age)")
    print("📧 Email bodies written to email/body.txt and email/body.html")

    # Print summary for debugging
    if new_opportunities:
        print("\n🎯 New Summer 2026 opportunities found (0d age):")
        for i, opp in enumerate(new_opportunities[:5], 1):  # Show first 5
            company = opp.get('company_name', 'Unknown')
            role = opp.get('title', 'Unknown')
            age = opp.get('age', 'Unknown')
            print(f"{i}. {company} - {role} (Age: {age})")
        if len(new_opportunities) > 5:
            print(f"... and {len(new_opportunities) - 5} more")
    else:
        print("📭 No new Summer 2026 opportunities (0d age) found in the changes")

if __name__ == "__main__":
    main()
