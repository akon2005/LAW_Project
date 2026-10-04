import re

with open(r'C:\Users\vinay\.gemini\antigravity-ide\brain\f1ccc72d-bf92-46c7-9522-eb12c70806af\.system_generated\steps\22\content.md', encoding='utf-8') as f:
    html = f.read()

svg = re.search(r'<svg viewBox="0 0 600 440".*?</svg>', html, re.DOTALL)
if svg:
    with open('extracted_svg.txt', 'w', encoding='utf-8') as f:
        f.write(svg.group(0))
    print("Extracted SVG successfully.")
else:
    print("SVG not found.")
