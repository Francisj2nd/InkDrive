# ✒️ InkDrive

InkDrive is a smart, interactive web application that leverages the power of Google's Gemini AI to transform simple topics into full-length, SEO-optimized articles. It is designed for content creators, marketers, and writers who need to quickly generate high-quality drafts, complete with real-time image suggestions from the Google Custom Search API.

The application is built around a collection of specialized **"Studios,"** each tailored for a specific content-generation task—from long-form articles and social media posts to business proposals and video scripts. Its unique refinement process allows users to have a conversational follow-up with the AI to edit and improve generated content, turning a simple idea into a polished final product in minutes.

**➡️ Visit the Live Demo:** [https://inkdrive.ink/](https://inkdrive.ink/)

## ✨ Core Features

InkDrive offers a comprehensive suite of tools for modern content creation:

-   **Multi-Studio Workspace**: A collection of specialized tools for different content needs:
    -   **Article Studio**: Generate comprehensive, structured long-form articles.
    -   **Social Studio**: Create engaging posts for platforms like Twitter and LinkedIn.
    -   **Editing & Refinement Studio**: Improve existing text by changing its tone, summarizing it, or translating it.
    -   **Content Repurposing Studio**: Transform one piece of content into multiple formats (e.g., article to Twitter thread).
    -   **SEO Studio**: Develop keyword strategies and perform on-page SEO audits.
    -   **Brainstorming Studio**: Generate creative ideas, titles, and outlines.
    -   **Scriptwriting Studio**: Write scripts for YouTube, TikTok, and podcasts.
    -   **E-commerce & Web Copy Studios**: Craft persuasive product descriptions, landing page copy, and ad copy.
    -   **Business Docs Studio**: Draft professional press releases, proposals, and reports.
-   **AI-Powered Content Generation**: Enter a topic or a detailed prompt and receive a comprehensive, structured draft from Google's Gemini AI.
-   **Interactive Refinement**: Give follow-up instructions to edit, expand, or change the tone of the generated draft.
-   **Dynamic Image Suggestions**: Automatically finds and displays relevant, royalty-free images from Google Search to match the article's content, complete with AI-generated titles and alt text.
-   **Built-in SEO Tools**: Each article draft includes a list of suggested SEO keywords and a meta description to guide your content strategy.
-   **User Authentication**: Secure user registration and login system with support for both email/password and Google OAuth.
-   **Downloadable Formats**: Export the final article as a formatted Microsoft Word (`.docx`) document with embedded images.
-   **Content Management**: Users can view, manage, publish, and delete their generated articles from a personal dashboard.
-   **Admin Panel**: A comprehensive dashboard for administrators to manage users, moderate content, and view platform-wide statistics.
-   **Modern UI**: A clean, responsive user interface with a light/dark mode toggle.

---

## 🛠️ Tech Stack

| Category      | Technology                                                                                                    |
| :------------ | :------------------------------------------------------------------------------------------------------------ |
| **Backend**   | Flask (Python) with Gunicorn WSGI Server                                                                      |
| **Frontend**  | Standard HTML5, CSS3, and JavaScript (no framework)                                                           |
| **AI Model**  | Google Gemini (via Vertex AI API)                                                                             |
| **Database**  | Flask-SQLAlchemy ORM with support for PostgreSQL (production) and SQLite (development), with Flask-Migrate    |
| **Image API** | Google Custom Search API                                                                                      |
| **Auth**      | Flask-Login for session management, Google OAuth for social sign-in, and `bcrypt` for password hashing        |
| **Forms**     | Flask-WTF for secure form handling                                                                            |
| **Testing**   | Playwright for end-to-end and automated browser testing                                                       |
| **Deployment**| Pre-configured for deployment on services like Render or Google Cloud Run                                   |

---

## 🚀 Getting Started

Follow these instructions to get a local copy up and running for development and testing.

### Prerequisites

*   Python 3.9+
*   A Google Cloud Platform (GCP) project with the **Vertex AI API** and **Custom Search API** enabled.
*   Google OAuth 2.0 credentials (`Client ID` and `Client Secret`).
*   A Google Custom Search Engine ID.
*   `pip` for package installation.

### 1. Clone the Repository

```bash
git clone https://github.com/Francisj2nd/InkDrive
cd InkDrive
```

### 2. Install Dependencies

Install all required Python packages using the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the root of the project and add the following configuration variables. You can use the `app.py` and `admin.py` files as a reference for all required variables.

```env
# Flask Settings
SECRET_KEY='a_strong_random_secret_key'
DATABASE_URL='sqlite:///inkdrive.db' # Or your postgresql:// URL

# Google Cloud & AI Settings
GCP_PROJECT_ID='your-gcp-project-id'
GCP_LOCATION='us-central1'
GOOGLE_API_KEY='your-google-api-key' # For Custom Search
GOOGLE_CSE_ID='your-custom-search-engine-id'
GOOGLE_APPLICATION_CREDENTIALS='/path/to/your/gcp-credentials.json'

# Google OAuth Settings
GOOGLE_CLIENT_ID='your-google-client-id.apps.googleusercontent.com'
GOOGLE_CLIENT_SECRET='your-google-client-secret'

# Admin Settings
SUPERADMIN_EMAILS='your-admin-email@example.com'
```

### 4. Initialize the Database

Run the initialization script to create the necessary database tables and apply migrations.

```bash
python init_db.py
```

### 5. Run the Application

Start the Flask development server.

```bash
flask run
# Or use Gunicorn for a more production-like environment
gunicorn --bind 0.0.0.0:5001 app:app
```

The application will be running at `http://127.0.0.1:5001`.

---

## 📂 Project Structure

The project follows a standard Flask application structure, organizing logic into dedicated modules and blueprints.

```
InkDrive/
├── admin.py                # Flask blueprint for the admin panel and all related logic.
├── app.py                  # Main Flask application: handles routing, AI logic, and user auth.
├── forms.py                # Defines user input forms using Flask-WTF.
├── models.py               # Contains SQLAlchemy database models (User, Article, ChatSession).
├── migrations.py           # Logic for applying database schema changes.
├── init_db.py              # Script to initialize the database schema on first run.
├── requirements.txt        # Python package dependencies.
├── static/
│   ├── css/style.css       # Main stylesheet for the application.
│   └── images/             # Image assets for the UI.
└── templates/
    ├── admin/              # Templates for the admin dashboard, user, and article management.
    ├── article/            # Templates for viewing and sharing generated articles.
    ├── auth/               # Templates for login, registration, and Google sign-in.
    ├── profile/            # User profile, settings, and personal article list.
    ├── legal/              # Templates for Privacy, Terms, Support, and Contact pages.
    └── *.html              # Base and studio templates.
```

---

## 📜 License

This project is licensed under the MIT License. See the `LICENSE` file for more details.
