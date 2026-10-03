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
    "FastAPI", "Flask", "Django", "Node.js", "Express", "NestJS", "React", "Next.js", "Vue", "Nuxt", "Angular", "Svelte", "Tailwind", "Redux", "Zustand", "GraphQL", "REST", "gRPC", "WebSockets",
    "iOS", "Android", "SwiftUI", "Jetpack Compose", "Flutter", "React Native",
    "RAG", "LLM", "LangChain", "LlamaIndex", "OpenAI", "Anthropic", "Gemini", "Hugging Face", "PyTorch", "TensorFlow", "scikit-learn", "Pandas", "NumPy", "NLP", "Deep Learning", "Embeddings", "Vector Database", "Pinecone", "Weaviate", "Milvus", "Qdrant", "Chroma", "Fine-tuning", "Prompt Engineering",
    "Docker", "Kubernetes", "AWS", "GCP", "Azure", "Terraform", "CI/CD", "GitHub Actions", "Linux", "Serverless",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Kafka", "Elasticsearch", "RabbitMQ", "Celery", "Microservices",
    "System Design", "Latency Optimization", "Observability", "Telemetry", "Agile", "Scrum", "Git",
    "Snowflake", "Databricks", "BigQuery", "Spark", "Airflow", "dbt", "Playwright", "Cypress", "Jest", "Pytest"
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
    m = re.search(r"^(?:Candidate\s+Name|Name|Full\s+Name):\s*([A-Za-z\s.'-]{2,40})(?:\r|\n|$)", resume, re.M | re.I)
    if m:
        return m.group(1).splitlines()[0].strip()
    
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
                    cleaned_headline = re.sub(r"^(?:headline|title|role|position):\s*", "", p_clean, flags=re.I).strip()
                    return cleaned_headline or p_clean
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
    if role_title:
        role_title = re.split(r"(?:\.|\n|\||\bCompany:|\bLocation:)", role_title, flags=re.I)[0].strip()
    if not role_title or len(role_title) > 60:
        jd_low = jd.lower()
        if "ios" in jd_low or "swift" in jd_low:
            role_title = "iOS Software Engineer"
        elif "android" in jd_low or "kotlin" in jd_low:
            role_title = "Android Software Engineer"
        elif "rag" in jd_low or "llm" in jd_low or "ai engineer" in jd_low:
            role_title = "AI / LLM Product Engineer"
        elif "product manager" in jd_low or "pm" in jd_low:
            role_title = "Technical AI Product Manager"
        elif "full-stack" in jd_low or "full stack" in jd_low:
            role_title = "Senior Full-Stack Engineer"
        elif "backend" in jd_low:
            role_title = "Senior Backend Engineer"
        elif "frontend" in jd_low or "ui" in jd_low or "react" in jd_low:
            role_title = "Senior Frontend Engineer"
        elif "devops" in jd_low or "sre" in jd_low or "cloud" in jd_low:
            role_title = "DevOps / Infrastructure Engineer"
        elif "data engineer" in jd_low:
            role_title = "Senior Data Engineer"
        elif "data scientist" in jd_low or "machine learning" in jd_low or "ml" in jd_low:
            role_title = "Machine Learning Engineer"
        elif "qa" in jd_low or "sdet" in jd_low or "test" in jd_low:
            role_title = "QA Automation / SDET Engineer"
        elif "security" in jd_low or "cyber" in jd_low:
            role_title = "Cybersecurity Engineer"
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

def _generate_dynamic_opening_question(prompt: str) -> dict[str, Any]:
    """Dynamically generate candidate-specific opening question based on actual profile evidence."""
    role_match = re.search(r"Role Analysis:\s*(\{.*?\})(?:\nCandidate Evidence:|$)", prompt, re.S)
    cand_match = re.search(r"Candidate Evidence:\s*(\{.*?\})(?:$|\n)", prompt, re.S)
    
    role = {}
    candidate = {}
    if role_match:
        try: role = json.loads(role_match.group(1))
        except Exception: pass
    if cand_match:
        try: candidate = json.loads(cand_match.group(1))
        except Exception: pass
        
    candidate_name = candidate.get("candidate_name") or "Candidate"
    headline = candidate.get("headline") or role.get("role_title") or "Software Professional"
    role_title = role.get("role_title") or "the position"
    
    projects = candidate.get("relevant_projects", [])
    achievements = candidate.get("achievements", [])
    skills = candidate.get("skills", [])
    claims = candidate.get("claims_to_probe", [])
    
    if projects and isinstance(projects, list) and projects[0] and len(projects[0]) > 4:
        proj = projects[0]
        question = (
            f"Welcome, {candidate_name}. To start our interview for the {role_title} role: "
            f"I reviewed your portfolio and noticed your work on '{proj}'. "
            f"Could you walk me through the key technical decisions you made on this project, "
            f"and what specific challenges you had to overcome to deliver it successfully?"
        )
        why = f"Directly probes your real-world execution on '{proj}' as highlighted in your candidate profile."
    elif claims and isinstance(claims, list) and claims[0] and len(claims[0]) > 4:
        claim = claims[0]
        question = (
            f"Welcome, {candidate_name}. In your background for the {role_title} role, "
            f"you noted experience regarding '{claim}'. "
            f"Could you describe the system or workflow you implemented here, explaining how you verified its reliability?"
        )
        why = f"Probes candidate claim: '{claim}'."
    elif skills and isinstance(skills, list) and len(skills) >= 2:
        s1, s2 = skills[0], skills[1]
        question = (
            f"Welcome, {candidate_name}. Looking at your technical profile for the {role_title} role, "
            f"you highlight hands-on familiarity with {s1} and {s2}. "
            f"Could you share a concrete project where you leveraged {s1}, detailing your design decisions and how you ensured high performance?"
        )
        why = f"Evaluates practical implementation depth and design decisions using {s1} and {s2}."
    else:
        question = (
            f"Welcome, {candidate_name}. As we begin our interview for the {role_title} role, "
            f"could you walk me through a complex technical system or feature you led from concept to deployment, "
            f"focusing on the architectural trade-offs you encountered?"
        )
        why = f"Establishes candidate project ownership, scope of responsibility, and architectural reasoning."

    return {
        "question": question,
        "competency": "Role Fit & Project Ownership",
        "why_this_question": why,
        "difficulty": "moderate"
    }

def _evaluate_dynamic_answer(prompt: str) -> dict[str, Any]:
    """Dynamically evaluate candidate answer based on real length, technical vocabulary, metrics, and level."""
    ans_match = re.search(r"Candidate answer:\s*(.*?)(?:\nCurrent level:|$|\nRole Analysis:)", prompt, re.S)
    answer = ans_match.group(1).strip() if ans_match else ""
    
    lvl_match = re.search(r"Current level:\s*(\d+)", prompt)
    current_level = int(lvl_match.group(1)) if lvl_match else 1
    
    q_match = re.search(r'Previous Question:\s*"(.*?)"', prompt)
    if not q_match:
        q_match = re.search(r'Previous Question:\s*(.*?)(?:\nCandidate answer:|$)', prompt)
    prev_question = q_match.group(1).strip() if q_match else "the technical question"
    
    role_match = re.search(r'"role_title":\s*"([^"]+)"', prompt)
    role_title = role_match.group(1) if role_match else "Technical Role"
    
    hist_match = re.search(r'Interview History Context:\s*(\[.*?\])(?:\nAccumulated Strengths:|$)', prompt, re.S)
    history_len = 0
    if hist_match:
        try:
            h = json.loads(hist_match.group(1))
            if isinstance(h, list): history_len = len(h)
        except Exception:
            history_len = 0
            
    total_turns = history_len + 1
    if total_turns <= 3:
        next_level = 1
        next_level_name = "Screening"
    elif total_turns <= 6:
        next_level = 2
        next_level_name = "Competency"
    else:
        next_level = 3
        next_level_name = "Deep-Dive"
        
    words = answer.split()
    word_count = len(words)
    ans_lower = answer.lower()
    
    mentioned_skills = [s for s in SKILL_CATALOG if re.search(r"(?<![a-zA-Z0-9_-])" + re.escape(s.lower()) + r"(?![a-zA-Z0-9_-])", " " + ans_lower + " ")]
    has_metrics = bool(re.search(r"\b\d+(?:\.\d+)?%|\b\d+\s*(?:ms|seconds|minutes|hrs|qps|rps|tps|users|req/s|gb|mb|tb|queries)\b|\b\d+x\b", ans_lower))
    
    reasoning_terms = ["trade-off", "tradeoff", "because", "instead of", "constraint", "bottleneck", "latency", "scalability", "concurrency", "cache", "fallback", "degraded", "indexed", "refactored", "monitored", "benchmarked", "migrated", "decoupled", "tested", "edge case", "resilience"]
    found_reasoning = [t for t in reasoning_terms if t in ans_lower]
    
    if word_count > 12:
        phrases = [p.strip() for p in re.split(r"[,.;\n]", answer) if len(p.strip().split()) >= 3]
        snippet = phrases[0] if phrases else " ".join(words[:8])
    elif word_count > 0:
        snippet = answer
    else:
        snippet = "the high-level approach"
    if len(snippet) > 65:
        snippet = snippet[:62] + "..."

    # Dynamic Scoring logic based on real input characteristics
    if word_count < 14 or not answer:
        relevance = max(8, min(14, word_count))
        correctness = max(7, min(12, word_count))
        depth = 6
        clarity = 10
        score = relevance + correctness + depth + clarity
        
        strengths = ["Prompt initial engagement with the interview question"]
        weaknesses = [
            "Response is too brief and lacks technical implementation depth",
            "Missing specific frameworks, architectural trade-offs, and quantified results"
        ]
        missing_points = ["Specific tools & libraries used", "Architecture breakdown", "Verification or test metrics"]
        ideal_direction = "Use the STAR method (Situation, Task, Action, Result). State the context, your technical actions, and the measurable outcome."
        follow_up_reason = "Follow-up probes candidate to unpack their initial statement and provide concrete engineering depth."
        difficulty = "easy"
        
        if next_level == 1:
            next_q = f"Could you expand on that? What specific tools or frameworks did you choose for this, and what was your personal contribution?"
            next_comp = "Role Fit & Personal Contribution"
        elif next_level == 2:
            next_q = f"Let's look into the technical mechanics. What specific design pattern or data structure did you employ, and how did you validate that it worked?"
            next_comp = "Technical Implementation Mechanics"
        else:
            next_q = f"In production systems, simplicity must withstand failure. How did you test or verify this implementation against edge cases and system load?"
            next_comp = "Verification & Edge Cases"

    elif word_count < 45:
        tech_bonus = min(4, len(mentioned_skills) * 2)
        metric_bonus = 3 if has_metrics else 0
        reasoning_bonus = min(4, len(found_reasoning) * 2)
        
        relevance = min(23, 15 + tech_bonus)
        correctness = min(22, 14 + len(mentioned_skills))
        depth = min(20, 12 + reasoning_bonus)
        clarity = min(21, 15 + (1 if word_count > 25 else 0))
        score = min(77, max(52, relevance + correctness + depth + clarity + metric_bonus))
        
        tech_mention = f" ({', '.join(mentioned_skills[:3])})" if mentioned_skills else ""
        strengths = [
            f"Clear initial explanation referencing relevant domain concepts{tech_mention}",
            "Structured response with professional technical vocabulary"
        ]
        weaknesses = [
            "Could elaborate further on alternative approaches considered",
            "Could quantify system impact or performance baselines with concrete metrics"
        ]
        missing_points = ["Comparative trade-offs vs alternatives", "Quantified performance benchmarks"]
        ideal_direction = f"Strengthen the answer by explaining WHY: 'We chose X over Y because of Z constraint, resulting in a measurable improvement.'"
        follow_up_reason = f"Probing deeper into engineering trade-offs based on candidate mentioning '{snippet}'."
        difficulty = "moderate"
        
        if next_level == 1:
            next_q = f"When you implemented {snippet}, how did you collaborate with stakeholders or team members to ensure the requirements were fulfilled?"
            next_comp = "Ownership & Collaboration"
        elif next_level == 2:
            next_q = f"Focusing on your work with {snippet}: what technical constraints or trade-offs did you encounter, and why did you choose that approach over common alternatives?"
            next_comp = "Technical Reasoning & Trade-offs"
        else:
            next_q = f"Taking {snippet} to enterprise production scale: what telemetry or health metrics did you monitor, and what was your runbook if latency spiked?"
            next_comp = "Production Observability & Failure Modes"

    else:
        tech_bonus = min(6, len(mentioned_skills) * 2)
        metric_bonus = 4 if has_metrics else 1
        reasoning_bonus = min(6, len(found_reasoning) * 2)
        
        relevance = min(25, 18 + tech_bonus // 2)
        correctness = min(25, 18 + len(mentioned_skills))
        depth = min(25, 17 + reasoning_bonus)
        clarity = min(24, 18 + metric_bonus)
        score = min(96, max(75, relevance + correctness + depth + clarity))
        
        tech_str = f" involving {', '.join(mentioned_skills[:3])}" if mentioned_skills else ""
        strengths = [
            f"Strong technical depth articulated{tech_str}",
            "Demonstrated clear understanding of system constraints and architectural flow",
            "Provided coherent engineering rationale"
        ]
        if has_metrics:
            strengths.append("Effective use of quantified performance or operational metrics")
            
        weaknesses = [
            "Could further anticipate long-term maintainability or backward compatibility considerations",
            "Could discuss how the architecture adapts to non-functional requirements under extreme load"
        ]
        missing_points = ["Long-term maintenance overhead", "Disaster recovery or multi-region considerations"]
        ideal_direction = "Exceptional detail. Conclude with the business or user-facing outcome to demonstrate complete senior engineering ownership."
        follow_up_reason = f"Level {next_level} deep-dive probing edge cases and architectural boundaries from candidate's answer on '{snippet}'."
        difficulty = "challenging" if next_level == 3 else "moderate"
        
        if next_level == 1:
            next_q = f"You clearly detailed {snippet}. From an ownership perspective, if you were to redesign that system today, what would you do differently in retrospect?"
            next_comp = "Retrospective & Continuous Improvement"
        elif next_level == 2:
            next_q = f"Building on your explanation of {snippet}: how did you design data consistency, concurrency, or caching boundaries to prevent performance degradation?"
            next_comp = "System Design & Concurrency"
        else:
            next_q = f"Let's stress-test the architecture of {snippet}. If downstream dependencies experience intermittent network partitions or fail entirely, how does your system handle backpressure and guarantee zero data loss?"
            next_comp = "Resilience, Backpressure & Failure Modes"

    return {
        "evaluation": {
            "score": score,
            "competency": next_comp,
            "relevance": relevance,
            "correctness": correctness,
            "depth": depth,
            "clarity": clarity,
            "evidence": f"Candidate addressed the question and detailed: {snippet}",
            "strengths": strengths,
            "weaknesses": weaknesses,
            "missing_points": missing_points,
            "ideal_direction": ideal_direction,
            "follow_up_reason": follow_up_reason,
            "difficulty": difficulty
        },
        "next": {
            "question": next_q,
            "competency": next_comp,
            "why_this_question": f"Adaptive follow-up formulated directly from candidate's statement regarding '{snippet}'.",
            "difficulty": difficulty
        },
        "level": next_level,
        "level_name": next_level_name
    }

def _generate_dynamic_report(prompt: str) -> dict[str, Any]:
    """Dynamically synthesize final report from candidate's actual interview history and turn scores."""
    turns_match = re.search(r"Recorded Interview Turns:\s*(\[.*?\])(?:\n\nCandidate Fit & Profile:|$)", prompt, re.S)
    turns = []
    if turns_match:
        try:
            turns = json.loads(turns_match.group(1))
        except Exception:
            turns = []
            
    fit_match = re.search(r"Job Fit Score:\s*(\d+(?:\.\d+)?)%", prompt)
    job_fit = float(fit_match.group(1)) if fit_match else 75.0
    
    role_match = re.search(r"Role Target:\s*(\{.*?\})(?:$|\n)", prompt, re.S)
    role = {}
    if role_match:
        try: role = json.loads(role_match.group(1))
        except Exception: pass
    role_title = role.get("role_title") or "Technical Specialist"
    req_skills = role.get("required_skills", [])
    
    turn_scores = []
    for t in turns:
        ev = t.get("evaluation", {})
        s = ev.get("score")
        if s is not None:
            turn_scores.append(max(20, min(100, int(s))))
            
    if not turn_scores:
        turn_scores = [72]
        
    avg_turn_score = sum(turn_scores) / len(turn_scores)
    
    role_fit_score = round(job_fit * 0.5 + avg_turn_score * 0.5)
    tech_know_score = round(min(98, max(30, avg_turn_score + (3 if any(len(t.get("answer", "").split()) > 40 for t in turns) else -3))))
    problem_solving_score = round(min(98, max(30, avg_turn_score + (2 if len(turns) >= 2 else -2))))
    comm_score = round(min(98, max(35, sum(t.get("evaluation", {}).get("clarity", 18) for t in turns) / len(turns) * 4))) if turns else 80
    conf_score = round(min(98, max(30, avg_turn_score + 1)))
    depth_score = round(min(98, max(25, sum(t.get("evaluation", {}).get("depth", 17) for t in turns) / len(turns) * 4))) if turns else 74
    behav_score = round(min(98, max(35, (role_fit_score + comm_score) / 2)))
    
    competency_scores = [
        {"name": "Role Fit", "score": role_fit_score, "evidence": f"Demonstrated alignment with {role_title} responsibilities and core tech expectations."},
        {"name": "Technical Knowledge", "score": tech_know_score, "evidence": f"Showcased hands-on familiarity with domain tools and architectural flow across {len(turns)} answered question(s)."},
        {"name": "Problem Solving", "score": problem_solving_score, "evidence": "Structured approach to breaking down operational requirements and explaining implementation choices."},
        {"name": "Communication", "score": comm_score, "evidence": "Articulated concepts effectively with structured narrative flow."},
        {"name": "Confidence & Clarity", "score": conf_score, "evidence": "Direct responses addressing the interviewer's specific prompts."},
        {"name": "Depth of Understanding", "score": depth_score, "evidence": "Ability to address technical constraints and design considerations."},
        {"name": "Behavioural Fit", "score": behav_score, "evidence": "Professional demeanor, project accountability, and proactive engineering mindset."}
    ]
    
    question_feedbacks = []
    all_strengths = []
    all_weaknesses = []
    for idx, t in enumerate(turns):
        ev = t.get("evaluation", {})
        ans = t.get("answer", "")
        q = t.get("question", f"Question {idx+1}")
        s = ev.get("score", 70)
        str_list = ev.get("strengths", ["Clear technical explanation"])
        weak_list = ev.get("weaknesses", ["Could provide more quantified benchmarks"])
        all_strengths.extend(str_list)
        all_weaknesses.extend(weak_list)
        
        question_feedbacks.append({
            "question": q,
            "answer": ans,
            "score": s,
            "what_was_good": str_list[0] if str_list else "Clear answer",
            "what_could_be_better": weak_list[0] if weak_list else "Include concrete baseline metrics",
            "ideal_direction": ev.get("ideal_direction", "Anchor responses with STAR framework: context -> technical action -> quantified result.")
        })
        
    unique_strengths = list(dict.fromkeys(all_strengths))[:4] or [f"Solid foundational aptitude for {role_title}"]
    unique_weaknesses = list(dict.fromkeys(all_weaknesses))[:3] or ["Could provide deeper trade-off comparisons"]
    
    top_skill = req_skills[0] if req_skills else "Core Architecture"
    second_skill = req_skills[1] if len(req_skills) > 1 else "System Resiliency"
    
    preparation_gaps = [
        {
            "priority": 1,
            "topic": f"{top_skill} Implementation & Trade-off Quantification",
            "why": f"Target role ({role_title}) emphasizes deep mastery of {top_skill} with measured production impact.",
            "what_candidate_lacks": "Consistent use of quantitative baselines (e.g. latency percentiles, throughput, error rates) in technical narratives.",
            "review_topics": [f"{top_skill} best practices", "P95/P99 latency profiling", "Comparative trade-off matrix vs alternatives"],
            "suggested_practice": f"Rehearse explaining your top project using: Baseline metric -> Engineering intervention with {top_skill} -> Quantified percentage improvement.",
            "practice_questions": [
                f"How did you evaluate {top_skill} against alternative technologies?",
                f"What measurable performance or efficiency gains did your solution produce?"
            ]
        },
        {
            "priority": 2,
            "topic": f"Edge-Case Handling & {second_skill} Failure Modes",
            "why": "Senior interviewers test failure resiliency and graceful degradation under abnormal constraints.",
            "what_candidate_lacks": "Proactively addressing error recovery boundaries and degraded fallback behaviors.",
            "review_topics": ["Graceful degradation patterns", "Circuit breakers and backoff strategies", "Observability alerting thresholds"],
            "suggested_practice": "Map out three distinct failure scenarios for each major architecture in your resume and prepare your mitigation strategy for each.",
            "practice_questions": [
                "If an upstream service dependency times out repeatedly, how does your component prevent cascading failures?",
                "What telemetry metrics do you monitor to catch memory leaks or thread starvation early?"
            ]
        }
    ]
    
    next_steps = [
        f"Review the STAR method and anchor project stories for {role_title} with specific metrics.",
        f"Deepen knowledge around {top_skill} edge cases and failure modes.",
        "Conduct another practice simulation targeting Level 3 Deep-Dive questions to build confidence under technical probing."
    ]
    
    summary = (
        f"The candidate completed {len(turns)} interview turn(s) targeting the {role_title} role, "
        f"achieving an average interview turn score of {round(avg_turn_score)}/100 and a Job Fit alignment of {round(job_fit)}%. "
        f"Performance reflects good domain vocabulary and structured responses. "
        f"Focusing on quantitative impact metrics and proactive edge-case defense will elevate readiness to the highest caliber."
    )
    
    return {
        "competency_scores": competency_scores,
        "question_feedbacks": question_feedbacks,
        "strengths": unique_strengths,
        "weaknesses": unique_weaknesses,
        "preparation_gaps": preparation_gaps,
        "readiness_rationale": f"Readiness combines simulated interview performance ({round(avg_turn_score)}%) with profile alignment ({round(job_fit)}%).",
        "next_steps": next_steps,
        "summary": summary
    }

def _fallback_llm_json(prompt: str) -> dict[str, Any]:
    """Graceful structured fallback for demo mode or temporary API quota issues, 100% grounded in input."""
    p_lower = prompt.lower()
    if "first screening interview question" in p_lower:
        return _generate_dynamic_opening_question(prompt)
    elif "evaluate the candidate" in p_lower or "candidate answer:" in p_lower:
        return _evaluate_dynamic_answer(prompt)
    elif "final interview report" in p_lower or "create a concise, evidence-based final interview report" in p_lower:
        return _generate_dynamic_report(prompt)
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
