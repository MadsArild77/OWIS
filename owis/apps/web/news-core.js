    let currentSources = [];
    let healthStateBySource = {};
    let selectedCollectionItems = new Set();
    let latestItems = [];
    let topItems = [];
    let mergedItems = [];
    let collectionsLoaded = false;
    let matchReviewItems = [];
    let storyLinks = [];
    let viewMode = 'reading';
    let activeDetailItemId = null;
    let activeDetailCollectionKey = null;
    let runProgressTimer = null;
    let runProgressStartedAt = null;
    let runProgressCurrent = 0;
    let runProgressTarget = 0;
    let runProgressWarningShown = false;
    let runProgressSourceRows = [];
    let runProgressSourceCursor = 0;
    let activeJobPollTimer = null;
    let latestSourceReportBySource = {};
    let readingLayout = localStorage.getItem('owisReadingLayout') === 'cards' ? 'cards' : 'list';
    let readingUnit = localStorage.getItem('owisReadingUnit') === 'news' ? 'news' : 'stories';
    let caseGroups = new Map();

    function relevanceLabel(status) {
      if (status === 'relevant') return 'Relevant';
      if (status === 'non_relevant') return 'Non-relevant';
      return 'Not yet rated';
    }

    function setViewMode(mode) {
      viewMode = mode === 'review' ? 'review' : 'reading';
      renderReadingPage();
      renderMergedPage();
      renderMatchReview();
    }

    const pageSize = { latest: 24, top: 24, reading: 12, merged: 8 };
    const pageState = { latest: 1, top: 1, reading: 1, merged: 1 };

    async function getJson(path) {
      const res = await fetch(path);
      if (!res.ok) throw new Error(`Request failed: ${path}`);
      return await res.json();
    }

    async function postJson(path, body = {}) {
      const res = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`Request failed: ${path}`);
      return await res.json();
    }

    function setStatus(msg, warn = false) {
      const el = document.getElementById(document.getElementById('settingsView').hidden ? 'feedbackNotice' : 'adminStatus');
      el.textContent = msg;
      el.className = warn ? 'status warn' : 'status';
    }

    function formatDuration(ms) {
      const totalSeconds = Math.max(0, Math.floor(ms / 1000));
      const minutes = Math.floor(totalSeconds / 60);
      const seconds = totalSeconds % 60;
      return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }

    function renderRunProgress() {
      const fill = document.getElementById('runProgressFill');
      const percent = document.getElementById('runProgressPercent');
      if (fill) fill.style.width = `${Math.max(0, Math.min(100, runProgressCurrent))}%`;
      if (percent) percent.textContent = `${Math.round(runProgressCurrent)}%`;
    }

    let quickFetchActive = false;

    function applyJobProgress(job) {
      if (!job) return;
      if (quickFetchActive && job.status === 'running') document.getElementById('quickFetchStatus').textContent = `${Math.round(job.percent || 0)}% · ${job.step || 'Working…'}`;
      const root = document.getElementById('runProgress');
      const title = document.getElementById('runProgressTitle');
      const step = document.getElementById('runProgressStep');
      const warning = document.getElementById('runProgressWarning');
      const time = document.getElementById('runProgressTime');
      if (root) root.classList.add('active');
      if (title) title.textContent = jobTitle(job.operation, job.status);
      if (step) step.textContent = job.error ? `${job.step || 'Failed'}: ${job.error}` : (job.step || 'Working...');
      if (warning) warning.classList.toggle('active', job.status === 'running' && runProgressStartedAt && Date.now() - runProgressStartedAt >= 45000);
      runProgressCurrent = Number(job.percent || 0);
      runProgressTarget = runProgressCurrent;
      if (time && runProgressStartedAt) time.textContent = formatDuration(Date.now() - runProgressStartedAt);
      renderSourceProgress(job.source_progress || []);
      renderRunProgress();
    }

    function jobTitle(operation, status) {
      const names = {
        fetch_process: 'Fetch + processing',
        rediscover_rss: 'RSS discovery',
        source_health: 'Source health',
        match_review: 'Match review AI',
      };
      const suffix = status === 'completed' ? 'completed' : status === 'failed' ? 'failed' : 'running';
      return `${names[operation] || 'Operation'} ${suffix}`;
    }

    async function startBackendJob(operation, payload, options = {}) {
      if (activeJobPollTimer) {
        clearInterval(activeJobPollTimer);
        activeJobPollTimer = null;
      }
      startOperationProgress({
        title: options.title || jobTitle(operation, 'running'),
        step: options.step || 'Starting backend job...',
        initialPercent: 2,
        targetPercent: 8,
        sourceRows: options.sourceRows || [],
      });
      const started = await postJson('/api/news/jobs/start', { operation, payload });
      const jobId = started.job_id;
      if (!jobId) throw new Error('Backend did not return a job_id');

      return await new Promise((resolve, reject) => {
        const poll = async () => {
          try {
            const job = await getJson(`/api/news/jobs/${encodeURIComponent(jobId)}`);
            applyJobProgress(job);
            if (job.status === 'completed') {
              clearInterval(activeJobPollTimer);
              activeJobPollTimer = null;
              resolve(job.result || {});
            } else if (job.status === 'failed') {
              clearInterval(activeJobPollTimer);
              activeJobPollTimer = null;
              reject(new Error(job.error || 'Job failed'));
            }
          } catch (err) {
            clearInterval(activeJobPollTimer);
            activeJobPollTimer = null;
            reject(err);
          }
        };
        activeJobPollTimer = window.setInterval(poll, 1200);
        poll();
      });
    }

    function setRunProgressStep(label, percent) {
      const step = document.getElementById('runProgressStep');
      if (step) step.textContent = label;
      runProgressTarget = Math.max(runProgressCurrent, Math.min(percent, 95));
      renderRunProgress();
    }

    function sourceProgressKey(row) {
      const source = String(row?.source || 'unknown').trim() || 'unknown';
      const method = String(row?.type || row?.method || 'fetch').trim() || 'fetch';
      return `[${source}:${method}]`;
    }

    function sourceProgressRowsForCurrentSources(status = 'pending', detail = 'Waiting for backend') {
      return (currentSources || [])
        .filter(source => source && source.enabled !== false)
        .map(source => ({
          source: source.name || 'Unknown',
          type: source.type || 'source',
          status,
          detail,
        }));
    }

    function renderSourceProgress(rows = []) {
      const root = document.getElementById('sourceProgressList');
      if (!root) return;
      if (!Array.isArray(rows) || rows.length === 0) {
        root.innerHTML = '';
        return;
      }
      root.innerHTML = rows.map(row => {
        const items = Number(row.items || 0);
        const filtered = Number(row.filtered || 0);
        const error = row.error ? String(row.error) : '';
        const status = String(row.status || '').trim();
        const health = row.health ? ` | health=${escapeHtml(row.health)}` : '';
        const paywalled = row.paywalled ? ` | paywall=${Number(row.paywalled || 0)}` : '';
        const detail = error
          ? `error=${escapeHtml(error.slice(0, 110))}`
          : row.detail
            ? escapeHtml(row.detail)
            : `items=${items} | filtered=${filtered}${paywalled}${health}`;
        return `
          <div class="source-progress-item ${error ? 'is-error' : status ? `is-${escapeHtml(status)}` : 'is-done'}">
            <div class="source-progress-name">${escapeHtml(sourceProgressKey(row))}</div>
            <div class="source-progress-detail">${detail}</div>
          </div>
        `;
      }).join('');
    }

    function stopRunProgress(success = true, finalStep = '', titleText = '') {
      if (runProgressTimer) {
        clearInterval(runProgressTimer);
        runProgressTimer = null;
      }
      if (activeJobPollTimer) {
        clearInterval(activeJobPollTimer);
        activeJobPollTimer = null;
      }
      runProgressCurrent = success ? 100 : runProgressCurrent;
      runProgressTarget = runProgressCurrent;
      renderRunProgress();

      const root = document.getElementById('runProgress');
      const title = document.getElementById('runProgressTitle');
      const step = document.getElementById('runProgressStep');
      const warning = document.getElementById('runProgressWarning');
      const time = document.getElementById('runProgressTime');

      if (title) title.textContent = titleText || (success ? 'Operation completed' : 'Operation stopped');
      if (step && finalStep) step.textContent = finalStep;
      if (warning) warning.classList.remove('active');
      if (time && runProgressStartedAt) {
        time.textContent = formatDuration(Date.now() - runProgressStartedAt);
      }

      window.setTimeout(() => {
        if (root) root.classList.remove('active');
      }, success ? 2200 : 4000);
    }

    function startOperationProgress(options = {}) {
      const root = document.getElementById('runProgress');
      const title = document.getElementById('runProgressTitle');
      const step = document.getElementById('runProgressStep');
      const warning = document.getElementById('runProgressWarning');
      const time = document.getElementById('runProgressTime');

      runProgressStartedAt = Date.now();
      runProgressCurrent = Number(options.initialPercent || 4);
      runProgressTarget = Number(options.targetPercent || 12);
      runProgressWarningShown = false;
      runProgressSourceRows = Array.isArray(options.sourceRows) ? options.sourceRows : [];
      runProgressSourceCursor = 0;

      if (root) root.classList.add('active');
      if (title) title.textContent = options.title || 'Operation running';
      if (step) step.textContent = options.step || 'Starting...';
      if (warning) warning.classList.remove('active');
      if (time) time.textContent = '00:00';
      renderSourceProgress(runProgressSourceRows);
      renderRunProgress();

      if (runProgressTimer) clearInterval(runProgressTimer);
      runProgressTimer = window.setInterval(() => {
        const elapsed = Date.now() - runProgressStartedAt;
        if (time) time.textContent = formatDuration(elapsed);

        if (runProgressSourceRows.length) {
          runProgressSourceRows = runProgressSourceRows.map((row, index) => {
            if (index < runProgressSourceCursor) return { ...row, status: row.status === 'pending' ? 'done' : row.status, detail: row.detail || 'Checked' };
            if (index === runProgressSourceCursor) return { ...row, status: 'active', detail: row.detail || 'Working...' };
            return row;
          });
          if (elapsed > (runProgressSourceCursor + 1) * 2500 && runProgressSourceCursor < runProgressSourceRows.length - 1) {
            runProgressSourceCursor += 1;
          }
          renderSourceProgress(runProgressSourceRows);
        }

        if (runProgressCurrent < runProgressTarget) {
          runProgressCurrent = Math.min(runProgressTarget, runProgressCurrent + 1);
          renderRunProgress();
        } else if (runProgressCurrent < 92) {
          runProgressCurrent = Math.min(92, runProgressCurrent + 0.2);
          renderRunProgress();
        }

        if (!runProgressWarningShown && elapsed >= 45000) {
          runProgressWarningShown = true;
          if (warning) warning.classList.add('active');
        }
      }, 1000);
    }

    function startRunProgress(daysBack) {
      startOperationProgress({
        title: 'Fetch + processing running',
        step: `Starting run (days_back=${daysBack})`,
        initialPercent: 4,
        targetPercent: 12,
        sourceRows: sourceProgressRowsForCurrentSources('pending', 'Queued for fetch'),
      });
    }

    function setButtonBusy(buttonId, isBusy, busyLabel = 'Working...') {
      const btn = document.getElementById(buttonId);
      if (!btn) return;
      if (!btn.dataset.defaultLabel) btn.dataset.defaultLabel = btn.textContent || '';
      if (isBusy) {
        btn.disabled = true;
        btn.classList.add('is-busy');
        btn.textContent = busyLabel;
      } else {
        btn.disabled = false;
        btn.classList.remove('is-busy');
        btn.textContent = btn.dataset.defaultLabel || btn.textContent;
      }
    }

    function escapeHtml(value) {
      return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function formatCsv(value) {
      const items = String(value || '')
        .split(',')
        .map(x => x.trim())
        .filter(Boolean);
      return items.length ? items.join(', ') : 'n/a';
    }

    function parseCsvTags(value) {
      return String(value || '')
        .split(',')
        .map(x => x.trim())
        .filter(Boolean);
    }

    function uniqueTags(...groups) {
      return Array.from(new Set(groups.flat().filter(Boolean)));
    }

    function tagBadgeHtml(tags, cls = '') {
      return tags.map(tag => `<span class="inline-tag ${cls}">${escapeHtml(readableLabel(tag))}</span>`).join('');
    }

    // Internal tags such as "general_news" are shown as "General news"; names like "Ørsted" are left alone.
    function readableLabel(value) {
      const text = String(value || '').trim();
      if (!/^[a-z0-9_]+$/.test(text)) return text;
      const words = text.replace(/_/g, ' ');
      return words.charAt(0).toUpperCase() + words.slice(1);
    }

    // Older processed stories contain tags such as "general_news" inside sentences.
    function readableText(value) {
      return String(value || '').replace(/\b[a-z]+(?:_[a-z]+)+\b/g, tag => tag.replace(/_/g, ' '));
    }

    function readableDate(value) {
      const date = new Date(value || '');
      if (!value || Number.isNaN(date.getTime())) return value || 'Date unavailable';
      return date.toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric'});
    }

    function shortText(value, maxLength = 260) {
      const text = String(value || '').replace(/\s+/g, ' ').trim();
      if (text.length <= maxLength) return text;
      const clipped = text.slice(0, maxLength);
      const sentenceEnd = Math.max(clipped.lastIndexOf('. '), clipped.lastIndexOf('! '), clipped.lastIndexOf('? '));
      const cut = sentenceEnd > 120 ? sentenceEnd + 1 : clipped.lastIndexOf(' ');
      return `${clipped.slice(0, cut > 80 ? cut : maxLength).trim()}...`;
    }

    function cssImageUrl(value) {
      const url = String(value || '').trim();
      if (!url || !/^https?:\/\//i.test(url)) return '';
      return url.replace(/["'\\\n\r]/g, encodeURIComponent);
    }

    function detailMetaChip(label, value) {
      return `
        <div class="detail-meta-chip">
          <span class="detail-meta-label">${escapeHtml(label)}</span>
          <span class="detail-meta-value">${escapeHtml(value || 'n/a')}</span>
        </div>
      `;
    }

    function textBlockHtml(value) {
      return escapeHtml(value || 'n/a').replace(/\n{2,}/g, '<br><br>').replace(/\n/g, '<br>');
    }
