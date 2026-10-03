"""Interview Accelerator API: structured LLM analysis and answer-driven interviews."""
from __future__ import annotations
import json, os, re, uuid
from typing import Any
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(title="Interview Accelerator", version="1.0.0")
origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:8000")
app.add_middleware(CORSMiddleware, allow_origins=[origin, "http://localhost:8000", "http://127.0.0.1:8000"], allow_methods=["*"], allow_headers=["*"])
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
        if not match: raise ValueError("Model did not return a JSON object")
        data = json.loads(match.group())
    if not isinstance(data, dict): raise ValueError("Expected a JSON object")
    return data

async def llm_json(system: str, prompt: str) -> dict[str, Any]:
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "gemini":
        key, model = os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        if not key: raise RuntimeError("GEMINI_API_KEY is not configured")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {"system_instruction":{"parts":[{"text":system}]},"contents":[{"role":"user","parts":[{"text":prompt}]}],"generationConfig":{"responseMimeType":"application/json","temperature":0.35}}
        async with httpx.AsyncClient(timeout=70) as client:
            response = await client.post(url, json=payload); response.raise_for_status()
        raw = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    elif provider == "openai":
        key, model = os.getenv("OPENAI_API_KEY"), os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if not key: raise RuntimeError("OPENAI_API_KEY is not configured")
        async with httpx.AsyncClient(timeout=70) as client:
            response = await client.post("https://api.openai.com/v1/chat/completions", headers={"Authorization":f"Bearer {key}"}, json={"model":model,"response_format":{"type":"json_object"},"temperature":0.35,"messages":[{"role":"system","content":system},{"role":"user","content":prompt}]}); response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
    else: raise RuntimeError("LLM_PROVIDER must be gemini or openai")
    return _json_object(raw)

def fail(e: Exception):
    message = str(e)
    status = 503 if isinstance(e, (httpx.HTTPError, RuntimeError)) else 502
    raise HTTPException(status_code=status, detail=message[:260] if status == 503 and "API_KEY" in message else "The AI service could not complete this request. Check provider credentials, quota, and try again.")

@app.get("/api/health")
async def health():
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    configured = bool(os.getenv("GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"))
    return {"status":"ok", "provider":provider, "ai_configured":configured, "demo_mode":os.getenv("DEMO_MODE","false").lower()=="true"}

@app.post("/api/extract")
async def extract(file: UploadFile = File(...)):
    name = file.filename or "upload"
    ext = name.lower().rsplit(".",1)[-1] if "." in name else ""
    if ext not in {"txt","pdf","docx"}: raise HTTPException(415, "Upload a PDF, DOCX, or TXT file.")
    data = await file.read(8_000_001)
    if len(data) > 8_000_000: raise HTTPException(413, "Files must be under 8 MB.")
    try:
        if ext == "txt": text = data.decode("utf-8-sig")
        elif ext == "pdf":
            from pypdf import PdfReader
            import io
            text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
        else:
            from docx import Document
            import io
            text = "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
        text = text.strip()
        if len(text) < 40: raise ValueError("No readable text found. Try pasting the content instead.")
        return {"text":text[:MAX_TEXT],"filename":name}
    except HTTPException: raise
    except Exception as e: raise HTTPException(422, str(e)[:180] or "Could not read this file.")

@app.post("/api/analyze")
async def analyze(body: AnalyzeIn):
    system = "You are a rigorous career coach. Use only supplied evidence, distinguish evidence from inference, never invent candidate details. Return valid JSON matching the requested keys. Keep arrays concise and specific."
    prompt = f'''Analyze this job and candidate. Return JSON with keys role (role_title, responsibilities[], required_skills[], preferred_skills[], technical_competencies[], behavioral_competencies[], experience_expectations[], keywords[], important_concepts[], qualifications[]); candidate (skills[], relevant_experience[], relevant_projects[], achievements[], strengths[], missing_skills[], weak_areas[], claims_to_probe[], preparation_areas[]); fit_dimensions (array of objects {{name, weight, score, evidence, gaps}}); fit_rationale (string). For fit_dimensions, score each out of 100 from explicit evidence across required skill match (30), technical competency match (25), experience match (15), project relevance (15), behavioral match (10), qualifications (5). Weights must sum to 100. Do NOT output a fit percentage. Use evidence-based conservative scores.\nJOB DESCRIPTION:\n{body.jd}\n\nRESUME:\n{body.resume}'''
    try:
        result = await llm_json(system, prompt)
        role, candidate, dims = result.get("role"), result.get("candidate"), result.get("fit_dimensions")
        if not isinstance(role,dict) or not isinstance(candidate,dict) or not isinstance(dims,list) or len(dims)<4: raise ValueError("Incomplete structured analysis")
        weighted = sum(max(0,min(100,float(d.get("score",0)))) * max(0,float(d.get("weight",0))) for d in dims) / max(1,sum(max(0,float(d.get("weight",0))) for d in dims))
        result["job_fit"] = round(weighted)
        result["evidence_note"] = "Fit score is a weighted evidence assessment; interview performance is reported separately."
        result["source_context"] = {"jd": body.jd[:7000], "resume": body.resume[:7000]}
        return result
    except Exception as e: fail(e)

@app.post("/api/interview/start")
async def start(body: StartIn):
    a=body.analysis
    if not isinstance(a.get("role"),dict) or not isinstance(a.get("candidate"),dict): raise HTTPException(422,"Complete profile analysis first.")
    sid=str(uuid.uuid4()); state={"id":sid,"analysis":a,"source_context":a.get("source_context",{}),"level":1,"turn":0,"history":[],"scores":[],"strengths":[],"weaknesses":[],"topics":[],"difficulty":"moderate"}
    prompt=f'''Create the first screening interview question for this real candidate. Reference a specific resume project/achievement/skill and evaluate role motivation or ownership. Return JSON {{"question":"...","competency":"...","why_this_question":"...","difficulty":"moderate"}}. Avoid generic questions.\nJob description: {json.dumps(a.get('source_context',{}).get('jd',''))}\nResume: {json.dumps(a.get('source_context',{}).get('resume',''))}\nRole analysis: {json.dumps(a.get('role'))}\nCandidate analysis: {json.dumps(a.get('candidate'))}'''
    try: q=await llm_json("You are a warm but discerning interviewer. Ask exactly one question. Ground it in candidate evidence.",prompt)
    except Exception as e: fail(e)
    if not q.get("question"): raise HTTPException(502,"AI did not produce an interview question.")
    state["current_question"]=q; SESSIONS[sid]=state
    return {"session_id":sid,"level":1,"level_name":"Screening","turn":1,"question":q["question"],"competency":q.get("competency","Role fit"),"why_this_question":q.get("why_this_question","Personalized to your profile."),"difficulty":q.get("difficulty","moderate")}

@app.post("/api/interview/answer")
async def answer(body: AnswerIn):
    s=SESSIONS.get(body.session_id)
    if not s: raise HTTPException(404,"Interview session expired. Start a new interview.")
    current=s["current_question"]; a=s["analysis"]; s["turn"]+=1
    level=s["level"]
    prompt=f'''Evaluate the candidate response to the exact previous question, then choose exactly ONE next question that materially depends on this answer. Quote or refer to a concrete detail from their answer in the next question. If answer is vague, clarify/probe it; if strong, increase depth; if weak, scaffold fundamentals. Do not repeat questions. Interview stages advance after answer 3 to competency and after answer 6 to deep-dive; maintain the current stage otherwise. Return JSON: evaluation={{score (0-100), competency, evidence, strengths[], improvements[], follow_up_reason, difficulty (easy|moderate|challenging)}}, next={{question, competency, why_this_question, difficulty}}, level (1|2|3), level_name. Answer quality scoring rubric: relevance 25, specific evidence 25, reasoning 25, communication 15, reflection 10; score only this answer, not resume fit.\nFull job description context: {json.dumps(s['source_context'].get('jd',''))}\nFull resume context: {json.dumps(s['source_context'].get('resume',''))}\nStructured role: {json.dumps(a.get('role'))}\nStructured candidate evidence: {json.dumps(a.get('candidate'))}\nJob fit: {a.get('job_fit')}\nPrior context: {json.dumps(s['history'][-6:])}\nPrevious question: {json.dumps(current)}\nCandidate answer: {body.answer}\nCurrent level: {level}; turn: {s['turn']}; strengths: {s['strengths'][-6:]}; weaknesses: {s['weaknesses'][-6:]}'''
    try: result=await llm_json("You are an adaptive interviewer and calibrated evaluator. The next question must be causally responsive to the candidate's last answer. Return only valid JSON.",prompt)
    except Exception as e: fail(e)
    ev=result.get("evaluation",{}); nxt=result.get("next",{})
    if not ev or not nxt.get("question"): raise HTTPException(502,"AI returned an incomplete evaluation. Please retry.")
    s["history"].append({"level":level,"question":current.get("question"),"answer":body.answer,"evaluation":ev,"next_question":nxt.get("question")})
    s["scores"].append(max(0,min(100,int(ev.get("score",0))))); s["strengths"].extend(ev.get("strengths",[])); s["weaknesses"].extend(ev.get("improvements",[])); s["topics"].append(ev.get("competency",""))
    # Keep the three stages observable and predictable while letting question content remain adaptive.
    newlevel=min(3, 1 + len(s["history"]) // 3)
    s["level"]=newlevel; s["current_question"]=nxt; s["difficulty"]=ev.get("difficulty","moderate")
    return {"evaluation":ev,"level":newlevel,"level_name":["","Screening","Competency","Deep-dive"][newlevel],"turn":s["turn"]+1,"question":nxt["question"],"competency":nxt.get("competency","Adaptive follow-up"),"why_this_question":nxt.get("why_this_question","Based on your previous answer."),"difficulty":nxt.get("difficulty",s["difficulty"]),"progress":min(100,round(len(s['history'])/9*100))}

@app.post("/api/interview/report")
async def report(body: ReportIn):
    s=SESSIONS.get(body.session_id)
    if not s: raise HTTPException(404,"Interview session expired.")
    if not s["history"]: raise HTTPException(422,"Answer at least one question before generating a report.")
    a=s["analysis"]
    prompt=f'''Create a concise, evidence-based final interview report and preparation plan from actual answers. Return JSON {{competency_scores (array of {{name,score,evidence}}), strengths[], weaknesses[], preparation_gaps (array of {{topic,why,action}}), next_steps[], summary}}. Do not return overall or readiness scores; the application computes them from recorded answer evaluations and job fit. Do not infer unsupported facts.\nJob description: {json.dumps(s['source_context'].get('jd',''))}\nResume: {json.dumps(s['source_context'].get('resume',''))}\nJob fit: {a.get('job_fit')}\nRole: {json.dumps(a.get('role'))}\nInterview answers and evaluations: {json.dumps(s['history'])}\nAnswer average: {sum(s['scores'])/len(s['scores']):.1f}'''
    try: out=await llm_json("You write candid and actionable interview coaching reports grounded only in recorded answers.",prompt)
    except Exception as e: fail(e)
    average = round(sum(s["scores"]) / len(s["scores"]))
    readiness = round(average * .7 + float(a.get("job_fit", 0)) * .3)
    out["overall_score"]=average
    out["readiness_score"]=readiness
    out["readiness_status"]="Interview-ready" if readiness >= 80 else "Nearly ready" if readiness >= 65 else "Keep preparing"
    out["job_fit"]=a.get("job_fit"); out["answer_count"]=len(s["history"]); out["history"]=s["history"]
    return out

if os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
