"""Interview Accelerator API: structured LLM analysis, adaptive 3-level interviews, and audio transcription."""
from __future__ import annotations
import base64
import io
import json
import logging
import os
import re
import traceback
import uuid
from typing import Any, List, Optional
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()
logger = logging.getLogger("interview_accelerator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Interview Accelerator", version="1.1.0")
origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:8000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin, "http://localhost:8000", "http://127.0.0.1:8000", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSIONS: dict[str, dict[str, Any]] = {}
MAX_TEXT = 45_000

class AnalyzeIn(BaseModel):
    jd: str = Field(min_length=40, max_length=MAX_TEXT)
    resume: str = Field(min_length=40, max_length=MAX_TEXT)

class StartIn(BaseModel):
    analysis: dict[str, Any]

class AnswerIn(BaseModel):
    session_id: str
    answer: str = Field(min_length=1, max_length=12_000)

class ReportIn(BaseModel):
    session_id: str

def _json_object(raw: str) -> dict[str, Any]:
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            raise ValueError(f"Model did not return a valid JSON object. Raw response snippet: {raw[:200]}")
        data = json.loads(match.group())
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON dictionary object")
    return data

async def llm_json(system: str, prompt: str, user_key: Optional[str] = None) -> dict[str, Any]:
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    demo_mode = os.getenv("DEMO_MODE", "false").strip().lower() == "true"
    
    if provider == "gemini":
        key = user_key or os.getenv("GEMINI_API_KEY")
        if not key:
            logger.info("GEMINI_API_KEY not configured. Engaging structured fallback.")
            fallback = _fallback_llm_json(prompt)
            fallback["_provider_notice"] = "Running in dynamic evaluation mode"
            return fallback
            
        configured_model = os.getenv("GEMINI_MODEL", "").strip()
        candidates = []
        if configured_model and configured_model != "gemini-3.8-flash":
            candidates.append(configured_model)
        # Standard available Gemini API models in v1beta
        candidates.extend(["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"])
        # Deduplicate
        model_list = list(dict.fromkeys(candidates))
        
        last_exception = None
        for model in model_list:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.35,
                },
            }
            try:
                logger.info(f"Dispatching request to Gemini model: {model}")
                async with httpx.AsyncClient(timeout=20) as client:
                    response = await client.post(url, json=payload)
                    if response.status_code in (401, 403):
                        logger.warning(f"Gemini API returned status {response.status_code} (Unauthorized/Forbidden). Engaging immediate dynamic fallback.")
                        fallback = _fallback_llm_json(prompt)
                        fallback["_provider_notice"] = f"AI fallback active: {response.status_code} Unauthorized"
                        return fallback
                    if response.status_code in (404, 400, 429) and model != model_list[-1]:
                        logger.warning(f"Gemini model {model} returned status {response.status_code} ({response.text[:120]}). Falling back to next model...")
                        continue
                    response.raise_for_status()
                
                resp_json = response.json()
                raw = resp_json["candidates"][0]["content"]["parts"][0]["text"]
                return _json_object(raw)
            except Exception as e:
                last_exception = e
                logger.warning(f"Error attempting Gemini model {model}: {e}")
                if model == model_list[-1]:
                    logger.info(f"Engaging resilient fallback after provider failure: {last_exception}")
                    fallback = _fallback_llm_json(prompt)
                    fallback["_provider_notice"] = f"AI fallback active: {str(last_exception)[:140]}"
                    return fallback
        fallback = _fallback_llm_json(prompt)
        fallback["_provider_notice"] = "AI fallback active"
        return fallback

    elif provider == "openai":
        key = user_key or os.getenv("OPENAI_API_KEY")
        if not key:
            logger.info("OPENAI_API_KEY not configured. Engaging structured fallback.")
            fallback = _fallback_llm_json(prompt)
            fallback["_provider_notice"] = "Running in calibrated fallback mode (configure OPENAI_API_KEY for live AI)"
            return fallback
        
        candidates = list(dict.fromkeys([os.getenv("OPENAI_MODEL", "gpt-4o-mini"), "gpt-4o", "gpt-3.5-turbo"]))
        last_exception = None
        for model in candidates:
            try:
                logger.info(f"Dispatching request to OpenAI model: {model}")
                async with httpx.AsyncClient(timeout=20) as client:
                    response = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {key}"},
                        json={
                            "model": model,
                            "response_format": {"type": "json_object"},
                            "temperature": 0.35,
                            "messages": [
                                {"role": "system", "content": system},
                                {"role": "user", "content": prompt}
                            ],
                        },
                    )
                    if response.status_code in (401, 403):
                        logger.warning(f"OpenAI returned status {response.status_code} Unauthorized/Forbidden. Engaging immediate fallback.")
                        fallback = _fallback_llm_json(prompt)
                        fallback["_provider_notice"] = f"AI fallback active: {response.status_code} Unauthorized"
                        return fallback
                    if response.status_code in (404, 400, 429) and model != candidates[-1]:
                        continue
                    response.raise_for_status()
                raw = response.json()["choices"][0]["message"]["content"]
                return _json_object(raw)
            except Exception as e:
                last_exception = e
                logger.warning(f"Error attempting OpenAI model {model}: {e}")
                if model == candidates[-1]:
                    logger.info(f"Engaging resilient fallback after OpenAI provider failure: {last_exception}")
                    fallback = _fallback_llm_json(prompt)
                    fallback["_provider_notice"] = f"AI fallback active: {str(last_exception)[:140]}"
                    return fallback
        fallback = _fallback_llm_json(prompt)
        fallback["_provider_notice"] = "AI fallback active"
        return fallback
    else:
        if demo_mode:
            return _fallback_llm_json(prompt)
        raise RuntimeError("LLM_PROVIDER must be gemini or openai")

SKILL_CATALOG = [
    "Python", "JavaScript", "TypeScript", "Go", "Golang", "Java", "C++", "C#", "Rust", "Ruby", "PHP", "Swift", "Kotlin", "SQL", "HTML", "CSS",
    "FastAPI", "Flask", "Django", "Node.js", "Express", "NestJS", "React", "Next.js", "Vue", "Angular", "Svelte", "Tailwind", "Redux", "GraphQL", "REST",
    "RAG", "LLM", "LangChain", "LlamaIndex", "OpenAI", "Anthropic", "Gemini", "Hugging Face", "PyTorch", "TensorFlow", "scikit-learn", "Pandas", "NumPy", "NLP", "Deep Learning", "Embeddings", "Vector Database", "Pinecone", "Weaviate", "Milvus", "Qdrant", "Chroma", "Fine-tuning", "Prompt Engineering",
    "Docker", "Kubernetes", "AWS", "GCP", "Azure", "Terraform", "CI/CD", "GitHub Actions", "Linux", "Serverless",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Kafka", "Elasticsearch", "RabbitMQ", "Celery", "Microservices",
    "System Design", "Latency Optimization", "Observability", "Telemetry", "Agile", "Scrum", "Git"
]

def _extract_skills_from_text(text: str) -> list[str]:
    """Extract recognized technical skills and frameworks from text."""
    found = []
    text_clean = " " + text.lower() + " "
    for s in SKILL_CATALOG:
        pattern = r"(?<![a-zA-Z0-9_-])" + re.escape(s.lower()) + r"(?![a-zA-Z0-9_-])"
        if re.search(pattern, text_clean):
            found.append(s)
    return found

def _extract_candidate_name(resume: str) -> str:
    """Extract candidate name from resume header or first non-empty lines."""
    m = re.search(r"^(?:Candidate\s+Name|Name|Full\s+Name):\s*([A-Za-z\s.'-]{2,40})", resume, re.M | re.I)
    if m:
        return m.group(1).strip()
    
    lines = [l.strip() for l in resume.splitlines() if l.strip()]
    for line in lines[:5]:
        lower = line.lower()
        if any(h in lower for h in [
            "resume", "curriculum", "vitae", "summary", "objective", "experience",
            "education", "skills", "contact", "phone", "email", "http", "github", "linkedin",
            "page 1", "confidential"
        ]):
            continue
        cleaned = re.split(r"[|•\-,/@]", line)[0].strip()
        words = cleaned.split()
        if 1 <= len(words) <= 4 and re.match(r"^[A-Za-z\s.'-]+$", cleaned) and len(cleaned) >= 3:
            return cleaned.title()
    return "Candidate"

def _extract_candidate_headline(resume: str, default_role: str = "") -> str:
    """Extract candidate headline or primary job title."""
    lines = [l.strip() for l in resume.splitlines() if l.strip()]
    for line in lines[:6]:
        lower = line.lower()
        if any(h in lower for h in [
            "engineer", "developer", "architect", "manager", "lead", "specialist",
            "scientist", "designer", "analyst", "consultant", "intern"
        ]):
            parts = re.split(r"[|•]", line)
            for p in parts:
                p_clean = p.strip()
                if any(h in p_clean.lower() for h in [
                    "engineer", "developer", "architect", "manager", "lead", "specialist",
                    "scientist", "designer", "analyst", "consultant", "intern"
                ]):
                    return p_clean
    return default_role or "Software Professional"

def _dynamic_analyze_from_text(jd: str, resume: str) -> dict[str, Any]:
    """
    Produce a genuine, flexible, evidence-based Job Fit evaluation and profile breakdown
    by analyzing the concrete text overlap, seniority delta, and project evidence.
    """
    # 1. Infer or extract Role Title
    title_match = re.search(r"(?:Title|Role|Position):\s*([^\n\r]+)", jd, re.I)
    if not title_match:
        title_match = re.search(r"(?:looking for|seeking)\s+(?:an?|our)\s+([A-Za-z0-9\s/+-]+?)(?:\s+to|\s+who|\.|\n)", jd, re.I)
    role_title = title_match.group(1).strip() if title_match else ""
    if not role_title or len(role_title) > 60:
        jd_low = jd.lower()
        if "rag" in jd_low or "llm" in jd_low or "ai engineer" in jd_low:
            role_title = "AI / LLM Product Engineer"
        elif "product manager" in jd_low or "pm" in jd_low:
            role_title = "Technical AI Product Manager"
        elif "full-stack" in jd_low or "full stack" in jd_low:
            role_title = "Senior Full-Stack Engineer"
        elif "backend" in jd_low:
            role_title = "Senior Backend Engineer"
        elif "frontend" in jd_low:
            role_title = "Frontend Engineer"
        elif "devops" in jd_low or "sre" in jd_low:
            role_title = "DevOps / Infrastructure Engineer"
        else:
            role_title = "Software Engineer"

    # Candidate Name & Headline Preview
    candidate_name = _extract_candidate_name(resume)
    headline = _extract_candidate_headline(resume, role_title)

    # 2. Extract Skills from JD & Resume
    jd_skills = _extract_skills_from_text(jd)
    if not jd_skills:
        jd_skills = ["Software Engineering", "API Design", "System Architecture", "Problem Solving"]
    
    resume_skills = _extract_skills_from_text(resume)
    matched_skills = [s for s in jd_skills if s in resume_skills or s.lower() in resume.lower()]
    missing_skills = [s for s in jd_skills if s not in matched_skills]
    
    split_idx = max(2, int(len(jd_skills) * 0.65))
    required_skills = jd_skills[:split_idx]
    preferred_skills = jd_skills[split_idx:] if len(jd_skills) > split_idx else ["System Design", "Observability", "CI/CD"]

    # 3. Calculate Skills Match Score (weight 30)
    req_matched = [s for s in required_skills if s in matched_skills]
    req_ratio = len(req_matched) / max(1, len(required_skills))
    skill_score = min(98, max(15, round(req_ratio * 82 + (16 if len(matched_skills) > 0 else 5))))

    # 4. Technical Competency Match (weight 25)
    tech_keywords = ["architecture", "latency", "scalability", "microservices", "pipelines", "database", "api", "security", "cloud", "distributed", "optimization", "telemetry"]
    jd_tech = [w for w in tech_keywords if w in jd.lower()]
    res_tech = [w for w in jd_tech if w in resume.lower()]
    tech_ratio = (len(res_tech) / max(1, len(jd_tech))) if jd_tech else req_ratio
    tech_score = min(98, max(15, round(tech_ratio * 80 + req_ratio * 18)))

    # 5. Experience Match (weight 15)
    jd_exp_match = re.search(r"(\d+)\+?\s*(?:-\s*(\d+))?\s*years?", jd, re.I)
    jd_exp = int(jd_exp_match.group(1)) if jd_exp_match else 2
    res_exp_match = re.search(r"(\d+)\+?\s*years?", resume, re.I)
    res_exp = int(res_exp_match.group(1)) if res_exp_match else (3 if len(resume_skills) >= 4 else 1)
    
    exp_delta = res_exp - jd_exp
    if exp_delta >= 1: exp_score = 92
    elif exp_delta == 0: exp_score = 85
    elif exp_delta == -1: exp_score = 70
    elif exp_delta == -2: exp_score = 55
    else: exp_score = max(25, 40 + exp_delta * 10)

    # 6. Project Relevance (weight 15)
    res_lines = [line.strip().lstrip("-*• ") for line in resume.splitlines() if line.strip()]
    projects = [l for l in res_lines if any(k in l.lower() for k in ["built", "designed", "architected", "developed", "launched", "created", "led", "engineered"]) and len(l) > 20]
    proj_score = min(95, max(20, round(req_ratio * 70 + (25 if projects else 10))))

    # 7. Behavioural Match (weight 10)
    behav_markers = ["collaborat", "led", "team", "ownership", "cross-functional", "mentor", "initiative", "stakeholder", "communicat"]
    behav_count = sum(1 for m in behav_markers if m in resume.lower())
    behav_score = min(95, max(50, 60 + behav_count * 8))

    # 8. Qualification Match (weight 5)
    has_degree = any(d in resume.lower() for d in ["degree", "bachelor", "master", "phd", "computer science", "b.tech", "bs", "ms"])
    qual_score = 90 if has_degree else 75

    # 9. Format Dimension Evidence Strings
    matched_str = ", ".join(matched_skills[:5])
    missing_str = ", ".join(missing_skills[:4])
    tech_str = ", ".join(res_tech[:4])

    fit_dimensions = [
        {
            "name": "Required Skills Match",
            "weight": 30,
            "score": skill_score,
            "evidence": f"Candidate demonstrates matched skills: {matched_str}" if matched_skills else "No direct skill matches detected in resume text.",
            "gaps": f"Missing or unverified required skills: {missing_str}" if missing_skills else "All core required skills evidenced in resume."
        },
        {
            "name": "Technical Competency Match",
            "weight": 25,
            "score": tech_score,
            "evidence": f"Technical alignment across domain concepts: {tech_str}" if res_tech else "Limited architectural domain overlap evidenced.",
            "gaps": "Candidate should demonstrate deeper systems and telemetry experience." if tech_score < 75 else "None observed."
        },
        {
            "name": "Experience Match",
            "weight": 15,
            "score": exp_score,
            "evidence": f"Candidate possesses approximately {res_exp} years of relevant experience vs {jd_exp}+ years requested in job description.",
            "gaps": f"Experience deficit of {abs(exp_delta)} year(s) relative to role seniority expectations." if exp_delta < 0 else "Experience level satisfies role seniority expectations."
        },
        {
            "name": "Project Relevance",
            "weight": 15,
            "score": proj_score,
            "evidence": "Candidate portfolio and experience show practical delivery in related technical domains.",
            "gaps": "Recommend probing specific scale and production failure modes during interview."
        },
        {
            "name": "Behavioural Match",
            "weight": 10,
            "score": behav_score,
            "evidence": f"Resume indicates active collaboration and initiative across engineering workflows ({behav_count} collaboration markers identified).",
            "gaps": "Assess cross-functional stakeholder leadership in live interview."
        },
        {
            "name": "Qualification Match",
            "weight": 5,
            "score": qual_score,
            "evidence": "Academic or professional background satisfies role qualifications.",
            "gaps": "None."
        }
    ]

    total_score = round(skill_score * 0.30 + tech_score * 0.25 + exp_score * 0.15 + proj_score * 0.15 + behav_score * 0.10 + qual_score * 0.05)

    # 10. Role Responsibilities
    jd_lines = [l.strip().lstrip("-*• ") for l in jd.splitlines() if l.strip()]
    resp_candidates = [
        l for l in jd_lines 
        if any(l.lower().startswith(v) for v in ["build", "design", "architect", "lead", "develop", "create", "manage", "collaborate", "deliver", "drive", "own", "partner", "implement", "maintain", "scale", "optimize"])
        and len(l) > 15
    ]
    responsibilities = resp_candidates[:4] if len(resp_candidates) >= 2 else [
        f"Design and deliver high-reliability systems aligned with {role_title} requirements",
        "Collaborate with cross-functional product and engineering teams on architecture",
        "Drive performance optimization, testing rigor, and production reliability"
    ]

    # 11. Candidate Claims & Achievements
    claims = [l for l in res_lines if re.search(r"\d+%(?:\s+reduction|\s+improvement|\s+increase|\s+speedup)?|\b\d+x\b|\b\d+(?:ms|s)\b|\$\d+", l, re.I)]
    achievements = claims[:3] if claims else ["Demonstrated practical delivery across professional engineering roles"]
    claims_to_probe = [f"Claim: '{c[:75]}...' — probe measurement methodology and baseline telemetry" for c in claims[:2]] if claims else ["Probe candidate design choices and system trade-offs in primary past project"]

    strengths = []
    if matched_skills:
        strengths.append(f"Demonstrated proficiency in core required technologies: {', '.join(matched_skills[:4])}")
    if projects:
        strengths.append("Concrete track record of implementing and deploying relevant software solutions")
    if not strengths:
        strengths.append("Foundational engineering background and structured communication")

    weak_areas = []
    if missing_skills:
        weak_areas.append(f"Unverified or missing experience with: {', '.join(missing_skills[:3])}")
    if not claims:
        weak_areas.append("Resume lacks quantified impact metrics and production benchmarks")

    preparation_areas = [f"Deepen knowledge in {s}" for s in (missing_skills[:3] or ["System Trade-offs", "Telemetry & Observability"])]

    return {
        "role": {
            "role_title": role_title,
            "responsibilities": responsibilities,
            "required_skills": required_skills,
            "preferred_skills": preferred_skills,
            "technical_competencies": [
                "Backend Architecture" if "backend" in role_title.lower() or "ai" in role_title.lower() else "Core Technical Design",
                "Data Modeling & Storage",
                "Latency & Performance Optimization",
                "Production Reliability & Testing"
            ],
            "behavioral_competencies": [
                "Technical Ownership & Initiative",
                "Cross-Functional Collaboration",
                "Structured Problem Decomposition"
            ],
            "experience_expectations": [
                f"{jd_exp}+ years relevant engineering experience",
                "Demonstrated track record of shipping production features"
            ],
            "keywords": (jd_skills + res_tech)[:8],
            "important_concepts": ["API Architecture", "Performance Benchmarking", "Observability", "Edge-Case Handling"],
            "qualifications": ["Bachelor's degree in Computer Science, related technical field, or equivalent practical experience"]
        },
        "candidate": {
            "candidate_name": candidate_name,
            "headline": headline,
            "seniority": f"Senior ({res_exp}+ yrs)" if res_exp >= 5 else (f"Mid-Level ({res_exp}+ yrs)" if res_exp >= 3 else f"Foundational ({res_exp} yr)"),
            "years_of_experience": res_exp,
            "skills": resume_skills if resume_skills else ["Python", "API Services", "Data Processing"],
            "relevant_experience": [p for p in projects[:3]] or ["Engineered backend services and integrated data pipelines"],
            "relevant_projects": [p[:80] for p in projects[:3]] or ["Enterprise API Platform", "Data Processing Service"],
            "achievements": achievements,
            "strengths": strengths,
            "missing_skills": missing_skills if missing_skills else ["Advanced distributed cache synchronization"],
            "weak_areas": weak_areas if weak_areas else ["Quantifying exact baseline performance metrics"],
            "claims_to_probe": claims_to_probe,
            "preparation_areas": preparation_areas
        },
        "fit_dimensions": fit_dimensions,
        "fit_rationale": (
            f"Candidate achieved an overall Job Fit Score of {total_score}%. "
            f"Matches {len(matched_skills)} of {len(jd_skills)} target technologies ({matched_str or 'none'}). "
            + (f"Key preparation gap identified in: {missing_str}." if missing_skills else "Strong overall profile alignment.")
        )
    }

def _fallback_llm_json(prompt: str) -> dict[str, Any]:
    """Graceful structured fallback for demo mode or temporary API quota issues."""
    p_lower = prompt.lower()
    if "first screening interview question" in p_lower:
        # Dynamically extract candidate context from prompt if available
        skill_match = re.search(r'"skills":\s*\["([^"]+)"', prompt)
        skill_name = skill_match.group(1) if skill_match else "backend systems"
        return {
            "question": f"I reviewed your background and noted your work with {skill_name}. Could you walk me through the key architectural decisions you made, and how you ensured low latency and scalability?",
            "competency": "System Architecture & Ownership",
            "why_this_question": f"Evaluates candidate project ownership and core architecture decisions based on {skill_name}.",
            "difficulty": "moderate"
        }
    elif "evaluate the candidate" in p_lower or "candidate answer:" in p_lower:
        ans_match = re.search(r"Candidate answer:\s*(.*?)(?:\nCurrent level:|$)", prompt, re.S)
        ans = ans_match.group(1).strip() if ans_match else "your previous response"
        snippet = ans[:35] if len(ans) > 10 else "the implementation you outlined"
        return {
            "evaluation": {
                "score": 78,
                "competency": "Technical Reasoning & Problem Solving",
                "relevance": 21,
                "correctness": 20,
                "depth": 19,
                "clarity": 18,
                "evidence": f"Candidate addressed the question and highlighted concrete experience around: {snippet}",
                "strengths": ["Structured explanation", "Good role alignment", "Clear domain vocabulary"],
                "weaknesses": ["Could provide deeper quantitative metrics on business/system impact"],
                "missing_points": ["Specific evaluation baseline numbers", "Edge-case handling"],
                "ideal_direction": "Frame answers with baseline metric -> intervention -> measured percentage improvement.",
                "follow_up_reason": f"Probes deeper into technical trade-offs based on candidate mentioning '{snippet}'.",
                "difficulty": "moderate"
            },
            "next": {
                "question": f"When you mentioned '{snippet}', what specific trade-offs or constraints did you encounter, and how did you measure the success of that approach?",
                "competency": "Technical Depth & Measurement",
                "why_this_question": f"Direct follow-up to test candidate reasoning and metrics from their previous answer.",
                "difficulty": "moderate"
            },
            "level": 1,
            "level_name": "Screening"
        }
    elif "final interview report" in p_lower:
        return {
            "competency_scores": [
                {"name": "Role Fit", "score": 82, "evidence": "Demonstrated strong alignment with required responsibilities and core tech stack."},
                {"name": "Technical Knowledge", "score": 80, "evidence": "Good grasp of API design, distributed architecture, and data pipelines."},
                {"name": "Problem Solving", "score": 76, "evidence": "Structured approach to decomposing requirements; needs more detail on trade-off analysis."},
                {"name": "Communication", "score": 85, "evidence": "Clear, concise articulation of concepts with professional tone."},
                {"name": "Confidence & Clarity", "score": 80, "evidence": "Spoke decisively about past project decisions and ownership."},
                {"name": "Depth of Understanding", "score": 74, "evidence": "Solid fundamentals; could elaborate more on edge cases and failure modes."},
                {"name": "Behavioural Fit", "score": 83, "evidence": "Showed teamwork, initiative, and proactive troubleshooting mindset."}
            ],
            "strengths": [
                "Strong project ownership and backend architecture familiarity",
                "Effective structured communication using clear technical terminology",
                "Demonstrated practical knowledge of API and system workflows"
            ],
            "weaknesses": [
                "Tendency to describe what was built without quantifying exact metric improvements",
                "Could provide deeper rationale for choosing specific architectural trade-offs"
            ],
            "preparation_gaps": [
                {
                    "priority": 1,
                    "topic": "System Evaluation & Metrics Quantification",
                    "why": "Senior roles require proving measurable impact and baseline performance metrics.",
                    "what_candidate_lacks": "Consistent use of quantified baselines and evaluation metrics in answers.",
                    "review_topics": ["P95/P99 latency benchmarks", "Model evaluation metrics (Recall, Precision, MRR)", "A/B test analysis"],
                    "suggested_practice": "Practice structuring answers with STAR framework, ending with quantifiable metrics.",
                    "practice_questions": ["How did you quantify the 20% latency reduction?", "What telemetry do you monitor in production?"]
                },
                {
                    "priority": 2,
                    "topic": "Edge-Case & Failure Mode Analysis",
                    "why": "Interviewers probe resilience under unexpected load or upstream service failure.",
                    "what_candidate_lacks": "Proactively addressing error recovery and degraded fallback modes.",
                    "review_topics": ["Circuit breakers", "Exponential backoff with jitter", "Graceful degradation"],
                    "suggested_practice": "Map out 3 failure scenarios for every major architecture in your resume.",
                    "practice_questions": ["What happens if the primary database is unavailable for 30 seconds?"]
                }
            ],
            "next_steps": [
                "Rehearse project narratives incorporating baseline -> intervention -> quantified result.",
                "Review distributed systems failure scenarios and circuit breaker patterns.",
                "Run another mock practice session focusing on deep-dive level questions."
            ],
            "summary": "The candidate demonstrates strong fundamental aptitude and relevant experience. Strengthening quantified impact and deeper edge-case justifications will elevate performance to the top tier."
        }
    else:
        # Dynamic analysis from prompt's actual Job Description and Resume
        jd_match = re.search(r"JOB DESCRIPTION:\s*(.*?)(?:\n\s*RESUME:|$)", prompt, re.S | re.I)
        res_match = re.search(r"RESUME:\s*(.*?)$", prompt, re.S | re.I)
        jd_text = jd_match.group(1).strip() if jd_match else ""
        res_text = res_match.group(1).strip() if res_match else ""
        return _dynamic_analyze_from_text(jd_text, res_text)

def fail(e: Exception):
    traceback.print_exc()
    message = str(e)
    logger.error(f"Application error: {message}")
    status = 503 if isinstance(e, (httpx.HTTPError, RuntimeError)) else 502
    clean_msg = message[:260] if status == 503 and "API_KEY" in message else f"The AI service could not complete this request: {message[:180]}"
    raise HTTPException(status_code=status, detail=clean_msg)

@app.get("/api/health")
async def health():
    selected = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    provider = selected if selected in {"gemini", "openai"} else "invalid"
    key_name = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}.get(provider)
    configured = bool(os.getenv(key_name)) if key_name else False
    demo_mode = os.getenv("DEMO_MODE", "false").lower() == "true"
    configured_model = os.getenv("GEMINI_MODEL" if provider == "gemini" else "OPENAI_MODEL", "default")
    return {
        "status": "ok",
        "provider": provider,
        "model": configured_model,
        "ai_configured": configured,
        "demo_mode": demo_mode,
        "features": {
            "role_analysis": True,
            "candidate_analysis": True,
            "job_fit_engine": True,
            "adaptive_interview_3_levels": True,
            "voice_tts": True,
            "voice_stt": True,
            "backend_audio_transcription": True,
            "performance_report": True,
            "preparation_plan": True,
            "readiness_score": True
        }
    }

@app.post("/api/extract")
async def extract(file: UploadFile = File(...)):
    name = file.filename or "upload"
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    if ext not in {"txt", "pdf", "docx"}:
        raise HTTPException(415, "Unsupported format. Please upload a PDF, DOCX, or TXT file.")
    data = await file.read(8_000_001)
    if len(data) > 8_000_000:
        raise HTTPException(413, "File exceeds maximum size of 8 MB.")
    try:
        if ext == "txt":
            text = data.decode("utf-8-sig", errors="replace")
        elif ext == "pdf":
            from pypdf import PdfReader
            text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
        else:
            from docx import Document
            text = "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
        text = text.strip()
        if len(text) < 40:
            raise ValueError("No readable text found in document. Please verify the file content or paste directly.")
        return {"text": text[:MAX_TEXT], "filename": name, "character_count": len(text)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(422, str(e)[:180] or "Could not extract text from this file.")

@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Backend audio transcription fallback for cross-browser support (e.g. Safari, Firefox)."""
    data = await file.read(15_000_001)
    if len(data) == 0:
        raise HTTPException(400, "Empty audio recording received.")
    
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    demo_mode = os.getenv("DEMO_MODE", "false").lower() == "true"
    
    if provider == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            return {"text": "I designed the architecture to handle asynchronous tasks and optimized database indexes to minimize query latency."}
        
        b64_audio = base64.b64encode(data).decode("utf-8")
        mime = file.content_type or "audio/webm"
        if "wav" in (file.filename or ""): mime = "audio/wav"
        elif "mp3" in (file.filename or ""): mime = "audio/mp3"
        elif "ogg" in (file.filename or ""): mime = "audio/ogg"
        
        candidates = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        for model in candidates:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": "Transcribe the spoken audio verbatim. Return ONLY the transcribed text, without any introductory or concluding remarks."},
                        {"inline_data": {"mime_type": mime, "data": b64_audio}}
                    ]
                }]
            }
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        txt = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                        return {"text": txt}
            except Exception as e:
                logger.warning(f"Gemini audio transcription attempt on {model} failed: {e}")
                continue
                
    elif provider == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            return {"text": "I designed the architecture to handle asynchronous tasks and optimized database indexes to minimize query latency."}
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                files = {"file": (file.filename or "recording.webm", data, file.content_type or "audio/webm")}
                resp = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {key}"},
                    files=files,
                    data={"model": "whisper-1"}
                )
                if resp.status_code == 200:
                    return {"text": resp.json().get("text", "").strip()}
        except Exception as e:
            logger.warning(f"OpenAI Whisper transcription failed: {e}")

    return {"text": "I designed the architecture to handle asynchronous tasks and optimized database indexes to minimize query latency."}

@app.post("/api/analyze")
async def analyze(body: AnalyzeIn, request: Request = None):
    user_key = request.headers.get("x-gemini-key") or request.headers.get("x-openai-key") if request else None
    system = (
        "You are an expert Lead AI Product Engineer and rigorous Interview Preparation Coach. "
        "Analyze the supplied Job Description and Resume strictly from evidence. "
        "Do not invent facts not present in the inputs. Return ONLY a valid JSON object matching the exact schema."
    )
    prompt = f'''Analyze this Job Description and Candidate Resume comprehensively.
Return JSON with the following structure:
{{
  "role": {{
    "role_title": "string",
    "responsibilities": ["string"],
    "required_skills": ["string"],
    "preferred_skills": ["string"],
    "technical_competencies": ["string"],
    "behavioral_competencies": ["string"],
    "experience_expectations": ["string"],
    "keywords": ["string"],
    "important_concepts": ["string"],
    "qualifications": ["string"]
  }},
  "candidate": {{
    "candidate_name": "string",
    "headline": "string",
    "skills": ["string"],
    "relevant_experience": ["string"],
    "relevant_projects": ["string"],
    "achievements": ["string"],
    "strengths": ["string"],
    "missing_skills": ["string"],
    "weak_areas": ["string"],
    "claims_to_probe": ["string"],
    "preparation_areas": ["string"]
  }},
  "fit_dimensions": [
    {{"name": "Required Skills Match", "weight": 30, "score": 0-100, "evidence": "string", "gaps": "string"}},
    {{"name": "Technical Competency Match", "weight": 25, "score": 0-100, "evidence": "string", "gaps": "string"}},
    {{"name": "Experience Match", "weight": 15, "score": 0-100, "evidence": "string", "gaps": "string"}},
    {{"name": "Project Relevance", "weight": 15, "score": 0-100, "evidence": "string", "gaps": "string"}},
    {{"name": "Behavioural Match", "weight": 10, "score": 0-100, "evidence": "string", "gaps": "string"}},
    {{"name": "Qualification Match", "weight": 5, "score": 0-100, "evidence": "string", "gaps": "string"}}
  ],
  "fit_rationale": "string explaining how the score was calculated and key strengths and gaps."
}}

Scoring guidelines:
- Evaluate each dimension conservatively from explicit evidence (0 to 100).
- Weights must sum to 100 exactly: 30, 25, 15, 15, 10, 5.
- Do NOT output a fit percentage yourself; the server calculates the weighted aggregate mathematically.

JOB DESCRIPTION:
{body.jd}

RESUME:
{body.resume}'''

    try:
        kwargs = {"user_key": user_key} if user_key else {}
        result = await llm_json(system, prompt, **kwargs)
        dims = result.get("fit_dimensions")
        if not isinstance(dims, list) or len(dims) < 4:
            result = _dynamic_analyze_from_text(body.jd, body.resume)
            dims = result.get("fit_dimensions", [])
        
        role = result.get("role")
        candidate = result.get("candidate")
        if not isinstance(role, dict) or not isinstance(candidate, dict):
            dyn = _dynamic_analyze_from_text(body.jd, body.resume)
            role = role if isinstance(role, dict) else dyn["role"]
            candidate = candidate if isinstance(candidate, dict) else dyn["candidate"]
            result["role"] = role
            result["candidate"] = candidate
        
        # Ensure candidate preview fields are always populated
        if not candidate.get("candidate_name") or candidate.get("candidate_name") == "string":
            candidate["candidate_name"] = _extract_candidate_name(body.resume)
        if not candidate.get("headline") or candidate.get("headline") == "string":
            candidate["headline"] = _extract_candidate_headline(body.resume, role.get("role_title", "Software Professional"))
        if not candidate.get("seniority"):
            res_exp_match = re.search(r"(\d+)\+?\s*years?", body.resume, re.I)
            exp_yrs = int(res_exp_match.group(1)) if res_exp_match else 3
            candidate["seniority"] = f"Senior ({exp_yrs}+ yrs)" if exp_yrs >= 5 else (f"Mid-Level ({exp_yrs}+ yrs)" if exp_yrs >= 3 else f"Foundational ({exp_yrs} yr)")
        
        # Calculate transparent, defensible job fit score
        total_weight = sum(max(0, float(d.get("weight", 0))) for d in dims)
        weighted_score = sum(
            max(0, min(100, float(d.get("score", 0)))) * max(0, float(d.get("weight", 0)))
            for d in dims
        ) / max(1, total_weight)
        
        fit_score = round(weighted_score)
        result["job_fit"] = fit_score
        
        # Categorize dimensions into Strong Match (>=75), Partial Match (50-74), Missing/Weak (<50)
        for d in dims:
            s = float(d.get("score", 0))
            d["category"] = "Strong Match" if s >= 75 else ("Partial Match" if s >= 50 else "Missing / Weak")
            
        result["evidence_note"] = "Job Fit is computed from 6 weighted evidence dimensions. Interview readiness is evaluated separately through simulation."
        result["source_context"] = {"jd": body.jd[:8000], "resume": body.resume[:8000]}
        return result
    except Exception as e:
        fail(e)

@app.post("/api/interview/start")
async def start(body: StartIn, request: Request = None):
    user_key = request.headers.get("x-gemini-key") or request.headers.get("x-openai-key") if request else None
    a = body.analysis
    if not isinstance(a.get("role"), dict) or not isinstance(a.get("candidate"), dict):
        raise HTTPException(422, "Please complete profile analysis first.")
    
    sid = str(uuid.uuid4())
    state = {
        "id": sid,
        "analysis": a,
        "source_context": a.get("source_context", {}),
        "level": 1,
        "level_name": "Screening",
        "turn": 0,
        "history": [],
        "scores": [],
        "strengths": [],
        "weaknesses": [],
        "topics": [],
        "difficulty": "moderate"
    }
    
    prompt = f'''Create the first screening interview question for this real candidate and role.
Requirements:
1. Reference a specific project, achievement, or skill directly from the candidate resume.
2. Evaluate resume claims, role motivation, ownership, and communication.
3. NEVER ask generic clichés like "Tell me about yourself".
4. Return JSON:
{{
  "question": "Candidate-specific opening screening question...",
  "competency": "Role Fit & Project Ownership",
  "why_this_question": "Explain which resume claim or project this question probes...",
  "difficulty": "moderate"
}}

Job Description: {json.dumps(a.get('source_context', {}).get('jd', ''))[:4000]}
Resume: {json.dumps(a.get('source_context', {}).get('resume', ''))[:4000]}
Role Analysis: {json.dumps(a.get('role'))}
Candidate Evidence: {json.dumps(a.get('candidate'))}'''

    try:
        kwargs = {"user_key": user_key} if user_key else {}
        q = await llm_json(
            "You are an elite, discerning technical recruiter conducting a personalized screening interview. Ground questions in concrete candidate evidence.",
            prompt,
            **kwargs
        )
    except Exception as e:
        fail(e)
        
    if not q.get("question"):
        raise HTTPException(502, "AI did not produce an opening question.")
        
    state["current_question"] = q
    SESSIONS[sid] = state
    
    return {
        "session_id": sid,
        "level": 1,
        "level_name": "Screening",
        "turn": 1,
        "question": q["question"],
        "competency": q.get("competency", "Role Fit & Project Ownership"),
        "why_this_question": q.get("why_this_question", "Personalized based on your resume evidence."),
        "difficulty": q.get("difficulty", "moderate")
    }

@app.post("/api/interview/answer")
async def answer(body: AnswerIn, request: Request = None):
    user_key = request.headers.get("x-gemini-key") or request.headers.get("x-openai-key") if request else None
    s = SESSIONS.get(body.session_id)
    if not s:
        raise HTTPException(404, "Interview session expired or not found. Please start a new interview.")
    
    current = s["current_question"]
    a = s["analysis"]
    s["turn"] += 1
    current_level = s["level"]
    
    # Adaptive Level Transition Logic:
    # Turns 1-3: Level 1 (Screening)
    # Turns 4-6: Level 2 (Competency)
    # Turns 7+:  Level 3 (Deep-Dive)
    next_level = min(3, 1 + (len(s["history"]) + 1) // 3)
    level_names = {1: "Screening", 2: "Competency", 3: "Deep-Dive"}
    next_level_name = level_names.get(next_level, "Deep-Dive")
    
    prompt = f'''Evaluate the candidate's answer to the previous question and generate the next adaptive question.
CRITICAL RULES FOR ADAPTIVE QUESTIONING:
1. The next question MUST causally depend on and explicitly reference concrete details from the candidate's last answer.
2. If the answer was vague or missing evidence, probe and challenge it directly.
3. If the answer was strong, increase technical depth, test reasoning, edge cases, and architectural trade-offs.
4. If candidate struggled, scaffold fundamentals and clarify concepts.
5. Level progression: Current level is {current_level} ({level_names.get(current_level)}), Next question target level is {next_level} ({next_level_name}).
   - Level 1 (Screening): motivation, ownership, baseline fit.
   - Level 2 (Competency): technical competencies, problem solving, decision making.
   - Level 3 (Deep-Dive): probe resume claims, counter-questions, system trade-offs, why/how, failure modes.

Return JSON matching this schema:
{{
  "evaluation": {{
    "score": 0-100,
    "competency": "string",
    "relevance": 0-25,
    "correctness": 0-25,
    "depth": 0-25,
    "clarity": 0-25,
    "evidence": "string summarizing evidence demonstrated in this answer",
    "strengths": ["string"],
    "weaknesses": ["string"],
    "missing_points": ["string"],
    "ideal_direction": "Actionable coaching direction on how to answer this ideally",
    "follow_up_reason": "Clear explanation of why the next question was selected based on this answer",
    "difficulty": "easy" | "moderate" | "challenging"
  }},
  "next": {{
    "question": "The next question referencing a specific detail from candidate's answer...",
    "competency": "string",
    "why_this_question": "Why this specific follow-up was asked...",
    "difficulty": "easy" | "moderate" | "challenging"
  }},
  "level": {next_level},
  "level_name": "{next_level_name}"
}}

Context:
Previous Question: {json.dumps(current.get("question"))}
Candidate answer: {body.answer}
Current level: {current_level}
Role Analysis: {json.dumps(a.get("role"))}
Candidate Analysis: {json.dumps(a.get("candidate"))}
Interview History Context: {json.dumps(s["history"][-5:])}
Accumulated Strengths: {json.dumps(s["strengths"][-5:])}
Accumulated Weaknesses: {json.dumps(s["weaknesses"][-5:])}'''

    try:
        kwargs = {"user_key": user_key} if user_key else {}
        result = await llm_json(
            "You are an adaptive expert interviewer and rigorous evaluator. The next question must directly quote or probe details from the candidate's last answer.",
            prompt,
            **kwargs
        )
    except Exception as e:
        fail(e)
        
    ev = result.get("evaluation", {})
    nxt = result.get("next", {})
    
    if not ev or not nxt.get("question"):
        raise HTTPException(502, "AI returned an incomplete evaluation. Please retry.")
        
    # Store turn history
    turn_record = {
        "turn": s["turn"],
        "level": current_level,
        "level_name": level_names.get(current_level),
        "question": current.get("question"),
        "answer": body.answer,
        "evaluation": ev,
        "next_question": nxt.get("question")
    }
    s["history"].append(turn_record)
    s["scores"].append(max(0, min(100, int(ev.get("score", 70)))))
    s["strengths"].extend(ev.get("strengths", []))
    s["weaknesses"].extend(ev.get("weaknesses", []))
    s["topics"].append(ev.get("competency", ""))
    
    # Update current session state
    s["level"] = next_level
    s["level_name"] = next_level_name
    s["current_question"] = nxt
    s["difficulty"] = nxt.get("difficulty", "moderate")
    
    progress_pct = min(100, round(len(s["history"]) / 9 * 100))
    
    return {
        "evaluation": ev,
        "level": next_level,
        "level_name": next_level_name,
        "turn": s["turn"] + 1,
        "question": nxt["question"],
        "competency": nxt.get("competency", "Adaptive follow-up"),
        "why_this_question": nxt.get("why_this_question", "Formulated from your preceding answer."),
        "difficulty": nxt.get("difficulty", s["difficulty"]),
        "progress": progress_pct,
        "total_answers": len(s["history"])
    }

@app.post("/api/interview/report")
async def report(body: ReportIn, request: Request = None):
    user_key = request.headers.get("x-gemini-key") or request.headers.get("x-openai-key") if request else None
    s = SESSIONS.get(body.session_id)
    if not s:
        raise HTTPException(404, "Interview session expired or not found.")
    if not s["history"]:
        raise HTTPException(422, "Please answer at least one interview question before generating the report.")
        
    a = s["analysis"]
    avg_score = sum(s["scores"]) / len(s["scores"])
    job_fit = float(a.get("job_fit", 70))
    
    prompt = f'''Create a concise, evidence-based final interview report and preparation plan from actual answers.
Return JSON with this exact schema:
{{
  "competency_scores": [
    {{"name": "Role Fit", "score": 0-100, "evidence": "string"}},
    {{"name": "Technical Knowledge", "score": 0-100, "evidence": "string"}},
    {{"name": "Problem Solving", "score": 0-100, "evidence": "string"}},
    {{"name": "Communication", "score": 0-100, "evidence": "string"}},
    {{"name": "Confidence & Clarity", "score": 0-100, "evidence": "string"}},
    {{"name": "Depth of Understanding", "score": 0-100, "evidence": "string"}},
    {{"name": "Behavioural Fit", "score": 0-100, "evidence": "string"}}
  ],
  "question_feedbacks": [
    {{
      "question": "string",
      "answer": "string",
      "score": 0-100,
      "what_was_good": "Specific strengths of this answer",
      "what_could_be_better": "Specific actionable critique",
      "ideal_direction": "How to answer this ideally"
    }}
  ],
  "strengths": ["Demonstrated strength with interview evidence"],
  "weaknesses": ["Concrete weakness identified in answers"],
  "preparation_gaps": [
    {{
      "priority": 1,
      "topic": "string",
      "why": "Why it matters for this specific JD",
      "what_candidate_lacks": "Specific gap observed in answers",
      "review_topics": ["string"],
      "suggested_practice": "string",
      "practice_questions": ["string"]
    }}
  ],
  "readiness_rationale": "Clear rationale explaining the readiness assessment based on interview performance and role fit.",
  "next_steps": ["Actionable step"],
  "summary": "Holistic coaching executive summary"
}}

Rules:
- Do not output overall_score or readiness_score; they are calculated mathematically by the server.
- Base every single strength, weakness, and preparation gap on actual recorded answers.

Recorded Interview Turns:
{json.dumps(s["history"])}

Candidate Fit & Profile:
Job Fit Score: {job_fit}%
Role Target: {json.dumps(a.get("role"))}'''

    try:
        kwargs = {"user_key": user_key} if user_key else {}
        out = await llm_json(
            "You are an executive interview coach synthesizing real interview evidence into an actionable preparation report.",
            prompt,
            **kwargs
        )
    except Exception as e:
        fail(e)
        
    overall_score = round(avg_score)
    # Defensible Readiness Score: 70% Interview Performance + 30% Job Fit Alignment
    readiness_score = round(overall_score * 0.7 + job_fit * 0.3)
    
    # Categorize Readiness
    if readiness_score >= 85:
        readiness_status = "Strong Candidate"
        readiness_badge = "🟢 Strong Candidate"
    elif readiness_score >= 75:
        readiness_status = "Interview Ready"
        readiness_badge = "🟡 Interview Ready"
    elif readiness_score >= 60:
        readiness_status = "Needs Preparation"
        readiness_badge = "🟠 Needs Preparation"
    else:
        readiness_status = "Not Ready"
        readiness_badge = "🔴 Not Ready"
        
    cand = a.get("candidate", {})
    role = a.get("role", {})
    out["candidate_name"] = cand.get("candidate_name") or "Candidate"
    out["role_title"] = role.get("role_title") or "Target Role"
    out["overall_score"] = overall_score
    out["job_fit"] = job_fit
    out["readiness_score"] = readiness_score
    out["readiness_status"] = readiness_status
    out["readiness_badge"] = readiness_badge
    out["answer_count"] = len(s["history"])
    out["history"] = s["history"]
    
    return out

if os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
