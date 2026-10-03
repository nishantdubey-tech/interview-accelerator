import unittest
import os
from unittest.mock import patch
import httpx
import app


class InterviewFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_never_returns_unrecognized_provider_value(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "sensitive-value", "GEMINI_API_KEY": "test-key"}):
            result = await app.health()
        self.assertEqual(result["provider"], "invalid")
        self.assertFalse(result["ai_configured"])
        self.assertNotIn("sensitive-value", str(result))

    async def test_health_and_upload_api(self):
        transport = httpx.ASGITransport(app=app.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/api/health")
            self.assertEqual(health.status_code, 200)
            data = health.json()
            self.assertEqual(data["status"], "ok")
            self.assertTrue(data["features"]["job_fit_engine"])
            self.assertTrue(data["features"]["adaptive_interview_3_levels"])

            good = await client.post(
                "/api/extract",
                files={"file": ("resume.txt", b"A candidate has several years of engineering work with measurable delivery.", "text/plain")}
            )
            self.assertEqual(good.status_code, 200)
            self.assertIn("measurable delivery", good.json()["text"])

            bad = await client.post(
                "/api/extract",
                files={"file": ("resume.exe", b"not a resume", "application/octet-stream")}
            )
            self.assertEqual(bad.status_code, 415)

    async def test_analyze_computes_job_fit_and_categorizes_dimensions(self):
        mock_analysis = {
            "role": {
                "role_title": "AI Engineer",
                "responsibilities": ["Build LLM agents", "Optimize latency"],
                "required_skills": ["Python", "FastAPI", "RAG"],
                "preferred_skills": ["LangChain", "Vector DBs"],
                "technical_competencies": ["Backend Architecture", "Data Modeling"],
                "behavioral_competencies": ["Communication", "Ownership"],
                "experience_expectations": ["3+ years"],
                "keywords": ["RAG", "LLM"],
                "important_concepts": ["Embeddings", "Chunking"],
                "qualifications": ["CS Degree"]
            },
            "candidate": {
                "skills": ["Python", "FastAPI", "Pinecone"],
                "relevant_experience": ["Built RAG systems"],
                "relevant_projects": ["Enterprise RAG Search"],
                "achievements": ["Decreased query time by 30%"],
                "strengths": ["Strong Python & API experience"],
                "missing_skills": ["Kubernetes"],
                "weak_areas": ["Cloud cost optimization"],
                "claims_to_probe": ["Claim of 30% speedup"],
                "preparation_areas": ["Metrics quantification"]
            },
            "fit_dimensions": [
                {"name": "Required Skills Match", "weight": 30, "score": 90, "evidence": "Expert in Python & FastAPI", "gaps": "None"},
                {"name": "Technical Competency Match", "weight": 25, "score": 80, "evidence": "Good RAG architecture", "gaps": "Distributed caching"},
                {"name": "Experience Match", "weight": 15, "score": 75, "evidence": "Solid backend experience", "gaps": "Slightly junior for lead role"},
                {"name": "Project Relevance", "weight": 15, "score": 85, "evidence": "Directly built vector search engines", "gaps": "None"},
                {"name": "Behavioural Match", "weight": 10, "score": 80, "evidence": "Collaborative track record", "gaps": "None"},
                {"name": "Qualification Match", "weight": 5, "score": 100, "evidence": "Matches requirements", "gaps": "None"}
            ],
            "fit_rationale": "High profile match with strong core RAG skills."
        }
        with patch.object(app, "llm_json", return_value=mock_analysis):
            result = await app.analyze(app.AnalyzeIn(
                jd="We are seeking an AI Engineer with expertise in Python, FastAPI, and RAG architectures.",
                resume="Experienced AI Engineer with 3 years building Python FastAPI services and vector databases."
            ))
            # Weighted average:
            # 90*0.30 + 80*0.25 + 75*0.15 + 85*0.15 + 80*0.10 + 100*0.05 = 27 + 20 + 11.25 + 12.75 + 8 + 5 = 84
            self.assertEqual(result["job_fit"], 84)
            self.assertIn("fit_dimensions", result)
            self.assertEqual(result["fit_dimensions"][0]["category"], "Strong Match")
            self.assertIn("job_fit", result)

    async def test_adaptive_three_level_flow_and_report(self):
        async def fake_llm(system, prompt):
            if "Create the first screening" in prompt:
                return {
                    "question": "You built Atlas; what did you own?",
                    "competency": "Ownership",
                    "why_this_question": "Resume project",
                    "difficulty": "moderate"
                }
            if "Create a concise" in prompt:
                return {
                    "competency_scores": [
                        {"name": "Role Fit", "score": 85, "evidence": "Good role fit"},
                        {"name": "Technical Knowledge", "score": 75, "evidence": "Good technical depth"},
                        {"name": "Problem Solving", "score": 70, "evidence": "Explained contribution"},
                        {"name": "Communication", "score": 80, "evidence": "Clear answers"},
                        {"name": "Confidence & Clarity", "score": 75, "evidence": "Confident responses"},
                        {"name": "Depth of Understanding", "score": 70, "evidence": "Understands concepts"},
                        {"name": "Behavioural Fit", "score": 80, "evidence": "Team-oriented"}
                    ],
                    "strengths": ["Specific example"],
                    "weaknesses": ["Quantify results"],
                    "preparation_gaps": [
                        {
                            "priority": 1,
                            "topic": "Metrics",
                            "why": "Impact was vague",
                            "what_candidate_lacks": "Baselines",
                            "review_topics": ["Telemetry"],
                            "suggested_practice": "Practice explaining baselines",
                            "practice_questions": ["How did you measure improvement?"]
                        }
                    ],
                    "readiness_rationale": "Strong performance across screening and competency rounds.",
                    "next_steps": ["Practice STAR"],
                    "summary": "Good practice."
                }
            answer = prompt.split("Candidate answer: ")[-1].split("\nCurrent level:")[0]
            return {
                "evaluation": {
                    "score": 70,
                    "competency": "Ownership",
                    "relevance": 20,
                    "correctness": 18,
                    "depth": 17,
                    "clarity": 15,
                    "evidence": "Answer detail",
                    "strengths": ["Specific"],
                    "weaknesses": ["Quantify"],
                    "missing_points": ["Exact numbers"],
                    "ideal_direction": "Include baselines",
                    "follow_up_reason": "Probes the detail you gave",
                    "difficulty": "moderate"
                },
                "next": {
                    "question": f"You said {answer[:30]}; how did you measure the result?",
                    "competency": "Evidence",
                    "why_this_question": "Based on your last answer",
                    "difficulty": "moderate"
                },
                "level": 1
            }

        analysis = {"role": {"role_title": "Engineer"}, "candidate": {"relevant_projects": ["Atlas"]}, "job_fit": 72}
        with patch.object(app, "llm_json", fake_llm):
            first = await app.start(app.StartIn(analysis=analysis))
            self.assertIn("Atlas", first["question"])
            levels = []
            for i in range(7):
                answer = f"I measured metric result {i} on Atlas."
                result = await app.answer(app.AnswerIn(session_id=first["session_id"], answer=answer))
                self.assertIn("metric result", result["question"])
                self.assertIn("Based on your last answer", result["why_this_question"])
                levels.append(result["level"])
            # Level 1 for 1-3, Level 2 for 4-6, Level 3 for 7+
            self.assertEqual(levels, [1, 1, 2, 2, 2, 3, 3])
            report = await app.report(app.ReportIn(session_id=first["session_id"]))
            self.assertEqual(report["answer_count"], 7)
            self.assertEqual(report["overall_score"], 70)
            # 70 * 0.7 + 72 * 0.3 = 49 + 21.6 = 70.6 -> round to 71
            self.assertEqual(report["readiness_score"], 71)
            self.assertEqual(report["job_fit"], 72)
            self.assertEqual(report["readiness_status"], "Needs Preparation")

    async def test_transcribe_audio_fallback(self):
        transport = httpx.ASGITransport(app=app.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            with patch.dict(os.environ, {"DEMO_MODE": "true"}):
                resp = await client.post(
                    "/api/transcribe",
                    files={"file": ("speech.webm", b"RIFF....fake_audio_bytes....", "audio/webm")}
                )
                self.assertEqual(resp.status_code, 200)
                self.assertIn("text", resp.json())
                self.assertTrue(len(resp.json()["text"]) > 10)

    async def test_missing_session_is_rejected(self):
        with self.assertRaises(Exception) as caught:
            await app.answer(app.AnswerIn(session_id="missing", answer="My answer"))
        self.assertEqual(getattr(caught.exception, "status_code", None), 404)


if __name__ == "__main__":
    unittest.main()
