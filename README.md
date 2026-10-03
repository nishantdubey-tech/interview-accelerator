# Forma — AI Interview Accelerator

Forma is an AI-powered interview practice platform that analyzes a job description and candidate resume, calculates an explainable evidence-weighted Job Fit score, conducts a personalized three-level adaptive interview, evaluates answers, and produces a preparation report. Its readiness score is a coaching estimate, not a hiring decision or validated psychometric result.

---

## Live Deployment & Repository

- **Live Deployed Application:** [https://interview-accelerator-44ui.onrender.com](https://interview-accelerator-44ui.onrender.com)
- **GitHub Repository:** [https://github.com/nishantdubey-tech/interview-accelerator](https://github.com/nishantdubey-tech/interview-accelerator)
- **Health Endpoint:** [https://interview-accelerator-44ui.onrender.com/api/health](https://interview-accelerator-44ui.onrender.com/api/health)
- **Demo video:** Pending recording. Follow [DEMO_SCRIPT.md](DEMO_SCRIPT.md) to capture the full journey.

---

## Problem Statement

Most interview preparation tools fail in two critical ways:
1. **Generic Question Lists:** They ask standardized questions (*"Tell me about a time you solved a conflict"*) rather than grilling candidates on the specific claims, frameworks, and metrics written in their resumes.
2. **Static Question Trees:** They cannot adapt dynamically to candidate answers. In a real interview, if a candidate claims they *"optimized search latency by 28%"*, the interviewer will immediately probe the baseline, measurement tooling, and system trade-offs.

Forma solves this by acting as a calibrated, adaptive technical interviewer that reads the fine print of both the job brief and the candidate's actual projects, dynamically shaping each follow-up question based on what the candidate just said.

---

## Complete User Journey

```
[Job Description (Paste/Upload)] + [Candidate Resume (Paste/Upload)]
                           │
                           ▼
          [Step 1: AI Role Competency Extraction]
                           │
                           ▼
          [Step 2: AI Candidate Evidence & Claims Extraction]
                           │
                           ▼
          [Step 3: Transparent 6-Factor Job Fit Engine]
                           │
                           ▼
          [Step 4: Start AI Interview Simulator]
                           │
         ┌─────────────────┴─────────────────┐
         ▼                                   ▼
[Level 1: Screening]             [Candidate Voice Response]
(Motivation & Resume claims)     (Web Speech STT / MediaRecorder fallback)
         │                                   │
         ▼                                   ▼
[Level 2: Competency]            [Real-Time Answer Evaluation]
(System Design & Problem Solving)(Relevance, Depth, Evidence)
         │                                   │
         ▼                                   ▼
[Level 3: Deep-Dive]             [Adaptive Next Question]
(Edge cases & Trade-offs)        (Causally conditioned on answer)
         └─────────────────┬─────────────────┘
                           ▼
           [Step 5: Final Performance Report]
         ┌─────────────────┴─────────────────┐
         ▼                                   ▼
[7 Competency Scores]             [Prioritized Preparation Gaps]
         ▼                                   ▼
[Question-Level Feedback]        [Interview Readiness Score /100]
```

1. **Input & Profile Ingestion:** Paste text directly or upload PDF, DOCX, or TXT files (up to 8 MB). Three built-in sample profiles let evaluators try the flow quickly.
2. **Role & Candidate Analysis:** Structured AI extraction separates requirements into required skills, preferred qualifications, and candidate claims to probe.
3. **Transparent Job Fit Engine:** Computes a mathematical score (0–100%) from 6 weighted evidence dimensions with Strong/Partial/Weak categorization.
4. **Adaptive Interview Simulator:**
   - **Level 1 (Screening):** Probes resume background, ownership, and role motivation.
   - **Level 2 (Competency):** Deepens into domain competencies, technical architecture, and decision making.
   - **Level 3 (Deep-Dive):** Challenges vague claims, asks why/how, and probes edge-case failure modes.
5. **Voice AI & Video Preview:**
   - AI speaks each question using browser SpeechSynthesis with replay and stop controls.
   - Candidates answer via live speech recognition (Web Speech API) or backend cloud audio transcription fallback (`/api/transcribe`).
   - Live speech analytics tracks duration, Words Per Minute (WPM), and filler word counts.
   - Optional candidate webcam preview toggle.
6. **Real-Time Evaluation:** Every answer receives immediate structured feedback with scores and the rationale for the subsequent question.
7. **Performance Report:** Synthesizes an overall interview score, competency breakdown, answer-grounded strengths/weaknesses, prioritized preparation gaps, question-by-question feedback, and a readiness coaching estimate.

---

## Technical Architecture & Stack

```
forma-interview-accelerator/
├── app.py                   # FastAPI application, multi-model LLM abstraction, audio transcription
├── requirements.txt         # Production Python dependencies
├── render.yaml              # Render web service deployment configuration
├── tests/
│   └── test_flow.py         # Deterministic API and flow tests
├── test_e2e_live.py         # Optional live-provider end-to-end exercise
├── demo/
│   └── forma-demo.mp4       # Recorded evaluator walkthrough
├── static/
│   ├── index.html           # Semantic, accessible HTML5 dashboard & interview room
│   ├── styles.css           # Modern custom CSS design system, animations, print stylesheet
│   └── app.js               # Client state, Web Speech STT/TTS, MediaRecorder fallback, UI rendering
├── ASSIGNMENT_CHECKLIST.md  # 42-point requirement traceability matrix
├── DEMO_SCRIPT.md           # 3-5 minute demonstration walkthrough script
└── README.md                # Technical documentation & architecture reference
```

- **Backend:** Python 3.11+, FastAPI, Pydantic v2 schemas, httpx async client.
- **Frontend:** Vanilla HTML5 / Modern CSS / Vanilla JavaScript. Zero build step, fast loading, responsive on mobile and desktop.
- **AI Providers:** Provider abstraction supporting:
  - **Google Gemini:** `gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-1.5-flash`, `gemini-1.5-pro` with automatic model fallback.
  - **OpenAI:** `gpt-4o-mini`, `gpt-4o` with structured JSON mode.
- **Voice Stack:**
  - **Text-to-Speech (TTS):** Browser `SpeechSynthesis` with rate tuning, animated speaking state, play, replay, and stop.
  - **Speech-to-Text (STT):** Primary: Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`).
  - **Cloud Transcription Fallback:** In-browser `MediaRecorder` captures audio bytes and uploads to `/api/transcribe` powered by Gemini multimodal audio analysis or Whisper.
- **State Management:** Interview sessions are held in server-process memory and cleared when the service restarts.

---

## AI & Scoring Methodologies

### 1. Job Fit Scoring Engine
Forma avoids asking the LLM for a hallucinated percentage. Instead, the server mathematically computes the weighted aggregate of six conservative evidence dimensions:

$$\text{Job Fit Score} = \sum_{i=1}^{6} (\text{Dimension Score}_i \times \text{Weight}_i)$$

| Dimension | Weight | Criteria |
|---|---|---|
| **Required Skills Match** | 30% | Explicit match between core job requirements and resume skills |
| **Technical Competency Match** | 25% | Demonstrated depth in architecture, APIs, and systems |
| **Experience Match** | 15% | Years of relevant experience and seniority alignment |
| **Project Relevance** | 15% | Direct relevance of past projects to target responsibilities |
| **Behavioural Match** | 10% | Evidence of ownership, collaboration, and problem decomposition |
| **Qualification Match** | 5% | Degrees, certifications, and educational background |

Each dimension is categorized as:
- **Strong Match:** $\ge 75\%$
- **Partial Match:** $50\% - 74\%$
- **Missing / Weak:** $< 50\%$

### 2. Adaptive Interview Engine & 3 Levels
Rather than iterating over a static list of questions, Forma prompts the LLM with:
- Target Job Description context
- Candidate Resume evidence & claims to probe
- Last question asked
- Verbatim candidate answer
- Interview history & accumulated strengths/weaknesses
- Target stage level

The prompt strictly directs the model to:
1. Quote or reference a concrete claim from the candidate's last answer.
2. Probe vague claims (e.g. asking for baseline metrics, tooling, and trade-offs).
3. Increase technical depth if the answer was strong, or scaffold fundamentals if the candidate struggled.

**Stage Transitions:**
- **Turns 1–3 (Level 1: Screening):** Explores project ownership, resume claims, and motivation.
- **Turns 4–6 (Level 2: Competency):** Probes system design, technical depth, and practical trade-offs.
- **Turns 7+ (Level 3: Deep-Dive):** Tests edge cases, failure recovery, counter-arguments, and architectural reasoning.

### 3. Interview Readiness Scoring
Interview readiness is a coaching estimate combining simulated performance with baseline profile fit:

$$\text{Readiness Score} = \text{Round}(\text{Interview Performance Average} \times 0.70 + \text{Job Fit} \times 0.30)$$

- 🟢 **Strong Candidate:** $\ge 85\%$ — coaching band for strong simulated performance and profile fit.
- 🟡 **Interview Ready:** $75\% - 84\%$ — coaching band for solid performance with areas to refine.
- 🟠 **Needs Preparation:** $60\% - 74\%$ — coaching band indicating practice gaps.
- 🔴 **Not Ready:** $< 60\%$ — coaching band indicating more targeted preparation may help.

This heuristic has not been validated as a psychometric instrument. Answer ratings depend on model judgments; inspect their evidence and feedback rather than treating a band as a hiring recommendation.

---

## API Documentation

| Method | Endpoint | Description | Payload / Response |
|---|---|---|---|
| `GET` | `/api/health` | Service health, active AI provider, model, and configured state | Returns JSON with status, provider, model, demo_mode |
| `POST` | `/api/extract` | Multipart file upload for PDF, DOCX, TXT (Max 8 MB) | Form: `file` → `{text, filename, character_count}` |
| `POST` | `/api/transcribe` | Audio file upload for cross-browser fallback | Form: `file` (audio/webm, wav) → `{text}` |
| `POST` | `/api/analyze` | Structured role analysis, candidate profile, and job fit | Body: `{jd, resume}` → `{role, candidate, fit_dimensions, job_fit}` |
| `POST` | `/api/interview/start` | Starts session & generates personalized Level 1 question | Body: `{analysis}` → `{session_id, level, turn, question, why_this_question}` |
| `POST` | `/api/interview/answer` | Evaluates answer & returns causally adapted next question | Body: `{session_id, answer}` → `{evaluation, next, level, turn}` |
| `POST` | `/api/interview/report` | Generates final performance report & preparation gap plan | Body: `{session_id}` → `{overall_score, readiness_score, competency_scores, gaps}` |

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | Yes | `gemini` | `gemini` or `openai` |
| `GEMINI_API_KEY` | If Gemini | Unset | Google AI Studio Gemini API key |
| `GEMINI_MODEL` | No | `gemini-2.5-flash` | Gemini model endpoint (`gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-1.5-flash`) |
| `OPENAI_API_KEY` | If OpenAI | Unset | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | OpenAI model endpoint (`gpt-4o-mini`, `gpt-4o`) |
| `DEMO_MODE` | No | `false` | Enables the app's explicit demo fallback behavior |
| `FRONTEND_ORIGIN` | No | `http://localhost:8000` | Permitted CORS origin |

Provider credentials are server-side only. Set the active provider key in Render's environment settings; never place a provider key in browser storage or paste one into the public repository. `/api/health` reports whether a key is configured, not whether it is valid or usable. If a provider request fails, the app keeps the practice flow usable with a local answer-grounded fallback and shows a visible notice that the response is not from a live model. Restore real LLM responses by replacing the provider key and verifying a successful live request.

---

## Local Setup & Development

```bash
# 1. Clone repository
git clone https://github.com/nishantdubey-tech/interview-accelerator.git
cd interview-accelerator

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your_key_here

# 5. Run local dev server
uvicorn app:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in Google Chrome or Microsoft Edge for the best Web Speech API voice experience.

---

## Running Automated Tests

```bash
python3 -m unittest discover -s tests
```

The 6 test cases validate:
1. Provider configuration masking.
2. Health API, file extraction, and rejection of unsupported formats.
3. Structured Job Fit calculation and dimension categorization.
4. 3-level adaptive interview progression, answer-dependent follow-up generation, and report arithmetic.
5. Cloud audio transcription fallback handling.
6. Rejection of an invalid interview session.

The separate `test_e2e_live.py` script sends sample data through the configured provider, all interview levels, transcription, and report endpoints. It can use provider quota, so it is intentionally separate from the deterministic test command. Use fictional or anonymized candidate data during evaluation.

---

## Assignment hand-in

- Live application: [interview-accelerator-44ui.onrender.com](https://interview-accelerator-44ui.onrender.com)
- Public source repository: [nishantdubey-tech/interview-accelerator](https://github.com/nishantdubey-tech/interview-accelerator)
- Guided demo: pending recording; use [DEMO_SCRIPT.md](DEMO_SCRIPT.md)
- Walkthrough script: [DEMO_SCRIPT.md](DEMO_SCRIPT.md)
- Requirement map: [ASSIGNMENT_CHECKLIST.md](ASSIGNMENT_CHECKLIST.md)

Open the app, choose a sample profile or enter a job description and resume, run analysis, inspect Job Fit, start the interview, answer by voice or text, and open the final report. The service is configured for live Gemini requests. For voice input, use Chrome or Edge and allow microphone access when prompted; questions are read with browser speech synthesis.

## Live deployment status

On October 4, 2026, `/api/health` showed a Gemini credential is configured, but a synthetic live request failed at the provider. The health endpoint confirms presence only, not validity. Until the key is replaced, the app uses its clearly labeled local fallback to keep the practice journey available. Replace `GEMINI_API_KEY` in Render's Environment settings and save/redeploy; then run a fresh analysis and complete an interview/report to verify live LLM access. Render's free instance may spin down after inactivity. The public Render service is connected to this repository, and `render.yaml` documents settings for a new service.

## Evaluation methodology

The deterministic suite checks API validation, the weighted Job Fit calculation, answer-conditioned follow-ups and three-stage transitions, report arithmetic, transcription fallback handling, and invalid sessions. Run `python3 -m unittest discover -s tests`. The optional live pipeline script exercises a seven-answer session with the configured provider. During the walkthrough, verify that a follow-up responds to the immediately preceding answer, the speech transcript is editable, and report strengths/gaps match submitted answers. This is example-based functional evaluation; there is no held-out benchmark, inter-rater study, or validated model-judgment calibration set yet.

## Privacy and limitations

The app sends job descriptions, resumes, answers, and audio sent to the transcription endpoint to the configured model provider. Sessions are held in process memory and disappear after restart; there is no account system or persistence layer. The optional Bring Your Own Key feature stores its key in browser `localStorage`. Do not use confidential candidate data on the public demo. For a production service, add explicit retention/deletion controls, authentication, rate limits, session expiry, monitoring, and a calibrated evaluation dataset.
