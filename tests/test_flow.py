import unittest
from unittest.mock import patch

import app
import httpx


class InterviewFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_and_upload_api(self):
        transport = httpx.ASGITransport(app=app.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/api/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["status"], "ok")
            good = await client.post("/api/extract", files={"file": ("resume.txt", b"A candidate has several years of engineering work with measurable delivery.", "text/plain")})
            self.assertEqual(good.status_code, 200)
            self.assertIn("measurable delivery", good.json()["text"])
            bad = await client.post("/api/extract", files={"file": ("resume.exe", b"not a resume", "application/octet-stream")})
            self.assertEqual(bad.status_code, 415)

    async def test_adaptive_three_level_flow_and_report(self):
        async def fake_llm(system, prompt):
            if "Create the first screening" in prompt:
                return {"question": "You built Atlas; what did you own?", "competency": "Ownership", "why_this_question": "Resume project", "difficulty": "moderate"}
            if "Create a concise" in prompt:
                return {"competency_scores": [{"name": "Ownership", "score": 75, "evidence": "Explained contribution"}], "strengths": ["Specific example"], "weaknesses": ["Quantify results"], "preparation_gaps": [{"topic": "Metrics", "why": "Impact was vague", "action": "Practice explaining baselines"}], "next_steps": ["Practice STAR"], "summary": "Good practice."}
            answer = prompt.split("Candidate answer: ")[-1].split("\nCurrent level:")[0]
            return {"evaluation": {"score": 70, "competency": "Ownership", "evidence": "Answer detail", "strengths": ["Specific"], "improvements": ["Quantify"], "follow_up_reason": "Probes the detail you gave", "difficulty": "moderate"}, "next": {"question": f"You said {answer[:30]}; how did you measure the result?", "competency": "Evidence", "why_this_question": "Based on your last answer", "difficulty": "moderate"}, "level": 1}

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
            self.assertEqual(levels, [1, 1, 2, 2, 2, 3, 3])
            report = await app.report(app.ReportIn(session_id=first["session_id"]))
            self.assertEqual(report["answer_count"], 7)
            self.assertEqual(report["overall_score"], 70)
            self.assertEqual(report["readiness_score"], 71)
            self.assertEqual(report["job_fit"], 72)

    async def test_missing_session_is_rejected(self):
        with self.assertRaises(Exception) as caught:
            await app.answer(app.AnswerIn(session_id="missing", answer="My answer"))
        self.assertEqual(getattr(caught.exception, "status_code", None), 404)


if __name__ == "__main__":
    unittest.main()
