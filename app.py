from flask import Flask, request, render_template, send_from_directory, jsonify, make_response
import os
import re
import html
import zipfile
import urllib.request
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MEDIA_FOLDER'] = 'static/media'
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB limit

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['MEDIA_FOLDER'], exist_ok=True)

# Regex for message
pattern = r'^(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4},?\s\d{1,2}:\d{2}\s?(AM|PM|am|pm)?)\s-\s([^:]+):\s(.*)$'
# Regex for media
media_pattern = r'([A-Z0-9\-_]+\.(jpg|jpeg|png|gif|mp4|avi|pdf|doc|docx|txt|zip|rar))\s*\(file attached\)'

def parse_chat(content):
    messages = []
    lines = content.split('\n')
    current_message = None
    for line in lines:
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
            is_media = False
            media_type = None
            filename = None
            is_edited = False
            edited_time = None
            media_match = re.search(media_pattern, text, re.IGNORECASE)
            if media_match:
                filename = media_match.group(1)
                ext = media_match.group(2).lower()
                if ext in ['jpg', 'jpeg', 'png', 'gif']:
                    media_type = 'image'
                elif ext in ['mp4', 'avi']:
                    media_type = 'video'
                else:
                    media_type = 'file'
                is_media = True
                text = text.replace(media_match.group(0), '').strip()
            # Check for edited marker
            if '<This message was edited>' in text or '(edited)' in text.lower():
                is_edited = True
                text = text.replace('<This message was edited>', '').replace('(edited)', '').strip()
            current_message = {'datetime': date_time, 'author': author, 'text': text, 'is_media': is_media, 'media_type': media_type, 'filename': filename, 'is_edited': is_edited}
        else:
            if current_message:
                current_message['text'] += '\n' + line
    if current_message:
        messages.append(current_message)
    return messages

def extract_drive_file_id(url):
    parsed = urlparse(url)
    if 'drive.google.com' not in parsed.netloc:
        return None
    path = parsed.path
    id_match = re.search(r'/d/([a-zA-Z0-9_-]+)', path)
    if id_match:
        return id_match.group(1)
    qs = parse_qs(parsed.query)
    if 'id' in qs:
        return qs['id'][0]
    return None


def download_google_drive_file(url):
    file_id = extract_drive_file_id(url)
    if not file_id:
        raise ValueError('Invalid Google Drive URL. Paste a valid share link.')
    download_url = f'https://drive.google.com/uc?export=download&id={file_id}'
    request = urllib.request.Request(download_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(request) as response:
        raw_data = response.read()
        content = raw_data.decode('utf-8', errors='replace')
    if '<title>Google Drive</title>' in content and 'download' not in content.lower():
        raise ValueError('Unable to download file from Google Drive. Check the sharing link and permissions.')
    return content


@app.after_request
def add_cors_headers(response):
    # Allow simple CORS for the static frontend to call this endpoint during testing/deployment
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return response


@app.route('/fetch-drive', methods=['POST', 'OPTIONS'])
def fetch_drive():
    if request.method == 'OPTIONS':
        return make_response(('', 204))
    data = request.get_json(silent=True) or {}
    drive_link = data.get('drive_link') or request.form.get('drive_link')
    if not drive_link:
        return jsonify({'error': 'No drive_link provided'}), 400
    try:
        content = download_google_drive_file(drive_link)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    messages = parse_chat(content)
    users = list(dict.fromkeys(msg['author'] for msg in messages))
    return jsonify({'messages': messages, 'users': users})


def generate_chat_html(messages, user_name):
    content = ""
    for msg in messages:
        avatar_initial = msg['author'][0].upper()
        # Determine if this is user's message or other person's message
        is_user_msg = user_name and msg['author'].lower() == user_name.lower()
        side = 'right' if is_user_msg else 'left'
        
        content += f"""
            <div class="message {side}" data-datetime="{html.escape(msg['datetime'])}" data-user="{html.escape(msg['author'])}">
                <div class="avatar" style="background-color: #25d366;">{avatar_initial}</div>
                <div class="bubble">
                    <div class="author">{html.escape(msg['author'])}</div>
        """
        if msg['is_media']:
            if msg['media_type'] == 'image':
                content += f'<img src="/static/media/{html.escape(msg["filename"])}" alt="Image" style="max-width: 100%; border-radius: 10px;">'
            elif msg['media_type'] == 'video':
                content += f'<video controls style="max-width: 100%;"><source src="/static/media/{html.escape(msg["filename"])}" type="video/mp4"></video>'
            else:
                content += f'<a href="/static/media/{html.escape(msg["filename"])}" download>{html.escape(msg["filename"])}</a>'
        if msg['text']:
            content += f'<div class="text">{html.escape(msg["text"]).replace(chr(10), "<br>")}</div>'
        ticks = '<span class="ticks">✓✓</span>' if is_user_msg else ''
        edited_label = '<span class="edited-label">Edited</span>' if msg.get('is_edited') else ''
        content += f"""
                    <div class="timestamp">{html.escape(msg['datetime'])} {ticks}{edited_label}</div>
                </div>
            </div>
        """
    return content

@app.route('/static/media/<path:filename>')
def media_file(filename):
    return send_from_directory(app.config['MEDIA_FOLDER'], filename)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        chat_file = request.files.get('chat_file')
        media_file = request.files.get('media_file')
        drive_link = request.form.get('drive_link', '').strip()
        theme = request.form.get('theme', 'light')
        content = None

        if drive_link:
            try:
                content = download_google_drive_file(drive_link)
            except Exception as e:
                return render_template('index.html', error=str(e))
        elif chat_file and chat_file.filename.endswith('.txt'):
            try:
                content = chat_file.read().decode('utf-8')
            except Exception:
                return render_template('index.html', error='Could not read uploaded text file. Ensure it is a valid UTF-8 .txt file.')
        else:
            return render_template('index.html', error='Please upload a .txt file or paste a Google Drive share link.')

        messages = parse_chat(content)
        users = list(set(msg['author'] for msg in messages))
        first_user = users[0] if len(users) > 0 else None

        if media_file and media_file.filename.endswith('.zip'):
            zip_path = os.path.join(app.config['UPLOAD_FOLDER'], media_file.filename)
            media_file.save(zip_path)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(app.config['MEDIA_FOLDER'])
            os.remove(zip_path)

        chat_html = generate_chat_html(messages, first_user)
        return render_template('result.html', chat_content=chat_html, theme=theme, users=users)
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))