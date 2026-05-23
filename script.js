const chatFile = document.getElementById('chatFile');
const pasteText = document.getElementById('pasteText');
const driveLinkInput = document.getElementById('driveLink');
const parseBtn = document.getElementById('parseBtn');
const clearBtn = document.getElementById('clearBtn');
const errorMessage = document.getElementById('errorMessage');
const authorSelectContainer = document.getElementById('authorSelectContainer');
const authorSelect = document.getElementById('authorSelect');
const chatFrame = document.getElementById('chatFrame');
const chatContainer = document.getElementById('chatContainer');
const chatSummary = document.getElementById('chatSummary');
const swapBtn = document.getElementById('swapBtn');
const contactName = document.getElementById('contactName');
const contactStatus = document.getElementById('contactStatus');
const messageInput = document.getElementById('messageInput');

let currentMessages = [];
let currentUsers = [];
let activeUser = null;
let swapped = false;

const messagePattern = /^(\d{1,2}[\/.-]\d{1,2}[\/.-]\d{2,4},?\s\d{1,2}:\d{2}\s?(?:AM|PM|am|pm)?)\s-\s([^:]+):\s(.*)$/;

function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function parseChat(text) {
    const lines = text.split(/\r?\n/);
    const messages = [];
    let current = null;

    for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line) continue;
        const match = line.match(messagePattern);
        if (match) {
            if (current) messages.push(current);
            current = {
                datetime: match[1],
                author: match[2].trim(),
                text: match[3].trim(),
                isEdited: /<This message was edited>|\(edited\)/i.test(match[3]),
            };
        } else if (current) {
            current.text += '\n' + rawLine;
            if (/edited/i.test(rawLine)) {
                current.isEdited = true;
            }
        }
    }
    if (current) messages.push(current);
    return messages;
}

function buildAuthorList(messages) {
    const authors = [];
    for (const msg of messages) {
        if (!authors.includes(msg.author)) {
            authors.push(msg.author);
        }
    }
    return authors;
}

function renderChat(messages, user) {
    chatContainer.innerHTML = '';
    currentMessages = messages;
    activeUser = user;
    currentUsers = buildAuthorList(messages);
    authorSelectContainer.classList.toggle('hidden', currentUsers.length === 0);
    authorSelect.innerHTML = '';

    // Update contact info header
    if (user) {
        contactName.textContent = user;
        const userMessageCount = messages.filter(msg => msg.author === user).length;
        const totalMessages = messages.length;
        contactStatus.textContent = `${userMessageCount} messages · online`;
    }

    currentUsers.forEach((author, index) => {
        const option = document.createElement('option');
        option.value = author;
        option.textContent = author;
        if (author === user) option.selected = true;
        authorSelect.appendChild(option);
    });

    messages.forEach((msg, index) => {
        const isUser = swapped ? msg.author !== user : msg.author === user;
        const side = isUser ? 'right' : 'left';
        const messageEl = document.createElement('div');
        messageEl.className = `message ${side}`;
        
        const bubble = document.createElement('div');
        bubble.className = 'bubble';

        const authorEl = document.createElement('div');
        authorEl.className = 'author';
        authorEl.textContent = msg.author;

        const textEl = document.createElement('div');
        textEl.className = 'text';
        textEl.innerHTML = escapeHtml(msg.text).replace(/\n/g, '<br>');

        const timestampEl = document.createElement('div');
        timestampEl.className = 'timestamp';
        let timestampText = msg.datetime;
        if (msg.isEdited) timestampText += ' · Edited';
        
        // Add status icon for outgoing messages
        if (isUser) {
            timestampEl.innerHTML = escapeHtml(timestampText) + ' <span class="message-status">✓✓</span>';
        } else {
            timestampEl.textContent = timestampText;
        }

        bubble.appendChild(authorEl);
        bubble.appendChild(textEl);
        bubble.appendChild(timestampEl);
        messageEl.appendChild(bubble);
        chatContainer.appendChild(messageEl);
    });

    chatFrame.classList.remove('hidden');
    // Auto-scroll to bottom
    setTimeout(() => {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }, 100);
}

function showError(message) {
    errorMessage.textContent = message;
}

function clearError() {
    errorMessage.textContent = '';
}

function processContent(content) {
    const messages = parseChat(content);
    if (messages.length === 0) {
        showError('No valid WhatsApp messages found. Please use a proper exported .txt chat file.');
        return;
    }
    const authors = buildAuthorList(messages);
    if (authors.length === 0) {
        showError('Unable to detect any authors in the chat file.');
        return;
    }
    activeUser = authors[0];
    authorSelectContainer.classList.toggle('hidden', false);
    authorSelect.innerHTML = '';
    authors.forEach((author, index) => {
        const option = document.createElement('option');
        option.value = author;
        option.textContent = author;
        if (index === 0) option.selected = true;
        authorSelect.appendChild(option);
    });
    chatSummary.textContent = `${messages.length} messages from ${authors.length} author${authors.length === 1 ? '' : 's'}.`;
    renderChat(messages, activeUser);
}

parseBtn.addEventListener('click', async () => {
    clearError();
    // Try client-side Drive fetch first (works only if Google allows CORS for the file)
    const driveLink = driveLinkInput ? driveLinkInput.value.trim() : '';
    if (driveLink) {
        try {
            parseBtn.disabled = true;
            parseBtn.textContent = 'Downloading...';

            // extract file id and build direct-download URL
            const fileId = extractDriveFileId(driveLink);
            if (!fileId) throw new Error('Invalid Google Drive share link.');
            const downloadUrl = `https://drive.google.com/uc?export=download&id=${fileId}`;

            // Attempt fetch (may fail due to Google CORS restrictions)
            const resp = await fetch(downloadUrl, { method: 'GET', mode: 'cors' });
            if (!resp.ok) {
                throw new Error(`Download failed (status ${resp.status}).`);
            }
            const text = await resp.text();

            // Quick sanity check: ensure it looks like a WhatsApp export
            const messages = parseChat(text);
            if (!messages || messages.length === 0) {
                throw new Error('Downloaded file does not contain valid WhatsApp messages.');
            }
            const users = buildAuthorList(messages);
            const firstUser = users.length ? users[0] : null;
            chatSummary.textContent = `${messages.length} messages from ${users.length} author${users.length === 1 ? '' : 's'}.`;
            renderChat(messages, firstUser);
            return;
        } catch (err) {
            // Common cause: CORS blocked by Google. Show actionable guidance.
            const msg = err.message || 'Failed to download from Google Drive.';
            showError(msg + '\nIf you see a CORS or cross-origin error, GitHub Pages (static hosting) cannot fetch the file directly from Google Drive.\n\nOptions:\n• Make the file publicly accessible and use a proxy\n• Upload the file directly instead\n• Use a backend server');
            parseBtn.disabled = false;
            parseBtn.textContent = 'Parse Chat';
            return;
        }
    }

    let content = pasteText.value.trim();
    if (!content && chatFile.files.length > 0) {
        const file = chatFile.files[0];
        const reader = new FileReader();
        reader.onload = () => {
            content = reader.result;
            processContent(content);
        };
        reader.onerror = () => showError('Could not read the selected text file.');
        reader.readAsText(file, 'utf-8');
        return;
    }
    if (!content) {
        showError('Please upload a WhatsApp .txt file, paste the exported text, or provide a Drive share link.');
        return;
    }
    processContent(content);
});

function extractDriveFileId(url) {
    try {
        const u = new URL(url);
        if (u.hostname.includes('drive.google.com')) {
            // /file/d/FILEID or /open?id=FILEID
            const parts = u.pathname.split('/');
            const dIndex = parts.indexOf('d');
            if (dIndex >= 0 && parts.length > dIndex + 1) return parts[dIndex + 1];
            const qs = new URLSearchParams(u.search);
            if (qs.has('id')) return qs.get('id');
        }
    } catch (e) {
        return null;
    }
    return null;
}

// Event listeners
clearBtn.addEventListener('click', () => {
    chatFile.value = '';
    pasteText.value = '';
    driveLinkInput.value = '';
    clearError();
});

authorSelect.addEventListener('change', (e) => {
    activeUser = e.target.value;
    renderChat(currentMessages, activeUser);
});

swapBtn.addEventListener('click', () => {
    swapped = !swapped;
    renderChat(currentMessages, activeUser);
    swapBtn.textContent = swapped ? 'Swap Users (Swapped)' : 'Swap Users';
});

// Prevent default behavior for composer
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
    }
});

document.querySelectorAll('.send-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        // Send button is just for UI - actual sending would require backend
        console.log('Send button clicked - demo only');
    });
});
