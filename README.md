# Forma — Interview Accelerator

A voice-enabled interview practice product that analyzes a job description and resume, calculates a transparent evidence-weighted job fit, conducts three stages of personalized practice, evaluates spoken or typed answers, and builds a preparation and readiness report.

## Problem and product

Candidates often prepare from generic question lists that do not reflect the job or their own experience. Forma compares the role brief with the candidate's supplied profile, finds evidence and gaps, then uses that context and the candidate's actual previous answers to run an adaptive interview.

## Features and journey

1. Paste a job description and resume, or upload PDF, DOCX, or TXT files (8 MB maximum).
2. Extract structured role and candidate analysis using the configured LLM.
3. Compute an evidence-weighted job fit score with per-dimension evidence and gaps.
4. Start a candidate-specific screening question; questions use resume projects, skills, achievements, and role requirements.
5. Speak an answer using browser speech recognition or type it. Speech transcripts remain editable before submission.
6. Evaluate each answer and generate a next question prompted with the exact prior question, exact answer, profile, prior evaluations, strengths, weaknesses, and covered topics. The UI explains why the follow-up was selected.
7. Move through screening, competency, and deep-dive stages (stage advances after every three submitted answers). The question remains answer-conditioned at every stage.
8. Hear questions with browser speech synthesis, replay or stop speech, then generate the final performance/readiness report and preparation plan.

Voice recognition depends on browser support and microphone permission (Chrome/Edge are the best-supported targets). Text entry is always available. Speech synthesis uses the browser's installed voice. This app does not upload audio or claim a cloud transcription fallback.

## Architecture and stack

- Python 3.11+, FastAPI, Pydantic validation, httpx provider clients, pypdf and python-docx parsing.
- Responsive HTML/CSS/vanilla JavaScript client served by FastAPI; no frontend build step.
- Gemini or OpenAI selected by environment. Keys stay server-side. Structured JSON output is parsed and basic structure is validated before use.
- Interview session and answers live in server process memory. Restarting/redeploying the service clears sessions. Add PostgreSQL/Supabase before multi-instance production use.
- Browser Web Speech API handles speech-to-text and speech synthesis. Interview question content and evaluations come from the configured live LLM. Missing credentials produce a clear service error; there is no fake AI demo path.

### AI and scoring methodology

Role and candidate analysis are generated together in a structured schema. The prompt requires the model to distinguish evidence from inference and only use supplied text. Job fit is not requested as a percentage: the server computes the weighted average of six model-assessed evidence dimensions: required skills (30%), technical competencies (25%), experience (15%), project relevance (15%), behavioral match (10%), and qualifications (5%). Scores are clamped to 0–100 and weights are normalized. The UI displays the dimensions, evidence/gaps, and the calculated aggregate. Fit describes profile alignment, not hiring odds.

For each answer the interviewer returns an answer score and evidence, strengths, improvements, follow-up rationale, and difficulty. The report requests competency results, strengths, weaknesses, preparation gaps, and next steps from the recorded answers. The server calculates overall interview score as the mean of answer scores, and readiness = interview answer average × 70% + job fit × 30%. These are coaching estimates, not a validated psychometric assessment.

### Adaptive interview and levels

The next-question request contains the last question and candidate answer verbatim, plus the role, candidate evidence, job fit, recent interview turns, accumulated strengths/weaknesses, and competency topics. The prompt directs the LLM to ask for clarification when an answer is vague, increase depth after a strong answer, and scaffold fundamentals after a weak answer. It explicitly requires the next question to refer to a concrete detail in the answer; this makes the content adaptive rather than a fixed question array. Level transitions are deterministic after answers 3 and 6 to ensure all three stages are visible; question content remains model-generated and answer-aware. This is a prompt-driven system and should be evaluated with representative profiles before high-stakes use.

### API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Service, selected provider, key-configured state |
| POST | `/api/extract` | Multipart file extraction and validation |
| POST | `/api/analyze` | Structured role/candidate analysis and computed job fit |
| POST | `/api/interview/start` | Create in-memory session and personalized first question |
| POST | `/api/interview/answer` | Evaluate answer and return adaptive next question |
| POST | `/api/interview/report` | Final performance and preparation report |

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add GEMINI_API_KEY or OPENAI_API_KEY to .env; keep this file private.
uvicorn app:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000). Choose one provider:

- Gemini: `LLM_PROVIDER=gemini`, `GEMINI_API_KEY`, optionally `GEMINI_MODEL` (default `gemini-3.8-flash`, currently listed by Google's docs as generally available).
- OpenAI: `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, optionally `OPENAI_MODEL` (default `gpt-4o-mini`).
- `FRONTEND_ORIGIN` sets the permitted browser origin. `DEMO_MODE` is reported by health but no mock AI implementation is provided.

The service makes outbound HTTPS calls to the selected provider. Errors and quota failures are surfaced as user-facing retry guidance without returning provider response bodies or credentials. Do not put keys in browser JavaScript.

## Deployment

`render.yaml` prepares a single-service Render deployment that serves both the API and client. Set `GEMINI_API_KEY` (or modify provider environment variables for OpenAI) in the Render service secret settings before using AI features. Configure `FRONTEND_ORIGIN` to the public app origin if serving the frontend separately. A GitHub repository has been created at https://github.com/nishantdubey-tech/interview-accelerator and the current source is pushed to `main`. The repository is private. A live application has not been deployed from this workspace. Deployment requires a hosting account and provider API key.

For production beyond a single-instance demo, add persistent database storage, request-level auth/rate limits, server-side session expiration, observability, and a separate transcription service if cross-browser voice support is required. Candidate resume content is sensitive: obtain consent and define retention/deletion policy before public launch.

## Verification

Automated tests are not included yet. Use `GET /api/health`, then walk the full path with a valid API key: upload/paste both inputs → analyze → review weighted fit dimensions → start interview → submit distinct spoken/typed answers → verify questions reference details from the immediately preceding answer → complete at least seven answers to see all three levels → generate report. Test missing key, malformed inputs, rejected file types, oversized files, and denied microphone permissions. Browser voice capability varies by browser and operating system. Do not interpret unrun checks as passes.

## Assignment checklist

See [ASSIGNMENT_CHECKLIST.md](ASSIGNMENT_CHECKLIST.md) for requirement locations, status, and manual verification steps. See [DEMO_SCRIPT.md](DEMO_SCRIPT.md) for the 3–5 minute recording script.

## Known limitations

- Single-process in-memory sessions are lost on restart and are not suitable for multiple app instances.
- Browser speech recognition coverage is uneven; unsupported browsers require text fallback. No audio-file transcription provider is included.
- This environment did not provide deployment credentials or a GitHub repository connection, so no live URL, repository, or demo video can be claimed.
- The generated readiness score and answer evaluation are LLM-based coaching estimates, not validated hiring instruments.
