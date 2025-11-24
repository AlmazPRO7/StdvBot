# ConstructionAI System 🏗️

An automated AI pipeline for handling customer service requests in retail (Construction materials domain).
Demonstrates **Prompt Engineering**, **Structured Data Extraction (JSON)**, and **Brand-Safe Automated Replies**.

## 🚀 Key Features

1.  **Analyst Agent:** Uses LLM to classify incoming unstructured messages into strict JSON format (`intent`, `sentiment`, `urgency`).
2.  **Support Agent:** Generates empathic, brand-safe apology letters for negative reviews.
    *   *Innovation:* Implements **Negative Constraints** in system prompts to prevent the model from admitting systemic failures ("we failed standards") and instead focuses on specific incident resolution.
3.  **Vision Agent:** Analyzes photos of construction materials/tools with product identification and search suggestions.
4.  **Automatic Fallback:** OpenRouter → Google Gemini Direct API при rate limits (200→1500 requests/day). See [FALLBACK_MECHANISM.md](FALLBACK_MECHANISM.md)
5.  **Robust Architecture:** Separation of concerns (Config, Logic, Prompts), Error Handling, and Environment Security.

## 🛠 Tech Stack
*   **Python 3.10+**
*   **Google Gemini API** (via `requests` for lightweight implementation)
*   **Pandas** for data processing
*   **Python-dotenv** for security

## 📦 Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ConstructionAI_System.git
   ```
2. Install dependencies:
   ```bash
   pip install python-dotenv pandas requests
   ```
3. Setup API Key:
   Create a `.env` file based on `.env.example` and add your `GEMINI_API_KEY`.

## ▶️ Usage

Run the main pipeline:
```bash
python3 main.py
```

The system will generate synthetic customer data, analyze it, and produce a report in `data/final_report.csv`.

## 🧠 Prompt Engineering Highlights

Check `src/prompts.py` to see how **Few-Shot Learning** and **Negative Constraints** are implemented to control the LLM's output structure and tone of voice.
