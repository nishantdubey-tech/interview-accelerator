/**
 * Forma — AI Interview Accelerator
 * Client Application Logic
 */

const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

const state = {
  analysis: null,
  session: null,
  lastReport: null,
  recognition: null,
  isRecordingSTT: false,
  mediaRecorder: null,
  audioChunks: [],
  isRecordingCloud: false,
  cameraStream: null,
  speechInterval: null,
  speechSeconds: 0,
  wpm: 0,
  fillerCount: 0
};

// Common Presets for 1-Click Evaluator Testing
const PRESETS = {
  aiEng: {
    jd: `Title: Senior AI / LLM Product Engineer
Company: Synthetix AI
Location: Remote (US / Global)

About the Role:
We are looking for a Senior AI Product Engineer to lead the development of our enterprise agentic workflows, RAG pipelines, and low-latency LLM inference architectures. You will architect production microservices, evaluate model outputs, and scale our retrieval systems.

Key Responsibilities:
- Build and optimize multi-agent RAG pipelines using Python, FastAPI, and LangChain/LlamaIndex.
- Architect low-latency vector search indices using Pinecone, Qdrant, or pgvector.
- Implement continuous LLM evaluation frameworks (Ragas, TruLens) for retrieval precision and hallucination prevention.
- Deploy scalable services on AWS (ECS, Lambda) with robust telemetry, P95 latency monitoring, and graceful fallback handling.

Required Skills:
- 3+ years experience building production software with Python, FastAPI, and asynchronous workflows.
- Hands-on expertise with vector databases (Pinecone, Weaviate, or Qdrant) and chunking/embedding optimization.
- Deep understanding of prompt engineering, few-shot tuning, and agent tool execution.
- Experience with cloud infrastructure (AWS/GCP), Docker, and CI/CD pipelines.

Preferred Skills & Qualifications:
- Experience fine-tuning open-source LLMs (Llama 3, Mistral).
- Familiarity with streaming token architectures (WebSockets, Server-Sent Events).
- BS/MS in Computer Science or equivalent practical engineering track record.`,
    resume: `Nishant Dubey
AI & Full-Stack Product Engineer | nishant@example.com | San Francisco, CA

PROFESSIONAL SUMMARY:
Product-focused AI Engineer with 3+ years of experience architecting LLM agents, scalable microservices, and high-performance RAG pipelines. Reduced search latency by 28% and improved hallucination detection accuracy across multi-tenant production deployments.

TECHNICAL SKILLS:
- Languages & Frameworks: Python, FastAPI, TypeScript, React, Next.js, Node.js
- AI & LLM Stack: LangChain, LlamaIndex, OpenAI API, Gemini API, Pinecone, Qdrant, Ragas
- Infrastructure: AWS (ECS, S3, CloudWatch), Docker, PostgreSQL, Redis, GitHub Actions

WORK EXPERIENCE:
AI Engineer — Nexus Data Labs (2023 - Present)
- Architected enterprise RAG pipeline serving 40k daily queries across 1.2M internal documents; achieved 28% P95 latency reduction using hybrid BM25 + dense vector reranking.
- Built multi-agent query routing system using FastAPI and LangChain, dynamically selecting optimal model endpoints to reduce monthly API inference costs by 35%.
- Implemented automated evaluation harness using Ragas to measure context recall and faithfulness across release candidates.

Software Engineer — CloudScale Systems (2021 - 2023)
- Developed RESTful API services handling 15k req/sec with FastAPI, Celery, and PostgreSQL.
- Designed distributed caching tier using Redis, reducing database CPU load by 40%.
- Led containerization migration to AWS ECS with zero-downtime deployment pipelines.

KEY PROJECTS:
- Agentic SQL Assistant: Built natural language SQL translation agent with automatic schema self-correction and validation sandboxing.
- Semantic Research Copilot: Vector search document ingestion engine indexing 50k research papers with hierarchical chunking.`
  },

  fullStack: {
    jd: `Title: Senior Full-Stack Engineer
Company: FinFlow Systems

About the Role:
We need a Senior Full-Stack Software Engineer to build our next-generation financial workflow application. You will take complete ownership of user-facing interfaces and backend business logic.

Key Responsibilities:
- Build responsive, accessible frontends using Next.js, React, and TypeScript.
- Architect high-throughput backend APIs using Node.js or Python with PostgreSQL and Redis.
- Maintain high test coverage (unit, integration, and E2E with Playwright).
- Collaborate with product designers to ship intuitive financial data visualizations.

Requirements:
- 4+ years full-stack development experience with React and TypeScript.
- Deep expertise with relational databases (PostgreSQL), index optimization, and transaction safety.
- Experience building secure authentication flows, OAuth, and RBAC systems.`,
    resume: `Alex Rivera
Senior Full-Stack Engineer | alex.rivera@example.com

SUMMARY:
Full-stack software engineer with 4+ years specializing in React, TypeScript, Next.js, and Node.js microservices. Proven history of shipping high-reliability fintech products.

SKILLS:
TypeScript, React, Next.js, Node.js, PostgreSQL, Redis, GraphQL, Docker, Tailwind CSS, Jest

EXPERIENCE:
Full-Stack Engineer — PayPulse (2022 - Present)
- Built customer dashboard using Next.js 14 and Tailwind, increasing session engagement by 22%.
- Designed idempotent webhook ingestion service processing $4M+ weekly transaction events with 99.99% uptime.
- Optimized slow PostgreSQL queries with composite indexes, reducing endpoint latency from 450ms to 65ms.`
  },

  productMgr: {
    jd: `Title: Technical AI Product Manager
Company: Vertex AI Ventures

About the Role:
Looking for a technical Product Manager to drive AI product roadmaps, define evaluation metrics, and guide our conversational AI agents from concept to market.

Responsibilities:
- Define product requirements (PRDs), customer journeys, and success KPIs for AI features.
- Partner with ML engineers to establish benchmark standards for accuracy, latency, and tone.
- Conduct quantitative user analytics and qualitative customer discovery interviews.

Requirements:
- 3+ years experience as a technical PM on data or machine learning products.
- Deep literacy in LLM capabilities, prompting strategies, and evaluation methodologies.`,
    resume: `Samantha Vance
Technical AI Product Manager | samantha.vance@example.com

SUMMARY:
Technical PM with 3.5 years shipping AI-driven SaaS products. Adept at translating complex LLM capabilities into high-retention customer workflows.

EXPERIENCE:
AI Product Manager — Cortex Solutions (2022 - Present)
- Led cross-functional team of 6 engineers to launch generative customer support copilot, achieving 42% deflection rate within 90 days.
- Established rigorous evaluation benchmarks tracking response relevance, Hallucination Rate (<2%), and CSAT (4.6/5.0).
- Directed user research interviews with 50+ enterprise stakeholders to prioritize sprint roadmaps.`
  }
};

// Escape HTML
function escapeHtml(str = '') {
  return String(str).replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[c]));
}

// API Helper
async function api(path, data) {
  const headers = { 'Content-Type': 'application/json' };
  const customKey = localStorage.getItem('forma_custom_api_key');
  if (customKey) {
    if (customKey.startsWith('AIzaSy')) {
      headers['X-Gemini-Key'] = customKey;
    } else if (customKey.startsWith('sk-')) {
      headers['X-OpenAI-Key'] = customKey;
    } else {
      headers['X-Gemini-Key'] = customKey;
    }
  }
  const resp = await fetch(path, {
    method: 'POST',
    headers: headers,
    body: JSON.stringify(data)
  });
  const json = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(json.detail || `Request failed with HTTP ${resp.status}`);
  }
  return json;
}

// UI State & View Switcher
function showView(viewId) {
  $$('.view').forEach(v => v.classList.remove('active'));
  $$('.nav-tab').forEach(t => t.classList.remove('active'));
  
  const targetView = $(`#${viewId}`);
  if (targetView) targetView.classList.add('active');
  
  const targetTab = $(`button[data-view="${viewId}"]`);
  if (targetTab) targetTab.classList.add('active');

  const titles = {
    setupView: 'Interview Preparation & Inputs',
    analysisView: 'Role & Candidate Fit Assessment',
    interviewView: 'AI Interview Simulator (Live)',
    resultsView: 'Final Performance & Preparation Report'
  };
  $('#crumbTitle').textContent = titles[viewId] || 'Workspace';
  window.scrollTo({ top: 0, behavior: 'smooth' });

  if (viewId === 'interviewView') {
    const noSess = $('#noSessionBanner');
    if (noSess) {
      if (!state.session) {
        noSess.classList.remove('hidden');
      } else {
        noSess.classList.add('hidden');
      }
    }
  }
}

function busy(show, title = 'Working...', subtitle = 'Please keep this tab open') {
  $('#busyOverlay').classList.toggle('hidden', !show);
  $('#busyTitle').textContent = title;
  $('#busySubtitle').textContent = subtitle;
}

function showError(id, msg) {
  const el = $(id);
  if (!el) return;
  el.textContent = msg;
  el.classList.remove('hidden');
}

function clearError(id) {
  const el = $(id);
  if (!el) return;
  el.classList.add('hidden');
  el.textContent = '';
}

// Initialize Health Check
async function checkHealth() {
  try {
    const res = await fetch('/api/health');
    const data = await res.json();
    if (data.status === 'ok') {
      const isConfigured = data.ai_configured;
      const provider = data.provider || 'gemini';
      const model = data.model || 'gemini-2.5-flash';
      
      $('#providerLabel').textContent = `${provider.toUpperCase()} AI ${isConfigured ? '(Active)' : '(Demo Mode)'}`;
      $('#providerSub').textContent = isConfigured ? `Model: ${model}` : 'Add API key for live AI';
      const dot = $('.status-dot');
      if (dot) dot.classList.toggle('active', isConfigured);
    }
  } catch (e) {
    console.warn('Health check failed:', e);
  }
}

// Attach Event Listeners
document.addEventListener('DOMContentLoaded', () => {
  checkHealth();

  // Navigation tab clicks
  $$('.nav-tab').forEach(tab => {
    tab.addEventListener('click', async () => {
      const viewId = tab.dataset.view;
      if (viewId === 'resultsView' && !state.lastReport) {
        alert('Complete at least one interview question in the Simulator first to generate your report.');
        return;
      }
      if (viewId === 'interviewView' && !state.session) {
        await ensureAndStartInterview();
        return;
      }
      showView(viewId);
    });
  });

  // Help Modal
  $('#helpBtn').addEventListener('click', () => $('#helpModal').classList.remove('hidden'));
  $('#closeHelpModal').addEventListener('click', () => $('#helpModal').classList.add('hidden'));

  // Custom API Key Modal & Persistence
  function updateApiKeyUI() {
    const key = localStorage.getItem('forma_custom_api_key') || '';
    const btn = $('#apiKeyModalBtn');
    const label = $('#apiKeyBtnLabel');
    if (btn && label) {
      if (key) {
        btn.classList.add('active-key');
        label.textContent = 'API Key (Active)';
        const provLabel = $('#providerLabel');
        const provSub = $('#providerSub');
        if (provLabel) provLabel.textContent = key.startsWith('sk-') ? 'OpenAI Live' : 'Gemini AI Studio (Active)';
        if (provSub) provSub.textContent = 'Key: ' + key.slice(0, 6) + '...' + key.slice(-4);
      } else {
        btn.classList.remove('active-key');
        label.textContent = 'API Key';
      }
    }
  }

  updateApiKeyUI();

  if ($('#apiKeyModalBtn')) {
    $('#apiKeyModalBtn').addEventListener('click', () => {
      const key = localStorage.getItem('forma_custom_api_key') || '';
      $('#customApiKeyInput').value = key;
      const notice = $('#apiKeyModalNotice');
      if (notice) notice.style.display = 'none';
      $('#apiKeyModal').classList.remove('hidden');
    });
  }

  if ($('#closeApiKeyModal')) {
    $('#closeApiKeyModal').addEventListener('click', () => {
      $('#apiKeyModal').classList.add('hidden');
    });
  }

  if ($('#saveApiKeyBtn')) {
    $('#saveApiKeyBtn').addEventListener('click', () => {
      const val = ($('#customApiKeyInput').value || '').trim();
      if (!val) {
        localStorage.removeItem('forma_custom_api_key');
        updateApiKeyUI();
        $('#apiKeyModal').classList.add('hidden');
        return;
      }
      localStorage.setItem('forma_custom_api_key', val);
      updateApiKeyUI();
      const notice = $('#apiKeyModalNotice');
      if (notice) {
        notice.style.display = 'block';
        notice.style.background = 'rgba(16, 185, 129, 0.15)';
        notice.style.color = '#a7f3d0';
        notice.textContent = 'Custom key applied! Future calls will use this key.';
      }
      setTimeout(() => $('#apiKeyModal').classList.add('hidden'), 800);
    });
  }

  if ($('#clearApiKeyBtn')) {
    $('#clearApiKeyBtn').addEventListener('click', () => {
      localStorage.removeItem('forma_custom_api_key');
      $('#customApiKeyInput').value = '';
      updateApiKeyUI();
      const notice = $('#apiKeyModalNotice');
      if (notice) {
        notice.style.display = 'block';
        notice.style.background = 'rgba(239, 68, 68, 0.15)';
        notice.style.color = '#fca5a5';
        notice.textContent = 'Custom key removed. Built-in engine will be used.';
      }
      setTimeout(() => $('#apiKeyModal').classList.add('hidden'), 800);
    });
  }

  // Quick Presets
  $('#presetAiEng').addEventListener('click', () => loadPreset('aiEng'));
  $('#presetFullStack').addEventListener('click', () => loadPreset('fullStack'));
  $('#presetProductMgr').addEventListener('click', () => loadPreset('productMgr'));

  // Character counts
  $('#jd').addEventListener('input', updateCharCounts);
  $('#resume').addEventListener('input', updateCharCounts);

  // File Upload Handlers
  $('#jdFile').addEventListener('change', e => handleFileUpload(e.target, '#jd', '#jdUploadStatus'));
  $('#resumeFile').addEventListener('change', e => handleFileUpload(e.target, '#resume', '#resumeUploadStatus'));

  // Drag and Drop
  setupDropzone('#jdDropzone', '#jdFile');
  setupDropzone('#resumeDropzone', '#resumeFile');

  // Analyze Button
  $('#analyzeBtn').addEventListener('click', handleAnalyzeProfile);

  // Subtabs in Analysis View
  $$('.subtab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $$('.subtab-btn').forEach(b => b.classList.remove('active'));
      $$('.subtab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      $(`#${btn.dataset.sub}`).classList.add('active');
    });
  });

  // Launch Interview Buttons
  $('#launchInterviewFromAnalysis').addEventListener('click', startInterviewFlow);
  if ($('#launchInterviewBottom')) {
    $('#launchInterviewBottom').addEventListener('click', startInterviewFlow);
  }
  if ($('#quickStartInterviewBtn')) {
    $('#quickStartInterviewBtn').addEventListener('click', ensureAndStartInterview);
  }
  if ($('#prepareQuestionsBtn')) {
    $('#prepareQuestionsBtn').addEventListener('click', ensureAndStartInterview);
  }

  // TTS Controls
  $('#speakBtn').addEventListener('click', () => speakQuestionText());
  $('#stopSpeakBtn').addEventListener('click', () => stopSpeech());

  // STT Microphone Control
  $('#micBtn').addEventListener('click', toggleSpeechRecognition);

  // Audio Recording Backend Fallback
  $('#cloudRecordBtn').addEventListener('click', toggleCloudAudioRecord);

  // Clear Answer
  $('#clearAnswerBtn').addEventListener('click', () => {
    $('#answerText').value = '';
    resetSpeechAnalytics();
  });

  // Submit Answer
  $('#submitAnswerBtn').addEventListener('click', handleSubmitAnswer);

  // Finish Interview
  $('#btnFinishInterview').addEventListener('click', generateFinalReport);

  // Webcam Preview
  $('#toggleCamBtn').addEventListener('click', toggleWebcam);

  // Report Actions
  $('#printReportBtn').addEventListener('click', () => window.print());
  $('#startNewInterviewBtn').addEventListener('click', () => {
    state.session = null;
    showView('setupView');
  });

  // Live text input analytics
  $('#answerText').addEventListener('input', updateLiveAnswerAnalytics);
});

// Load Preset
function loadPreset(key) {
  const p = PRESETS[key];
  if (!p) return;
  $('#jd').value = p.jd;
  $('#resume').value = p.resume;
  $('#jdUploadStatus').textContent = 'Loaded sample job profile';
  $('#resumeUploadStatus').textContent = 'Loaded sample candidate profile';
  updateCharCounts();
}

function updateCharCounts() {
  $('#jdCharCount').textContent = `${$('#jd').value.length.toLocaleString()} characters`;
  $('#resumeCharCount').textContent = `${$('#resume').value.length.toLocaleString()} characters`;
}

// File Upload Handler
async function handleFileUpload(input, targetTextarea, statusElId) {
  const file = input.files?.[0];
  if (!file) return;

  if (file.size > 8 * 1024 * 1024) {
    alert('File size exceeds the 8 MB maximum limit.');
    input.value = '';
    return;
  }

  const formData = new FormData();
  formData.append('file', file);
  input.disabled = true;
  $(statusElId).textContent = `Uploading & reading ${file.name}...`;

  try {
    const res = await fetch('/api/extract', { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to extract text from file.');

    $(targetTextarea).value = data.text;
    $(statusElId).textContent = `Loaded ${data.filename} (${data.character_count.toLocaleString()} chars)`;
    updateCharCounts();
  } catch (err) {
    alert(err.message || 'Could not parse uploaded file.');
    $(statusElId).textContent = 'Upload failed';
  } finally {
    input.disabled = false;
  }
}

// Drag & Drop Setup
function setupDropzone(dropzoneSelector, fileInputSelector) {
  const zone = $(dropzoneSelector);
  const fileInput = $(fileInputSelector);
  if (!zone || !fileInput) return;

  ['dragenter', 'dragover'].forEach(eventName => {
    zone.addEventListener(eventName, e => {
      e.preventDefault();
      zone.classList.add('drag-over');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    zone.addEventListener(eventName, e => {
      e.preventDefault();
      zone.classList.remove('drag-over');
    });
  });

  zone.addEventListener('drop', e => {
    const files = e.dataTransfer?.files;
    if (files && files.length > 0) {
      fileInput.files = files;
      fileInput.dispatchEvent(new Event('change'));
    }
  });
}

// Analyze Profile
async function handleAnalyzeProfile() {
  clearError('#setupError');
  const jd = $('#jd').value.trim();
  const resume = $('#resume').value.trim();

  if (jd.length < 40 || resume.length < 40) {
    showError('#setupError', 'Please provide at least 40 characters for both the Job Description and Candidate Resume.');
    return;
  }

  $('#analyzeBtn').disabled = true;
  busy(true, 'Analyzing Profile & Competencies...', 'Comparing job description expectations with candidate resume evidence...');

  try {
    const result = await api('/api/analyze', { jd, resume });
    state.analysis = result;
    renderAnalysisView(result);
    showView('analysisView');
  } catch (e) {
    showError('#setupError', e.message);
  } finally {
    busy(false);
    $('#analyzeBtn').disabled = false;
  }
}

// Render Analysis Dashboard
function renderAnalysisView(data) {
  // 1. Job Fit Hero
  const fitScore = data.job_fit || 0;
  $('#fitScoreVal').textContent = `${fitScore}%`;
  
  const statusBadge = $('#fitStatusBadge');
  if (fitScore >= 80) {
    statusBadge.textContent = 'Strong Profile Match (80%+)';
    statusBadge.className = 'fit-status-badge cat-strong';
  } else if (fitScore >= 65) {
    statusBadge.textContent = 'Moderate Match — Targeted Practice Advised';
    statusBadge.className = 'fit-status-badge cat-partial';
  } else {
    statusBadge.textContent = 'Significant Gaps — Intensive Prep Needed';
    statusBadge.className = 'fit-status-badge cat-weak';
  }

  if (data.fit_rationale) {
    $('#fitRationaleText').textContent = data.fit_rationale;
  }

  // 2. Dimensions Grid
  const dimsGrid = $('#fitDimensionsGrid');
  dimsGrid.innerHTML = (data.fit_dimensions || []).map(d => {
    const catClass = d.score >= 75 ? 'cat-strong' : (d.score >= 50 ? 'cat-partial' : 'cat-weak');
    return `
      <div class="dimension-card">
        <div class="dim-header">
          <span class="dim-name">${escapeHtml(d.name)}</span>
          <span class="dim-score">${Math.round(d.score)}%</span>
        </div>
        <div class="dim-bar">
          <div class="dim-bar-fill" style="width: ${Math.max(5, Math.min(100, d.score))}%"></div>
        </div>
        <span class="dim-category-tag ${catClass}">${escapeHtml(d.category || 'Evaluated')}</span>
        <p class="dim-notes"><b>Evidence:</b> ${escapeHtml(d.evidence || 'Analyzed from text')}</p>
        ${d.gaps ? `<p class="dim-notes" style="color:#fca5a5;margin-top:4px;"><b>Gaps:</b> ${escapeHtml(d.gaps)}</p>` : ''}
      </div>
    `;
  }).join('');

  // 3. Role Breakdown
  const role = data.role || {};
  $('#roleGrid').innerHTML = `
    <div class="info-block span-2">
      <h3>💼 Target Role</h3>
      <h2 style="font-size: 22px; margin-bottom: 8px;">${escapeHtml(role.role_title || 'Target Role')}</h2>
      <p style="color: var(--text-muted); font-size: 13px;">${escapeHtml((role.experience_expectations || []).join(' · '))}</p>
    </div>
    <div class="info-block">
      <h3>📋 Core Responsibilities</h3>
      <ul class="bullet-list">
        ${(role.responsibilities || []).map(r => `<li>${escapeHtml(r)}</li>`).join('')}
      </ul>
    </div>
    <div class="info-block">
      <h3>🔑 Required Skills</h3>
      <div class="chip-container">
        ${(role.required_skills || []).map(s => `<span class="chip chip-green">${escapeHtml(s)}</span>`).join('')}
      </div>
      <h3 style="margin-top: 16px;">🌟 Preferred Skills</h3>
      <div class="chip-container">
        ${(role.preferred_skills || []).map(s => `<span class="chip">${escapeHtml(s)}</span>`).join('')}
      </div>
    </div>
    <div class="info-block">
      <h3>⚙️ Technical Competencies</h3>
      <div class="chip-container">
        ${(role.technical_competencies || []).map(c => `<span class="chip">${escapeHtml(c)}</span>`).join('')}
      </div>
      <h3 style="margin-top: 16px;">🧠 Important Concepts</h3>
      <div class="chip-container">
        ${(role.important_concepts || []).map(k => `<span class="chip">${escapeHtml(k)}</span>`).join('')}
      </div>
    </div>
    <div class="info-block">
      <h3>🤝 Behavioural Competencies</h3>
      <ul class="bullet-list">
        ${(role.behavioral_competencies || []).map(b => `<li>${escapeHtml(b)}</li>`).join('')}
      </ul>
    </div>
  `;

  // 4. Candidate Breakdown
  const cand = data.candidate || {};
  $('#candidateGrid').innerHTML = `
    <div class="info-block">
      <h3>✅ Demonstrated Strengths</h3>
      <ul class="bullet-list">
        ${(cand.strengths || []).map(s => `<li>${escapeHtml(s)}</li>`).join('')}
      </ul>
    </div>
    <div class="info-block">
      <h3>⚠️ Missing Skills & Weak Areas</h3>
      <ul class="bullet-list">
        ${(cand.missing_skills || []).map(m => `<li style="color:#fca5a5;">${escapeHtml(m)}</li>`).join('')}
        ${(cand.weak_areas || []).map(w => `<li style="color:#fca5a5;">${escapeHtml(w)}</li>`).join('')}
      </ul>
    </div>
    <div class="info-block probe-card span-2">
      <h3>🎯 Resume Claims to Probe (Interviewer Target)</h3>
      <p style="font-size: 13px; color: var(--text-main); margin-bottom: 10px;">The AI interviewer will actively challenge and probe these claims during simulation:</p>
      <ul class="bullet-list">
        ${(cand.claims_to_probe || []).map(c => `<li><b>Probe:</b> ${escapeHtml(c)}</li>`).join('')}
      </ul>
    </div>
    <div class="info-block">
      <h3>💼 Key Projects & Achievements</h3>
      <ul class="bullet-list">
        ${(cand.relevant_projects || []).map(p => `<li><b>Project:</b> ${escapeHtml(p)}</li>`).join('')}
        ${(cand.achievements || []).map(a => `<li><b>Achievement:</b> ${escapeHtml(a)}</li>`).join('')}
      </ul>
    </div>
    <div class="info-block">
      <h3>📚 Recommended Preparation Areas</h3>
      <ul class="bullet-list">
        ${(cand.preparation_areas || []).map(p => `<li>${escapeHtml(p)}</li>`).join('')}
      </ul>
    </div>
  `;
}

// Start Interview Flow
async function startInterviewFlow() {
  if (!state.analysis) {
    await ensureAndStartInterview();
    return;
  }

  busy(true, 'Initializing Adaptive Interview Simulator...', 'Formulating candidate-specific opening question...');
  try {
    const session = await api('/api/interview/start', { analysis: state.analysis });
    state.session = session;
    $('#interviewActiveDot').classList.remove('hidden');
    const noSess = $('#noSessionBanner');
    if (noSess) noSess.classList.add('hidden');
    showView('interviewView');
    setInterviewQuestion(session);
    speakQuestionText();
  } catch (e) {
    alert(e.message || 'Could not start interview session.');
  } finally {
    busy(false);
  }
}

// Automatically analyze profile (if needed) and formulate opening questions
async function ensureAndStartInterview() {
  if (state.session) {
    showView('interviewView');
    return;
  }

  if (state.analysis) {
    await startInterviewFlow();
    return;
  }

  let jd = ($('#jd')?.value || '').trim();
  let resume = ($('#resume')?.value || '').trim();

  // If inputs are empty, load the default AI / RAG Engineer preset immediately!
  if (jd.length < 40 || resume.length < 40) {
    loadPreset('aiEng');
    jd = $('#jd').value.trim();
    resume = $('#resume').value.trim();
  }

  busy(true, 'Preparing Interview Session...', 'Analyzing role requirements and formulating candidate-specific opening question...');
  try {
    const analysis = await api('/api/analyze', { jd, resume });
    state.analysis = analysis;
    renderAnalysisView(analysis);

    const session = await api('/api/interview/start', { analysis });
    state.session = session;
    $('#interviewActiveDot').classList.remove('hidden');
    const noSess = $('#noSessionBanner');
    if (noSess) noSess.classList.add('hidden');
    showView('interviewView');
    setInterviewQuestion(session);
    speakQuestionText();
  } catch (e) {
    alert(e.message || 'Could not formulate interview questions.');
    showView('setupView');
  } finally {
    busy(false);
  }
}

// Display Question & State in Simulator
function setInterviewQuestion(q) {
  $('#questionText').textContent = q.question;
  $('#questionCompetency').textContent = q.competency || 'Role Fit & Ownership';
  $('#whyQuestionText').textContent = q.why_this_question ? `Why this question: ${q.why_this_question}` : 'Personalized to your resume and target role.';

  // Level & Turn Pills
  const lvl = q.level || 1;
  const levelNames = ['', 'SCREENING', 'COMPETENCY', 'DEEP-DIVE'];
  $('#levelPill').textContent = `LEVEL ${lvl}: ${q.level_name ? q.level_name.toUpperCase() : levelNames[lvl]}`;
  $('#turnPill').textContent = `Question ${q.turn || 1}`;
  $('#diffPill').textContent = `${(q.difficulty || 'moderate').toUpperCase()} DIFFICULTY`;

  // Stage Ribbon update
  $('#stage1Tag').classList.toggle('active', lvl === 1);
  $('#stage2Tag').classList.toggle('active', lvl === 2);
  $('#stage3Tag').classList.toggle('active', lvl === 3);

  // Progress Bar
  const pct = q.progress || Math.min(100, Math.round(((q.turn || 1) - 1) / 9 * 100));
  $('#interviewProgressBar').style.width = `${Math.max(10, pct)}%`;
  $('#interviewProgressText').textContent = `${pct}%`;

  // Reset answer field & hints
  $('#answerText').value = '';
  $('#transcriptLiveText').textContent = 'Voice recognition ready. Click "Start Speaking" or type below.';
  resetSpeechAnalytics();
}

// TTS Speech Synthesis
function speakQuestionText() {
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  
  const text = $('#questionText').textContent;
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 0.98;
  u.pitch = 1.0;

  u.onstart = () => {
    $('#aiStatusText').textContent = 'Interviewer is speaking...';
    $('#aiOrb').classList.add('speaking');
  };

  u.onend = () => {
    $('#aiStatusText').textContent = 'Listening for your answer';
    $('#aiOrb').classList.remove('speaking');
  };

  u.onerror = () => {
    $('#aiStatusText').textContent = 'Ready for candidate response';
    $('#aiOrb').classList.remove('speaking');
  };

  window.speechSynthesis.speak(u);
}

function stopSpeech() {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
  $('#aiOrb').classList.remove('speaking');
  $('#aiStatusText').textContent = 'Ready';
}

// STT: Primary Browser Web Speech API
function toggleSpeechRecognition() {
  if (state.isRecordingSTT) {
    stopSpeechRecognition();
    return;
  }

  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Rec) {
    alert('Browser speech recognition is not supported in this browser. Please use Chrome/Edge or use the "Cloud Audio Fallback" button.');
    return;
  }

  const rec = new Rec();
  rec.lang = 'en-US';
  rec.interimResults = true;
  rec.continuous = true;

  rec.onresult = e => {
    let finalStr = '', interimStr = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const text = e.results[i][0].transcript;
      if (e.results[i].isFinal) finalStr += text + ' ';
      else interimStr += text;
    }

    if (finalStr) {
      const current = $('#answerText').value;
      $('#answerText').value = (current ? current.trim() + ' ' : '') + finalStr.trim();
    }
    
    $('#transcriptLiveText').textContent = (($('#answerText').value + ' ' + interimStr).trim() || 'Listening...');
    updateLiveAnswerAnalytics();
  };

  rec.onerror = e => {
    console.warn('Speech recognition error:', e);
    stopSpeechRecognition();
    $('#transcriptLiveText').textContent = `Mic error (${e.error}). You can type your answer directly.`;
  };

  rec.onend = () => {
    if (state.isRecordingSTT) {
      try { rec.start(); } catch (_) {}
    }
  };

  state.recognition = rec;
  state.isRecordingSTT = true;
  $('#micBtn').classList.add('recording');
  $('#micBtnText').textContent = 'Stop Speaking';
  $('#sttStatusDot').classList.add('listening');
  $('#transcriptLiveText').textContent = 'Listening to your microphone...';

  startSpeechTimer();

  try {
    rec.start();
  } catch (err) {
    stopSpeechRecognition();
    alert('Could not start microphone: ' + err.message);
  }
}

function stopSpeechRecognition() {
  state.isRecordingSTT = false;
  if (state.recognition) {
    state.recognition.stop();
    state.recognition = null;
  }
  $('#micBtn').classList.remove('recording');
  $('#micBtnText').textContent = 'Start Speaking';
  $('#sttStatusDot').classList.remove('listening');
  stopSpeechTimer();
}

// Fallback: Cloud Audio Recording via MediaRecorder + /api/transcribe
async function toggleCloudAudioRecord() {
  if (state.isRecordingCloud) {
    stopCloudAudioRecord();
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.audioChunks = [];
    const mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = e => {
      if (e.data.size > 0) state.audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(state.audioChunks, { type: 'audio/webm' });
      stream.getTracks().forEach(t => t.stop());

      // Send to /api/transcribe
      const fd = new FormData();
      fd.append('file', audioBlob, 'recording.webm');
      $('#transcriptLiveText').textContent = 'Transcribing audio via Cloud AI...';

      try {
        const res = await fetch('/api/transcribe', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail);
        
        const current = $('#answerText').value;
        $('#answerText').value = (current ? current.trim() + ' ' : '') + data.text;
        $('#transcriptLiveText').textContent = 'Audio transcribed successfully!';
        updateLiveAnswerAnalytics();
      } catch (err) {
        alert('Cloud transcription error: ' + err.message);
        $('#transcriptLiveText').textContent = 'Transcription failed. Please type answer.';
      }
    };

    mediaRecorder.start();
    state.mediaRecorder = mediaRecorder;
    state.isRecordingCloud = true;
    $('#cloudRecordBtn').classList.add('recording');
    $('#cloudRecordBtn').querySelector('span').textContent = '⏹ Stop Cloud Recording';
    $('#transcriptLiveText').textContent = 'Recording audio for cloud transcription...';
    startSpeechTimer();
  } catch (err) {
    alert('Microphone access denied or unavailable: ' + err.message);
  }
}

function stopCloudAudioRecord() {
  state.isRecordingCloud = false;
  if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
    state.mediaRecorder.stop();
  }
  $('#cloudRecordBtn').classList.remove('recording');
  $('#cloudRecordBtn').querySelector('span').textContent = '☁️ Cloud Audio Fallback';
  stopSpeechTimer();
}

// Speech Timer & Analytics (WPM, Fillers)
function startSpeechTimer() {
  state.speechSeconds = 0;
  clearInterval(state.speechInterval);
  state.speechInterval = setInterval(() => {
    state.speechSeconds++;
    const m = String(Math.floor(state.speechSeconds / 60)).padStart(2, '0');
    const s = String(state.speechSeconds % 60).padStart(2, '0');
    $('#speechTimer').textContent = `${m}:${s}`;
    updateLiveAnswerAnalytics();
  }, 1000);
}

function stopSpeechTimer() {
  clearInterval(state.speechInterval);
}

function resetSpeechAnalytics() {
  stopSpeechTimer();
  state.speechSeconds = 0;
  $('#speechTimer').textContent = '00:00';
  $('#speechWpm').textContent = '0 WPM';
  $('#fillerCount').textContent = '0';
}

function updateLiveAnswerAnalytics() {
  const text = $('#answerText').value.trim();
  const words = text ? text.split(/\s+/).length : 0;

  // WPM
  const minutes = Math.max(0.1, state.speechSeconds / 60);
  const wpm = Math.round(words / minutes);
  $('#speechWpm').textContent = `${wpm > 0 && wpm < 300 ? wpm : 0} WPM`;

  // Filler words
  const fillers = ['um', 'uh', 'like', 'basically', 'actually', 'you know', 'sort of'];
  let count = 0;
  const lower = text.toLowerCase();
  fillers.forEach(f => {
    const matches = lower.match(new RegExp(`\\b${f}\\b`, 'g'));
    if (matches) count += matches.length;
  });
  $('#fillerCount').textContent = count;
}

// Webcam Preview Toggle
async function toggleWebcam() {
  const video = $('#webcamVideo');
  const placeholder = $('#webcamPlaceholder');
  const btn = $('#toggleCamBtn');

  if (state.cameraStream) {
    state.cameraStream.getTracks().forEach(t => t.stop());
    state.cameraStream = null;
    video.classList.add('hidden');
    placeholder.classList.remove('hidden');
    btn.textContent = 'Turn On';
    btn.classList.remove('active');
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    state.cameraStream = stream;
    video.srcObject = stream;
    video.classList.remove('hidden');
    placeholder.classList.add('hidden');
    btn.textContent = 'Turn Off';
    btn.classList.add('active');
  } catch (err) {
    alert('Could not access camera: ' + err.message);
  }
}

// Submit Answer
async function handleSubmitAnswer() {
  clearError('#answerError');
  const answer = $('#answerText').value.trim();

  if (!state.session) {
    showError('#answerError', 'No active interview question loaded. Formulating your personalized question now...');
    await ensureAndStartInterview();
    return;
  }

  if (!answer) {
    showError('#answerError', 'Please provide a response before submitting (either speak or type).');
    return;
  }

  if (state.isRecordingSTT) stopSpeechRecognition();
  if (state.isRecordingCloud) stopCloudAudioRecord();

  $('#submitAnswerBtn').disabled = true;
  $('#aiStatusText').textContent = 'Evaluating your answer...';
  busy(true, 'Evaluating Response & Formulating Follow-up...', 'Analyzing answer reasoning and adapting question difficulty...');

  try {
    const result = await api('/api/interview/answer', {
      session_id: state.session.session_id,
      answer
    });

    state.session = { ...state.session, ...result };
    setInterviewQuestion(result);

    // Show micro-eval card
    const ev = result.evaluation;
    $('#evalScoreBadge').textContent = `${ev.score || 75}/100`;
    $('#evalCompBadge').textContent = ev.competency || 'Evaluated';
    $('#evalFeedbackText').textContent = ev.evidence || (ev.strengths || []).join('; ');
    $('#evalFollowupReason').textContent = `Adaptive Rationale: ${ev.follow_up_reason || 'Next question targets details from your answer.'}`;
    $('#microEvalCard').classList.remove('hidden');

    speakQuestionText();
  } catch (e) {
    showError('#answerError', e.message);
  } finally {
    busy(false);
    $('#submitAnswerBtn').disabled = false;
  }
}

// Generate Final Report
async function generateFinalReport() {
  if (!state.session) {
    alert('No active interview session.');
    return;
  }

  stopSpeech();
  busy(true, 'Synthesizing Performance Report...', 'Computing interview readiness score and personalized preparation plan...');

  try {
    const report = await api('/api/interview/report', {
      session_id: state.session.session_id
    });
    state.lastReport = report;
    $('#interviewActiveDot').classList.add('hidden');
    renderReportView(report);
    showView('resultsView');
  } catch (e) {
    alert(e.message || 'Could not generate report.');
  } finally {
    busy(false);
  }
}

// Render Results & Readiness Report
function renderReportView(rep) {
  const container = $('#reportContent');
  const badgeClass = rep.readiness_score >= 85 ? 'cat-strong' : (rep.readiness_score >= 75 ? 'cat-strong' : (rep.readiness_score >= 60 ? 'cat-partial' : 'cat-weak'));

  container.innerHTML = `
    <!-- High-level Summary Cards -->
    <div class="summary-score-cards">
      <div class="score-card">
        <span class="score-title">INTERVIEW SCORE</span>
        <span class="big-number">${rep.overall_score ?? '—'}<small style="font-size:20px;color:var(--text-subtle);">/100</small></span>
        <span class="score-sub">From ${rep.answer_count || 0} evaluated questions</span>
      </div>

      <div class="score-card">
        <span class="score-title">JOB FIT MATCH</span>
        <span class="big-number">${rep.job_fit ?? '—'}<small style="font-size:20px;color:var(--text-subtle);">%</small></span>
        <span class="score-sub">Weighted profile alignment</span>
      </div>

      <div class="score-card" style="grid-column: span 2;">
        <span class="score-title">INTERVIEW READINESS STATUS</span>
        <div style="display:flex;align-items:center;justify-content:center;gap:12px;">
          <span class="big-number">${rep.readiness_score ?? '—'}<small style="font-size:20px;color:var(--text-subtle);">/100</small></span>
          <span class="badge-lg ${badgeClass}">${escapeHtml(rep.readiness_badge || rep.readiness_status)}</span>
        </div>
        <span class="score-sub">Calculated: 70% Interview Performance + 30% Role Fit Match</span>
      </div>
    </div>

    <!-- Executive Summary -->
    <div class="executive-summary-card">
      <h3>Executive Coaching Summary</h3>
      <p>${escapeHtml(rep.summary || 'Solid candidate performance with clear domain strengths.')}</p>
      ${rep.readiness_rationale ? `<p style="margin-top:10px;font-style:italic;color:var(--mint-accent);"><b>Readiness Rationale:</b> ${escapeHtml(rep.readiness_rationale)}</p>` : ''}
    </div>

    <!-- 7 Core Competency Scores -->
    <div class="competency-bars-card">
      <h3 style="font-family:var(--font-display);font-size:18px;color:var(--mint-accent);margin-bottom:16px;">
        Core Competency Breakdown
      </h3>
      <div class="competency-list">
        ${(rep.competency_scores || []).map(c => `
          <div class="competency-item">
            <div class="comp-header">
              <span>${escapeHtml(c.name)}</span>
              <span class="comp-score">${Math.round(c.score)}/100</span>
            </div>
            <div class="comp-bar">
              <div class="comp-bar-fill" style="width: ${Math.max(5, Math.min(100, c.score))}%"></div>
            </div>
            <div class="comp-evidence">${escapeHtml(c.evidence || '')}</div>
          </div>
        `).join('')}
      </div>
    </div>

    <!-- Strengths & Weaknesses Grid -->
    <div class="feedback-columns">
      <div class="feedback-card strengths">
        <h3>✅ Demonstrated Strengths</h3>
        <ul class="bullet-list">
          ${(rep.strengths || []).map(s => `<li>${escapeHtml(s)}</li>`).join('')}
        </ul>
      </div>

      <div class="feedback-card weaknesses">
        <h3>⚠️ Concrete Growth Areas</h3>
        <ul class="bullet-list">
          ${(rep.weaknesses || []).map(w => `<li>${escapeHtml(w)}</li>`).join('')}
        </ul>
      </div>
    </div>

    <!-- Prioritized Preparation Gap Engine -->
    <div class="gap-engine-card">
      <h3>Prioritized Preparation Gap Engine</h3>
      <div class="gap-items-list">
        ${(rep.preparation_gaps || []).map((g, idx) => `
          <div class="gap-item">
            <div class="gap-header">
              <span class="gap-priority-pill">PRIORITY ${g.priority || (idx + 1)}</span>
              <span class="gap-topic">${escapeHtml(g.topic)}</span>
            </div>
            <div class="gap-details">
              <p><b>Why It Matters for This JD:</b> ${escapeHtml(g.why)}</p>
              ${g.what_candidate_lacks ? `<p><b>Observed Gap:</b> ${escapeHtml(g.what_candidate_lacks)}</p>` : ''}
              ${g.suggested_practice ? `<p><b>Actionable Practice:</b> ${escapeHtml(g.suggested_practice)}</p>` : ''}
              ${g.review_topics && g.review_topics.length ? `
                <div class="gap-review-tags">
                  <b>Review Topics:</b>
                  ${g.review_topics.map(t => `<span class="gap-tag">${escapeHtml(t)}</span>`).join('')}
                </div>
              ` : ''}
              ${g.practice_questions && g.practice_questions.length ? `
                <div style="margin-top:8px;font-size:12px;color:var(--text-muted);">
                  <b>Mock Practice Questions:</b>
                  <ul style="padding-left:18px;margin-top:4px;">
                    ${g.practice_questions.map(pq => `<li>${escapeHtml(pq)}</li>`).join('')}
                  </ul>
                </div>
              ` : ''}
            </div>
          </div>
        `).join('')}
      </div>
    </div>

    <!-- Question-by-Question Deep Dive -->
    <div class="question-breakdown-card">
      <h3>Question-by-Question Detailed Feedback</h3>
      ${(rep.history || []).map((h, i) => {
        const ev = h.evaluation || {};
        return `
          <div class="turn-feedback-card">
            <div class="turn-header">
              <span class="turn-tag">Question ${i + 1} · Level ${h.level || 1} (${escapeHtml(h.level_name || 'Interview')})</span>
              <span class="turn-score">Score: ${ev.score || 70}/100</span>
            </div>
            <div class="turn-q">Q: ${escapeHtml(h.question)}</div>
            <div class="turn-a"><b>Your Answer:</b> "${escapeHtml(h.answer)}"</div>
            <div class="turn-grid">
              <div class="turn-good"><b>What Was Good:</b> ${(ev.strengths || []).join('; ') || 'Direct response provided.'}</div>
              <div class="turn-better"><b>What Could Be Better:</b> ${(ev.weaknesses || []).join('; ') || 'Provide more quantitative metrics.'}</div>
              ${ev.ideal_direction ? `<div class="turn-direction"><b>Ideal Direction:</b> ${escapeHtml(ev.ideal_direction)}</div>` : ''}
            </div>
          </div>
        `;
      }).join('')}
    </div>
  `;
}
