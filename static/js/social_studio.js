var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
import { showNotification } from './notifications.js';
// Global helper functions
function escapeHtml(unsafe) {
    return unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
function copyToClipboard(button) {
    const content = button.previousElementSibling.textContent;
    if (content) {
        navigator.clipboard.writeText(content).then(() => {
            button.textContent = 'Copied!';
            setTimeout(() => { button.textContent = 'Copy'; }, 2000);
        }).catch(err => console.error('Copy failed', err));
    }
}
// Expose copyToClipboard to the global scope for inline onclick handlers
window.copyToClipboard = copyToClipboard;
document.addEventListener('DOMContentLoaded', function () {
    var _a, _b, _c, _d;
    // --- COMMON ELEMENTS ---
    const outputDisplay = document.getElementById('output-display');
    let socialChatSessionId = null;
    // --- TAB SWITCHING ---
    const tabs = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            const tabElement = tab; // Cast to HTMLElement
            document.getElementById(tabElement.dataset.tab).classList.add('active');
            outputDisplay.innerHTML = `<div class="empty-state"><span class="material-symbols-outlined" style="font-size: 48px;">campaign</span><p>Your generated content will appear here.</p></div>`;
        });
    });
    // --- EVENT LISTENERS ---
    (_a = document.getElementById('newSessionBtn')) === null || _a === void 0 ? void 0 : _a.addEventListener('click', startNewSession);
    (_b = document.getElementById('generateSocialBtn')) === null || _b === void 0 ? void 0 : _b.addEventListener('click', generateSocial);
    (_c = document.getElementById('generateEmailBtn')) === null || _c === void 0 ? void 0 : _c.addEventListener('click', generateEmail);
    (_d = document.getElementById('generateAdBtn')) === null || _d === void 0 ? void 0 : _d.addEventListener('click', generateAdCopy);
    // --- HELPER FUNCTIONS ---
    function setInputsDisabled(disabled) {
        // Social Post Inputs
        document.getElementById('social-topic').disabled = disabled;
        document.getElementById('social-goal').disabled = disabled;
        document.getElementById('social-platform').disabled = disabled;
        document.getElementById('social-tone').disabled = disabled;
        document.getElementById('social-cta').disabled = disabled;
        document.getElementById('social-variations').disabled = disabled;
        document.getElementById('social-emojis').disabled = disabled;
        document.getElementById('generateSocialBtn').disabled = disabled;
        // Email Inputs
        document.getElementById('email-topic').disabled = disabled;
        document.getElementById('email-audience').disabled = disabled;
        document.getElementById('email-tone').disabled = disabled;
        document.getElementById('email-type').disabled = disabled;
        document.getElementById('email-brand').disabled = disabled;
        document.getElementById('email-cta').disabled = disabled;
        document.getElementById('generateEmailBtn').disabled = disabled;
        // Ad Copy Inputs
        document.getElementById('ad-product').disabled = disabled;
        document.getElementById('ad-audience').disabled = disabled;
        document.getElementById('ad-platform').disabled = disabled;
        document.getElementById('ad-benefit').disabled = disabled;
        document.getElementById('ad-tone').disabled = disabled;
        document.getElementById('generateAdBtn').disabled = disabled;
    }
    function startNewSession() {
        // Re-enable all inputs
        setInputsDisabled(false);
        // Clear all inputs
        // Social
        document.getElementById('social-topic').value = '';
        document.getElementById('social-goal').value = 'Promote a product/service';
        document.getElementById('social-platform').value = 'Twitter';
        document.getElementById('social-tone').value = 'Professional';
        document.getElementById('social-cta').value = '';
        document.getElementById('social-variations').value = '3';
        document.getElementById('social-emojis').checked = true;
        // Email
        document.getElementById('email-topic').value = '';
        document.getElementById('email-audience').value = '';
        document.getElementById('email-tone').value = 'Professional';
        document.getElementById('email-type').value = 'Promotional';
        document.getElementById('email-brand').value = '';
        document.getElementById('email-cta').value = '';
        // Ad Copy
        document.getElementById('ad-product').value = '';
        document.getElementById('ad-audience').value = '';
        document.getElementById('ad-platform').value = 'Google Ads';
        document.getElementById('ad-benefit').value = '';
        document.getElementById('ad-tone').value = 'Urgent';
        // Reset buttons
        resetButton(document.getElementById('generateSocialBtn'), 'auto_awesome', 'Generate Posts');
        resetButton(document.getElementById('generateEmailBtn'), 'mark_email_unread', 'Generate Email');
        resetButton(document.getElementById('generateAdBtn'), 'campaign', 'Generate Ad Copy');
        // Reset output
        outputDisplay.innerHTML = `<div class="empty-state"><span class="material-symbols-outlined" style="font-size: 48px;">campaign</span><p>Your generated content will appear here.</p></div>`;
        socialChatSessionId = null;
        showNotification('New session started.', 'success');
    }
    // --- API FUNCTIONS ---
    function generateSocial(event) {
        return __awaiter(this, void 0, void 0, function* () {
            const topic = document.getElementById('social-topic').value;
            const goal = document.getElementById('social-goal').value;
            const platform = document.getElementById('social-platform').value;
            if (!topic) {
                alert('Please enter a topic.');
                return;
            }
            const settings = {
                tone: document.getElementById('social-tone').value,
                cta: document.getElementById('social-cta').value,
                variations: document.getElementById('social-variations').value,
                emojis: document.getElementById('social-emojis').checked
            };
            showLoading(event.currentTarget, "Generating posts...");
            try {
                const response = yield fetch('/api/v1/generate/social', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tool: 'social_post', topic, goal, platform, settings, chat_session_id: socialChatSessionId })
                });
                const data = yield response.json();
                if (response.ok) {
                    socialChatSessionId = data.chat_session_id;
                    displaySocialPosts(data.posts);
                    if (typeof window.loadChatHistory === 'function')
                        window.loadChatHistory('social');
                    setInputsDisabled(true);
                }
                else {
                    throw new Error(data.error);
                }
            }
            catch (error) {
                showError(error.message);
            }
            finally {
                resetButton(event.currentTarget, 'auto_awesome', 'Generate Posts');
            }
        });
    }
    function generateEmail(event) {
        return __awaiter(this, void 0, void 0, function* () {
            const topic = document.getElementById('email-topic').value;
            const audience = document.getElementById('email-audience').value;
            const tone = document.getElementById('email-tone').value;
            if (!topic) {
                alert('Please enter a topic.');
                return;
            }
            const settings = {
                emailType: document.getElementById('email-type').value,
                brandName: document.getElementById('email-brand').value,
                ctaButton: document.getElementById('email-cta').value
            };
            showLoading(event.currentTarget, "Generating email...");
            try {
                const response = yield fetch('/api/v1/generate/social', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tool: 'email', topic, audience, tone, settings, chat_session_id: socialChatSessionId })
                });
                const data = yield response.json();
                if (response.ok) {
                    socialChatSessionId = data.chat_session_id;
                    displayEmailContent(data.email_content);
                    if (typeof window.loadChatHistory === 'function')
                        window.loadChatHistory('social');
                    setInputsDisabled(true);
                }
                else {
                    throw new Error(data.error);
                }
            }
            catch (error) {
                showError(error.message);
            }
            finally {
                resetButton(event.currentTarget, 'mark_email_unread', 'Generate Email');
            }
        });
    }
    function generateAdCopy(event) {
        return __awaiter(this, void 0, void 0, function* () {
            const product = document.getElementById('ad-product').value;
            const audience = document.getElementById('ad-audience').value;
            if (!product || !audience) {
                alert('Please enter a product and audience.');
                return;
            }
            const settings = {
                platform: document.getElementById('ad-platform').value,
                keyBenefit: document.getElementById('ad-benefit').value,
                tone: document.getElementById('ad-tone').value
            };
            showLoading(event.currentTarget, "Generating ad copy...");
            try {
                const response = yield fetch('/api/v1/generate/social', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tool: 'ad_copy', product, audience, settings, chat_session_id: socialChatSessionId })
                });
                const data = yield response.json();
                if (response.ok) {
                    socialChatSessionId = data.chat_session_id;
                    displayAdCopy(data.ad_copy);
                    if (typeof window.loadChatHistory === 'function')
                        window.loadChatHistory('social');
                    setInputsDisabled(true);
                }
                else {
                    throw new Error(data.error);
                }
            }
            catch (error) {
                showError(error.message);
            }
            finally {
                resetButton(event.currentTarget, 'campaign', 'Generate Ad Copy');
            }
        });
    }
    // --- DISPLAY & HELPER FUNCTIONS ---
    function showLoading(btn, message) {
        btn.disabled = true;
        btn.innerHTML = `<span class="material-symbols-outlined">hourglass_top</span> Generating...`;
        outputDisplay.innerHTML = `<div class="loading" style="padding: 40px; display:flex; justify-content: center; align-items: center; gap: 8px;"><div class="spinner"></div><span>${message}</span></div>`;
    }
    function showError(message) {
        outputDisplay.innerHTML = `<p style="color: red; padding: 20px;">Error: ${message}</p>`;
    }
    function resetButton(btn, icon, text) {
        btn.disabled = false;
        btn.innerHTML = `<span class="material-symbols-outlined">${icon}</span> ${text}`;
    }
    function displaySocialPosts(posts) {
        outputDisplay.innerHTML = posts.map((post, index) => `
            <div class="post-card"><h4>Option ${index + 1}</h4><pre class="post-content">${escapeHtml(post)}</pre><button class="btn btn-secondary" onclick="copyToClipboard(this)">Copy</button></div>
        `).join('');
    }
    function displayEmailContent(content) {
        const parts = content.split('---');
        const subjects = parts[0].trim();
        const body = parts.length > 1 ? parts.slice(1).join('---').trim() : '';
        outputDisplay.innerHTML = `
            <div class="post-card"><h4>Subject Line Options</h4><pre class="post-content">${escapeHtml(subjects)}</pre><button class="btn btn-secondary" onclick="copyToClipboard(this)">Copy Subjects</button></div>
            <div class="post-card"><h4>Email Body</h4><pre class="post-content">${escapeHtml(body)}</pre><button class="btn btn-secondary" onclick="copyToClipboard(this)">Copy Body</button></div>
        `;
    }
    function displayAdCopy(adCopy) {
        outputDisplay.innerHTML = adCopy.map((ad, index) => `
            <div class="post-card"><h4>Ad Variation ${index + 1}</h4><pre class="post-content">${escapeHtml(ad)}</pre><button class="btn btn-secondary" onclick="copyToClipboard(this)">Copy</button></div>
        `).join('');
    }
    window.loadSessionIntoView = function (sessionId) {
        return __awaiter(this, void 0, void 0, function* () {
            try {
                outputDisplay.innerHTML = `<div class="loading" style="padding: 40px; display:flex; justify-content: center; align-items: center; gap: 8px;"><div class="spinner"></div><span>Loading session...</span></div>`;
                const response = yield fetch(`/api/chat-session/${sessionId}`);
                if (!response.ok)
                    throw new Error('Failed to fetch session data.');
                const session = yield response.json();
                socialChatSessionId = session.session_id;
                // The user's original input is stored as a JSON string in the first message.
                const userInput = JSON.parse(session.messages[0].content);
                if (session.studio_type === 'SOCIAL_POST') {
                    document.querySelector('.tab-button[data-tab="social-posts"]').click();
                    document.getElementById('social-topic').value = userInput.topic || '';
                    document.getElementById('social-goal').value = userInput.goal || '';
                    document.getElementById('social-platform').value = userInput.platform || '';
                    document.getElementById('generateSocialBtn').disabled = true;
                    displaySocialPosts(session.raw_text.split('---').map((p) => p.trim()).filter((p) => p));
                }
                else if (session.studio_type === 'EMAIL') {
                    document.querySelector('.tab-button[data-tab="emails"]').click();
                    document.getElementById('email-topic').value = userInput.topic || '';
                    document.getElementById('email-audience').value = userInput.audience || '';
                    document.getElementById('email-tone').value = userInput.tone || '';
                    document.getElementById('generateEmailBtn').disabled = true;
                    displayEmailContent(session.raw_text);
                }
                else if (session.studio_type === 'AD_COPY') {
                    document.querySelector('.tab-button[data-tab="ad-copy"]').click();
                    document.getElementById('ad-product').value = userInput.product || '';
                    document.getElementById('ad-audience').value = userInput.audience || '';
                    document.getElementById('generateAdBtn').disabled = true;
                    displayAdCopy(session.raw_text.split('---').map((p) => p.trim()).filter((p) => p));
                }
                showNotification('Session loaded successfully!');
                setInputsDisabled(true);
            }
            catch (error) {
                showError(error.message);
            }
        });
    };
});
//# sourceMappingURL=social_studio.js.map