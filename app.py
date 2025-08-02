import os
import io
import re
import requests
import markdown
from flask import Flask, render_template, request, jsonify, send_file
from bs4 import BeautifulSoup
from docx import Document
from docx.shared import Inches
from google import genai  # Updated import

# --- 1. INITIALIZATION & HELPERS ---
app = Flask(__name__)

# Load environment variables with fallbacks and validation
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash-lite")  # Adjusted to match snippet
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

if not GCP_PROJECT_ID or not UNSPLASH_ACCESS_KEY:
    raise RuntimeError("Required environment variables (GCP_PROJECT_ID, UNSPLASH_ACCESS_KEY) are not set.")

# Supported Vertex AI regions
SUPPORTED_REGIONS = {
    'europe-central2', 'us-east5', 'asia-southeast1', 'europe-southwest1', 'europe-north1',
    'me-central2', 'australia-southeast2', 'me-central1', 'us-east4', 'europe-west1',
    'europe-west2', 'asia-northeast1', 'me-west1', 'africa-south1', 'europe-west4',
    'europe-west12', 'northamerica-northeast2', 'europe-west9', 'southamerica-east1',
    'us-central1', 'asia-northeast3', 'europe-west6', 'northamerica-northeast1',
    'asia-south1', 'asia-east1', 'us-west3', 'us-east1', 'australia-southeast1',
    'us-south1', 'asia-southeast2', 'europe-west8', 'europe-west3', 'southamerica-west1',
    'us-west1', 'asia-east2', 'us-west4', 'us-west2', 'asia-northeast2'
}

# Validate and set GCP_LOCATION
if GCP_LOCATION not in SUPPORTED_REGIONS:
    print(f"Warning: {GCP_LOCATION} is not a supported Vertex AI region. Defaulting to us-central1.")
    GCP_LOCATION = "us-central1"

def construct_initial_prompt(topic):
    article_requirements = """
**Article Requirements:**
1.  Focus and Depth: Focus entirely on the topic. Educate the reader in-depth.
2.  Length: Aim for over 1000 words.
3.  Structure: Use clear sections with H2 and H3 subheadings using Markdown.
4.  Placeholders: Include 3 relevant image placeholders. For each, provide a suggested title and a full, SEO-optimized alt text. Format them exactly like this: `[Image Placeholder: Title, Alt Text]`
5.  SEO Elements: At the very end of the article, provide "SEO Keywords:" and "Meta Description:".
6.  Quality: The content must be original, human-readable, and valuable.
"""
    return f"""I want you to generate a high-quality, SEO-optimized thought-leadership article on the topic of: "{topic}"\n\n{article_requirements}"""

def get_image_url(query):
    if not UNSPLASH_ACCESS_KEY or "YOUR_KEY" in UNSPLASH_ACCESS_KEY:
        return None
    api_url = "https://api.unsplash.com/search/photos"
    params = {"query": query, "per_page": 1, "client_id": UNSPLASH_ACCESS_KEY}
    try:
        response = requests.get(api_url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data["results"]:
            photo = data["results"][0]
            return {"url": photo["urls"]["regular"], "attribution": f"Photo by {photo['user']['name']} on Unsplash"}
        return None
    except requests.RequestException:
        return None

try:
    # Initialize genai client with Vertex AI
    genai.configure(api_key=None)  # No API key needed for Vertex AI
    CLIENT = genai.Client(
        vertexai=True,
        project=GCP_PROJECT_ID,
        location=GCP_LOCATION,
    )
    print(f"✅ Google AI Client Initialized Successfully via Vertex AI in region {GCP_LOCATION}.")
except Exception as e:
    print(f"❌ Failed to initialize Google AI client. Error details: {e}")
    CLIENT = None

# --- 2. FORMATTING & WEB ROUTES ---

def format_article_content(raw_markdown_text):
    """
    This definitive version adds a VISIBLE paragraph for the Alt Text.
    """
    hybrid_content = raw_markdown_text
    placeholder_regex = re.compile(r"\[Image Placeholder: (.*?),\s*(.*?)\]")

    for match in placeholder_regex.finditer(raw_markdown_text):
        original_placeholder = match.group(0)
        title = match.group(1).strip()
        alt_text = match.group(2).strip()
        image_data = get_image_url(alt_text)

        if image_data:
            new_image_tag = (
                f'<div class="real-image-container">'
                f'<p class="image-title">{title}</p>'
                f'<img src="{image_data["url"]}" alt="{alt_text}">'
                f'<p class="alt-text-display"><strong>Alt Text:</strong> {alt_text}</p>'
                f'<p class="attribution">{image_data["attribution"]}</p>'
                f'</div>'
            )
            hybrid_content = hybrid_content.replace(original_placeholder, new_image_tag, 1)

    final_html = markdown.markdown(hybrid_content, extensions=['fenced_code', 'tables'])
    return final_html

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate_article():
    if not CLIENT:
        return jsonify({"error": "AI client is not initialized."}), 500
    data = request.get_json()
    user_topic = data.get("topic")
    if not user_topic:
        return jsonify({"error": "Topic is missing."}), 400

    full_prompt = construct_initial_prompt(user_topic)
    try:
        response = CLIENT.generate_content(
            model=MODEL_NAME,
            contents=full_prompt,
        )
        if not response.candidates:
            return jsonify({"error": "Model response was empty."}), 500
        
        raw_text = response.candidates[0].content.parts[0].text
        final_html = format_article_content(raw_text)
        
        return jsonify({"article_html": final_html, "raw_text": raw_text})
    except Exception as e:
        return jsonify({"error": f"API Error: {str(e)}"}), 500

@app.route("/refine", methods=["POST"])
def refine_article():
    if not CLIENT:
        return jsonify({"error": "AI client is not initialized."}), 500
    data = request.get_json()
    raw_text, refinement_prompt = data.get("raw_text"), data.get("refinement_prompt")
    if not all([raw_text, refinement_prompt]):
        return jsonify({"error": "Missing data for refinement."}), 400
    
    try:
        history = [
            {"role": "user", "parts": [{"text": "You are an AI assistant. You provided this article draft."}]},
            {"role": "model", "parts": [{"text": raw_text}]},
            {"role": "user", "parts": [{"text": refinement_prompt}]}
        ]
        response = CLIENT.generate_content(
            model=MODEL_NAME,
            contents=history,
        )
        if not response.candidates:
            return jsonify({"error": "Refinement response was empty."}), 500

        refined_text = response.candidates[0].content.parts[0].text
        final_html = format_article_content(refined_text)

        return jsonify({"article_html": final_html, "raw_text": refined_text})
    except Exception as e:
        return jsonify({"error": f"API Error: {str(e)}"}), 500

@app.route("/download-docx", methods=["POST"])
def download_docx():
    data = request.get_json()
    html_content = data.get("html")
    topic = data.get("topic", "Generated Article")
    if not html_content:
        return jsonify({"error": "Missing HTML content."}), 400
    soup = BeautifulSoup(html_content, 'html.parser')
    doc = Document()
    doc.add_heading(topic, level=0)
    for element in soup.find_all(['h2', 'h3', 'p', 'div']):
        if element.name == 'h2':
            doc.add_heading(element.get_text(), level=2)
        elif element.name == 'h3':
            doc.add_heading(element.get_text(), level=3)
        elif element.name == 'p' and not element.find_parents("div"):
            doc.add_paragraph(element.get_text())
        elif element.name == 'div' and "real-image-container" in element.get('class', []):
            title_p = element.find('p', class_='image-title')
            img_tag = element.find('img')
            alt_text_p = element.find('p', class_='alt-text-display')
            attr_p = element.find('p', class_='attribution')
            
            if title_p:
                p = doc.add_paragraph(title_p.get_text())
                p.alignment = 1
                p.bold = True
            
            if img_tag and img_tag.get('src'):
                try:
                    img_response = requests.get(img_tag['src'], stream=True)
                    img_response.raise_for_status()
                    doc.add_picture(io.BytesIO(img_response.content), width=Inches(5.0))
                except requests.RequestException:
                    doc.add_paragraph(f"[Image failed to load]")
            
            if alt_text_p:
                p = doc.add_paragraph()
                clean_alt_text = alt_text_p.get_text().replace("Alt Text: ", "")
                p.add_run(clean_alt_text).italic = True
                p.alignment = 1

            if attr_p:
                p = doc.add_paragraph(attr_p.get_text())
                p.alignment = 1
                p.italic = True
    
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    filename = f"{topic[:50].strip().replace(' ', '_')}.docx"
    return send_file(file_stream, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

if __name__ == "__main__":
    app.run(debug=True, port=5001)
