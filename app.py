from flask import Flask, request, render_template, send_from_directory, jsonify, make_response
import os
import re
import html
import zipfile
import urllib.request
import socket
import logging
from urllib.parse import urlparse, parse_qs
from urllib.error import URLError, HTTPError

app = Flask(__name__, template_folder='templates')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MEDIA_FOLDER'] = 'static/media'
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB limit

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['MEDIA_FOLDER'], exist_ok=True)

# Regex for message
pattern = r'^(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4},?\s\d{1,2}:\d{2}\s?(AM|PM|am|pm)?)\s-\s([^:]+):\s(.*)$'
# Regex for media
media_pattern = r'([A-Z0-9\-_]+\.(jpg|jpeg|png|gif|mp4|avi|pdf|doc|docx|txt|zip|rar))\s*\(file attached\)'

def parse_chat(content):
    """Parse chat content with better error handling"""
    if not content or not isinstance(content, str):
        raise ValueError('Invalid content: empty or not a string')
    
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
            
            current_message = {
                'datetime': date_time,
                'author': author,
                'text': text,
                'is_media': is_media,
                'media_type': media_type,
                'filename': filename,
                'is_edited': is_edited
            }
        else:
            if current_message:
                current_message['text'] += '\n' + line
    
    if current_message:
        messages.append(current_message)
    
    if not messages:
        raise ValueError('No valid WhatsApp messages found in the file')
    
    return messages

def extract_drive_file_id(url):
    """Extract Google Drive file ID from URL"""
    try:
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
    except Exception as e:
        logger.error(f"Error extracting drive file ID: {e}")
    
    return None

def download_google_drive_file(url, timeout=30):
    """Download file from Google Drive with proper error handling and timeout"""
    try:
        file_id = extract_drive_file_id(url)
        if not file_id:
            raise ValueError('Invalid Google Drive URL. Please use a valid share link.')
        
        # Build download URL
        download_url = f'https://drive.google.com/uc?export=download&id={file_id}'
        
        # Create request with timeout
        req = urllib.request.Request(
            download_url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        
        # Download with timeout
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw_data = response.read()
        
        # Try to decode as UTF-8
        try:
            content = raw_data.decode('utf-8')
        except UnicodeDecodeError:
            # Try with error replacement
            content = raw_data.decode('utf-8', errors='replace')
        
        # Validate that we got actual content
        if not content or len(content.strip()) == 0:
            raise ValueError('Downloaded file is empty')
        
        if '<title>Google Drive</title>' in content and len(content) < 1000:
            raise ValueError('Unable to download file. Check that: 1) The link is shared, 2) It\'s a .txt file, 3) You have view access.')
        
        return content
    
    except HTTPError as e:
        logger.error(f"HTTP Error downloading from Google Drive: {e}")
        raise ValueError(f'Google Drive error: File not found or access denied (HTTP {e.code})')
    except URLError as e:
        logger.error(f"URL Error downloading from Google Drive: {e}")
        raise ValueError('Network error: Unable to reach Google Drive. Please check your internet connection.')
    except socket.timeout:
        logger.error("Timeout downloading from Google Drive")
        raise ValueError('Download timeout: Google Drive took too long to respond. Try again later.')
    except Exception as e:
        logger.error(f"Unexpected error downloading from Google Drive: {e}")
        raise ValueError(f'Error downloading from Google Drive: {str(e)[:100]}')

@app.after_request
def add_cors_headers(response):
    """Add CORS headers for development/testing"""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return response

@app.route('/fetch-drive', methods=['POST', 'OPTIONS'])
def fetch_drive():
    """API endpoint for fetching Google Drive files"""
    if request.method == 'OPTIONS':
        return make_response(('', 204))
    
    try:
        data = request.get_json(silent=True) or {}
        drive_link = data.get('drive_link') or request.form.get('drive_link')
        
        if not drive_link:
            return jsonify({'error': 'No drive_link provided'}), 400
        
        content = download_google_drive_file(drive_link)
        messages = parse_chat(content)
        users = list(dict.fromkeys(msg['author'] for msg in messages))
        
        return jsonify({'messages': messages, 'users': users})
    
    except ValueError as e:
        logger.warning(f"Validation error in fetch_drive: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error in fetch_drive: {e}", exc_info=True)
        return jsonify({'error': 'Server error: Unable to process the file'}), 500

def generate_chat_html(messages, user_name):
    """Generate HTML for chat display"""
    content = ""
    for msg in messages:
        try:
            avatar_initial = msg['author'][0].upper() if msg['author'] else '?'
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
        except Exception as e:
            logger.error(f"Error rendering message: {e}")
            continue
    
    return content

@app.route('/static/media/<path:filename>')
def media_file(filename):
    """Serve media files"""
    try:
        return send_from_directory(app.config['MEDIA_FOLDER'], filename)
    except Exception as e:
        logger.error(f"Error serving media file: {e}")
        return 'File not found', 404

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main route - handle file upload and display"""
    if request.method == 'POST':
        try:
            chat_file = request.files.get('chat_file')
            media_file = request.files.get('media_file')
            drive_link = request.form.get('drive_link', '').strip()
            theme = request.form.get('theme', 'light')
            content = None

            # Try to get content from Google Drive
            if drive_link:
                try:
                    content = download_google_drive_file(drive_link)
                except ValueError as e:
                    return render_template('index.html', error=str(e))
                except Exception as e:
                    logger.error(f"Unexpected error with Google Drive: {e}", exc_info=True)
                    return render_template('index.html', error='Error downloading from Google Drive. Please try again.')
            
            # Otherwise try to get from uploaded file
            elif chat_file and chat_file.filename.endswith('.txt'):
                try:
                    file_content = chat_file.read()
                    
                    # Try UTF-8 first, then fallback to other encodings
                    try:
                        content = file_content.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            content = file_content.decode('utf-16')
                        except UnicodeDecodeError:
                            content = file_content.decode('latin-1', errors='replace')
                    
                    if not content or len(content.strip()) == 0:
                        return render_template('index.html', error='The uploaded file is empty.')
                
                except Exception as e:
                    logger.error(f"Error reading uploaded file: {e}")
                    return render_template('index.html', error='Could not read the uploaded file. Make sure it\'s a valid text file.')
            else:
                return render_template('index.html', error='Please upload a .txt file or provide a Google Drive share link.')

            # Parse the chat content
            try:
                messages = parse_chat(content)
            except ValueError as e:
                logger.warning(f"Error parsing chat: {e}")
                return render_template('index.html', error=str(e))
            except Exception as e:
                logger.error(f"Unexpected error parsing chat: {e}", exc_info=True)
                return render_template('index.html', error='Error parsing the chat file. Please make sure it\'s a valid WhatsApp export.')

            # Get unique users
            users = list(set(msg['author'] for msg in messages))
            first_user = users[0] if len(users) > 0 else None

            # Handle media zip file
            if media_file and media_file.filename.endswith('.zip'):
                try:
                    zip_path = os.path.join(app.config['UPLOAD_FOLDER'], media_file.filename)
                    media_file.save(zip_path)
                    
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(app.config['MEDIA_FOLDER'])
                    
                    os.remove(zip_path)
                except zipfile.BadZipFile:
                    logger.error("Bad zip file uploaded")
                    return render_template('index.html', error='The uploaded media file is not a valid ZIP file.')
                except Exception as e:
                    logger.error(f"Error processing media zip: {e}")
                    return render_template('index.html', error='Error processing the media zip file.')

            # Generate and return the result
            chat_html = generate_chat_html(messages, first_user)
            return render_template('result.html', chat_content=chat_html, theme=theme, users=users)
        
        except Exception as e:
            logger.error(f"Unexpected error in POST handler: {e}", exc_info=True)
            return render_template('index.html', error='An unexpected error occurred. Please try again.')
    
    return render_template('index.html')

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file size limit errors"""
    return render_template('index.html', error='File is too large. Maximum size is 32MB.'), 413

@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors"""
    logger.error(f"Internal server error: {error}", exc_info=True)
    return render_template('index.html', error='Server error. Please try again later.'), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
