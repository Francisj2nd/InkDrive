import os
import io
import json
import re
import requests
import markdown
from flask import Flask, render_template, request, jsonify, send_file
from bs4 import BeautifulSoup
from docx import Document
from docx.shared import Inches
import google.genai as genai

# --- 1. INITIALIZATION & HELPERS ---
app = Flask(__name__)

def load_config(filename="config.json"):
    try:
        with open(filename, "r") as f: return json.load(f)
    except FileNotFoundError: return None

CONFIG = load_config()
if not CONFIG: raise RuntimeError("Failed to load config.json.")

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
    access_key = CONFIG.get("unsplash_config", {}).get("access_key")
    if not access_key or "YOUR_KEY" in access_key: return None
    api_url = "https://api.unsplash.com/search/photos"
    params = {"query": query, "per_page": 1, "client_id": access_key}
    try:
        response = requests.get(api_url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data["results"]:
            photo = data["results"][0]
            return {"url": photo["urls"]["regular"], "attribution": f"Photo by {photo['user']['name']} on Unsplash"}
        return None
    except requests.RequestException: return None

try:
    CLIENT = genai.Client(vertexai=True, project=CONFIG['project_config']['project_id'], location=CONFIG['project_config']['location'])
    print("✅ Google AI Client Initialized Successfully via Vertex AI.")
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
            # THE FIX IS HERE: We add a new <p> tag with the class "alt-text-display"
            new_image_tag = (
                f'<div class="real-image-container">'
                f'<p class="image-title">{title}</p>'
                f'<img src="{image_data["url"]}" alt="{alt_text}">'
                f'<p class="alt-text-display"><strong>Alt Text:</strong> {alt_text}</p>'  # <-- THIS LINE IS NEW
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
    if not CLIENT: return jsonify({"error": "AI client is not initialized."}), 500
    data = request.get_json()
    user_topic = data.get("topic")
    if not user_topic: return jsonify({"error": "Topic is missing."}), 400

    full_prompt = construct_initial_prompt(user_topic)
    try:
        response = CLIENT.models.generate_content(model=CONFIG['model_config']['model_name'], contents=full_prompt)
        if not response.candidates: return jsonify({"error": "Model response was empty."}), 500
        
        raw_text = response.text
        # THE FIX: Call the correct function name here
        final_html = format_article_content(raw_text)
        
        return jsonify({"article_html": final_html, "raw_text": raw_text})
    except Exception as e:
        return jsonify({"error": f"API Error: {str(e)}"}), 500

@app.route("/refine", methods=["POST"])
def refine_article():
    if not CLIENT: return jsonify({"error": "AI client is not initialized."}), 500
    data = request.get_json()
    raw_text, refinement_prompt = data.get("raw_text"), data.get("refinement_prompt")
    if not all([raw_text, refinement_prompt]): return jsonify({"error": "Missing data for refinement."}), 400
    
    try:
        history = [
            {'role': 'user', 'parts': [{'text': "You are an AI assistant. You provided this article draft."}]},
            {'role': 'model', 'parts': [{'text': raw_text}]},
            {'role': 'user', 'parts': [{'text': refinement_prompt}]}
        ]
        response = CLIENT.models.generate_content(model=CONFIG['model_config']['model_name'], contents=history)
        if not response.candidates: return jsonify({"error": "Refinement response was empty."}), 500

        refined_text = response.text
        # THE FIX: Call the correct function name here
        final_html = format_article_content(refined_text)

        return jsonify({"article_html": final_html, "raw_text": refined_text})
    except Exception as e:
        return jsonify({"error": f"API Error: {str(e)}"}), 500

@app.route("/download-docx", methods=["POST"])
def download_docx():
    data = request.get_json()
    html_content = data.get("html")
    topic = data.get("topic", "Generated Article")
    if not html_content: return jsonify({"error": "Missing HTML content."}), 400
    soup = BeautifulSoup(html_content, 'html.parser')
    doc = Document()
    doc.add_heading(topic, level=0)
    for element in soup.find_all(['h2', 'h3', 'p', 'div']):
        if element.name == 'h2': doc.add_heading(element.get_text(), level=2)
        elif element.name == 'h3': doc.add_heading(element.get_text(), level=3)
        elif element.name == 'p' and not element.find_parents("div"):
            doc.add_paragraph(element.get_text())
        elif element.name == 'div' and "real-image-container" in element.get('class', []):
            # Capture all parts of the image container
            title_p = element.find('p', class_='image-title')
            img_tag = element.find('img')
            alt_text_p = element.find('p', class_='alt-text-display') # Find the new alt text p
            attr_p = element.find('p', class_='attribution')
            
            # Add Title
            if title_p:
                p = doc.add_paragraph(title_p.get_text())
                p.alignment = 1; p.bold = True
            
            # Add Image
            if img_tag and img_tag.get('src'):
                try:
                    img_response = requests.get(img_tag['src'], stream=True)
                    img_response.raise_for_status()
                    doc.add_picture(io.BytesIO(img_response.content), width=Inches(5.0))
                except requests.RequestException:
                    doc.add_paragraph(f"[Image failed to load]")
            
            # THE FIX IS HERE: Add the visible Alt Text to the document
            if alt_text_p:
                p = doc.add_paragraph()
                # Remove "Alt Text: " label for cleaner doc output
                clean_alt_text = alt_text_p.get_text().replace("Alt Text: ", "")
                p.add_run(clean_alt_text).italic = True
                p.alignment = 1

            # Add Attribution
            if attr_p: 
                p = doc.add_paragraph(attr_p.get_text())
                p.alignment = 1; p.italic = True
    
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    filename = f"{topic[:50].strip().replace(' ', '_')}.docx"
    return send_file(file_stream, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

if __name__ == "__main__":
    app.run(debug=True, port=5001)