import { showNotification } from './notifications.js';

// Global helper functions
function escapeHtml(unsafe: string): string {
    return unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function copyToClipboard(button: HTMLButtonElement) {
    const content = (button.previousElementSibling as HTMLElement).textContent;
    if (content) {
        navigator.clipboard.writeText(content).then(() => {
            button.textContent = 'Copied!';
            setTimeout(() => { button.textContent = 'Copy' }, 2000);
        }).catch(err => console.error('Copy failed', err));
    }
}
// Expose copyToClipboard to the global scope for inline onclick handlers
(window as any).copyToClipboard = copyToClipboard;


interface SocialPostSettings {
    tone: string;
    cta: string;
    variations: string;
    emojis: boolean;
}

interface EmailSettings {
    emailType: string;
    brandName: string;
    ctaButton: string;
}

interface AdCopySettings {
    platform: string;
    keyBenefit: string;
    tone: string;
}

document.addEventListener('DOMContentLoaded', function() {
    // --- COMMON ELEMENTS ---
    const outputDisplay = document.getElementById('output-display') as HTMLDivElement;
    let socialChatSessionId: string | null = null;

    // --- TAB SWITCHING ---
    const tabs = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            const tabElement = tab as HTMLElement; // Cast to HTMLElement
            document.getElementById(tabElement.dataset.tab!)!.classList.add('active');
            outputDisplay.innerHTML = `<div class="empty-state"><span class="material-symbols-outlined" style="font-size: 48px;">campaign</span><p>Your generated content will appear here.</p></div>`;
        });
    });

    // --- EVENT LISTENERS ---
    document.getElementById('newSessionBtn')?.addEventListener('click', startNewSession);
    document.getElementById('generateSocialBtn')?.addEventListener('click', generateSocial);
    document.getElementById('generateEmailBtn')?.addEventListener('click', generateEmail);
    document.getElementById('generateAdBtn')?.addEventListener('click', generateAdCopy);

    // --- HELPER FUNCTIONS ---
    function setInputsDisabled(disabled: boolean) {
        // Social Post Inputs
        (document.getElementById('social-topic') as HTMLTextAreaElement).disabled = disabled;
        (document.getElementById('social-goal') as HTMLSelectElement).disabled = disabled;
        (document.getElementById('social-platform') as HTMLSelectElement).disabled = disabled;
        (document.getElementById('social-tone') as HTMLSelectElement).disabled = disabled;
        (document.getElementById('social-cta') as HTMLInputElement).disabled = disabled;
        (document.getElementById('social-variations') as HTMLInputElement).disabled = disabled;
        (document.getElementById('social-emojis') as HTMLInputElement).disabled = disabled;
        (document.getElementById('generateSocialBtn') as HTMLButtonElement).disabled = disabled;

        // Email Inputs
        (document.getElementById('email-topic') as HTMLTextAreaElement).disabled = disabled;
        (document.getElementById('email-audience') as HTMLInputElement).disabled = disabled;
        (document.getElementById('email-tone') as HTMLSelectElement).disabled = disabled;
        (document.getElementById('email-type') as HTMLSelectElement).disabled = disabled;
        (document.getElementById('email-brand') as HTMLInputElement).disabled = disabled;
        (document.getElementById('email-cta') as HTMLInputElement).disabled = disabled;
        (document.getElementById('generateEmailBtn') as HTMLButtonElement).disabled = disabled;

        // Ad Copy Inputs
        (document.getElementById('ad-product') as HTMLInputElement).disabled = disabled;
        (document.getElementById('ad-audience') as HTMLInputElement).disabled = disabled;
        (document.getElementById('ad-platform') as HTMLSelectElement).disabled = disabled;
        (document.getElementById('ad-benefit') as HTMLInputElement).disabled = disabled;
        (document.getElementById('ad-tone') as HTMLSelectElement).disabled = disabled;
        (document.getElementById('generateAdBtn') as HTMLButtonElement).disabled = disabled;
    }

    function startNewSession() {
        // Re-enable all inputs
        setInputsDisabled(false);

        // Clear all inputs
        // Social
        (document.getElementById('social-topic') as HTMLTextAreaElement).value = '';
        (document.getElementById('social-goal') as HTMLSelectElement).value = 'Promote a product/service';
        (document.getElementById('social-platform') as HTMLSelectElement).value = 'Twitter';
        (document.getElementById('social-tone') as HTMLSelectElement).value = 'Professional';
        (document.getElementById('social-cta') as HTMLInputElement).value = '';
        (document.getElementById('social-variations') as HTMLInputElement).value = '3';
        (document.getElementById('social-emojis') as HTMLInputElement).checked = true;
        // Email
        (document.getElementById('email-topic') as HTMLTextAreaElement).value = '';
        (document.getElementById('email-audience') as HTMLInputElement).value = '';
        (document.getElementById('email-tone') as HTMLSelectElement).value = 'Professional';
        (document.getElementById('email-type') as HTMLSelectElement).value = 'Promotional';
        (document.getElementById('email-brand') as HTMLInputElement).value = '';
        (document.getElementById('email-cta') as HTMLInputElement).value = '';
        // Ad Copy
        (document.getElementById('ad-product') as HTMLInputElement).value = '';
        (document.getElementById('ad-audience') as HTMLInputElement).value = '';
        (document.getElementById('ad-platform') as HTMLSelectElement).value = 'Google Ads';
        (document.getElementById('ad-benefit') as HTMLInputElement).value = '';
        (document.getElementById('ad-tone') as HTMLSelectElement).value = 'Urgent';

        // Reset buttons
        resetButton(document.getElementById('generateSocialBtn') as HTMLButtonElement, 'auto_awesome', 'Generate Posts');
        resetButton(document.getElementById('generateEmailBtn') as HTMLButtonElement, 'mark_email_unread', 'Generate Email');
        resetButton(document.getElementById('generateAdBtn') as HTMLButtonElement, 'campaign', 'Generate Ad Copy');

        // Reset output
        outputDisplay.innerHTML = `<div class="empty-state"><span class="material-symbols-outlined" style="font-size: 48px;">campaign</span><p>Your generated content will appear here.</p></div>`;
        socialChatSessionId = null;
        showNotification('New session started.', 'success');
    }


    // --- API FUNCTIONS ---
    async function generateSocial(event: MouseEvent) {
        const topic = (document.getElementById('social-topic') as HTMLTextAreaElement).value;
        const goal = (document.getElementById('social-goal') as HTMLSelectElement).value;
        const platform = (document.getElementById('social-platform') as HTMLSelectElement).value;
        if (!topic) { alert('Please enter a topic.'); return; }

        const settings: SocialPostSettings = {
            tone: (document.getElementById('social-tone') as HTMLSelectElement).value,
            cta: (document.getElementById('social-cta') as HTMLInputElement).value,
            variations: (document.getElementById('social-variations') as HTMLInputElement).value,
            emojis: (document.getElementById('social-emojis') as HTMLInputElement).checked
        };

        showLoading(event.currentTarget as HTMLButtonElement, "Generating posts...");
        try {
            const response = await fetch('/api/v1/generate/social', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tool: 'social_post', topic, goal, platform, settings, chat_session_id: socialChatSessionId })
            });
            const data = await response.json();
            if (response.ok) {
                socialChatSessionId = data.chat_session_id;
                displaySocialPosts(data.posts);
                if (typeof (window as any).loadChatHistory === 'function') (window as any).loadChatHistory('social');
                setInputsDisabled(true);
            } else { throw new Error(data.error); }
        } catch (error: any) {
            showError(error.message);
        } finally {
            resetButton(event.currentTarget as HTMLButtonElement, 'auto_awesome', 'Generate Posts');
        }
    }

    async function generateEmail(event: MouseEvent) {
        const topic = (document.getElementById('email-topic') as HTMLTextAreaElement).value;
        const audience = (document.getElementById('email-audience') as HTMLInputElement).value;
        const tone = (document.getElementById('email-tone') as HTMLSelectElement).value;
        if (!topic) { alert('Please enter a topic.'); return; }

        const settings: EmailSettings = {
            emailType: (document.getElementById('email-type') as HTMLSelectElement).value,
            brandName: (document.getElementById('email-brand') as HTMLInputElement).value,
            ctaButton: (document.getElementById('email-cta') as HTMLInputElement).value
        };

        showLoading(event.currentTarget as HTMLButtonElement, "Generating email...");
        try {
            const response = await fetch('/api/v1/generate/social', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tool: 'email', topic, audience, tone, settings, chat_session_id: socialChatSessionId })
            });
            const data = await response.json();
            if (response.ok) {
                socialChatSessionId = data.chat_session_id;
                displayEmailContent(data.email_content);
                if (typeof (window as any).loadChatHistory === 'function') (window as any).loadChatHistory('social');
                setInputsDisabled(true);
            } else { throw new Error(data.error); }
        } catch (error: any) {
            showError(error.message);
        } finally {
            resetButton(event.currentTarget as HTMLButtonElement, 'mark_email_unread', 'Generate Email');
        }
    }

    async function generateAdCopy(event: MouseEvent) {
        const product = (document.getElementById('ad-product') as HTMLInputElement).value;
        const audience = (document.getElementById('ad-audience') as HTMLInputElement).value;
        if (!product || !audience) { alert('Please enter a product and audience.'); return; }

        const settings: AdCopySettings = {
            platform: (document.getElementById('ad-platform') as HTMLSelectElement).value,
            keyBenefit: (document.getElementById('ad-benefit') as HTMLInputElement).value,
            tone: (document.getElementById('ad-tone') as HTMLSelectElement).value
        };

        showLoading(event.currentTarget as HTMLButtonElement, "Generating ad copy...");
        try {
            const response = await fetch('/api/v1/generate/social', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tool: 'ad_copy', product, audience, settings, chat_session_id: socialChatSessionId })
            });
            const data = await response.json();
            if (response.ok) {
                socialChatSessionId = data.chat_session_id;
                displayAdCopy(data.ad_copy);
                if (typeof (window as any).loadChatHistory === 'function') (window as any).loadChatHistory('social');
                setInputsDisabled(true);
            } else { throw new Error(data.error); }
        } catch (error: any) {
            showError(error.message);
        } finally {
            resetButton(event.currentTarget as HTMLButtonElement, 'campaign', 'Generate Ad Copy');
        }
    }

    // --- DISPLAY & HELPER FUNCTIONS ---
    function showLoading(btn: HTMLButtonElement, message: string) {
        btn.disabled = true;
        btn.innerHTML = `<span class="material-symbols-outlined">hourglass_top</span> Generating...`;
        outputDisplay.innerHTML = `<div class="loading" style="padding: 40px; display:flex; justify-content: center; align-items: center; gap: 8px;"><div class="spinner"></div><span>${message}</span></div>`;
    }

    function showError(message: string) {
        outputDisplay.innerHTML = `<p style="color: red; padding: 20px;">Error: ${message}</p>`;
    }

    function resetButton(btn: HTMLButtonElement, icon: string, text: string) {
        btn.disabled = false;
        btn.innerHTML = `<span class="material-symbols-outlined">${icon}</span> ${text}`;
    }

    function displaySocialPosts(posts: string[]) {
        outputDisplay.innerHTML = posts.map((post, index) => `
            <div class="post-card"><h4>Option ${index + 1}</h4><pre class="post-content">${escapeHtml(post)}</pre><button class="btn btn-secondary" onclick="copyToClipboard(this)">Copy</button></div>
        `).join('');
    }

    function displayEmailContent(content: string) {
        const parts = content.split('---');
        const subjects = parts[0].trim();
        const body = parts.length > 1 ? parts.slice(1).join('---').trim() : '';
        outputDisplay.innerHTML = `
            <div class="post-card"><h4>Subject Line Options</h4><pre class="post-content">${escapeHtml(subjects)}</pre><button class="btn btn-secondary" onclick="copyToClipboard(this)">Copy Subjects</button></div>
            <div class="post-card"><h4>Email Body</h4><pre class="post-content">${escapeHtml(body)}</pre><button class="btn btn-secondary" onclick="copyToClipboard(this)">Copy Body</button></div>
        `;
    }

    function displayAdCopy(adCopy: string[]) {
        outputDisplay.innerHTML = adCopy.map((ad, index) => `
            <div class="post-card"><h4>Ad Variation ${index + 1}</h4><pre class="post-content">${escapeHtml(ad)}</pre><button class="btn btn-secondary" onclick="copyToClipboard(this)">Copy</button></div>
        `).join('');
    }

    (window as any).loadSessionIntoView = async function(sessionId: string) {
        try {
            outputDisplay.innerHTML = `<div class="loading" style="padding: 40px; display:flex; justify-content: center; align-items: center; gap: 8px;"><div class="spinner"></div><span>Loading session...</span></div>`;
            const response = await fetch(`/api/chat-session/${sessionId}`);
            if (!response.ok) throw new Error('Failed to fetch session data.');

            const session = await response.json();
            socialChatSessionId = session.session_id;

            // The user's original input is stored as a JSON string in the first message.
            const userInput = JSON.parse(session.messages[0].content);

            if (session.studio_type === 'SOCIAL_POST') {
                (document.querySelector('.tab-button[data-tab="social-posts"]') as HTMLElement).click();
                (document.getElementById('social-topic') as HTMLTextAreaElement).value = userInput.topic || '';
                (document.getElementById('social-goal') as HTMLSelectElement).value = userInput.goal || '';
                (document.getElementById('social-platform') as HTMLSelectElement).value = userInput.platform || '';
                (document.getElementById('generateSocialBtn') as HTMLButtonElement).disabled = true;
                displaySocialPosts(session.raw_text.split('---').map((p: string) => p.trim()).filter((p: string) => p));
            } else if (session.studio_type === 'EMAIL') {
                (document.querySelector('.tab-button[data-tab="emails"]') as HTMLElement).click();
                (document.getElementById('email-topic') as HTMLTextAreaElement).value = userInput.topic || '';
                (document.getElementById('email-audience') as HTMLInputElement).value = userInput.audience || '';
                (document.getElementById('email-tone') as HTMLSelectElement).value = userInput.tone || '';
                (document.getElementById('generateEmailBtn') as HTMLButtonElement).disabled = true;
                displayEmailContent(session.raw_text);
            } else if (session.studio_type === 'AD_COPY') {
                (document.querySelector('.tab-button[data-tab="ad-copy"]') as HTMLElement).click();
                (document.getElementById('ad-product') as HTMLInputElement).value = userInput.product || '';
                (document.getElementById('ad-audience') as HTMLInputElement).value = userInput.audience || '';
                (document.getElementById('generateAdBtn') as HTMLButtonElement).disabled = true;
                displayAdCopy(session.raw_text.split('---').map((p: string) => p.trim()).filter((p: string) => p));
            }
            showNotification('Session loaded successfully!');
            setInputsDisabled(true);
        } catch (error: any) {
            showError(error.message);
        }
    }
});