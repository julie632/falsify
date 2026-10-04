(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const state = { status: null, cases: [], selectedCase: null, run: null, polling: null, statusPolling: null, activeRunId: null, busy: false, loadingRun: false, isReplay: false, showAllEvents: false, renderedEvents: '', history: [], examples: {} };
  const modeNames = { omnigent: 'Live Omnigent', local: 'Deterministic local', replay: 'Recorded replay' };
  const roleNames = { planner: 'Planner', coordinator: 'Planner', operator: 'Experiment operator', experiment_operator: 'Experiment operator', researcher: 'Experiment operator', reviewer: 'Reviewer agent', critic: 'Reviewer agent', system: 'Lab system', tool: 'Scientific tool' };

  async function request(path, options = {}) {
    const response = await fetch(path, { cache: 'no-store', ...options, headers: { 'Content-Type': 'application/json', ...options.headers } });
    let data;
    try { data = await response.json(); } catch (_) { throw new Error(`The lab returned an unreadable response (${response.status}).`); }
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.error || `The request failed (${response.status}).`);
    return data;
  }

  function setError(message = '') { $('error-message').textContent = message; $('error-message').hidden = !message; }
  function number(value, digits = 1) { return Number.isFinite(Number(value)) && value !== null && value !== '' ? Number(value).toFixed(digits) : null; }
  function humanize(value) { return String(value || '').replace(/[_-]/g, ' ').replace(/^./, (char) => char.toUpperCase()); }
  function timestamp(value) { if (!value) return ''; const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
  function dateAndTime(value) { if (!value) return ''; const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
  function readable(value) { if (value === undefined || value === null) return ''; return typeof value === 'string' ? value : JSON.stringify(value, null, 2); }
  function element(tag, className, content) { const node = document.createElement(tag); if (className) node.className = className; if (content !== undefined) node.textContent = content; return node; }
  function caseName(id) { return ({ row_split: 'Flawed evaluation', participant_holdout: 'Valid control' })[id] || humanize(id); }
  function sourceMode(mode) { return mode === 'omnigent' ? 'Omnigent agents' : mode === 'local' ? 'Deterministic reference' : humanize(mode); }
  function splitName(value) { return ({ stratified_random_rows_from_official_training_pool: 'Shuffled recordings', official_participant_holdout: 'Participant holdout' })[value] || humanize(value); }

  function updateModeExplanation() {
    if (state.status?.public_demo) return;
    const live = $('run-mode').value === 'omnigent';
    $('mode-explainer').textContent = live ? 'Omnigent coordinates AI agents and real scientific tools using the existing Codex sign-in. Per-run dollar cost is not reported.' : 'Deterministic local runs real scientific checks using a fixed decision policy. It does not use AI agents or paid inference.';
  }

  function renderStatus(status) {
    state.status = status;
    const publicDemo = status.public_demo === true;
    state.activeRunId = publicDemo ? null : status.active_run_id || (state.busy ? state.run?.id : null);
    $('connection-status').className = 'connection connected';
    $('connection-label').textContent = publicDemo ? 'Recorded evidence ready' : 'Lab connected';
    $('app-version').textContent = status.version ? `Falsify · ${status.version}` : 'Falsify POC';
    $('public-demo-notice').hidden = !publicDemo;
    $('case-fieldset').hidden = publicDemo;
    $('run-controls').hidden = publicDemo;
    $('mode-explainer').hidden = publicDemo;
    $('history-label').textContent = publicDemo ? 'Reviewed recorded investigations' : 'All investigations, including failures';
    if (publicDemo) {
      $('dataset-status').textContent = 'Dataset provenance accompanies each recorded result.';
      if (!status.recorded_evidence_available) $('connection-label').textContent = 'Recorded evidence unavailable';
      updateControls();
      return;
    }
    $('dataset-status').textContent = status.dataset_ready ? 'Dataset available locally' : 'Dataset will be prepared for the first investigation.';
    const live = $('run-mode').querySelector('[value="omnigent"]');
    live.disabled = !(status.omnigent_available && status.auth_ready);
    live.textContent = !status.omnigent_available ? 'Live Omnigent · unavailable' : !status.auth_ready ? 'Live Omnigent · credentials needed' : 'Live Omnigent';
    if (live.disabled && $('run-mode').value === 'omnigent') $('run-mode').value = 'local';
    if (!state.run && !state.busy && !live.disabled && !$('run-mode').dataset.userSelected) $('run-mode').value = 'omnigent';
    updateModeExplanation();
    updateControls();
    scheduleStatusCheck();
  }

  function renderCases(cases) {
    state.cases = cases;
    if (!state.selectedCase) state.selectedCase = cases[0]?.id || null;
    const target = $('case-options');
    target.replaceChildren();
    cases.forEach((item) => {
      const label = element('label', `case-option${item.id === state.selectedCase ? ' selected' : ''}`);
      const input = element('input'); input.type = 'radio'; input.name = 'case'; input.value = item.id; input.checked = item.id === state.selectedCase;
      input.addEventListener('change', () => { state.selectedCase = item.id; clearDisplayedRun(); renderCases(state.cases); if (!state.busy) $('claim-text').textContent = item.claim; });
      const content = element('span');
      content.append(element('span', 'case-name', caseName(item.id)), element('span', 'case-description', item.description));
      label.append(input, content); target.append(label);
    });
    if (!cases.length) target.append(element('p', 'loading-copy', 'No cases are configured.'));
    if (!state.run) $('claim-text').textContent = cases.find((item) => item.id === state.selectedCase)?.claim || 'No claim is configured.';
    updateControls();
  }

  function updateControls() {
    const readOnly = state.status?.public_demo === true || state.status?.read_only === true;
    const locked = !!state.activeRunId || state.busy || state.loadingRun;
    $('run-button').disabled = readOnly || locked || !state.selectedCase || !state.status;
    $('run-button-text').textContent = state.busy || state.activeRunId ? 'Investigation running' : state.loadingRun ? 'Loading recorded evidence' : 'Run new investigation';
    $('run-mode').disabled = readOnly || locked;
    document.querySelectorAll('input[name="case"]').forEach((input) => { input.disabled = readOnly || locked; });
    $('run-history').disabled = state.loadingRun;
    ['flawed', 'control'].forEach((key) => { $('demo-' + key).disabled = state.loadingRun || !state.examples[key]; });
    $('active-run-notice').hidden = readOnly || !state.activeRunId;
    $('view-active-run').disabled = state.loadingRun || state.run?.id === state.activeRunId;
    document.body.classList.toggle('is-running', state.busy);
  }

  function clearDisplayedRun() {
    stopPolling(); state.run = null; state.isReplay = false; state.renderedEvents = ''; setError();
    const clearedUrl = new URL(window.location.href); clearedUrl.searchParams.delete('run'); window.history.replaceState(null, '', clearedUrl);
    renderResults(null); renderEvents(null);
    $('run-state').textContent = 'Awaiting an investigation'; $('run-state').className = 'run-state';
    $('execution-badge').textContent = 'No run selected'; $('execution-badge').className = 'execution-badge';
    $('ledger-meta').hidden = true; $('run-usage').hidden = true; $('result-context').hidden = true; $('run-history').value = '';
    ['flawed', 'control'].forEach((key) => $('demo-' + key).classList.remove('selected'));
    $('export-link').removeAttribute('href'); $('export-link').classList.add('disabled'); $('export-link').setAttribute('aria-disabled', 'true');
  }

  function setScore(prefix, result) {
    const metrics = result?.metrics;
    const score = number(metrics?.accuracy !== undefined ? metrics.accuracy * 100 : undefined, 2);
    const node = $(`${prefix}-score`);
    node.replaceChildren();
    node.classList.toggle('pending', score === null);
    if (score !== null) { node.append(document.createTextNode(score), element('span', 'metric-unit', '%')); } else node.textContent = 'Pending';
    $(`${prefix}-bar`).style.width = score !== null ? `${Math.max(0, Math.min(100, Number(score)))}%` : '0%';
    const split = result?.split;
    $(`${prefix}-caption`).textContent = result ? `Accuracy · ${splitName(split?.strategy || result.evaluation || 'measured result')}` : prefix === 'original' ? 'Accuracy · awaiting a real run' : 'Accuracy · awaiting verification';
    const macroF1 = number(metrics?.macro_f1 !== undefined ? metrics.macro_f1 * 100 : undefined, 2);
    $(`${prefix}-secondary`).textContent = macroF1 !== null ? `Macro F1 ${macroF1}%${split?.n_test !== undefined ? ` · ${Number(split.n_test).toLocaleString()} test samples` : ''}` : prefix === 'original' ? 'Measured classification results will appear here.' : 'The follow-up is determined by evidence.';
  }

  function renderResults(run) {
    const results = run?.results || {};
    const original = results.original;
    const verifiedControl = !results.corrected && run?.status === 'completed' && run?.verdict?.status === 'supported' && run?.validation?.agrees_with_split_rule !== false && results.audit?.split?.overlap_count === 0;
    const corrected = results.corrected || (verifiedControl ? original : null);
    setScore('original', original);
    setScore('corrected', corrected);
    $('corrected-label').textContent = verifiedControl ? 'Original evaluation retained' : 'Participant-held-out evaluation';
    $('comparison-note').hidden = !results.corrected || !original || original.split?.strategy === results.corrected.split?.strategy;
    if (verifiedControl) {
      $('corrected-caption').textContent = 'Accuracy · original result retained';
      $('corrected-secondary').textContent = 'Split verified. No redundant rerun needed.';
    }
    if (run && !['running', 'queued'].includes(run.status)) {
      if (!original) { $('original-score').textContent = 'Not run'; $('original-caption').textContent = 'No original result was recorded'; }
      if (!corrected) { $('corrected-score').textContent = 'Not run'; $('corrected-caption').textContent = 'No follow-up result was recorded'; $('corrected-secondary').textContent = 'A recommendation is not an executed experiment.'; }
    }
    const audit = results.audit || {};
    const overlap = audit.overlap_count ?? audit.participant_overlap_count ?? audit.split?.overlap_count ?? original?.split?.overlap_count;
    $('overlap-score').textContent = overlap !== undefined && overlap !== null ? String(overlap) : run && !['running', 'queued'].includes(run.status) ? 'Not checked' : 'Pending';
    $('overlap-score').classList.toggle('pending', overlap === undefined || overlap === null);
    document.querySelector('.overlap-card').classList.toggle('has-overlap', Number(overlap) > 0);
    $('overlap-caption').textContent = 'Training and test overlap';
    const correctedOverlap = corrected?.split?.overlap_count;
    $('overlap-secondary').textContent = correctedOverlap !== undefined ? `Verified evaluation: ${correctedOverlap} shared participants.` : overlap === 0 ? 'No participants are shared between these splits.' : overlap > 0 ? 'The original test includes familiar participants.' : 'A direct check of the new-person claim.';
    const verdict = run?.verdict;
    const card = $('verdict-card'); card.className = 'verdict-card';
    $('next-experiment').hidden = true;
    $('validation-warning').hidden = true; $('repaired-claim').hidden = true;
    $('verdict-evidence').hidden = true; $('verdict-evidence').replaceChildren();
    if (!verdict) {
      $('verdict-icon').textContent = '?'; $('verdict-label').textContent = 'Conclusion';
      const stopped = ['failed', 'cancelled'].includes(run?.status);
      $('verdict-title').textContent = stopped ? 'This investigation could not finish.' : state.busy ? 'The investigation is in progress.' : 'The evidence gets the final word.';
      $('verdict-summary').textContent = stopped ? 'The ledger preserves the work completed before the investigation stopped. No final scientific conclusion is available.' : state.busy ? 'The lab is collecting evidence. A conclusion will appear after the review.' : state.status?.public_demo ? 'Choose a reviewed recording to inspect the measured results and reviewer conclusion.' : 'Run an investigation to see whether the claim is supported, needs revision, or requires more evidence.';
      return;
    }
    const status = String(verdict.status || '').toLowerCase();
    const disagrees = run?.validation?.agrees_with_split_rule === false;
    const isSupported = ['supported', 'retained', 'valid', 'claim_supported', 'supported_with_limitations'].includes(status);
    const incomplete = ['failed', 'cancelled'].includes(run?.status);
    const needsRevision = ['revised', 'unsupported', 'needs_revision', 'rejected', 'invalid', 'claim_revised', 'not_supported'].includes(status) || /revision|unsupported|invalid|reject/.test(status);
    card.classList.toggle('supported', isSupported && !disagrees && !incomplete); card.classList.toggle('needs-revision', needsRevision || disagrees || incomplete); card.classList.toggle('review-disagreement', disagrees);
    $('verdict-icon').textContent = disagrees || incomplete ? '!' : isSupported ? '✓' : needsRevision ? '↻' : 'i';
    $('verdict-label').textContent = incomplete ? 'Incomplete investigation · recorded review' : disagrees ? 'Review disagreement · human review required' : 'Reviewer conclusion';
    $('verdict-title').textContent = incomplete ? 'This investigation did not complete.' : disagrees ? isSupported ? 'Reviewer accepted; split check disagrees.' : 'Reviewer conclusion and split check disagree.' : isSupported ? 'The evaluation addresses the scoped claim.' : needsRevision ? 'The submitted evidence needs revision.' : humanize(verdict.status || 'Review complete');
    $('verdict-summary').textContent = readable(verdict.summary);
    if (disagrees) {
      $('validation-warning').textContent = `The AI review above is preserved as an observed outcome. The fixed participant-separation rule returned “${humanize(run.validation.deterministic_reference_status || 'a different conclusion')}”. Resolve this disagreement before using the AI conclusion.`;
      $('validation-warning').hidden = false;
    }
    if (verdict.repaired_claim) { $('repaired-claim').textContent = readable(verdict.repaired_claim); $('repaired-claim').hidden = false; }
    if (Array.isArray(verdict.evidence_ids) && verdict.evidence_ids.length) {
      $('verdict-evidence').hidden = false; $('verdict-evidence').append(element('span', '', 'Cited evidence'));
      verdict.evidence_ids.forEach((id) => { const link = element('a', '', id); link.href = `#evidence-${String(id)}`; $('verdict-evidence').append(link); });
    }
    if (verdict.next_experiment) { $('next-experiment').textContent = `Next experiment: ${readable(verdict.next_experiment)}`; $('next-experiment').hidden = false; }
  }

  function previewField(text, name) {
    const match = String(text || '').match(new RegExp('"' + name + '"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)'));
    if (!match) return '';
    try { return JSON.parse('"' + match[1] + '"'); } catch (_) { return match[1].replace(/\\n/g, ' '); }
  }

  function isKeyEvent(event, index, events) {
    if (event.type === 'omnigent_event' || event.type === 'tool_completed') return false;
    if (event.type === 'tool_started' && ['run_original', 'audit_split', 'participant_holdout'].includes(event.title)) return false;
    const next = events[index + 1];
    if (event.type === 'delegation_completed' && next?.type === event.type && event.role === next.role && event.data?.child_session_id && event.data.child_session_id === next.data?.child_session_id && Math.abs(new Date(event.timestamp) - new Date(next.timestamp)) < 2000) return false;
    if (event.type === 'decision' && next?.type === 'verdict' && event.detail === next.detail) return false;
    return true;
  }

  function evidenceFacts(data) {
    const facts = element('dl', 'evidence-facts');
    const items = [];
    if (typeof data.metrics?.accuracy === 'number') items.push(['Accuracy', `${number(data.metrics.accuracy * 100, 2)}%`]);
    if (typeof data.split?.overlap_count === 'number') items.push(['Shared participants', String(data.split.overlap_count)]);
    if (typeof data.split?.n_test === 'number') items.push(['Test recordings', data.split.n_test.toLocaleString()]);
    for (const [label, value] of items) { const item = element('div'); item.append(element('dt', '', label), element('dd', '', value)); facts.append(item); }
    return items.length ? facts : null;
  }

  function renderEvents(run) {
    const events = Array.isArray(run?.events) ? run.events : [];
    const keyEvents = events.filter(isKeyEvent);
    const visibleEvents = state.showAllEvents ? events : keyEvents;
    $('event-count').textContent = `${events.length} recorded events`;
    $('ledger-toolbar').hidden = !events.length;
    $('ledger-filter-note').textContent = state.showAllEvents ? `All ${events.length} events, including transport messages and repeated status updates.` : `${keyEvents.length} key events shown. Transport messages and repeated status updates remain in the complete record.`;
    $('show-all-events').textContent = state.showAllEvents ? 'Show key events' : `Show all ${events.length} events`;
    $('show-all-events').setAttribute('aria-pressed', String(state.showAllEvents));
    const signature = JSON.stringify([state.showAllEvents, events]);
    if (signature === state.renderedEvents) return;
    state.renderedEvents = signature;
    const timeline = $('timeline');
    const openIds = new Set([...timeline.querySelectorAll('details[open]')].map((item) => item.dataset.eventId));
    const wasAtBottom = timeline.scrollHeight - timeline.scrollTop - timeline.clientHeight < 75;
    timeline.replaceChildren();
    if (!events.length) {
      const empty = element('div', 'empty-state'); const copy = element('div');
      copy.append(element('h3', '', state.busy ? 'The lab is starting its investigation.' : 'Every decision leaves a trace.'), element('p', '', 'Agent decisions, tool outputs, and review findings will appear here as the investigation runs.'));
      empty.append(element('span', 'empty-symbol', '↳'), copy); timeline.append(empty);
    }
    visibleEvents.forEach((event, index) => {
      const eventId = String(event.id ?? index);
      const article = element('article', `timeline-event${event.type === 'omnigent_event' ? ' raw-event' : ''}`); article.id = `evidence-${eventId}`;
      const role = String(event.role || 'system').toLowerCase();
      const symbol = /plan|coord/.test(role) ? 'P' : /oper|tool|research/.test(role) ? 'E' : /review|critic/.test(role) ? 'R' : '·';
      const content = element('div'); const meta = element('div');
      const time = element('time', 'event-time', timestamp(event.timestamp)); if (event.timestamp) time.dateTime = event.timestamp;
      meta.append(element('span', 'event-role', roleNames[role] || humanize(role)), time);
      if (event.type === 'omnigent_event') {
        const details = element('details', 'event-data raw-orchestration'); details.dataset.eventId = eventId; details.open = openIds.has(eventId);
        details.append(element('summary', '', `${event.title || 'Omnigent orchestration'}${event.detail ? ` · ${String(event.detail).slice(0, 90)}` : ''}`));
        details.append(element('pre', '', readable(event.data || event.detail)));
        content.append(meta, details); article.append(element('span', 'event-symbol', '·'), content); timeline.append(article); return;
      }
      let title = event.title || humanize(event.type || 'Evidence recorded');
      let detail = readable(event.detail);
      if (event.type === 'delegation_completed') {
        const preview = event.data?.child?.last_message_preview || event.detail;
        const action = previewField(preview, 'action');
        const reason = previewField(preview, 'reason');
        const actions = { audit_split: 'Selected the participant audit', participant_holdout: 'Requested a participant-held-out test', accept: 'Accepted the scoped evaluation', reject: 'Rejected the original evidence', inconclusive: 'Requested more evidence' };
        if (actions[action]) title = actions[action];
        if (reason) detail = `Recorded excerpt: ${reason}`;
      }
      content.append(meta, element('h3', 'event-title', title));
      if (detail) content.append(element('p', 'event-detail', detail));
      if (event.type === 'tool_result') {
        const facts = evidenceFacts(event.data || {}); if (facts) content.append(facts);
        if (event.data?.reason) content.append(element('p', 'event-finding', event.data.reason));
      }
      if (event.data && Object.keys(event.data).length) {
        const details = element('details', 'event-data'); details.dataset.eventId = eventId; details.open = openIds.has(eventId);
        details.append(element('summary', '', 'Inspect recorded evidence'), element('pre', '', JSON.stringify(event.data, null, 2))); content.append(details);
      }
      article.append(element('span', 'event-symbol', symbol), content); timeline.append(article);
    });
    if (wasAtBottom && state.busy) timeline.scrollTop = timeline.scrollHeight;
    const lastRole = String(keyEvents.at(-1)?.role || '').toLowerCase();
    const order = /review|critic/.test(lastRole) ? 2 : /oper|tool|research/.test(lastRole) ? 1 : /plan|coord/.test(lastRole) ? 0 : -1;
    document.querySelectorAll('.protocol-step').forEach((step, index) => { step.classList.toggle('current', state.busy && index === order); step.classList.toggle('complete', run?.status === 'completed' || index < order); });
  }

  function renderRun(run, replay = state.isReplay) {
    state.run = run;
    const runUrl = new URL(window.location.href);
    runUrl.searchParams.set('run', run.id);
    window.history.replaceState(null, '', runUrl);
    state.isReplay = replay;
    state.busy = ['queued', 'running'].includes(run.status);
    if (state.busy) state.activeRunId = run.id;
    else if (state.activeRunId === run.id) state.activeRunId = null;
    updateControls();
    scheduleStatusCheck();
    const caseInfo = state.cases.find((item) => item.id === run.case_id);
    if (caseInfo?.claim) $('claim-text').textContent = caseInfo.claim;
    $('run-state').textContent = ({ queued: 'Investigation queued', running: 'Investigation in progress', completed: 'Investigation complete', failed: 'Investigation failed' })[run.status] || humanize(run.status);
    $('run-state').className = `run-state ${run.status}`;
    const recorded = replay && !state.busy;
    $('execution-badge').textContent = recorded ? `Recorded replay · ${sourceMode(run.mode)}` : state.busy ? modeNames[run.mode] || humanize(run.mode) : `Completed · ${sourceMode(run.mode)}`;
    $('execution-badge').className = `execution-badge${run.mode === 'omnigent' && state.busy ? ' live' : ''}`;
    $('result-context').hidden = false;
    $('result-context').className = `result-context${recorded ? ' recorded' : ''}`;
    $('context-label').textContent = recorded ? 'Recorded replay' : state.busy ? 'Running now' : run.status === 'completed' ? 'Run complete' : `Run ${humanize(run.status).toLowerCase()}`;
    $('context-detail').textContent = `${caseName(run.case_id)} · ${sourceMode(run.mode)}${run.started_at ? ` · ${dateAndTime(run.started_at)}` : ''}`;
    ['flawed', 'control'].forEach((key) => { const selected = recorded && state.examples[key]?.id === run.id; $('demo-' + key).classList.toggle('selected', selected); $('demo-' + key).setAttribute('aria-pressed', String(selected)); });
    $('ledger-meta').hidden = false;
    $('ledger-meta').textContent = `RUN ${run.id} · ${caseInfo?.title || humanize(run.case_id)}${run.started_at ? ` · started ${dateAndTime(run.started_at)}` : ''}${run.completed_at ? ` · completed ${timestamp(run.completed_at)}` : ''}`;
    $('export-link').href = `/api/runs/${encodeURIComponent(run.id)}/export`; $('export-link').classList.remove('disabled'); $('export-link').removeAttribute('aria-disabled');
    $('export-link').setAttribute('download', `falsify-${run.id}.json`);
    renderResults(run); renderEvents(run);
    $('run-usage').hidden = false;
    const usage = run.usage || {};
    $('usage-tools').textContent = usage.tool_calls !== undefined ? `${usage.tool_calls} scientific tool calls${run.budget?.max_tool_calls ? ` / ${run.budget.max_tool_calls} limit` : ''}` : 'Tool usage pending';
    const elapsed = run.started_at ? Math.max(0, Math.round(((run.completed_at ? new Date(run.completed_at) : new Date()) - new Date(run.started_at)) / 1000)) : null;
    $('usage-duration').textContent = elapsed !== null && Number.isFinite(elapsed) ? `${elapsed}s elapsed` : 'Timing pending';
    $('usage-cost').textContent = usage.cost_usd != null && Number.isFinite(Number(usage.cost_usd)) ? `Reported cost: $${Number(usage.cost_usd).toFixed(4)}` : run.mode === 'local' ? 'No model inference used' : state.status?.public_demo ? 'Model cost: not reported' : 'Cost: not reported / subscription';
    if (run.error) setError(readable(run.error));
  }

  function refreshExamples() {
    const eligible = (run, caseId) => {
      if (state.status?.public_demo && run.mode !== 'omnigent') return false;
      if (run.case_id !== caseId || run.status !== 'completed' || !run.results?.original?.metrics || !run.results?.audit || run.validation?.agrees_with_split_rule === false) return false;
      if (run.mode === 'omnigent' && run.validation?.protocol_verified !== true) return false;
      const overlap = run.results.audit.split?.overlap_count;
      return caseId === 'row_split' ? overlap > 0 && run.verdict?.status === 'unsupported' && run.results.corrected?.split?.overlap_count === 0 && !!run.results.corrected?.metrics : overlap === 0 && run.verdict?.status === 'supported';
    };
    const latest = [...state.history].sort((a, b) => Number(b.mode === 'omnigent') - Number(a.mode === 'omnigent') || new Date(b.started_at) - new Date(a.started_at));
    state.examples = { flawed: latest.find((run) => eligible(run, 'row_split')), control: latest.find((run) => eligible(run, 'participant_holdout')) };
    $('demo-strip').hidden = !state.examples.flawed && !state.examples.control;
    ['flawed', 'control'].forEach((key) => {
      const run = state.examples[key];
      $('demo-' + key + '-mode').textContent = run ? `${run.mode === 'omnigent' ? 'Omnigent' : 'Fixed-rule'} replay` : 'No completed example';
      $('demo-' + key).setAttribute('aria-label', run ? `Open recorded ${caseName(run.case_id).toLowerCase()} from ${sourceMode(run.mode)}` : 'No completed example available');
    });
    updateControls();
  }

  async function refreshHistory() {
    try {
      const data = await request('/api/runs');
      const runs = Array.isArray(data) ? data : data.runs || [];
      state.history = runs;
      refreshExamples();
      const select = $('run-history'); const selected = state.run?.id || select.value; select.replaceChildren();
      const blank = element('option', '', runs.length ? 'Select a recorded investigation' : 'No recorded investigations yet'); blank.value = ''; select.append(blank);
      runs.forEach((run) => { const option = element('option', '', `${caseName(run.case_id)} · ${sourceMode(run.mode)} · ${humanize(run.status)}${run.started_at ? ` · ${dateAndTime(run.started_at)}` : ''} · ${run.id.slice(0, 8)}`); option.value = run.id; select.append(option); });
      if (runs.some((run) => run.id === selected)) select.value = selected;
    } catch (error) { if (state.status?.public_demo) setError(`Could not load the reviewed recordings. ${error.message}`); }
  }

  function stopPolling() { if (state.polling) clearTimeout(state.polling); state.polling = null; }
  function scheduleStatusCheck() {
    if (state.statusPolling || !state.activeRunId) return;
    state.statusPolling = setTimeout(async () => {
      state.statusPolling = null;
      const previous = state.activeRunId;
      try { renderStatus(await request('/api/status')); if (previous && !state.activeRunId) await refreshHistory(); }
      catch (_) { scheduleStatusCheck(); }
    }, 5000);
  }
  async function pollRun(id) {
    try {
      const run = await request(`/api/runs/${encodeURIComponent(id)}`);
      if (state.run?.id !== id) return;
      $('connection-status').className = 'connection connected'; $('connection-label').textContent = 'Lab connected';
      if ($('error-message').textContent.startsWith('Unable to refresh')) setError();
      renderRun(run);
      if (state.busy) state.polling = setTimeout(() => pollRun(id), 1000);
      else { stopPolling(); await refreshHistory(); const status = await request('/api/status'); renderStatus(status); }
    } catch (error) {
      $('connection-status').className = 'connection disconnected'; $('connection-label').textContent = 'Connection interrupted';
      setError(`Unable to refresh this investigation: ${error.message} The lab may still be running. Retrying automatically.`);
      state.polling = setTimeout(() => pollRun(id), 2500);
    }
  }

  async function startRun() {
    if (state.status?.public_demo || state.status?.read_only || state.busy || state.activeRunId || state.loadingRun || !state.selectedCase) return;
    setError(); stopPolling(); state.busy = true; state.isReplay = false; updateControls();
    try {
      const data = await request('/api/runs', { method: 'POST', body: JSON.stringify({ case_id: state.selectedCase, mode: $('run-mode').value }) });
      const id = data.run_id || data.id;
      if (!id) throw new Error('The lab did not return an investigation identifier.');
      state.renderedEvents = '';
      renderRun({ id, case_id: state.selectedCase, status: 'queued', mode: $('run-mode').value, events: [], results: {} }, false);
      await pollRun(id);
    } catch (error) { state.busy = false; updateControls(); setError(error.message); }
  }

  async function loadRun(id, replay = true, scrollToResults = false) {
    if (!id || state.loadingRun) return;
    stopPolling(); setError();
    state.loadingRun = true; updateControls();
    try {
      const run = await request(`/api/runs/${encodeURIComponent(id)}`);
      state.selectedCase = run.case_id; state.showAllEvents = false; renderCases(state.cases); state.renderedEvents = ''; renderRun(run, replay);
      $('run-history').value = run.id;
      if (scrollToResults) $('results-heading').scrollIntoView?.({ behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
      if (state.busy) await pollRun(id);
    } catch (error) { setError(error.message); }
    finally { state.loadingRun = false; updateControls(); }
  }

  async function init() {
    ['original-score', 'corrected-score', 'overlap-score'].forEach((id) => $(id).classList.add('pending'));
    $('run-button').addEventListener('click', startRun);
    $('run-mode').addEventListener('change', () => { $('run-mode').dataset.userSelected = 'true'; updateModeExplanation(); });
    $('run-history').addEventListener('change', (event) => loadRun(event.target.value));
    $('view-active-run').addEventListener('click', () => loadRun(state.activeRunId, false, true));
    $('show-all-events').addEventListener('click', () => { state.showAllEvents = !state.showAllEvents; renderEvents(state.run); });
    ['flawed', 'control'].forEach((key) => $('demo-' + key).addEventListener('click', () => loadRun(state.examples[key]?.id, true, true)));
    $('verdict-evidence').addEventListener('click', (event) => {
      const link = event.target.closest('a'); if (!link) return;
      const id = link.hash.slice(1);
      if (!document.getElementById(id)) { state.showAllEvents = true; renderEvents(state.run); }
      const evidence = document.getElementById(id);
      const details = evidence?.querySelector('details'); if (details) details.open = true;
    });
    try {
      const [status, data] = await Promise.all([request('/api/status'), request('/api/cases')]);
      renderCases(Array.isArray(data) ? data : data.cases || []); renderStatus(status); await refreshHistory();
      const savedRun = new URLSearchParams(window.location.search).get('run');
      if (savedRun && /^[a-f0-9]{32}$/.test(savedRun)) await loadRun(savedRun, true);
      else if (status.active_run_id) await loadRun(status.active_run_id, false);
      else if (status.public_demo) {
        const example = state.examples.flawed || state.examples.control;
        if (example) await loadRun(example.id, true);
        else {
          $('run-state').textContent = 'No reviewed recording available';
          renderResults(null);
          setError('No reviewed recording is available at the moment. Please return later.');
        }
      }
    } catch (error) {
      $('connection-status').className = 'connection disconnected'; $('connection-label').textContent = 'Lab unavailable';
      $('case-options').replaceChildren(element('p', 'loading-copy', 'The experiment service is unavailable.'));
      $('dataset-status').textContent = 'Dataset status unavailable';
      setError(state.status?.public_demo ? `Could not load the recorded evidence. ${error.message} Please refresh the page.` : `Could not connect to the lab. ${error.message} Refresh after starting the server.`);
    }
  }
  window.addEventListener('beforeunload', () => { stopPolling(); if (state.statusPolling) clearTimeout(state.statusPolling); });
  init();
})();
