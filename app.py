import os
import io
import re
import requests
import markdown
from flask import Flask, render_template, request, jsonify, send_file
from bs4 import BeautifulSoup
from docx import Document
from docx.shared import Inches
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import json # Needed to parse the JSON key content

# --- 1. INITIALIZATION & HELPERS ---
app = Flask(__name__)

# Load environment variables from Render
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash-lite-preview-06-17")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

# Retrieve the service account key content from Render's environment variable
GOOGLE_APPLICATION_CREDENTIALS_CONTENT = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

if not GCP_PROJECT_ID or not UNSPLASH_ACCESS_KEY or not GOOGLE_APPLICATION_CREDENTIALS_CONTENT:
    missing_vars = []
    if not GCP_PROJECT_ID: missing_vars.append("GCP_PROJECT_ID")
    if not UNSPLASH_ACCESS_KEY: missing_vars.append("UNSPLASH_ACCESS_KEY")
    if not GOOGLE_APPLICATION_CREDENTIALS_CONTENT: missing_vars.append("GOOGLE_APPLICATION_CREDENTIALS")
    raise RuntimeError(f"Required environment variables are not set: {', '.join(missing_vars)}")

# --- Initialize genai client with Vertex AI ---
service_account_file_path = None # Define it here, outside the try block

try:
    # --- Handle the service account key content ---
    os.makedirs('/tmp', exist_ok=True)
    service_account_file_path = '/tmp/service_account_key.json' # Now it's always defined

    with open(service_account_file_path, 'w') as f:
        f.write(GOOGLE_APPLICATION_CREDENTIALS_CONTENT)
    
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_file_path
    
    genai.configure()
    print(f"✅ Configured Google AI using credentials from {service_account_file_path}.")
    print(f"   Using project: {GCP_PROJECT_ID}, location: {GCP_LOCATION}, model: {MODEL_NAME}")

    CLIENT = genai.GenerativeModel(model_name=f"projects/{GCP_PROJECT_ID}/locations/{GCP_LOCATION}/models/{MODEL_NAME}")
    print(f"✅ Google AI Client Initialized Successfully via Vertex AI.")

except FileNotFoundError:
    print(f"❌ Error: Could not write service account key to {service_account_file_path}")
    CLIENT = None
except google_exceptions.GoogleAPIError as e:
    print(f"❌ Google API Error initializing AI client: {e}")
    CLIENT = None
except Exception as e:
    print(f"❌ Failed to initialize Google AI client. Error details: {e}")
    CLIENT = None

# --- Rest of your app.py remains the same ---

def construct_initial_prompt(topic):
    article_requirements = """
**Article Requirements:**
1. Focus and Depth: Focus entirely on the topic. Educate the reader in-depth.
2. Length: Aim for over 1000 words.
3. Structure: Use clear sections with H2 and H3 subheadings using Markdown.
4. Placeholders: Include 3 relevant image placeholders. For each, provide a suggested title and a full, SEO-optimized alt text. Format them exactly like this: `[Image Placeholder: Title, Alt Text]`
5. SEO Elements: At the very end of the article, provide "SEO Keywords:" and "Meta Description:".
6. Quality: The content must be original, human-readable, and valuable.
"""
    return f"""I want you to generate a high-quality, SEO-optimized thought-leadership article on the topic of: "{topic}"

{article_requirements}
"""

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
                f'<p class="image-title">{title}</p>' # Added title here
                f'<img src="{image_data["url"]}" alt="">'
                f'<p class="alt-text-display"><strong>Alt Text:</strong> {alt_text}</p>' # Added alt text directly
                f'<p class="attribution">{image_data["attribution"]}</p>'
                f'</div>'
            )
            hybrid_content = hybrid_content.replace(original_placeholder, new_image_tag, 1)
        else:
            # If image fetch fails, keep a placeholder or a simple text
            hybrid_content = hybrid_content.replace(original_placeholder, f'<p>[Image Placeholder: {title} - Could not fetch image]</p>', 1)

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
        response = CLIENT.generate_content(contents=full_prompt)

        if not response.candidates:
            error_message = "Model response was empty or blocked."
            if response.prompt_feedback:
                error_message += f" Prompt feedback: {response.prompt_feedback}"
            return jsonify({"error": error_message}), 500

        if not response.candidates[0].content.parts:
            return jsonify({"error": "Model response content is empty."}), 500

        raw_text = response.candidates[0].content.parts[0].text
        final_html = format_article_content(raw_text)

        return jsonify({"article_html": final_html, "raw_text": raw_text})
    except google_exceptions.GoogleAPIError as e:
        return jsonify({"error": f"Google API Error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

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
        response = CLIENT.generate_content(contents=history) # Use contents for chat history

        if not response.candidates:
            error_message = "Refinement response was empty or blocked."
            if response.prompt_feedback:
                error_message += f" Prompt feedback: {response.prompt_feedback}"
            return jsonify({"error": error_message}), 500

        if not response.candidates[0].content.parts:
            return jsonify({"error": "Refinement response content is empty."}), 500

        refined_text = response.candidates[0].content.parts[0].text
        final_html = format_article_content(refined_text)

        return jsonify({"article_html": final_html, "raw_text": refined_text})
    except google_exceptions.GoogleAPIError as e:
        return jsonify({"error": f"Google API Error during refinement: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred during refinement: {str(e)}"}), 500

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
                p.alignment = 1 # Center alignment (adjust as needed)
                p.bold = True

            if img_tag and img_tag.get('src'):
                try:
                    img_response = requests.get(img_tag['src'], stream=True)
                    img_response.raise_for_status()
                    doc.add_picture(io.BytesIO(img_response.content), width=Inches(5.5))
                except requests.RequestException:
                    doc.add_paragraph(f"[Image failed to load from {img_tag['src']}]")

            if alt_text_p:
                p = doc.add_paragraph()
                clean_alt_text = alt_text_p.get_text()
                if clean_alt_text.lower().startswith("alt text:"):
                    clean_alt_text = clean_alt_text[len("Alt Text:"):].strip()
                run = p.add_run(clean_alt_text)
                run.italic = True
                p.alignment = 1 # Center alignment

            if attr_p:
                p = doc.add_paragraph(attr_p.get_text())
                p.alignment = 1 # Center alignment
                p.italic = True

    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    filename = f"{topic[:50].strip().replace(' ', '_')}.docx"
    return send_file(file_stream, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

if __name__ == "__main__":
    # Clean up the temporary service account file on startup if it exists
    # This is good practice, though in ephemeral containers, it's less critical.
    # Ensure service_account_file_path is defined here before checking its existence.
    # If initialization failed, service_account_file_path might still be None.
    
    # Only attempt cleanup if service_account_file_path was successfully assigned
    if 'service_account_file_path' in locals() and service_account_file_path and os.path.exists(service_account_file_path):
        try:
            os.remove(service_account_file_path)
            print(f"Cleaned up temporary service account file: {service_account_file_path}")
        except OSError as e:
            print(f"Error removing temporary service account file: {e}")

    app.run(debug=True, port=5001)
