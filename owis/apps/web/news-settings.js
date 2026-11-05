
    function fillEditForm(source) {
      document.getElementById('editIndex').value = source.index;
      document.getElementById('editName').value = source.name || '';
      document.getElementById('editInterest').value = source.interest_topic || 'all';
      document.getElementById('editHomepage').value = source.homepage || '';
      document.getElementById('editType').value = source.type || 'rss';
      document.getElementById('editUrl').value = source.url || '';
      document.getElementById('editPriority').value = source.priority || 'medium';
    }

    function healthDotClass(color) {
      if (color === 'green') return 'health-dot health-green';
      if (color === 'yellow') return 'health-dot health-yellow';
      if (color === 'red') return 'health-dot health-red';
      return 'health-dot health-gray';
    }

    function renderSourcesTable() {
      const body = document.getElementById('sourcesBody');
      body.innerHTML = '';

      for (const s of currentSources) {
        const health = healthStateBySource[s.name || ''] || {};
        const lastReport = latestSourceReportBySource[s.name || ''] || {};
        const color = health.health_color || 'gray';
        const tooltip = health.last_error || (health.updated_at ? `Updated ${health.updated_at}` : 'No fetch history yet');
        const lastItems = Number.isFinite(Number(lastReport.items)) ? Number(lastReport.items) : Number(health.last_items || 0);
        const countBadgeClass = lastItems > 0 ? 'count-badge' : 'count-badge is-zero';
        const countTooltip = lastReport.status
          ? `Latest run: items=${lastReport.items || 0}, filtered=${lastReport.filtered || 0}${lastReport.error ? `, error=${lastReport.error}` : ''}`
          : 'Latest stored item count from last fetch run';

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${s.index}</td>
          <td>${escapeHtml(s.name || '')}</td>
          <td>${escapeHtml(s.type || '')}</td>
          <td>${escapeHtml(s.url || '')}</td>
          <td title="${String(countTooltip).replace(/"/g, '&quot;')}"><span class="${countBadgeClass}">${lastItems}</span></td>
          <td title="${tooltip.replace(/"/g, '&quot;')}"><span class="${healthDotClass(color)}"></span>${color}</td>
          <td><input type="checkbox" ${s.enabled ? 'checked' : ''} data-toggle-index="${s.index}" /></td>
          <td class="row-actions">
            <button data-history-index="${s.index}" class="btn-secondary">Error log</button>
            <button data-edit-index="${s.index}" class="btn-secondary">Edit</button>
            <button data-delete-index="${s.index}" class="btn-warning">Delete</button>
          </td>
        `;
        body.appendChild(tr);
      }

      body.querySelectorAll('[data-history-index]').forEach(btn => {
        btn.addEventListener('click', async () => {
          const source = currentSources.find(x => x.index === Number(btn.dataset.historyIndex));
          if (!source) return;
          let panel = document.getElementById('sourceHistoryPanel');
          if (!panel) {
            panel = document.createElement('div'); panel.id = 'sourceHistoryPanel';
            body.closest('table').after(panel);
          }
          panel.textContent = 'Loading history…';
          try {
            const url = source.type === 'rss' ? source.url : (source.homepage || source.url);
            const result = await getJson('/api/news/sources/history?source_url=' + encodeURIComponent(url));
            panel.innerHTML = `<h3>${escapeHtml(source.name)} – source history</h3><p>Last 100 checks and fetches. Earlier failures remain in the history.</p>` +
              (result.items.length ? result.items.map(row => `<div class="source-progress-item ${row.status === 'error' ? 'is-error' : ''}">
                <strong>${escapeHtml(new Date(row.created_at).toLocaleString())} · ${escapeHtml(row.operation)} · ${row.status === 'error' ? 'Error' : row.status === 'empty' ? 'No results' : 'OK'}</strong>
                <div>${escapeHtml(row.category === 'none' ? '' : row.category)} ${row.http_status || ''} ${escapeHtml(row.message)} ${row.items == null ? '' : ' · Treff: ' + row.items}</div>
                <small>${escapeHtml(row.source_url)}</small></div>`).join('') : '<p>No checks recorded yet. Check sources or fetch news.</p>');
          } catch (err) { panel.textContent = 'Could not load history: ' + err.message; }
        });
      });

      body.querySelectorAll('[data-edit-index]').forEach(btn => {
        btn.addEventListener('click', () => {
          const idx = Number(btn.getAttribute('data-edit-index'));
          const source = currentSources.find(x => x.index === idx);
          if (source) fillEditForm(source);
        });
      });

      body.querySelectorAll('[data-delete-index]').forEach(btn => {
        btn.addEventListener('click', async () => {
          const idx = Number(btn.getAttribute('data-delete-index'));
          const source = currentSources.find(x => x.index === idx);
          const label = source?.name || `#${idx}`;
          if (!window.confirm(`Delete source ${label}?`)) return;

          await postJson('/api/news/sources/delete', { index: idx });
          setStatus(`Deleted source ${label}`);
          await refreshSources();
          await refreshSignals();
          await refreshCollections();
        });
      });
      body.querySelectorAll('[data-toggle-index]').forEach(chk => {
        chk.addEventListener('change', async () => {
          const idx = Number(chk.getAttribute('data-toggle-index'));
          await postJson('/api/news/sources/toggle', { index: idx, enabled: chk.checked });
          setStatus(`Updated source #${idx} enabled=${chk.checked}`);
          await refreshSources();
        });
      });
    }

    async function refreshHealthState() {
      const result = await getJson('/api/news/sources/health-state');
      const items = Array.isArray(result.items) ? result.items : [];
      healthStateBySource = {};
      for (const row of items) {
        healthStateBySource[row.source_name] = row;
      }
    }

    async function refreshSources() {
      const [sources] = await Promise.all([
        getJson('/api/news/sources'),
        refreshHealthState(),
      ]);
      currentSources = Array.isArray(sources) ? sources : [];
      renderSourceFilterOptions();
      renderSourcesTable();
    }

    async function refreshSignals() {
      const [latest, top] = await Promise.all([
        getJson(`/api/news/latest?limit=120${sourceFilterQuery()}`),
        getJson(`/api/news/top-signals?limit=120${sourceFilterQuery()}`)
      ]);
      latestItems = Array.isArray(latest) ? latest : [];
      topItems = Array.isArray(top) ? top : [];
      pageState.latest = 1;
      pageState.top = 1;
      renderLatestPage();
      renderTopPage();
      await refreshCollections();
      renderMatchReview();
    }

    async function importSourcesFromText() {
      const text = document.getElementById('sourceInput').value.trim();
      if (!text) {
        setStatus('Paste at least one source first.', true);
        return;
      }

      setButtonBusy('importBtn', true, 'Importing sources...');
      setStatus('Importing sources...');
      try {
        const result = await postJson('/api/news/sources/import-text', { text });
        setStatus(`Added ${result.added_count} sources`);
        await refreshSources();
      } catch (err) {
        console.error(err);
        setStatus('Failed to import sources.', true);
      } finally {
        setButtonBusy('importBtn', false);
      }
    }

    async function saveEdit() {
      const index = Number(document.getElementById('editIndex').value);
      if (Number.isNaN(index)) {
        setStatus('Select a source via Edit button first.', true);
        return;
      }

      await postJson('/api/news/sources/update', {
        index,
        name: document.getElementById('editName').value,
        homepage: document.getElementById('editHomepage').value,
        type: document.getElementById('editType').value,
        url: document.getElementById('editUrl').value,
        priority: document.getElementById('editPriority').value,
        interest_topic: document.getElementById('editInterest').value,
      });

      setStatus(`Saved source #${index}`);
      await refreshSources();
    }

    async function dedupeSources() {
      const result = await postJson('/api/news/sources/dedupe');
      setStatus(`Dedupe done: removed ${result.removed_count} (${result.before} -> ${result.after})`);
      await refreshSources();
    }

    async function rediscoverRSS() {
      setButtonBusy('rediscoverBtn', true, 'Checking RSS...');
      startOperationProgress({
        title: 'RSS discovery running',
        step: 'Checking source homepages and RSS candidates...',
        initialPercent: 8,
        targetPercent: 18,
        sourceRows: sourceProgressRowsForCurrentSources('pending', 'Queued for RSS discovery'),
      });
      setStatus('Checking RSS feeds and source homepages...');
      try {
        const result = await startBackendJob('rediscover_rss', { only_scrape: false, with_debug: true }, {
          title: 'RSS discovery running',
          step: 'Starting backend RSS discovery job...',
          sourceRows: sourceProgressRowsForCurrentSources('pending', 'Queued for RSS discovery'),
        });
        let msg = `Rediscover done. updated=${result.updated_count}, checked=${result.checked_count || 0}`;
        if (Array.isArray(result.details)) {
          const misses = result.details.filter(d => d.status === 'no_feed_found');
          if (misses.length) {
            const sample = misses.slice(0, 2).map(m => {
              const base = `${m.source_name || m.homepage}: candidates=${m.candidate_count || 0}`;
              return m.homepage_error ? `${base}, homeErr=${m.homepage_error}` : base;
            }).join(' | ');
            msg += ` | no-feed sample: ${sample}`;
          }
        }
        setStatus(msg, (result.updated_count || 0) === 0);
        await refreshSources();
        stopRunProgress(true, 'RSS discovery completed.', 'RSS discovery completed');
      } catch (err) {
        console.error(err);
        stopRunProgress(false, 'RSS discovery failed.', 'RSS discovery failed');
        setStatus('RSS discovery failed: ' + (err?.message || 'Unknown error'), true);
      } finally {
        setButtonBusy('rediscoverBtn', false);
      }
    }

    async function sourceHealth() {
      setButtonBusy('healthBtn', true, 'Checking health...');
      startOperationProgress({
        title: 'Source health running',
        step: 'Checking enabled sources...',
        initialPercent: 8,
        targetPercent: 20,
        sourceRows: sourceProgressRowsForCurrentSources('pending', 'Queued for health check'),
      });
      setStatus('Checking source health...');
      try {
        const result = await startBackendJob('source_health', { only_enabled: true }, {
          title: 'Source health running',
          step: 'Starting backend source health job...',
          sourceRows: sourceProgressRowsForCurrentSources('pending', 'Queued for health check'),
        });
        const items = Array.isArray(result.items) ? result.items : [];
        if (!items.length) {
          setStatus('Health: no enabled sources found.', true);
          stopRunProgress(false, 'No enabled sources found.', 'Source health stopped');
          return;
        }
        const bad = items.filter(x => x.status !== 'healthy');
        const sample = bad.slice(0, 2).map(x => `${x.source}:${x.status}${x.detail ? `(${x.detail})` : ''}`).join(' | ');
        const msg = `Health done. total=${items.length}, issues=${bad.length}${sample ? ` | sample: ${sample}` : ''}`;
        setStatus(msg, bad.length > 0);
        await refreshSources();
        stopRunProgress(true, 'Source health completed.', 'Source health completed');
      } catch (err) {
        console.error(err);
        stopRunProgress(false, 'Source health failed.', 'Source health failed');
        setStatus('Source health failed: ' + (err?.message || 'Unknown error'), true);
      } finally {
        setButtonBusy('healthBtn', false);
      }
    }

    async function runMatchReviewQueue() {
      setButtonBusy('runMatchBtn', true, 'Running match AI...');
      startOperationProgress({
        title: 'Match review AI running',
        step: 'Checking candidate article pairs...',
        initialPercent: 10,
        targetPercent: 24,
        sourceRows: [],
      });
      setStatus('Running match review AI...');
      try {
        const result = await startBackendJob('match_review', {
          domain_bucket: currentDomainFilter(),
        }, {
          title: 'Match review AI running',
          step: 'Starting backend match review job...',
        });
        setStatus(`Match run done. checked=${result.checked_pairs}, queued=${result.enqueued_pairs}, AI-feil=${result.fallback_pairs}, utsatt=${result.deferred_pairs || 0}`);
        setRunProgressStep('Refreshing match review queue...', 86);
        await refreshMatchReview();
        stopRunProgress(true, 'Match review queue refreshed.', 'Match review AI completed');
      } catch (err) {
        console.error(err);
        stopRunProgress(false, 'Match review AI failed.', 'Match review AI failed');
        setStatus('Match review AI failed: ' + (err?.message || 'Unknown error'), true);
      } finally {
        setButtonBusy('runMatchBtn', false);
      }
    }

    // quick: the header button fetches the last two days (already stored articles are skipped), with a short status next to it.
    async function runPipeline(quick = false) {
      const daysInput = Number(document.getElementById('fetchDaysBack')?.value || 7);
      const days_back = quick ? 2 : Number.isFinite(daysInput) ? Math.max(1, Math.min(90, Math.trunc(daysInput))) : 7;
      const quickStatus = document.getElementById('quickFetchStatus');
      quickFetchActive = quick;

      setButtonBusy('runPipelineBtn', true, 'Running fetch + processing...');
      setButtonBusy('quickFetchBtn', true, 'Fetching…');
      quickStatus.textContent = quick ? 'Starting…' : '';
      startRunProgress(days_back);
      if (!quick) setStatus(`Running fetch + processing (days_back=${days_back}) ...`);
      try {
        setRunProgressStep('Contacting backend and preparing fetch pipeline...', 18);
        const result = await startBackendJob('fetch_process', { days_back }, {
          title: 'Fetch + processing running',
          step: 'Starting backend fetch/process job...',
          sourceRows: sourceProgressRowsForCurrentSources('pending', 'Queued for fetch'),
        });
        latestSourceReportBySource = {};
        if (Array.isArray(result.source_report)) {
          renderSourceProgress(result.source_report);
          for (const row of result.source_report) {
            if (row?.source) latestSourceReportBySource[row.source] = row;
          }
        }
        setRunProgressStep('Refreshing cards, collections and health state...', 82);

        let msg = `Done. fetched=${result.fetched_candidates}, dropped_old=${result.dropped_old_items || 0}, new=${result.new_raw_items}, queue=${result.queued_for_processing || 0}, processed=${result.processed_items} (new=${result.processed_new_items || 0}, backlog=${result.processed_backlog_items || 0}), errors=${result.processing_errors || 0}`;
        if (Array.isArray(result.processing_error_samples) && result.processing_error_samples.length ) {
          msg += ` | sample_error=${result.processing_error_samples[0]}`;
        }
        if ((result.fetched_candidates || 0) === 0 && Array.isArray(result.source_report)) {
          const summary = result.source_report.map(r => `${r.source}:items=${r.items},filtered=${r.filtered || 0}${r.error ? ` (${r.error})` : ''}`).join(' | ');
          msg += ` | sources => ${summary}`;
        }

        if (quick) {
          const fresh = result.processed_new_items || 0;
          quickStatus.textContent = `${fresh} new ${fresh === 1 ? 'article' : 'articles'}${result.processing_errors ? ` · ${result.processing_errors} errors` : ''}`;
        } else setStatus(msg, (result.fetched_candidates || 0) === 0);
        await refreshSignals();
        setRunProgressStep('Signals refreshed. Updating collections...', 88);
        await refreshCollections();
        setRunProgressStep('Collections refreshed. Updating review queue...', 92);
        await refreshMatchReview();
        setRunProgressStep('Review queue refreshed. Updating source table...', 96);
        await refreshSources();
        stopRunProgress(true, 'Fetch, processing and UI refresh completed.', 'Fetch + processing completed');
      } catch (err) {
        console.error(err);
        stopRunProgress(false, 'Run failed before the pipeline returned a complete result.', 'Fetch + processing failed');
        if (quick) quickStatus.textContent = 'Fetch failed: ' + (err?.message || 'Unknown error');
        else setStatus('Fetch + processing failed: ' + (err?.message || 'Unknown error'), true);
      } finally {
        quickFetchActive = false;
        setButtonBusy('runPipelineBtn', false);
        setButtonBusy('quickFetchBtn', false);
      }
    }
