# SG Finance Super Bot

A Telegram-based AI agent designed to help users objectively evaluate private home mortgage refinancing options and scan for the best savings alternatives. It fetches live SORA (Singapore Overnight Rate Average) benchmark data from the Monetary Authority of Singapore (MAS), scans live promotional banking rates across major institutions, and uses Google's Gemini AI to generate a mathematical comparison and risk-adjusted financial recommendations.

## 🚀 Features

* **Live Government Data Integration:** Automatically pulls the latest 3-Month Compounded SORA rate directly from the MAS public API.
* **Multi-Bank FD Scanner:** Leverages Google Search capabilities via Gemini to actively crawl live promotional fixed deposit interest rates across major Singapore banks (DBS, UOB, OCBC, CIMB, RHB, and more).
* **Mobile-Optimized UI Layout:** Swaps out wide, wrapping markdown tables for a clean, vertical visual hierarchy specifically designed to prevent horizontal text distortion on mobile screens.
* **Pre-Computed Math Accuracy:** Calculates effective floating rates programmatically in Python before passing data to the LLM, preventing AI arithmetic hallucinations.
* **AI-Powered Analysis:** Uses Google Gemini to format comparisons, review sovereign bond alternatives (T-Bills/SSB), and provide risk-adjusted recommendations.
* **Resilient Bot Design:** Built with automatic message chunking to bypass Telegram’s 4,096-character limit, plain-text fallback handling for entity parsing crashes, and exponential backoff retry logic for API 503 errors.
* **24/7 Cloud Availability:** Hosted on Render using Telegram Webhooks, allowing instant access via mobile phone without needing a local server running.

## 🛠️ Technologies Used

| Technology / Library | Purpose |
| :--- | :--- |
| **Python 3.11** | Core backend logic. |
| **python-telegram-bot[webhooks]** | Handles incoming messages from the Telegram app and manages the webhook connection. |
| **google-genai** | Google's official Python SDK to connect to the Gemini API (specifically `gemini-2.5-flash`) for the reasoning engine and live web search. |
| **requests** | Used to ping the MAS Datastore API securely while bypassing basic bot-protection firewalls using User-Agent headers. |
| **Render.com** | Cloud hosting platform used to deploy the Python script as a 24/7 web service. |

## 🧠 Core Logic & Workflow

Here is exactly how the bot processes a user's request from start to finish:

1.  **The Trigger (Telegram Webhook):** The user interacts with the bot via a structured command (`/bank`) or sends a message to the bot on Telegram in a structured mortgage format (e.g., `Loan: 800000`, `Fixed: 2.85`, `Spread: 0.65`). The Telegram API sends an HTTP POST request to our Render server via a Webhook, waking up the Python script.
2.  **The Data Fetch (MAS API & Live Web Search):** * For mortgage queries, the script executes the `get_latest_sora_rates()` function, querying the MAS API (`eservices.mas.gov.sg`) to get the absolute latest daily and 3-Month Compounded SORA rates. Fallback mechanisms are built-in just in case the MAS server times out.
    * For banking queries, the agent initializes the Gemini 2.5 Flash model with a target system prompt to execute a live web search for active fixed deposit promotional tiers.
3.  **The Pre-Computation (Python Math):** LLMs are historically bad at deterministic math. To ensure 100% financial accuracy on mortgage requests, the Python script calculates the effective floating rate (Current 3M SORA + Bank Spread) internally.
4.  **The Reasoning Engine (Google Gemini):** The script bundles the user's input, the live data feeds, and any pre-computed math into a strict system prompt. This prompt instructs Gemini to:
    * Conduct a "SORA Breakeven" Threshold analysis or multi-bank tier breakdown.
    * Apply a strict mobile-first layout limit (under 3,000 characters to safely bypass Telegram constraints).
    * Deliver a professional, risk-assessed recommendation based on a 2-year timeline.
5.  **The Output (Telegram Delivery):** Gemini returns the formatted text, and the Python script pushes it back to the user's Telegram chat interface, reverting to a plain-text parsing fallback if the formatting triggers an engine crash.

## 🏗️ Technical Architecture Explained

The application is built using an **Asynchronous Webhook Event-Driven Architecture**. Instead of constantly running a resource-heavy polling loop (`long-polling`) to check Telegram's servers for new messages, the application remains idle until poked, optimized for deployment on cloud platforms like Render.

```text
    ┌───────────────────┐               ┌────────────────┐               ┌───────────────────────┐
    │   Telegram App    │ ─────────────►│   Render App   │ ─────────────►│     MAS API Portal    │
    │  (User Interface) │ ◄─────────────│ (Python Logic) │ ◄─────────────│ (eservices.mas.gov.sg)│
    └───────────────────┘               └────────────────┘               └───────────────────────┘
                                                │
                                        (Generate Content)
                                                │
                                                ▼
                                    ┌───────────────────────┐
                                    │ Google Gemini Engine  │ ◄───(Live Search / Tooling)
                                    │  (gemini-2.5-flash)   │
                                    └───────────────────────┘
```

### 1. Webhook Lifecycle & Runtime Efficiency
The application configures a secure webhook pipeline mapping your private `TELEGRAM_BOT_TOKEN` as a strict routing path endpoint (`https://your-app.onrender.com/<TOKEN>`). When a user sends a string or triggers a slash command:
- Telegram handles the ingress edge traffic and maps it to a fast HTTP POST payload targeting our Render runtime container.
- The Python backend, managed via an asynchronous event loop (`asyncio`), safely processes incoming payloads concurrently without blocking execution tasks when waiting on slow third-party networks.

### 2. Guarding Against AI Hallucination & API Stability
Large Language Models are non-deterministic and prone to calculation drift. The system mitigates this by completely isolating **Data Ingestion** and **Arithmetic Calculations** inside native Python runtimes before involving the AI:
- **Deterministic Pre-Computation:** The exact string inputs from raw user data are processed via string parsers. Float values are converted and injected cleanly into the System context alongside real-time MAS baseline figures. The LLM acts solely as a *Reasoning and Personalization Engine*, not a calculator.
- **Resiliency & Retries:** API communication handles transient failures smoothly. If a search query or external benchmark api triggers a standard network delay or `HTTP 503 System Busy` failure, an execution loop catches the exception, relays a micro-update update directly to the client screen, applies a `3-second sleep` buffer, and safely retries the payload execution up to 3 times before timing out.

### 3. Handling Telegram API Platform Edge Cases
The application implements specific sanitization routines to handle Telegram's strict UI rendering criteria:
- **Chunking Subsystem:** Telegram's max text limitation per message is exactly 4,096 characters. When large data scans are returned from the web search tools, the application reviews the content size dynamically, splitting files over 4,000 characters into separate index chunks to prevent payload dropping.
- **Parsing Fallback Subsystem:** Shifting styles from rich Markdown layout structures to Telegram engines often crashes if symbols break edge formatting rules (such as unclosed brackets or mismatched underscores). To bypass parsing crashes, the application captures structural layout bugs inline, alerts the logging console, drops the `parse_mode="Markdown"` configuration array instantly, and sends a sanitized plain-text string so the user receives their financial assessment uninterrupted.

## ⚙️ Environment Configuration

To run this project, the following environment variables must be configured in your deployment platform (e.g., Render):
* `TELEGRAM_BOT_TOKEN`: The HTTP API token generated by @BotFather.
* `GEMINI_API_KEY`: The API key generated from Google AI Studio.
* `PYTHON_VERSION`: Set to `3.11.0` to ensure stable webhook routing.
* `RENDER_EXTERNAL_URL`: The public URL of your web service hosting the webhook.
