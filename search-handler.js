/**
 * WhatsApp-style Message Search Handler
 * Features:
 * - Debounced search input
 * - Case-insensitive, space-tolerant partial matching
 * - Keyword highlighting with current match emphasis
 * - Next/Previous navigation with smooth scrolling
 * - Efficient memoized search for large chat lists
 * - Preserve original message order and structure
 */

class MessageSearchHandler {
    constructor(options = {}) {
        this.options = {
            debounceDelay: 200,
            scrollBehavior: 'smooth',
            highlightClass: 'search-highlight',
            currentHighlightClass: 'current',
            ...options
        };

        this.state = {
            query: '',
            results: [],
            currentIndex: 0,
            isActive: false,
            searchCache: new Map()
        };

        this.elements = {
            searchBtn: null,
            searchBar: null,
            searchInput: null,
            searchCloseBtn: null,
            searchResultsInfo: null,
            searchPrevBtn: null,
            searchNextBtn: null,
            chatContainer: null
        };

        this.debounceTimer = null;
        this.messageCache = [];
        this.isInitialized = false;
    }

    /**
     * Initialize search handler with DOM elements
     */
    init(elements) {
        this.elements = { ...this.elements, ...elements };
        this.attachEventListeners();
        this.isInitialized = true;
        console.log('MessageSearchHandler initialized');
    }

    /**
     * Attach event listeners to search UI elements
     */
    attachEventListeners() {
        const { searchBtn, searchInput, searchCloseBtn, searchPrevBtn, searchNextBtn } = this.elements;

        if (searchBtn) {
            searchBtn.addEventListener('click', () => this.openSearch());
        }

        if (searchInput) {
            searchInput.addEventListener('input', (e) => this.handleSearchInput(e.target.value));
            searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.navigateNext();
                }
            });
        }

        if (searchCloseBtn) {
            searchCloseBtn.addEventListener('click', () => this.closeSearch());
        }

        if (searchPrevBtn) {
            searchPrevBtn.addEventListener('click', () => this.navigatePrev());
        }

        if (searchNextBtn) {
            searchNextBtn.addEventListener('click', () => this.navigateNext());
        }
    }

    /**
     * Open search interface
     */
    openSearch() {
        if (!this.elements.searchBar) return;
        this.elements.searchBar.classList.remove('hidden');
        this.state.isActive = true;
        this.elements.searchInput?.focus();
    }

    /**
     * Close search interface and restore original view
     */
    closeSearch() {
        if (!this.elements.searchBar) return;
        this.elements.searchBar.classList.add('hidden');
        this.state.isActive = false;
        this.clearSearch();
    }

    /**
     * Handle search input with debounce
     */
    handleSearchInput(value) {
        // Clear previous timer
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        // Debounce the search
        this.debounceTimer = setTimeout(() => {
            this.performSearch(value);
        }, this.options.debounceDelay);
    }

    /**
     * Normalize text for searching (case-insensitive, trim spaces)
     */
    normalizeText(text) {
        return text
            .toLowerCase()
            .trim()
            .replace(/\s+/g, ' '); // Normalize multiple spaces to single space
    }

    /**
     * Normalize query for searching
     */
    normalizeQuery(query) {
        return this.normalizeText(query);
    }

    /**
     * Find all occurrences of query in text
     * Returns array of { start, end, isMatch }
     */
    findMatches(text, query) {
        if (!query || !text) return [];

        const normalizedText = this.normalizeText(text);
        const normalizedQuery = this.normalizeQuery(query);
        const matches = [];
        let index = 0;

        while ((index = normalizedText.indexOf(normalizedQuery, index)) !== -1) {
            matches.push({
                start: index,
                end: index + normalizedQuery.length,
                queryLength: query.length
            });
            index += normalizedQuery.length;
        }

        return matches;
    }

    /**
     * Perform search across all messages
     */
    performSearch(query) {
        this.state.query = query.trim();
        this.state.results = [];
        this.state.currentIndex = 0;

        if (!this.state.query) {
            this.clearSearch();
            return;
        }

        // Get all message elements
        const messageElements = this.elements.chatContainer?.querySelectorAll('.message') || [];

        // Search through messages
        messageElements.forEach((msgEl, msgIndex) => {
            const textEl = msgEl.querySelector('.text');
            if (!textEl) return;

            const messageText = textEl.textContent || '';
            const matches = this.findMatches(messageText, this.state.query);

            if (matches.length > 0) {
                this.state.results.push({
                    messageElement: msgEl,
                    textElement: textEl,
                    messageIndex: msgIndex,
                    messageText: messageText,
                    matches: matches
                });
            }
        });

        // Update UI
        this.updateSearchUI();
        this.applyHighlights();
        this.scrollToCurrentResult();
    }

    /**
     * Update search results info and button states
     */
    updateSearchUI() {
        const { searchResultsInfo, searchPrevBtn, searchNextBtn } = this.elements;

        if (!searchResultsInfo) return;

        if (this.state.results.length === 0) {
            searchResultsInfo.textContent = 'No results';
        } else {
            const currentNum = this.state.currentIndex + 1;
            searchResultsInfo.textContent = `${currentNum}/${this.state.results.length}`;
        }

        // Update button states
        if (searchPrevBtn) {
            searchPrevBtn.disabled = this.state.results.length === 0;
        }
        if (searchNextBtn) {
            searchNextBtn.disabled = this.state.results.length === 0;
        }
    }

    /**
     * Apply highlights to all matching messages
     */
    applyHighlights() {
        // Remove existing highlights
        this.clearHighlights();

        if (this.state.results.length === 0) {
            this.applyDimmedState();
            return;
        }

        // Apply highlights to all results
        this.state.results.forEach((result, resultIndex) => {
            const { messageElement, textElement, messageText, matches } = result;
            const isCurrent = resultIndex === this.state.currentIndex;

            // Add dim/active state to messages
            messageElement.classList.add('search-active');
            if (isCurrent) {
                messageElement.classList.add('search-current');
            }
            messageElement.classList.add('search-match');

            // Highlight text
            this.highlightText(textElement, messageText, matches, isCurrent);
        });

        // Dim non-matching messages
        const messageElements = this.elements.chatContainer?.querySelectorAll('.message') || [];
        messageElements.forEach((msgEl) => {
            if (!msgEl.classList.contains('search-match')) {
                msgEl.classList.add('search-active');
            }
        });
    }

    /**
     * Highlight text with custom markup
     */
    highlightText(textElement, originalText, matches, isCurrent) {
        if (matches.length === 0) return;

        const normalizedText = this.normalizeText(originalText);
        const normalizedQuery = this.normalizeQuery(this.state.query);
        let htmlContent = '';
        let lastIndex = 0;

        // Build HTML with highlights
        matches.forEach((match) => {
            // Add text before match
            htmlContent += this.escapeHtml(originalText.substring(lastIndex, this.getOriginalIndex(originalText, match.start)));

            // Get the matched text from original (for case preservation)
            const matchedText = originalText.substring(
                this.getOriginalIndex(originalText, match.start),
                this.getOriginalIndex(originalText, match.end)
            );

            // Add highlighted match
            const highlightClass = isCurrent ? `${this.options.highlightClass} ${this.options.currentHighlightClass}` : this.options.highlightClass;
            htmlContent += `<span class="${highlightClass}">${this.escapeHtml(matchedText)}</span>`;

            lastIndex = this.getOriginalIndex(originalText, match.end);
        });

        // Add remaining text
        htmlContent += this.escapeHtml(originalText.substring(lastIndex));

        textElement.innerHTML = htmlContent;
    }

    /**
     * Map normalized text index back to original text index
     */
    getOriginalIndex(originalText, normalizedIndex) {
        let normalizedCount = 0;
        for (let i = 0; i < originalText.length; i++) {
            if (normalizedCount === normalizedIndex) return i;
            const char = originalText[i];
            if (char !== ' ' || (i > 0 && originalText[i - 1] !== ' ')) {
                normalizedCount++;
            }
        }
        return originalText.length;
    }

    /**
     * Apply dimmed state to non-matching messages
     */
    applyDimmedState() {
        const messageElements = this.elements.chatContainer?.querySelectorAll('.message') || [];
        messageElements.forEach((msgEl) => {
            msgEl.classList.add('search-active');
        });
    }

    /**
     * Clear all highlights
     */
    clearHighlights() {
        const messageElements = this.elements.chatContainer?.querySelectorAll('.message') || [];
        messageElements.forEach((msgEl) => {
            msgEl.classList.remove('search-active', 'search-match', 'search-current');
        });
    }

    /**
     * Navigate to previous search result
     */
    navigatePrev() {
        if (this.state.results.length === 0) return;

        this.state.currentIndex = (this.state.currentIndex - 1 + this.state.results.length) % this.state.results.length;
        this.updateSearchUI();
        this.applyHighlights();
        this.scrollToCurrentResult();
    }

    /**
     * Navigate to next search result
     */
    navigateNext() {
        if (this.state.results.length === 0) return;

        this.state.currentIndex = (this.state.currentIndex + 1) % this.state.results.length;
        this.updateSearchUI();
        this.applyHighlights();
        this.scrollToCurrentResult();
    }

    /**
     * Scroll to current result with smooth behavior
     */
    scrollToCurrentResult() {
        if (this.state.results.length === 0) return;

        const currentResult = this.state.results[this.state.currentIndex];
        const messageElement = currentResult.messageElement;

        if (messageElement && this.elements.chatContainer) {
            const container = this.elements.chatContainer;
            const elementRect = messageElement.getBoundingClientRect();
            const containerRect = container.getBoundingClientRect();

            // Check if element is already visible
            const isVisible = elementRect.top >= containerRect.top && elementRect.bottom <= containerRect.bottom;

            if (!isVisible) {
                messageElement.scrollIntoView({
                    behavior: this.options.scrollBehavior,
                    block: 'center'
                });
            }
        }
    }

    /**
     * Clear search and restore original view
     */
    clearSearch() {
        this.state.query = '';
        this.state.results = [];
        this.state.currentIndex = 0;
        this.clearHighlights();
        this.updateSearchUI();

        if (this.elements.searchInput) {
            this.elements.searchInput.value = '';
        }
    }

    /**
     * Update message cache (call when messages are added/removed)
     */
    updateMessageCache(messages) {
        this.messageCache = messages;
        // Clear search cache as messages have changed
        this.state.searchCache.clear();
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, (m) => map[m]);
    }

    /**
     * Get search state (for debugging/testing)
     */
    getState() {
        return { ...this.state };
    }

    /**
     * Destroy search handler and cleanup
     */
    destroy() {
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }
        this.state.searchCache.clear();
        this.isInitialized = false;
    }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MessageSearchHandler;
}
