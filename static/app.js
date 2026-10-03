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
  isCameraActive: false,
  isVirtualCamera: false,
  virtualAnimId: null,
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
    resume: `Jordan Lee
AI & Full-Stack Product Engineer | jordan.lee@example.com | Remote

PROFESSIONAL SUMMARY:
Product-focused AI Engineer with 3+ years of experience architecting LLM agents, scalable microservices, and high-performance RAG pipelines. Reduced search latency by 28% and improved hallucination detection accuracy across multi-tenant production deployments.

TECHNICAL SKILLS:
- Languages & Frameworks: Python, FastAPI, TypeScript, React, Next.js, Node.js
- AI & LLM Stack: LangChain, LlamaIndex, OpenAI API, Gemini API, Pinecone, Qdrant, Ragas
- Infrastructure: AWS (ECS, S3, CloudWatch), Docker, PostgreSQL, Redis, GitHub Actions

WORK EXPERIENCE:
AI Engineer — Northstar Analytics (2023 - Present)
- Architected an enterprise RAG pipeline serving 40k daily queries across a synthetic 1.2M-document corpus; achieved 28% P95 latency reduction using hybrid BM25 + dense vector reranking.
- Built a multi-agent query routing system using FastAPI and LangChain, dynamically selecting model endpoints to reduce monthly inference costs by 35%.
- Implemented an automated evaluation harness to measure context recall and faithfulness across release candidates.

Software Engineer — Cedar Labs (2021 - 2023)
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
  const resp = await fetch(path, {
    method: 'POST',
    headers: headers,
    body: JSON.stringify(data)
  });
  const json = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(json.detail || `Request failed with HTTP ${resp.status}`);
  }
  if (json._provider_notice) showProviderNotice(json._provider_notice);
  return json;
}

function showProviderNotice(message) {
  let notice = $('#providerFallbackNotice');
  if (!notice) {
    notice = document.createElement('div');
    notice.id = 'providerFallbackNotice';
    notice.setAttribute('role', 'status');
    notice.style.cssText = 'margin:12px 22px 0;padding:10px 14px;border:1px solid #b7791f;border-radius:8px;background:#33260f;color:#ffe2a8;font-size:13px;line-height:1.45';
    $('.main-content')?.prepend(notice);
  }
  notice.textContent = message;
  notice.classList.remove('hidden');
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
    startMeetingTimer();
    const noSess = $('#noSessionBanner');
    if (noSess) {
      if (!state.session) {
        noSess.classList.remove('hidden');
      } else {
        noSess.classList.add('hidden');
      }
    }
  } else {
    stopMeetingTimer();
  }

  if (state.isCameraActive) {
    updateVideoUI(true, state.isVirtualCamera);
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
      
      $('#providerLabel').textContent = isConfigured ? `${provider.toUpperCase()} KEY SET` : (data.demo_mode ? 'DEMO MODE' : 'AI NOT CONFIGURED');
      $('#providerSub').textContent = `Model: ${model} · credential presence only`;
      const dot = $('.status-dot');
      if (dot) dot.classList.toggle('active', isConfigured && !data.demo_mode);
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

  // Quick Presets
  $('#presetAiEng').addEventListener('click', () => loadPreset('aiEng'));
  $('#presetFullStack').addEventListener('click', () => loadPreset('fullStack'));
  $('#presetProductMgr').addEventListener('click', () => loadPreset('productMgr'));

  // Clear All Inputs button
  if ($('#clearInputsBtn')) {
    $('#clearInputsBtn').addEventListener('click', () => {
      $('#jd').value = '';
      $('#resume').value = '';
      $('#jdUploadStatus').textContent = 'No file loaded';
      $('#resumeUploadStatus').textContent = 'No file loaded';
      updateCharCounts();
      clearError('#setupError');
      const prev = $('#candidateLivePreviewCard');
      if (prev) prev.classList.add('hidden');
      state.analysis = null;
      state.session = null;
    });
  }

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

  // Meeting Dock Buttons
  if ($('#dockMicToggle')) {
    $('#dockMicToggle').addEventListener('click', () => {
      $('#micBtn').click();
    });
  }
  if ($('#dockCamToggle')) {
    $('#dockCamToggle').addEventListener('click', () => {
      $('#toggleCamBtn').click();
    });
  }
  if ($('#dockCcToggle')) {
    $('#dockCcToggle').addEventListener('click', () => {
      const cc = $('#liveCcConsole');
      const btn = $('#dockCcToggle');
      if (cc) cc.classList.toggle('hidden');
      if (btn) btn.classList.toggle('active');
      const lbl = $('#dockCcLabel');
      if (lbl) lbl.textContent = cc && cc.classList.contains('hidden') ? 'CC: OFF' : 'CC: ON';
    });
  }
  if ($('#dockNotesToggle')) {
    $('#dockNotesToggle').addEventListener('click', () => {
      const ch = $('#toggleCheatsheetBtn');
      if (ch) ch.click();
    });
  }
  if ($('#dockEndCallBtn')) {
    $('#dockEndCallBtn').addEventListener('click', () => {
      $('#btnFinishInterview').click();
    });
  }

  // Candidate Video Preview & Camera Controls
  if ($('#setupToggleCamBtn')) $('#setupToggleCamBtn').addEventListener('click', () => toggleCamera('setup'));
  if ($('#setupVirtualCamBtn')) $('#setupVirtualCamBtn').addEventListener('click', () => toggleVirtualCamera('setup'));
  if ($('#toggleCamBtn')) $('#toggleCamBtn').addEventListener('click', () => toggleCamera('interview'));
  if ($('#interviewVirtualCamBtn')) $('#interviewVirtualCamBtn').addEventListener('click', () => toggleVirtualCamera('interview'));

  // Report Actions
  $('#printReportBtn').addEventListener('click', () => window.print());
  $('#startNewInterviewBtn').addEventListener('click', () => {
    state.session = null;
    showView('setupView');
  });

  // Live text input analytics
  $('#answerText').addEventListener('input', updateLiveAnswerAnalytics);

  // Setup Candidate Live HUD & Cheatsheet
  setupCheatsheetToggle();

  // Initialize candidate preview
  updateCandidateLivePreview();
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
  updateCandidateLivePreview();
}

// Candidate Live Preview Parsing & Updating
function extractCandidatePreview(text) {
  if (!text || text.trim().length < 25) return null;

  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
  
  // 1. Candidate Name
  let name = '';
  const nameMatch = text.match(/^(?:Candidate\s+Name|Name|Full\s+Name):\s*([A-Za-z\s.'-]{2,40})(?:\r|\n|$)/mi);
  if (nameMatch) {
    name = nameMatch[1].split('\n')[0].trim();
  } else {
    for (const l of lines.slice(0, 5)) {
      const lower = l.toLowerCase();
      if (['resume', 'curriculum', 'vitae', 'summary', 'objective', 'experience', 'education', 'skills', 'contact', 'email', 'http', 'github', 'linkedin'].some(h => lower.includes(h))) {
        continue;
      }
      const cleaned = l.split(/[|•\-,/@]/)[0].trim();
      const words = cleaned.split(/\s+/);
      if (words.length >= 1 && words.length <= 4 && /^[A-Za-z\s.'-]+$/.test(cleaned) && cleaned.length >= 3) {
        name = cleaned.replace(/\b\w/g, c => c.toUpperCase());
        break;
      }
    }
  }
  if (!name) name = 'Candidate Profile';

  // 2. Initials for Avatar
  const nameParts = name.split(/\s+/).filter(Boolean);
  const initials = nameParts.length >= 2 
    ? (nameParts[0][0] + nameParts[nameParts.length - 1][0]).toUpperCase()
    : (name.slice(0, 2) || 'CP').toUpperCase();

  // 3. Headline / Title
  let headline = '';
  for (const l of lines.slice(0, 6)) {
    const lower = l.toLowerCase();
    if (['engineer', 'developer', 'architect', 'manager', 'lead', 'specialist', 'scientist', 'designer', 'analyst', 'intern'].some(k => lower.includes(k))) {
      const parts = l.split(/[|•]/);
      for (const p of parts) {
        const pClean = p.trim();
        if (['engineer', 'developer', 'architect', 'manager', 'lead', 'specialist', 'scientist', 'designer', 'analyst', 'intern'].some(k => pClean.toLowerCase().includes(k))) {
          headline = pClean.replace(/^(?:headline|title|role|position):\s*/i, '').trim() || pClean;
          break;
        }
      }
      if (headline) break;
    }
  }
  if (!headline) headline = 'Software Engineering Professional';

  // 4. Experience & Seniority
  let expText = 'Experience Evidenced';
  let badgeText = 'Mid-Level';
  const expMatch = text.match(/(\d+)\+?\s*years?/i);
  if (expMatch) {
    const yrs = parseInt(expMatch[1], 10);
    expText = `🕒 ${yrs}+ Years Exp`;
    badgeText = yrs >= 5 ? 'Senior' : (yrs >= 3 ? 'Mid-Level' : 'Foundational');
  } else if (/senior|lead|principal/i.test(headline)) {
    expText = '🕒 4+ Years (Senior)';
    badgeText = 'Senior';
  }

  // 5. Education
  let eduText = '🎓 Degree / Practical Exp';
  if (/phd/i.test(text)) eduText = '🎓 Ph.D. Level';
  else if (/master|m\.s\b|m\.tech/i.test(text)) eduText = '🎓 Master\'s Degree';
  else if (/bachelor|b\.s\b|b\.tech/i.test(text)) eduText = '🎓 Bachelor\'s Degree';

  // 6. Contact
  let contactText = '✉️ Contact Details';
  const emailMatch = text.match(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/);
  if (emailMatch) {
    contactText = `✉️ ${emailMatch[1]}`;
  }

  // 7. Recognized Skills
  const commonSkills = [
    'Python', 'JavaScript', 'TypeScript', 'React', 'Next.js', 'Node.js', 'FastAPI', 'Docker',
    'Kubernetes', 'AWS', 'GCP', 'PostgreSQL', 'Redis', 'LangChain', 'LlamaIndex', 'RAG', 'LLM',
    'PyTorch', 'TensorFlow', 'Pinecone', 'Qdrant', 'SQL', 'GraphQL', 'Tailwind', 'CI/CD', 'Git'
  ];
  const detectedSkills = commonSkills.filter(s => {
    const pattern = new RegExp(`(?<![a-zA-Z0-9_-])${s.replace('.', '\\.')}(?![a-zA-Z0-9_-])`, 'i');
    return pattern.test(text);
  });

  // 8. Key Highlight / Summary
  let highlight = '';
  for (const l of lines) {
    if (/\d+%(?:\s+reduction|\s+improvement|\s+increase|\s+faster)?|\b\d+x\b|\b\d+k\b|\$\d+/i.test(l) && l.length > 20) {
      highlight = l.replace(/^[-*•]\s*/, '');
      break;
    }
  }
  if (!highlight) {
    const sumIdx = lines.findIndex(l => /summary|overview|profile/i.test(l));
    if (sumIdx !== -1 && lines[sumIdx + 1]) {
      highlight = lines[sumIdx + 1];
    } else {
      highlight = lines.slice(1, 4).join(' ').slice(0, 160) + '...';
    }
  }

  return {
    name,
    initials,
    headline,
    badgeText,
    expText,
    eduText,
    contactText,
    skills: detectedSkills.slice(0, 7),
    highlight: highlight.slice(0, 180)
  };
}

function updateCandidateLivePreview() {
  const card = $('#candidateLivePreviewCard');
  if (!card) return;

  const text = $('#resume').value.trim();
  const preview = extractCandidatePreview(text);

  if (!preview) {
    card.classList.add('hidden');
    return;
  }

  $('#previewAvatar').textContent = preview.initials;
  $('#previewCandidateName').textContent = preview.name;
  $('#previewSeniorityBadge').textContent = preview.badgeText;
  $('#previewHeadline').textContent = preview.headline;
  $('#previewExpPill').textContent = preview.expText;
  $('#previewEduPill').textContent = preview.eduText;
  $('#previewContactPill').textContent = preview.contactText;

  const skillsContainer = $('#previewSkillsList');
  if (skillsContainer) {
    if (preview.skills.length > 0) {
      skillsContainer.innerHTML = preview.skills.map(s => `<span class="chip">${escapeHtml(s)}</span>`).join('');
      $('#previewSkillsContainer').classList.remove('hidden');
    } else {
      skillsContainer.innerHTML = '<span class="chip">General Engineering</span>';
    }
  }

  $('#previewSummaryText').textContent = preview.highlight;
  card.classList.remove('hidden');

  // Also update Candidate HUD in the interview room if present
  updateCandidateHud(preview);
}

function updateCandidateHud(preview) {
  const nameEl = $('#hudCandidateName');
  const roleEl = $('#hudCandidateRole');
  if (!nameEl) return;

  if (preview) {
    nameEl.textContent = preview.name;
    roleEl.textContent = preview.headline;
  } else if (state.analysis?.candidate) {
    const cand = state.analysis.candidate;
    nameEl.textContent = cand.candidate_name || 'Candidate Profile';
    roleEl.textContent = cand.headline || (state.analysis.role?.role_title || 'Software Engineer');
  }

  const displayName = preview?.name || state.analysis?.candidate?.candidate_name || 'Candidate';
  if ($('#setupHudCandidateName')) $('#setupHudCandidateName').textContent = displayName;
  if ($('#interviewHudCandidateName')) $('#interviewHudCandidateName').textContent = displayName;

  // Populate talking points drawer
  const cand = state.analysis?.candidate;
  if (cand) {
    const claimsList = $('#hudClaimsList');
    if (claimsList && cand.achievements?.length) {
      claimsList.innerHTML = cand.achievements.slice(0, 3).map(a => `<li>${escapeHtml(a)}</li>`).join('');
    }
    const skillsChips = $('#hudSkillsChips');
    if (skillsChips && cand.skills?.length) {
      skillsChips.innerHTML = cand.skills.slice(0, 6).map(s => `<span class="chip" style="font-size:10px; padding:2px 6px;">${escapeHtml(s)}</span>`).join('');
    }
    const prepFocus = $('#hudPrepFocus');
    if (prepFocus && cand.preparation_areas?.length) {
      prepFocus.textContent = cand.preparation_areas[0];
    }
  }
}

function setupCheatsheetToggle() {
  const btn = $('#toggleCheatsheetBtn');
  const drawer = $('#hudDrawerContent');
  const chevron = $('#hudChevron');
  if (!btn || !drawer) return;

  btn.addEventListener('click', () => {
    drawer.classList.toggle('hidden');
    if (drawer.classList.contains('hidden')) {
      chevron.style.transform = 'rotate(0deg)';
    } else {
      chevron.style.transform = 'rotate(180deg)';
    }
  });
}

let audioMeterInterval = null;
function startAudioMeter() {
  const fill = $('#hudAudioFill');
  const videoMiniMeter = $('#interviewHudMeterFill');
  const setupAudioIndicator = $('#setupHudAudioIndicator');
  if (audioMeterInterval) clearInterval(audioMeterInterval);
  audioMeterInterval = setInterval(() => {
    if (state.isRecordingSTT || state.isRecordingCloud) {
      const pct = Math.floor(Math.random() * 65) + 30;
      if (fill) fill.style.width = `${pct}%`;
      if (videoMiniMeter) videoMiniMeter.style.width = `${pct}%`;
      if (setupAudioIndicator) setupAudioIndicator.textContent = '🎙️ Voice Active';
    } else {
      if (fill) fill.style.width = '0%';
      if (videoMiniMeter) videoMiniMeter.style.width = '15%';
      if (setupAudioIndicator) setupAudioIndicator.textContent = '🎙️ Audio Normal';
      clearInterval(audioMeterInterval);
    }
  }, 180);
}

function stopAudioMeter() {
  if (audioMeterInterval) clearInterval(audioMeterInterval);
  const fill = $('#hudAudioFill');
  const videoMiniMeter = $('#interviewHudMeterFill');
  const setupAudioIndicator = $('#setupHudAudioIndicator');
  if (fill) fill.style.width = '0%';
  if (videoMiniMeter) videoMiniMeter.style.width = '15%';
  if (setupAudioIndicator) setupAudioIndicator.textContent = '🎙️ Audio Normal';
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
  const cName = cand.candidate_name || 'Candidate Profile';
  const cHead = cand.headline || (data.role?.role_title || 'Software Professional');
  const cSeniority = cand.seniority || 'Verified Profile';
  const cInitials = (cName.split(/\s+/).map(w => w[0]).join('').slice(0, 2) || 'CP').toUpperCase();

  $('#candidateGrid').innerHTML = `
    <div class="candidate-hero-card">
      <div class="candidate-hero-avatar">${escapeHtml(cInitials)}</div>
      <div class="candidate-hero-info">
        <div class="candidate-hero-top">
          <h3>${escapeHtml(cName)}</h3>
          <span class="preview-badge">${escapeHtml(cSeniority)}</span>
        </div>
        <div class="candidate-hero-headline">${escapeHtml(cHead)}</div>
        <div class="candidate-hero-metrics">
          <span class="candidate-hero-metric">🎯 Target: <b>${escapeHtml(data.role?.role_title || 'Role')}</b></span>
          <span class="candidate-hero-metric">⚡ Matched Skills: <b>${(cand.skills || []).length}</b></span>
          <span class="candidate-hero-metric">🔍 Claims to Probe: <b>${(cand.claims_to_probe || []).length}</b></span>
          <span class="candidate-hero-metric">💡 Identified Strengths: <b>${(cand.strengths || []).length}</b></span>
        </div>
      </div>
    </div>
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

let meetingTimerInterval = null;
let meetingSeconds = 0;

function startMeetingTimer() {
  stopMeetingTimer();
  meetingSeconds = 0;
  const timerEl = $('#meetingCallTimer');
  if (timerEl) timerEl.textContent = '⏱️ 00:00';
  meetingTimerInterval = setInterval(() => {
    meetingSeconds++;
    const m = String(Math.floor(meetingSeconds / 60)).padStart(2, '0');
    const s = String(meetingSeconds % 60).padStart(2, '0');
    if (timerEl) timerEl.textContent = `⏱️ ${m}:${s}`;
  }, 1000);
}

function stopMeetingTimer() {
  if (meetingTimerInterval) {
    clearInterval(meetingTimerInterval);
    meetingTimerInterval = null;
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

  // Validate user inputs strictly: do NOT auto-inject canned presets!
  if (jd.length < 25 || resume.length < 25) {
    showError('#setupError', 'Please enter your Job Description and Candidate Resume (or select one of the Quick Presets above) to start your customized interview.');
    showView('setupView');
    const jdEl = $('#jd');
    if (jdEl) jdEl.focus();
    return;
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

  // Update Live Closed-Captions subtitle ticker
  const ccText = $('#liveCcText');
  if (ccText) ccText.textContent = `"${q.question}"`;
  const ccSpeaker = $('#ccSpeakerLabel');
  if (ccSpeaker) ccSpeaker.textContent = 'Interviewer (Dr. Elena Vance)';

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
  updateCandidateHud();
}

// TTS Speech Synthesis with Equalizer Bar Animation
function speakQuestionText() {
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  
  const text = $('#questionText').textContent;
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 0.98;
  u.pitch = 1.0;

  const eq = $('#interviewerEqualizer');
  const badge = $('#evaluatorNeuralBadge');

  u.onstart = () => {
    $('#aiStatusText').textContent = 'Dr. Vance is speaking...';
    $('#aiOrb').classList.add('speaking');
    if (eq) eq.classList.add('active');
    if (badge) { badge.textContent = '● SPEAKING'; badge.style.color = '#34d399'; }
    const ccText = $('#liveCcText');
    if (ccText) ccText.textContent = `"${text}"`;
    const ccSpeaker = $('#ccSpeakerLabel');
    if (ccSpeaker) ccSpeaker.textContent = 'Interviewer (Dr. Elena Vance)';
  };

  u.onend = () => {
    $('#aiStatusText').textContent = 'Listening for your answer';
    $('#aiOrb').classList.remove('speaking');
    if (eq) eq.classList.remove('active');
    if (badge) { badge.textContent = '● NEURAL STREAM'; badge.style.color = '#6ee7b7'; }
  };

  u.onerror = () => {
    $('#aiStatusText').textContent = 'Ready for candidate response';
    $('#aiOrb').classList.remove('speaking');
    if (eq) eq.classList.remove('active');
    if (badge) { badge.textContent = '● NEURAL STREAM'; badge.style.color = '#6ee7b7'; }
  };

  window.speechSynthesis.speak(u);
}

function stopSpeech() {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
  $('#aiOrb').classList.remove('speaking');
  $('#aiStatusText').textContent = 'Ready';
  const eq = $('#interviewerEqualizer');
  if (eq) eq.classList.remove('active');
  const badge = $('#evaluatorNeuralBadge');
  if (badge) { badge.textContent = '● NEURAL STREAM'; badge.style.color = '#6ee7b7'; }
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
    
    const liveTxt = (($('#answerText').value + ' ' + interimStr).trim() || 'Listening...');
    $('#transcriptLiveText').textContent = liveTxt;

    // Live Closed Captions update
    const ccText = $('#liveCcText');
    if (ccText) ccText.textContent = `"${liveTxt}"`;
    const ccSpeaker = $('#ccSpeakerLabel');
    if (ccSpeaker) ccSpeaker.textContent = 'Candidate (Live Audio)';

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

  // Synchronize meeting dock mic toggle
  const dockMicLbl = $('#dockMicLabel');
  const dockMicBtn = $('#dockMicToggle');
  if (dockMicLbl) dockMicLbl.textContent = 'Mic Active';
  if (dockMicBtn) dockMicBtn.classList.add('active');

  startSpeechTimer();
  startAudioMeter();

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

  // Synchronize meeting dock mic toggle
  const dockMicLbl = $('#dockMicLabel');
  const dockMicBtn = $('#dockMicToggle');
  if (dockMicLbl) dockMicLbl.textContent = 'Mic On';
  if (dockMicBtn) dockMicBtn.classList.remove('active');

  stopSpeechTimer();
  stopAudioMeter();
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
    startAudioMeter();
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
  stopAudioMeter();
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

  // Live Closed-Captions subtitle update during typing
  if (text && !state.isRecordingSTT) {
    const ccText = $('#liveCcText');
    if (ccText) ccText.textContent = `"${text.slice(-140)}"`;
    const ccSpeaker = $('#ccSpeakerLabel');
    if (ccSpeaker) ccSpeaker.textContent = 'Candidate (Response)';
  }
}

// ==========================================
// Candidate Video Preview & Virtual Stream Engine
// ==========================================

function updateVideoUI(isActive, isVirtual = false) {
  state.isCameraActive = isActive;
  state.isVirtualCamera = isVirtual;

  // Setup View Elements
  const setupVideo = $('#setupWebcamVideo');
  const setupCanvas = $('#setupWebcamCanvas');
  const setupPlaceholder = $('#setupVideoPlaceholder');
  const setupHud = $('#setupVideoHud');
  const setupBtn = $('#setupToggleCamBtn');
  const setupVirtBtn = $('#setupVirtualCamBtn');
  const setupDot = $('#setupVideoStatusDot');
  const setupBadge = $('#setupVideoBadge');

  // Interview View Elements
  const intVideo = $('#webcamVideo');
  const intCanvas = $('#interviewWebcamCanvas');
  const intPlaceholder = $('#webcamPlaceholder');
  const intHud = $('#interviewVideoHud');
  const intBtn = $('#toggleCamBtn');
  const intVirtBtn = $('#interviewVirtualCamBtn');
  const intDot = $('#interviewVideoDot');
  const intBadge = $('#interviewVideoBadge');

  // Pre-flight checks
  const preLight = $('#preflightLighting');
  const preFrame = $('#preflightFraming');
  const preMic = $('#preflightMic');

  if (isActive) {
    if (setupPlaceholder) setupPlaceholder.classList.add('hidden');
    if (intPlaceholder) intPlaceholder.classList.add('hidden');
    if (setupHud) setupHud.classList.remove('hidden');
    if (intHud) intHud.classList.remove('hidden');

    if (setupDot) {
      setupDot.className = 'video-dot active ' + (isVirtual ? '' : 'live-green');
    }
    if (intDot) {
      intDot.classList.remove('hidden');
    }

    if (setupBadge) {
      setupBadge.textContent = isVirtual ? 'VIRTUAL HD' : 'LIVE 1080p';
      setupBadge.classList.add('active-badge');
    }
    if (intBadge) {
      intBadge.textContent = isVirtual ? 'VIRTUAL HD' : 'LIVE HD';
      intBadge.classList.add('active-badge');
    }

    if (setupBtn) {
      setupBtn.innerHTML = '<span>⏹ Stop Camera</span>';
      setupBtn.classList.add('active');
    }
    if (intBtn) {
      intBtn.textContent = 'Turn Off';
      intBtn.classList.add('active');
    }

    if (setupVirtBtn) {
      setupVirtBtn.classList.toggle('active', isVirtual);
    }
    if (intVirtBtn) {
      intVirtBtn.classList.toggle('active', isVirtual);
    }

    if (preLight) { preLight.textContent = 'Verified (Optimal)'; preLight.style.color = 'var(--mint-accent)'; }
    if (preFrame) { preFrame.textContent = 'Centered (Face Tracked)'; preFrame.style.color = 'var(--mint-accent)'; }
    if (preMic) { preMic.textContent = 'Active (Mic Ready)'; preMic.style.color = 'var(--mint-accent)'; }
  } else {
    // Hidden / Inactive
    if (setupVideo) setupVideo.classList.add('hidden');
    if (setupCanvas) setupCanvas.classList.add('hidden');
    if (intVideo) intVideo.classList.add('hidden');
    if (intCanvas) intCanvas.classList.add('hidden');

    if (setupPlaceholder) setupPlaceholder.classList.remove('hidden');
    if (intPlaceholder) intPlaceholder.classList.remove('hidden');
    if (setupHud) setupHud.classList.add('hidden');
    if (intHud) intHud.classList.add('hidden');

    if (setupDot) { setupDot.className = 'video-dot'; }
    if (intDot) { intDot.classList.add('hidden'); }

    if (setupBadge) { setupBadge.textContent = 'Ready'; setupBadge.classList.remove('active-badge'); }
    if (intBadge) { intBadge.textContent = 'Off'; intBadge.classList.remove('active-badge'); }

    if (setupBtn) { setupBtn.innerHTML = '<span>📹 Start Camera</span>'; setupBtn.classList.remove('active'); }
    if (intBtn) { intBtn.textContent = 'Turn On'; intBtn.classList.remove('active'); }

    if (setupVirtBtn) setupVirtBtn.classList.remove('active');
    if (intVirtBtn) intVirtBtn.classList.remove('active');

    if (preLight) { preLight.textContent = 'Optimal'; preLight.style.color = ''; }
    if (preFrame) { preFrame.textContent = 'Centered'; preFrame.style.color = ''; }
    if (preMic) { preMic.textContent = 'Detected'; preMic.style.color = ''; }
  }

  // Synchronize meeting dock camera toggle
  const dockCamLbl = $('#dockCamLabel');
  const dockCamBtn = $('#dockCamToggle');
  if (dockCamLbl) dockCamLbl.textContent = isActive ? (isVirtual ? 'Cam: Virtual' : 'Cam: Live') : 'Cam Off';
  if (dockCamBtn) dockCamBtn.classList.toggle('active', isActive);
}

async function toggleCamera(sourceView = 'setup') {
  if (state.isCameraActive && !state.isVirtualCamera) {
    stopCamera();
    return;
  }
  await startRealCamera();
}

async function toggleVirtualCamera(sourceView = 'setup') {
  if (state.isCameraActive && state.isVirtualCamera) {
    stopCamera();
    return;
  }
  startVirtualCamera();
}

async function startRealCamera() {
  stopCamera();

  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
      audio: false
    });

    state.cameraStream = stream;
    state.isVirtualCamera = false;

    const setupVideo = $('#setupWebcamVideo');
    const intVideo = $('#webcamVideo');

    if (setupVideo) {
      setupVideo.srcObject = stream;
      setupVideo.classList.remove('hidden');
      setupVideo.play().catch(() => {});
    }
    if (intVideo) {
      intVideo.srcObject = stream;
      intVideo.classList.remove('hidden');
      intVideo.play().catch(() => {});
    }

    updateVideoUI(true, false);
  } catch (err) {
    console.warn('Real webcam unavailable, engaging Virtual Candidate Video stream:', err.message);
    startVirtualCamera();
  }
}

function startVirtualCamera() {
  stopCamera();
  state.isVirtualCamera = true;

  const setupCanvas = $('#setupWebcamCanvas');
  const intCanvas = $('#interviewWebcamCanvas');
  const setupVideo = $('#setupWebcamVideo');
  const intVideo = $('#webcamVideo');

  const offscreen = document.createElement('canvas');
  offscreen.width = 640;
  offscreen.height = 360;
  const ctx = offscreen.getContext('2d');

  if (setupCanvas) {
    setupCanvas.width = 640;
    setupCanvas.height = 360;
    setupCanvas.classList.remove('hidden');
  }
  if (intCanvas) {
    intCanvas.width = 640;
    intCanvas.height = 360;
    intCanvas.classList.remove('hidden');
  }

  let stream = null;
  if (offscreen.captureStream) {
    try {
      stream = offscreen.captureStream(30);
      state.cameraStream = stream;
      if (setupVideo) {
        setupVideo.srcObject = stream;
        setupVideo.classList.remove('hidden');
        setupVideo.play().catch(() => {});
      }
      if (intVideo) {
        intVideo.srcObject = stream;
        intVideo.classList.remove('hidden');
        intVideo.play().catch(() => {});
      }
    } catch (_) {}
  }

  const startTime = Date.now();

  function loop() {
    renderVirtualVideoFrame(ctx, offscreen.width, offscreen.height, startTime);

    if (setupCanvas && !setupCanvas.classList.contains('hidden')) {
      const sCtx = setupCanvas.getContext('2d');
      sCtx.drawImage(offscreen, 0, 0);
    }
    if (intCanvas && !intCanvas.classList.contains('hidden')) {
      const iCtx = intCanvas.getContext('2d');
      iCtx.drawImage(offscreen, 0, 0);
    }

    state.virtualAnimId = requestAnimationFrame(loop);
  }

  state.virtualAnimId = requestAnimationFrame(loop);
  updateVideoUI(true, true);
}

function renderVirtualVideoFrame(ctx, w, h, startTime) {
  const elapsed = (Date.now() - startTime) / 1000;
  
  // 1. Dark Studio Gradient Background
  const grad = ctx.createLinearGradient(0, 0, w, h);
  grad.addColorStop(0, '#091512');
  grad.addColorStop(0.5, '#050c0a');
  grad.addColorStop(1, '#020504');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, w, h);

  // 2. Subtle Matrix Tech Grid
  ctx.strokeStyle = 'rgba(16, 185, 129, 0.05)';
  ctx.lineWidth = 1;
  const gridSize = 32;
  for (let x = 0; x < w; x += gridSize) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
  }
  for (let y = 0; y < h; y += gridSize) {
    ctx.beginPath(); ctx.moveTo(y, 0); ctx.lineTo(w, y); ctx.stroke();
  }

  // 3. Floating Ambient Glow Orbs
  const orb1X = w * 0.3 + Math.sin(elapsed * 0.8) * 30;
  const orb1Y = h * 0.35 + Math.cos(elapsed * 0.6) * 20;
  const orbGrad = ctx.createRadialGradient(orb1X, orb1Y, 5, orb1X, orb1Y, 140);
  orbGrad.addColorStop(0, 'rgba(16, 185, 129, 0.18)');
  orbGrad.addColorStop(1, 'transparent');
  ctx.fillStyle = orbGrad;
  ctx.fillRect(0, 0, w, h);

  // 4. Candidate Avatar Silhouette (with natural breathing & head tilt)
  const breath = Math.sin(elapsed * 2.2) * 3;
  const tilt = Math.sin(elapsed * 1.4) * 0.02;
  const centerX = w / 2;
  const centerY = h * 0.58 + breath;

  ctx.save();
  ctx.translate(centerX, centerY);
  ctx.rotate(tilt);

  // Shoulders & Body
  ctx.fillStyle = '#11221c';
  ctx.beginPath();
  ctx.ellipse(0, 110, 130, 80, 0, Math.PI, 0);
  ctx.fill();
  ctx.strokeStyle = 'rgba(16, 185, 129, 0.35)';
  ctx.lineWidth = 2;
  ctx.stroke();

  // Neck
  ctx.fillStyle = '#183027';
  ctx.fillRect(-18, 20, 36, 45);

  // Head
  ctx.fillStyle = '#1c392f';
  ctx.beginPath();
  ctx.ellipse(0, -10, 48, 60, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = 'rgba(52, 211, 153, 0.4)';
  ctx.lineWidth = 2;
  ctx.stroke();

  // Eyes (with periodic blink)
  const isBlinking = (Math.sin(elapsed * 1.8) > 0.94);
  ctx.fillStyle = '#a7f3d0';
  if (isBlinking) {
    ctx.strokeStyle = '#a7f3d0';
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(-22, -15); ctx.lineTo(-10, -15); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(10, -15); ctx.lineTo(22, -15); ctx.stroke();
  } else {
    ctx.beginPath(); ctx.ellipse(-16, -16, 5, 6, 0, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.ellipse(16, -16, 5, 6, 0, 0, Math.PI * 2); ctx.fill();
  }

  // Mouth (opens and animates when speaking)
  const isSpeaking = state.isRecordingSTT || state.isRecordingCloud;
  const mouthOpen = isSpeaking ? (4 + Math.abs(Math.sin(elapsed * 14)) * 7) : 2;
  ctx.fillStyle = '#34d399';
  ctx.beginPath();
  ctx.ellipse(0, 18, 12, mouthOpen, 0, 0, Math.PI * 2);
  ctx.fill();

  // Avatar Initials Badge on Chest
  const cName = state.analysis?.candidate?.candidate_name || ($('#previewCandidateName') ? $('#previewCandidateName').textContent : 'Candidate');
  const initials = (cName.split(/\s+/).map(w => w[0]).join('').slice(0, 2) || 'ND').toUpperCase();
  ctx.fillStyle = 'rgba(16, 185, 129, 0.9)';
  ctx.beginPath(); ctx.arc(0, 80, 18, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#06100c';
  ctx.font = 'bold 12px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(initials, 0, 80);

  ctx.restore();

  // 5. Broadcast Framing Brackets
  ctx.strokeStyle = 'rgba(52, 211, 153, 0.6)';
  ctx.lineWidth = 2;
  const bSize = 16;
  const pad = 16;
  // Top-left
  ctx.beginPath(); ctx.moveTo(pad, pad + bSize); ctx.lineTo(pad, pad); ctx.lineTo(pad + bSize, pad); ctx.stroke();
  // Top-right
  ctx.beginPath(); ctx.moveTo(w - pad - bSize, pad); ctx.lineTo(w - pad, pad); ctx.lineTo(w - pad, pad + bSize); ctx.stroke();
  // Bottom-left
  ctx.beginPath(); ctx.moveTo(pad, h - pad - bSize); ctx.lineTo(pad, h - pad); ctx.lineTo(pad + bSize, h - pad); ctx.stroke();
  // Bottom-right
  ctx.beginPath(); ctx.moveTo(w - pad - bSize, h - pad); ctx.lineTo(w - pad, h - pad); ctx.lineTo(w - pad, h - pad - bSize); ctx.stroke();

  // 6. Center Target Crosshair
  ctx.strokeStyle = 'rgba(52, 211, 153, 0.15)';
  ctx.beginPath(); ctx.moveTo(w/2 - 12, h/2); ctx.lineTo(w/2 + 12, h/2); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(w/2, h/2 - 12); ctx.lineTo(w/2, h/2 + 12); ctx.stroke();

  // 7. Live Soundwave visualization at bottom
  if (isSpeaking) {
    ctx.strokeStyle = '#34d399';
    ctx.lineWidth = 2;
    ctx.beginPath();
    const waveCount = 20;
    const waveWidth = 140;
    const waveXStart = (w - waveWidth) / 2;
    for (let i = 0; i < waveCount; i++) {
      const x = waveXStart + (i / waveCount) * waveWidth;
      const hWave = Math.sin(elapsed * 12 + i * 0.8) * 10 * Math.random();
      ctx.moveTo(x, h - 35 - hWave);
      ctx.lineTo(x, h - 35 + hWave);
    }
    ctx.stroke();
  }
}

function stopCamera() {
  if (state.cameraStream) {
    try {
      state.cameraStream.getTracks().forEach(t => t.stop());
    } catch (_) {}
    state.cameraStream = null;
  }

  if (state.virtualAnimId) {
    cancelAnimationFrame(state.virtualAnimId);
    state.virtualAnimId = null;
  }

  const setupVideo = $('#setupWebcamVideo');
  const intVideo = $('#webcamVideo');
  if (setupVideo) { setupVideo.srcObject = null; }
  if (intVideo) { intVideo.srcObject = null; }

  updateVideoUI(false, false);
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

  const cName = rep.candidate_name || state.analysis?.candidate?.candidate_name || 'Candidate Evaluation';
  const rTitle = rep.role_title || state.analysis?.role?.role_title || 'Software Engineering Professional';
  const cInitials = (cName.split(/\s+/).map(w => w[0]).join('').slice(0, 2) || 'CP').toUpperCase();

  container.innerHTML = `
    <!-- Candidate Profile Banner -->
    <div style="background:var(--bg-card); border:1px solid var(--border-highlight); border-radius:var(--radius-lg); padding:16px 22px; margin-bottom:16px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px;">
      <div style="display:flex; align-items:center; gap:14px;">
        <div class="candidate-avatar">${escapeHtml(cInitials)}</div>
        <div>
          <h2 style="font-size:18px; font-weight:800; color:var(--text-main); margin:0;">${escapeHtml(cName)}</h2>
          <div style="font-size:12px; color:var(--mint-accent); margin-top:2px;">Target Role: <b>${escapeHtml(rTitle)}</b></div>
        </div>
      </div>
      <div style="font-size:11px; color:var(--text-muted); text-align:right;">
        <span>Generated: ${new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}</span><br>
        <span style="color:var(--mint-accent); font-weight:600;">● AI Interview Accelerator Certified</span>
      </div>
    </div>

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
