import { showNotification } from './notifications.js';

const STUDIO_TYPE = 'article';
// This script is now self-contained within the Article Studio page.
let currentArticleData: any = null;
let currentChatSessionId: string | null = null;
let refinementsUsed: number = 0;
const studioDataElement = document.getElementById('studio-data');
const studioData = studioDataElement ? JSON.parse(studioDataElement.textContent || '{}') : {};

let maxRefinements: number = studioData.maxRefinements || 1;
let isAuthenticated: boolean = studioData.isAuthenticated || false;

const topicInput = document.getElementById('topicInput') as HTMLTextAreaElement;
const wordCountSelect = document.getElementById('wordCountSelect') as HTMLSelectElement;
const audienceInput = document.getElementById('audienceInput') as HTMLInputElement;
const toneSelect = document.getElementById('toneSelect') as HTMLSelectElement;
const keyPointsInput = document.getElementById('keyPointsInput') as HTMLTextAreaElement;
const keywordInput = document.getElementById('keywordInput') as HTMLInputElement;
const ctaInput = document.getElementById('ctaInput') as HTMLInputElement;
const generateBtn = document.getElementById('generateBtn') as HTMLButtonElement;
const imageToggle = document.getElementById('imageToggle') as HTMLInputElement;
const newArticleBtn = document.getElementById('newArticleBtn') as HTMLButtonElement;
const articleDisplay = document.getElementById('articleDisplay') as HTMLDivElement;
const refinementSection = document.getElementById('refinementSection') as HTMLDivElement;
const refinementInput = document.getElementById('refinementInput') as HTMLTextAreaElement;
const refineBtn = document.getElementById('refineBtn') as HTMLButtonElement;
const refinementsLeft = document.getElementById('refinementsLeft') as HTMLSpanElement;
const articleActions = document.getElementById('articleActions') as HTMLDivElement;
const downloadBtn = document.getElementById('downloadBtn') as HTMLButtonElement;

document.addEventListener('DOMContentLoaded', function() {
    generateBtn.addEventListener('click', generateArticle);
    refineBtn.addEventListener('click', refineArticle);
    downloadBtn.addEventListener('click', downloadArticle);
    newArticleBtn.addEventListener('click', startNewArticle);
});

function startNewArticle() {
    // Re-enable form inputs
    topicInput.disabled = false;
    wordCountSelect.disabled = false;
    audienceInput.disabled = false;
    toneSelect.disabled = false;
    keyPointsInput.disabled = false;
    keywordInput.disabled = false;
    ctaInput.disabled = false;
    generateBtn.disabled = false;

    // Only re-enable the image toggle if the user is a superadmin (i.e., no 'Premium' badge)
    const isPremiumFeature = imageToggle && imageToggle.nextElementSibling!.querySelector('.badge');
    if (imageToggle && !isPremiumFeature) {
        imageToggle.disabled = false;
    }

    // Clear inputs
    topicInput.value = '';
    wordCountSelect.value = '1000';
    audienceInput.value = '';
    toneSelect.value = 'Professional';
    keyPointsInput.value = '';
    keywordInput.value = '';
    ctaInput.value = '';

    // Reset output area
    articleDisplay.innerHTML = `
        <div class="empty-state">
            <span class="material-symbols-outlined">article</span>
            <h3>Ready to Create</h3>
            <p>Enter a topic above and click "Generate Article" to get started.</p>
        </div>
    `;

    // Hide refinement and action sections
    refinementSection.style.display = 'none';
    articleActions.style.display = 'none';

    // Reset state
    currentArticleData = null;
    currentChatSessionId = null;
    refinementsUsed = 0;
    generateBtn.disabled = false;
    generateBtn.innerHTML = '<span class="material-symbols-outlined">auto_awesome</span> Generate Article';

    showNotification('New article started', 'success');
}

function showLoading(message: string = 'Generating article...') {
    articleDisplay.innerHTML = `<div class="loading"><div class="spinner"></div><span>${message}</span></div>`;
}

function updateRefinementsDisplay() {
    const remaining = maxRefinements - refinementsUsed;
    refinementsLeft.textContent = `${remaining} refinements remaining`;
    if (remaining <= 0) {
        refineBtn.disabled = true;
        refinementInput.disabled = true;
        refinementInput.placeholder = 'No refinements remaining';
    }
}

async function generateArticle() {
    const topic = topicInput.value.trim();
    if (!topic) {
        showNotification('Please enter a topic', 'error');
        return;
    }

    generateBtn.disabled = true;
    showLoading();

    const settings = {
        wordCount: wordCountSelect.value,
        audience: audienceInput.value.trim(),
        tone: toneSelect.value,
        keyPoints: keyPointsInput.value.trim(),
        seoKeyword: keywordInput.value.trim(),
        cta: ctaInput.value.trim(),
        enable_images: imageToggle ? imageToggle.checked : false
    };

    try {
        const endpoint = isAuthenticated ? '/api/v1/generate/article' : '/api/v1/generate/article-guest';
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                topic: topic,
                settings: settings,
                chat_session_id: currentChatSessionId
            })
        });
        const data = await response.json();

        if (response.ok) {
            currentArticleData = data;
            currentChatSessionId = data.chat_session_id;
            refinementsUsed = 0;
            maxRefinements = data.refinements_remaining + refinementsUsed;

            articleDisplay.innerHTML = `<div class="article-content">${data.article_html}</div>`;
            refinementSection.style.display = 'block';
            articleActions.style.display = 'flex';
            updateRefinementsDisplay();
            showNotification('Article generated successfully!');
            generateBtn.innerHTML = `<span class="material-symbols-outlined">check</span> Generated`;
            if (typeof (window as any).loadChatHistory === 'function') (window as any).loadChatHistory(STUDIO_TYPE);

            // Lock the form inputs after generation
            topicInput.disabled = true;
            wordCountSelect.disabled = true;
            audienceInput.disabled = true;
            toneSelect.disabled = true;
            keyPointsInput.disabled = true;
            keywordInput.disabled = true;
            ctaInput.disabled = true;
            if (imageToggle) imageToggle.disabled = true;
            generateBtn.disabled = true;
        } else {
            throw new Error(data.error || 'Failed to generate article');
        }
    } catch (error: any) {
        showNotification(error.message, 'error');
        generateBtn.disabled = false;
    }
}

async function refineArticle() {
    const refinementPrompt = refinementInput.value.trim();
    if (!refinementPrompt || !currentArticleData) return;

    if (refinementsUsed >= maxRefinements) {
        showNotification('No refinements remaining', 'error');
        return;
    }

    refineBtn.disabled = true;
    showLoading('Refining article...');

    try {
        const response = await fetch('/api/v1/refine/article', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                raw_text: currentArticleData.raw_text,
                refinement_prompt: refinementPrompt,
                article_id: currentArticleData.article_id,
                chat_session_id: currentChatSessionId,
                refinements_used: refinementsUsed,
                topic: topicInput.value
            })
        });
        const data = await response.json();

        if (response.ok) {
            currentArticleData.article_html = data.article_html;
            currentArticleData.raw_text = data.raw_text;
            refinementsUsed = data.refinements_used;

            articleDisplay.innerHTML = `<div class="article-content">${data.article_html}</div>`;
            updateRefinementsDisplay();
            refinementInput.value = '';
            showNotification('Article refined successfully!');
            if (typeof (window as any).loadChatHistory === 'function') (window as any).loadChatHistory(STUDIO_TYPE);
        } else {
            throw new Error(data.error || 'Failed to refine article');
        }
    } catch (error: any) {
        showNotification(error.message, 'error');
    } finally {
        refineBtn.disabled = false;
    }
}

async function downloadArticle() {
    if (!currentArticleData) return;
    try {
        const response = await fetch('/download-docx', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                html: currentArticleData.article_html,
                topic: topicInput.value,
                article_id: currentArticleData.article_id
            })
        });
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${topicInput.value.substring(0, 50)}.docx`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();
            showNotification('Article downloaded successfully!');
        } else {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to download article');
        }
    } catch (error: any) {
        showNotification(error.message, 'error');
    }
}

async function loadSessionIntoView(sessionId: string) {
    try {
        showLoading('Loading session...');
        const response = await fetch(`/api/chat-session/${sessionId}`);
        if (!response.ok) throw new Error('Failed to fetch session data.');

        const session = await response.json();

        // Assuming the user's input is the first message, and AI response is the second.
        const userMessage = session.messages[0].content;
        const aiResponseHtml = session.messages[1].content;

        topicInput.value = userMessage;
        articleDisplay.innerHTML = `<div class="article-content">${aiResponseHtml}</div>`;

        // Update state
        currentChatSessionId = session.session_id;
        currentArticleData = {
            raw_text: session.raw_text,
            article_html: aiResponseHtml,
            article_id: session.article_id
        };
        refinementsUsed = 0; // Reset refinements for a loaded session for now
        updateRefinementsDisplay();

        refinementSection.style.display = 'block';
        articleActions.style.display = 'flex';
        showNotification('Session loaded successfully!');
        generateBtn.innerHTML = `<span class="material-symbols-outlined">check</span> Loaded`;
        generateBtn.disabled = true;

        // Lock the form inputs when loading from history
        topicInput.disabled = true;
        wordCountSelect.disabled = true;
        audienceInput.disabled = true;
        toneSelect.disabled = true;
        keyPointsInput.disabled = true;
        keywordInput.disabled = true;
        ctaInput.disabled = true;
        if (imageToggle) imageToggle.disabled = true;

    } catch (error: any) {
        showNotification(error.message, 'error');
    }
}
(window as any).loadSessionIntoView = loadSessionIntoView;