"""End-to-end verification script testing the entire Interview Accelerator pipeline."""
import asyncio
import io
import json
import httpx
import app

async def run_e2e_test():
    print("=" * 60)
    print("STARTING E2E VERIFICATION OF INTERVIEW ACCELERATOR")
    print("=" * 60)

    transport = httpx.ASGITransport(app=app.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        # Step 1: Health Check
        print("\n1. Testing GET /api/health...")
        health_resp = await client.get("/api/health")
        assert health_resp.status_code == 200, f"Health check failed: {health_resp.status_code}"
        health = health_resp.json()
        print("   Status:", health["status"])
        print("   Provider:", health["provider"])
        print("   Features:", list(health["features"].keys()))

        # Step 2: File Extraction
        print("\n2. Testing POST /api/extract with TXT file...")
        resume_text = (
            "Alex Rivera. AI Engineer with 4 years experience building "
            "RAG pipelines and LLM services with Python, FastAPI, and a vector database. "
            "Improved hybrid search latency by 28% on a synthetic 1.2M-document benchmark "
            "and deployed services to a managed container platform."
        )
        extract_resp = await client.post(
            "/api/extract",
            files={"file": ("resume.txt", resume_text.encode("utf-8"), "text/plain")}
        )
        assert extract_resp.status_code == 200, f"Extract failed: {extract_resp.text}"
        extracted = extract_resp.json()
        print(f"   Successfully extracted {extracted['character_count']} characters from {extracted['filename']}")

        # Step 3: Profile & Job Fit Analysis
        print("\n3. Testing POST /api/analyze...")
        jd_text = (
            "Title: Senior AI Platform Engineer. Company: Example Systems.\n"
            "We are seeking an AI Engineer to build RAG pipelines and LLM microservices using Python, "
            "FastAPI, LangChain, and vector databases (Pinecone, Qdrant). Must have experience with "
            "latency optimization, telemetry, and evaluation frameworks."
        )
        analyze_resp = await client.post(
            "/api/analyze",
            json={"jd": jd_text, "resume": resume_text}
        )
        assert analyze_resp.status_code == 200, f"Analyze failed: {analyze_resp.text}"
        analysis = analyze_resp.json()
        print(f"   Calculated Job Fit Score: {analysis['job_fit']}%")
        print(f"   Role Title: {analysis['role']['role_title']}")
        print(f"   Required Skills: {analysis['role']['required_skills'][:4]}")
        print(f"   Candidate Strengths: {analysis['candidate']['strengths'][:2]}")
        print(f"   Resume Claims to Probe: {analysis['candidate']['claims_to_probe'][:2]}")
        print("   Fit Dimensions:")
        for dim in analysis["fit_dimensions"]:
            print(f"     - {dim['name']} ({dim['weight']}%): {dim['score']}% [{dim['category']}]")

        # Step 4: Start AI Interview Simulator
        print("\n4. Testing POST /api/interview/start (Level 1: Screening)...")
        start_resp = await client.post(
            "/api/interview/start",
            json={"analysis": analysis}
        )
        assert start_resp.status_code == 200, f"Start failed: {start_resp.text}"
        session = start_resp.json()
        session_id = session["session_id"]
        print(f"   Session ID: {session_id}")
        print(f"   Level {session['level']}: {session['level_name']}")
        print(f"   Opening Question: {session['question']}")
        print(f"   Why This Question: {session['why_this_question']}")

        # Step 5: Answer Adaptive Questions (Levels 1 -> 2 -> 3)
        print("\n5. Testing POST /api/interview/answer across 7 turns (3 levels)...")
        candidate_answers = [
            "At Example Systems, I owned the RAG retrieval pipeline, building the query preprocessor and combining BM25 with dense vector search.",
            "We measured the 28% latency reduction by comparing P95 response times before and after asynchronous batching and embedding caching.",
            "Our primary metrics were P95 latency and Recall@10 on held-out benchmark queries.",
            "When scaling to 15 thousand requests per second, we introduced horizontal autoscaling and partitioned vector indexes by tenant ID.",
            "For consistency, we implemented optimistic locking with version vectors and idempotent webhook handlers to prevent duplicate transactions.",
            "If the primary vector database experiences transient timeouts, we degrade gracefully by serving cached semantic search results and falling back to lexical search.",
            "We chose hybrid search over pure dense vector retrieval because keyword matching is critical for exact domain terms like error codes and product SKU numbers."
        ]

        for i, ans in enumerate(candidate_answers):
            ans_resp = await client.post(
                "/api/interview/answer",
                json={"session_id": session_id, "answer": ans}
            )
            assert ans_resp.status_code == 200, f"Answer turn {i+1} failed: {ans_resp.text}"
            turn_data = ans_resp.json()
            ev = turn_data["evaluation"]
            print(f"\n   Turn {i+1} -> Answer Score: {ev['score']}/100 | Level {turn_data['level']} ({turn_data['level_name']}) | Difficulty: {turn_data['difficulty']}")
            print(f"   Strengths: {ev['strengths'][:2]}")
            print(f"   Adaptive Follow-up Rationale: {ev['follow_up_reason']}")
            print(f"   Next Question: {turn_data['question']}")

        # Step 6: Audio Transcription Fallback
        print("\n6. Testing POST /api/transcribe (Audio Fallback)...")
        fake_audio = b"RIFF....WAVEfmt ....data....fake_audio_content"
        trans_resp = await client.post(
            "/api/transcribe",
            files={"file": ("candidate_speech.webm", fake_audio, "audio/webm")}
        )
        assert trans_resp.status_code == 200, f"Transcribe failed: {trans_resp.text}"
        trans = trans_resp.json()
        print("   Transcribed Speech:", trans["text"])

        # Step 7: Final Performance Report
        print("\n7. Testing POST /api/interview/report...")
        rep_resp = await client.post(
            "/api/interview/report",
            json={"session_id": session_id}
        )
        assert rep_resp.status_code == 200, f"Report failed: {rep_resp.text}"
        report = rep_resp.json()
        print(f"   Overall Interview Score: {report['overall_score']}/100")
        print(f"   Job Fit Score: {report['job_fit']}%")
        print(f"   Interview Readiness Score: {report['readiness_score']}/100 [{report['readiness_badge']}]")
        print(f"   Executive Summary: {report['summary'][:150]}...")
        print("   Competency Breakdown:")
        for comp in report["competency_scores"]:
            print(f"     - {comp['name']}: {comp['score']}/100")
        print(f"   Total Evaluated Turns in History: {len(report['history'])}")
        print("   Preparation Gaps:")
        for gap in report["preparation_gaps"]:
            print(f"     - Priority {gap['priority']}: {gap['topic']} (Why: {gap['why'][:60]}...)")

        print("\n" + "=" * 60)
        print("✅ ALL 7 END-TO-END PIPELINE STAGES PASSED WITH 100% SUCCESS!")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_e2e_test())
