import re
import html
from collections import defaultdict

# Regex to match WhatsApp message lines
pattern = r'^(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4},?\s\d{1,2}:\d{2}\s?(AM|PM|am|pm)?)\s-\s([^:]+):\s(.*)$'

def parse_chat(file_path):
    messages = []
    with open(file_path, 'r', encoding='utf-8') as f:
        current_message = None
        for line in f:
            line = line.strip()
            if not line:
                continue
            match = re.match(pattern, line)
            if match:
                if current_message:
                    messages.append(current_message)
                date_time = match.group(1)
                author = match.group(3)
                text = match.group(4)
                current_message = {'datetime': date_time, 'author': author, 'text': text}
            else:
                if current_message:
                    current_message['text'] += '\n' + line
        if current_message:
            messages.append(current_message)
    return messages

def generate_html(messages, output_path):
    # Assign colors to authors
    authors = list(set(msg['author'] for msg in messages))
    colors = ['#dcf8c6', '#ffffff', '#f0f0f0', '#e1f5fe', '#f3e5f5']  # light colors
    author_color = {author: colors[i % len(colors)] for i, author in enumerate(authors)}
    
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>WhatsApp Chat</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #e5ddd5; margin: 0; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background-color: white; border-radius: 10px; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        .message { margin-bottom: 10px; display: flex; }
        .message.left { justify-content: flex-start; }
        .message.right { justify-content: flex-end; }
        .bubble { max-width: 70%; padding: 10px 15px; border-radius: 20px; position: relative; word-wrap: break-word; }
        .left .bubble { background-color: #ffffff; border: 1px solid #ddd; }
        .right .bubble { background-color: #dcf8c6; }
        .author { font-weight: bold; margin-bottom: 5px; font-size: 0.9em; }
        .timestamp { font-size: 0.8em; color: #999; margin-top: 5px; }
        .text { white-space: pre-wrap; }
        #search { width: 100%; padding: 10px; margin-bottom: 20px; border: 1px solid #ddd; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <input type="text" id="search" placeholder="Search messages...">
        <div id="chat">
"""
    
    prev_author = None
    for msg in messages:
        side = 'left' if msg['author'] != prev_author else 'right'  # simple alternation, but actually should be based on user
        # For simplicity, all left, but to mimic, perhaps check if consecutive same author
        # Actually, in WhatsApp, messages from same sender are grouped, but for now, all left with color
        side = 'left'
        bubble_color = author_color.get(msg['author'], '#ffffff')
        html_content += f"""
            <div class="message {side}" data-author="{html.escape(msg['author'])}" data-text="{html.escape(msg['text'])}">
                <div class="bubble" style="background-color: {bubble_color};">
                    <div class="author">{html.escape(msg['author'])}</div>
                    <div class="text">{html.escape(msg['text']).replace('\n', '<br>')}</div>
                    <div class="timestamp">{html.escape(msg['datetime'])}</div>
                </div>
            </div>
        """
        prev_author = msg['author']
    
    html_content += """
        </div>
    </div>
    <script>
        const searchInput = document.getElementById('search');
        const messages = document.querySelectorAll('.message');
        
        searchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            messages.forEach(msg => {
                const author = msg.dataset.author.toLowerCase();
                const text = msg.dataset.text.toLowerCase();
                if (author.includes(query) || text.includes(query)) {
                    msg.style.display = '';
                } else {
                    msg.style.display = 'none';
                }
            });
        });
    </script>
</body>
</html>
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python parser.py <chat.txt>")
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = input_file.replace('.txt', '.html')
    messages = parse_chat(input_file)
    generate_html(messages, output_file)
    print(f"HTML generated: {output_file}")