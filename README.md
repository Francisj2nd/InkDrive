# ✒️ Inkdrive

**Inkdrive** is a smart, interactive web application that leverages the power of Google's Gemini AI to transform simple topics into full-length, SEO-optimized articles. It's designed for content creators, marketers, and writers who need to quickly generate high-quality drafts, complete with real-time image suggestions from Unsplash.

The application features a unique refinement process, allowing the user to have a one-shot conversation with the AI to edit and improve the generated content, turning a simple idea into a polished article in minutes.

**➡️ Visit the Live Demo:** [https://inkdrive.ink/](https://inkdrive.ink/)  


## ✨ Features

- **AI-Powered Article Generation:** Enter a topic and receive a comprehensive, structured article draft.
- **Interactive Refinement:** Give a follow-up instruction to edit, expand, or change the generated draft.
- **Real-Time Image Suggestions:** The app automatically finds and displays relevant, royalty-free images from Unsplash to match the article's content.
- **Visible Title & Alt Text:** Image suggestions come with an AI-generated title and visible alt text to guide content strategy.
- **Built-in SEO Elements:** Each article concludes with a list of suggested SEO keywords and a meta description.
- **Downloadable Formats:** Export the final article as a formatted Microsoft Word (`.docx`) document, complete with embedded images.
- **Modern UI:** A clean, responsive user interface with a light/dark mode toggle.

## 🛠️ Tech Stack

- **Backend:** Flask (Python)
- **AI Model:** Google Gemini (via Vertex AI API)
- **Image Sourcing:** Unsplash API
- **Frontend:** Standard HTML5, CSS3, and JavaScript (no framework)
- **Deployment:** Gunicorn WSGI Server, prepared for services like Render or Google Cloud Run

## 🚀 Getting Started

Follow these instructions to get a local copy up and running for development and testing.

### Prerequisites

- Python 3.9+
- A Google Cloud Platform (GCP) project with the Vertex AI API enabled.
- An Unsplash Developer account for an API access key.
- `pip` for package installation.

### 1. Clone the Repository

```bash
git clone https://github.com/Francisj2nd/InkDrive
cd inkdrive
