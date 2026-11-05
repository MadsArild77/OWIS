    async function refreshOpsReport() {
      const button = document.getElementById('refreshOpsReport');
      const container = document.getElementById('opsReport');
      button.disabled = true;
      container.textContent = 'Loading...';
      try {
        const report = await getJson('/api/news/ops-report?days=30');
        container.innerHTML = report.sections.map(section => `<h4>${escapeHtml(section.title)}</h4>` +
          (section.summary ? `<p>${escapeHtml(section.summary)}</p>` : '') + section.tables.map(table =>
            (table.title ? `<h5>${escapeHtml(table.title)}</h5>` : '') +
            (!table.rows.length ? '<p>No data in this period.</p>' :
              '<div class="table-wrap"><table class="sources-table"><thead><tr>' +
              table.columns.map(column => `<th>${escapeHtml(column)}</th>`).join('') + '</tr></thead><tbody>' +
              table.rows.map(row => '<tr>' + row.map((value, index) => '<td>' + escapeHtml(
                value == null ? 'Not recorded' : String(value) +
                (table.percentages.includes(index) && typeof value === 'number' ? '%' : '')) + '</td>').join('') + '</tr>').join('') +
              '</tbody></table></div>')).join('')).join('');
      } catch (error) {
        container.textContent = 'Could not load system health. ' + error.message;
      } finally {
        button.disabled = false;
      }
    }
    document.getElementById('refreshOpsReport').addEventListener('click', refreshOpsReport);
    document.getElementById('showSettingsView').addEventListener('click', refreshOpsReport);

    // Source advisor: learned source quality with add / pause recommendations.
    let adviceDecisionDays = 60;
    async function showSearchBudget() {
      try {
        const b = await getJson('/api/news/search-budget');
        const resets = new Date(b.resets_on).toLocaleDateString('en-GB', {day: 'numeric', month: 'short'});
        const text = `Web searches this month: ${b.used} of ${b.limit} (research ${b.by_purpose.research}, policy ${b.by_purpose.policy}, `
          + `paywalled stories ${b.by_purpose.alternative}, extra coverage ${b.by_purpose.coverage}). `
          + `Automatic searches today: ${b.automatic_today} of ${b.automatic_per_day}. ${b.research_reserve} are kept for your own research. Resets ${resets}.`;
        for (const id of ['searchBudget', 'settingsSearchBudget']) {
          const el = document.getElementById(id);
          if (el) el.textContent = text;
        }
      } catch (error) { /* budget display is informational */ }
    }
    document.getElementById('showSettingsView').addEventListener('click', showSearchBudget);
    async function loadSourceAdvice() {
      const status = document.getElementById('adviceStatus');
      status.textContent = 'Loading…';
      let data;
      try { data = await getJson('/api/news/source-advisor'); }
      catch (error) { status.textContent = 'Could not load source advice.'; status.classList.add('warn'); return; }
      status.textContent = ''; status.classList.remove('warn');
      adviceDecisionDays = data.decision_days || 60;
      showSearchBudget();
      document.getElementById('navAdviceCount').textContent = (data.add.length + data.remove.length + (data.resume || []).length) || '';
      const shortDate = value => value ? new Date(value).toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric'}) : '';
      const resume = data.resume || [];
      document.getElementById('adviceResumeBlock').hidden = !resume.length;
      document.getElementById('adviceResume').innerHTML = resume.map(item => `
        <article class="advice-card" data-key="${escapeHtml(item.key)}">
          <div>
            <h4>${escapeHtml(item.name)}</h4>
            <p>${escapeHtml(item.reason)}</p>
            <ul>${item.examples.map(e => `<li><a href="${escapeHtml(e.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(e.title)}</a></li>`).join('')}</ul>
          </div>
          <div class="advice-actions">
            <button type="button" data-advice-resume="${item.index}" data-key="${escapeHtml(item.key)}">Resume source</button>
            <button type="button" class="btn-secondary" data-advice-keep="${escapeHtml(item.key)}">Keep paused</button>
          </div>
        </article>`).join('');
      const labels = {kept: 'Kept', dismissed: 'Dismissed', added: 'Added', paused: 'Paused'};
      const decisions = data.decisions || [];
      document.getElementById('adviceDecisionsBlock').hidden = !decisions.length;
      document.getElementById('adviceDecisions').innerHTML = decisions.map(d => `<tr>
          <td>${escapeHtml(d.key.split(':').slice(1).join(':'))}</td><td>${escapeHtml(labels[d.decision] || d.decision)}</td>
          <td>${escapeHtml(shortDate(d.decided_at))}</td><td>${escapeHtml(shortDate(d.reconsider_from))}</td>
          <td><button type="button" class="btn-ghost" style="margin:0" data-advice-undo="${escapeHtml(d.key)}">Reconsider now</button></td></tr>`).join('');
      document.getElementById('adviceWindow').textContent =
        `Last ${data.window_days} days. The ranking weight starts from the source's trade-press credibility and moves toward what it actually delivers as articles accumulate.`;
      const pct = value => `${Math.round((Number(value) || 0) * 100)} %`;
      const strategyLabels = {direct: 'Direct', extract: 'Via Tavily', closed: 'Paywalled or blocked', learning: 'Still learning'};
      const rate = (ok, tries) => tries ? `${ok} of ${tries}` : '–';
      const fulltext = data.fulltext || [];
      document.getElementById('adviceFulltext').innerHTML = fulltext.length ? fulltext.map(row => `<tr>
          <td>${escapeHtml(row.source)}</td><td>${escapeHtml(strategyLabels[row.strategy] || row.strategy)}</td>
          <td>${rate(row.direct_successes, row.direct_attempts)}</td><td>${rate(row.extract_successes, row.extract_attempts)}</td>
          <td>${escapeHtml(row.extract_last_at > (row.direct_last_at || '') ? row.extract_last_result : row.direct_last_result || '')}</td></tr>`).join('')
        : '<tr><td colspan="5" class="muted">Filled in as new articles are fetched.</td></tr>';
      const bar = value => `<span class="share-bar"><span style="width:${Math.round((Number(value) || 0) * 100)}%"></span></span>${pct(value)}`;

      const add = document.getElementById('adviceAdd');
      add.innerHTML = data.add.length ? data.add.map(item => `
        <article class="advice-card" data-key="${escapeHtml(item.key)}">
          <div>
            <h4>${escapeHtml(item.name)} <span class="muted" style="font-weight:400">· ${escapeHtml(item.host)}</span></h4>
            <p>${escapeHtml(item.reason)} <span class="muted">(${escapeHtml(item.origins.join(', '))})</span></p>
            <ul>${item.examples.map(e => `<li><a href="${escapeHtml(e.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(e.title)}</a></li>`).join('')}</ul>
          </div>
          <div class="advice-actions">
            <button type="button" data-advice-add="${escapeHtml(item.host)}" data-name="${escapeHtml(item.name)}">Add source</button>
            <button type="button" class="btn-secondary" data-advice-dismiss="${escapeHtml(item.key)}">Dismiss</button>
          </div>
        </article>`).join('')
        : '<div class="empty-state"><strong>No new sources to suggest yet</strong>Suggestions appear when other websites repeatedly supply verified coverage of your stories, for example open versions of paywalled articles or sources found in research.</div>';

      const remove = document.getElementById('adviceRemove');
      remove.innerHTML = data.remove.length ? data.remove.map(item => `
        <article class="advice-card" data-key="${escapeHtml(item.key)}">
          <div>
            <h4>${escapeHtml(item.name)}</h4>
            <p>${escapeHtml(item.reason)}</p>
            <p class="muted">${item.articles} articles · ${pct(item.offshore_share)} offshore wind · ${pct(item.focus_share)} wind &amp; related · ranking weight ${item.learned_weight}/10</p>
          </div>
          <div class="advice-actions">
            <button type="button" class="btn-warning" data-advice-pause="${item.index}" data-key="${escapeHtml(item.key)}">Pause source</button>
            <button type="button" class="btn-secondary" data-advice-keep="${escapeHtml(item.key)}">Keep</button>
          </div>
        </article>`).join('')
        : '<div class="empty-state"><strong>All active sources look useful</strong>Sources that are mostly off-focus, failing or silent will appear here.</div>';

      document.getElementById('adviceScorecard').innerHTML = data.scorecard.map(row => {
        const change = row.learned_weight - row.prior_weight;
        const weight = change === 0 ? `${row.learned_weight}/10`
          : `${row.prior_weight} → <span class="weight-change ${change > 0 ? 'up' : 'down'}">${row.learned_weight}/10</span>`;
        const feedback = row.positive_feedback + row.negative_feedback
          ? `${row.positive_feedback} 👍 · ${row.negative_feedback} 👎` : '–';
        const state = !row.enabled ? 'Paused' : row.health === 'red' ? 'Failing' : 'Active';
        return `<tr><td><strong>${escapeHtml(row.name)}</strong></td><td>${row.articles}</td><td>${bar(row.offshore_share)}</td>
          <td>${bar(row.focus_share)}</td><td>${row.strong_signals}</td><td>${feedback}</td><td>${weight}</td>
          <td><span class="health-dot health-${escapeHtml(row.health)}"></span>${state}</td></tr>`;
      }).join('');
    }

    document.addEventListener('click', async event => {
      const target = event.target.closest('[data-advice-add],[data-advice-dismiss],[data-advice-pause],[data-advice-keep],[data-advice-resume],[data-advice-undo]');
      if (!target) return;
      const status = document.getElementById('adviceStatus');
      const decide = (key, decision) => postJson('/api/news/source-advisor/decision', {key, decision});
      target.disabled = true;
      try {
        if (target.dataset.adviceAdd) {
          const host = target.dataset.adviceAdd;
          const result = await postJson('/api/news/sources/import-text', {text: `${target.dataset.name} - https://${host}`});
          await decide(`add:${host}`, 'added');
          status.textContent = result.added_count ? `${target.dataset.name} added. RSS was looked up automatically; check it under Settings → News sources.` : `${host} is already in your sources.`;
          refreshSources?.().catch?.(() => {});
        } else if (target.dataset.adviceDismiss) {
          await decide(target.dataset.adviceDismiss, 'dismissed');
          status.textContent = `Dismissed. It can come back if the website keeps supplying coverage after today (reconsidered after ${adviceDecisionDays} days).`;
        } else if (target.dataset.advicePause) {
          await postJson('/api/news/sources/toggle', {index: Number(target.dataset.advicePause), enabled: false});
          await decide(target.dataset.key, 'paused');
          status.textContent = 'Source paused. Its history is kept, and you can resume it under Settings.';
          refreshSources?.().catch?.(() => {});
        } else if (target.dataset.adviceResume) {
          await postJson('/api/news/sources/toggle', {index: Number(target.dataset.adviceResume), enabled: true});
          await decide(target.dataset.key, 'added');
          status.textContent = 'Source resumed. It is included from the next fetch.';
          refreshSources?.().catch?.(() => {});
        } else if (target.dataset.adviceKeep) {
          await decide(target.dataset.adviceKeep, 'kept');
          status.textContent = `Kept. OWIS will look at this source again in ${adviceDecisionDays} days, based on new data.`;
        } else if (target.dataset.adviceUndo) {
          await decide(target.dataset.adviceUndo, 'undo');
          status.textContent = 'The decision is cleared; the source is judged again on current data.';
        }
        await loadSourceAdvice();
      } catch (error) {
        status.textContent = error.message || 'The action failed.'; status.classList.add('warn');
        target.disabled = false;
      }
    });
    document.getElementById('adviceRefresh').addEventListener('click', loadSourceAdvice);

    // Links from the other pages (e.g. /einnsyn) open a section directly: /news#morning, #governance, #settings
    {
      const section = decodeURIComponent(location.hash.slice(1));
      if (section === 'settings') document.getElementById('showSettingsView').click();
      else if (section) document.querySelector(`.nav-item.tab-btn[data-tab="${CSS.escape(section)}"]`)?.click();
    }
