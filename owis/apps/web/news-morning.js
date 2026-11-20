
    let displayedMorningReport = null;
    let latestPolicyReport = null;
    let morningPollTimer = null;
    let morningLoadVersion = 0;
    let monitoredType = '';
    let monitoredOffset = 0;
    let monitoredVersion = 0;

    function monitoredRow(item) {
      const kind = {consultation:'Consultation', calendar:'Calendar', regulation:'Regulation'}[item.content_type] || '';
      const deadline = item.deadline ? new Date(item.deadline) : null;
      const now = new Date();
      const urgent = deadline && deadline > now && deadline - now <= 7 * 86400000;
      const deadlineText = deadline && !isNaN(deadline) ? deadline.toLocaleDateString('en-GB', {
        day:'numeric', month:'short', ...(deadline.getUTCFullYear() !== now.getUTCFullYear() ? {year:'numeric'} : {}), timeZone:'UTC'
      }) : '';
      return `<article class="research-panel"><h4>${reportSourceLink(item.url, item.title)}</h4>
        <p class="muted">${escapeHtml(item.organisation)} · ${escapeHtml(item.jurisdiction)} · ${item.content_type === 'regulation' ? kind : `<span class="sources-badge">${kind}</span>`} · ${osloTime(item.published_at || item.first_seen_at)}${deadlineText ? ` · <span${urgent ? ' style="color:var(--warn)"' : ''}>Deadline ${deadlineText}</span>` : ''}</p></article>`;
    }

    async function loadMonitoredPolicy(more = false) {
      const version = ++monitoredVersion;
      const offset = more ? monitoredOffset : 0;
      const root = document.getElementById('monitoredItems');
      const button = document.getElementById('monitoredMore');
      button.disabled = true;
      try {
        const query = new URLSearchParams({region:document.getElementById('policyRegion').value, content_type:monitoredType, offset});
        const data = await getJson('/api/policy/items?' + query);
        if (version !== monitoredVersion) return;
        let day = '';
        const html = data.items.map(item => {
          const date = new Date(item.published_at || item.first_seen_at).toLocaleDateString('en-GB', {timeZone:'Europe/Oslo'});
          const heading = monitoredType !== 'consultation' && date !== day ? `<h4>${escapeHtml(date)}</h4>` : '';
          day = date;
          return heading + monitoredRow(item);
        }).join('');
        root.innerHTML = html || '<p class="muted">No new items from monitored policy sources in this period.</p>';
        monitoredOffset = offset + data.items.length;
        button.hidden = monitoredOffset >= data.total;
        document.getElementById('monitoredSources').innerHTML = data.sources.map(source => `<p>
          ${escapeHtml(source.name)} · Last fetched: ${source.last_fetched ? osloTime(source.last_fetched) : 'Never'} · Last saved: ${source.last_saved ? osloTime(source.last_saved) : 'Never'}
          ${source.error ? `<span style="color:var(--danger)">${escapeHtml(source.error)}</span>` : ''}</p>`).join('');
      } catch (error) {
        if (version === monitoredVersion) root.textContent = `Could not load monitored sources: ${error.message}`;
      } finally {
        if (version === monitoredVersion) button.disabled = false;
      }
    }

    function monitoredReportHtml(report) {
      const items = report.monitored_policy || [];
      return items.length ? '<h3>New from monitored sources</h3>' + items.slice(0, 10).map(monitoredRow).join('')
        + '<p><a href="#governance">Policy &amp; regulation — view all monitored items</a></p>' : '';
    }

    function reportSourceLink(url, label) {
      return /^https?:\/\//i.test(url || '') ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>` : escapeHtml(label);
    }

    function policySection(title, events, region = '') {
      const rows = events.filter(event => !region || event.region === region);
      return `<h3>${title}</h3>${rows.length ? rows.map(event => `<article class="research-panel">
        <p class="muted">${escapeHtml(event.jurisdiction)} · ${escapeHtml(event.region)} · ${escapeHtml(event.event_date || 'Date not confirmed')} · ${escapeHtml(event.kind.replaceAll('_',' '))}</p>
        <h4>${escapeHtml(event.title)}</h4>
        <p><strong>Status: ${escapeHtml(event.legal_status.replaceAll('_',' '))}</strong> · AI-extracted</p>
        <p>${escapeHtml(event.summary)}</p>
        <p><strong>Why it matters · analysis:</strong> ${escapeHtml(event.implications)}</p>
        <p>${reportSourceLink(event.source.url, event.source.title || 'Official source')} · ${event.source.basis === 'fulltext' ? 'Official page text' : 'Search excerpt only'}</p>
        <details><summary>Supporting evidence</summary><blockquote>${escapeHtml(event.evidence_quote)}</blockquote>
          ${event.date_quote ? `<p>Date evidence: ${escapeHtml(event.date_quote)}</p>` : ''}
          ${event.proposed_date ? `<p>Unconfirmed date candidate: ${escapeHtml(event.proposed_date)}. Verify in the original source.</p>` : ''}
        </details>
      </article>`).join('') : '<p class="muted">No findings in this saved report. This does not establish that nothing is scheduled.</p>'}`;
    }

    function coverageHtml(report) {
      return `<p class="muted">${escapeHtml(report.coverage_note)}</p>
        ${report.warnings.length ? `<div class="research-panel"><strong>Coverage limitations</strong><ul>${report.warnings.map(text => `<li>${escapeHtml(text)}</li>`).join('')}</ul></div>` : ''}
        <details><summary>Sources checked</summary>
          <h4>Policy sources</h4><ul>${report.policy_coverage.map(row => `<li>${escapeHtml(row.region)} — ${escapeHtml(row.domains.join(', '))}: ${escapeHtml(row.status)} (${row.sources_read} sources, ${row.fulltext_sources || 0} full texts)</li>`).join('')}</ul>
          <h4>News sources</h4><ul>${report.news_coverage.map(row => `<li>${escapeHtml(row.source || 'Source')}: ${escapeHtml(row.error ? 'Failed' : `${row.items || 0} items`)}</li>`).join('')}</ul>
        </details>`;
    }

    function renderPolicy(report) {
      const root = document.getElementById('policyBody');
      if (!report) { root.innerHTML = '<p>No saved policy outlook. Generate a morning report to start.</p>'; return; }
      const region = document.getElementById('policyRegion').value;
      root.innerHTML = `<p class="muted">Report ${escapeHtml(report.report_date)} · Saved ${escapeHtml(new Date(report.generated_at).toLocaleString('en-GB', {timeZone:'Europe/Oslo'}))} (Oslo). Sections are relative to this report date.</p>`
        + policySection('Today', report.today, region) + policySection('Next 90 days', report.upcoming, region)
        + policySection('On the radar · date not confirmed', report.watchlist, region) + coverageHtml(report);
    }

    function osloTime(value) {
      return escapeHtml(new Date(value).toLocaleString('en-GB', {timeZone:'Europe/Oslo', dateStyle:'short', timeStyle:'short'}));
    }

    function briefHtml(brief, stories) {
      const byId = new Map();
      for (const story of stories || []) for (const source of story.sources) byId.set(source.id, story);
      const sourcesFor = ids => {
        const seen = new Set();
        return ids.map(id => byId.get(id)).filter(Boolean).flatMap(story => story.sources)
          .filter(source => !seen.has(source.article_url) && seen.add(source.article_url))
          .map(source => reportSourceLink(source.article_url, source.source_name)).join(' · ');
      };
      const list = (title, rows) => rows && rows.length ? `<h4>${title}</h4><ul>${rows.map(row => `<li>${escapeHtml(row)}</li>`).join('')}</ul>` : '';
      return `<article class="research-panel brief">
        <p class="brief-headline">${escapeHtml(brief.headline)}</p>
        ${brief.overview ? `<p>${escapeHtml(brief.overview)}</p>` : ''}
        ${brief.key_developments.length ? `<h4>Key developments</h4><ol>${brief.key_developments.map(item => `<li>
          <strong>${escapeHtml(item.headline)}</strong>
          ${item.what_happened ? `<p>${escapeHtml(item.what_happened)}</p>` : ''}
          ${item.why_it_matters ? `<p><em>Why it matters:</em> ${escapeHtml(readableText(item.why_it_matters))}</p>` : ''}
          ${item.story_ids.length ? `<p class="brief-sources">${sourcesFor(item.story_ids)}</p>` : ''}
        </li>`).join('')}</ol>` : ''}
        ${brief.trends && brief.trends.length ? `<h4>Trends from the past days</h4><ul>${brief.trends.map(item => `<li>
          <strong>${escapeHtml(item.headline)}</strong>${item.detail ? ` — ${escapeHtml(item.detail)}` : ''}
          ${item.story_ids.length ? `<p class="brief-sources">${sourcesFor(item.story_ids)}</p>` : ''}
        </li>`).join('')}</ul>` : ''}
        ${list('Policy & regulation', brief.policy)}${list('Watch next', brief.watch)}
        <p class="muted">${brief.ai ? 'AI-written summary of the collected stories; check the sources before acting.' : 'AI is not enabled: showing the highest-ranked stories without a written summary.'}</p>
      </article>`;
    }

    function storySources(stories) {
      const byId = new Map();
      for (const story of stories || []) {
        byId.set(story.id, story);
        for (const source of story.sources) byId.set(source.id, story);
      }
      return ids => {
        const seen = new Set();
        return (ids || []).map(id => byId.get(id)).filter(Boolean).flatMap(story => story.sources)
          .filter(source => !seen.has(source.article_url) && seen.add(source.article_url))
          .map(source => reportSourceLink(source.article_url, source.source_name));
      };
    }

    function shortDate(value) {
      const date = new Date(value + 'T12:00:00Z');
      return isNaN(date) ? escapeHtml(value) : escapeHtml(date.toLocaleDateString('en-GB', {day:'numeric', month:'short', timeZone:'UTC'}));
    }

    function sectionBriefHtml(brief, stories) {
      const sourcesFor = storySources(stories);
      const item = row => {
        const links = [...sourcesFor(row.story_ids), ...(row.policy || []).map(link => reportSourceLink(link.url, link.title))];
        return `<li><strong>${escapeHtml(row.headline)}</strong>
          ${row.what_happened ? `<p>${escapeHtml(row.what_happened)}</p>` : ''}
          ${row.why_it_matters ? `<p><em>So what:</em> ${escapeHtml(readableText(row.why_it_matters))}</p>` : ''}
          ${links.length ? `<p class="brief-sources">${links.join(' · ')}</p>` : ''}</li>`;
      };
      return `<p class="muted">Top story</p><p class="brief-headline">${escapeHtml(brief.headline)}</p>
        ${brief.in_brief && brief.in_brief.length ? `<h4>In brief</h4><ul>${brief.in_brief.map(row => `<li>${escapeHtml(row)}</li>`).join('')}</ul>` : ''}
        ${brief.sections.map(section => `<h4>${escapeHtml(section.title)}</h4><ol>${section.items.map(item).join('')}</ol>`).join('')}
        ${brief.trends && brief.trends.length ? `<h4>Trends from the past days</h4><ul>${brief.trends.map(row => `<li>
          <strong>${escapeHtml(row.headline)}</strong>${row.detail ? ` — ${escapeHtml(row.detail)}` : ''}
          ${row.story_ids.length ? `<p class="brief-sources">${sourcesFor(row.story_ids).join(' · ')}</p>` : ''}</li>`).join('')}</ul>` : ''}`;
    }

    function deadlinesHtml(rows) {
      return `<h4>Deadlines &amp; events · next 14 days</h4>${rows.length ? `<ul>${rows.map(row => `<li>
        <strong>${shortDate(row.date)}</strong> · ${escapeHtml(row.kind)} · ${reportSourceLink(row.url, row.title)}${row.where ? ` <span class="muted">· ${escapeHtml(row.where)}</span>` : ''}</li>`).join('')}</ul>`
        : '<p class="muted">No consultation, event or tender deadlines found for the next 14 days.</p>'}`;
    }

    function tendersHtml(rows) {
      return `<h4>New tenders · last 24 hours</h4>${rows.length ? `<ul>${rows.map(row => `<li>${reportSourceLink(row.source_url, row.title)}
        <span class="muted">· ${escapeHtml([row.buyer, row.country].filter(Boolean).join(', '))}${row.deadline ? ` · deadline ${shortDate(row.deadline.slice(0, 10))}` : ''} · ${escapeHtml(row.fit || '')} fit (${escapeHtml(row.profile_name || '')})</span></li>`).join('')}</ul>`
        : '<p class="muted">No new matching tenders since the previous report.</p>'}
        <p><a href="/opportunities">All tenders in Opportunities</a></p>`;
    }

    function renderSectionReport(state, report) {
      const brief = report.brief;
      const stories = [...report.news, ...(report.trend_stories || [])];
      const outlook = report.today.length + report.upcoming.length + report.watchlist.length;
      const monitored = report.monitored_policy || [];
      return `<p class="muted">${escapeHtml(new Date(report.report_date + 'T12:00:00Z').toLocaleDateString('en-GB', {weekday:'long', day:'numeric', month:'long', timeZone:'UTC'}))} · Window ${osloTime(report.window_start)} – ${osloTime(report.window_end)} (Oslo)</p>
        ${state.status !== 'completed' ? '<p>Showing the previous saved result while the new attempt is running or failed.</p>' : ''}
        <article class="research-panel brief">
          ${brief && brief.sections ? sectionBriefHtml(brief, stories) : brief ? briefHtml(brief, stories) : '<p>No collected stories with a confirmed publication timestamp in this window.</p>'}
          ${deadlinesHtml(report.deadlines || [])}
          ${tendersHtml(report.new_tenders || [])}
          ${brief && brief.watch && brief.watch.length ? `<h4>Watch next</h4><ul>${brief.watch.map(row => `<li>${escapeHtml(row)}</li>`).join('')}</ul>` : ''}
          <p class="muted">${brief && brief.ai ? 'AI-written summary of the collected stories; dates and tenders come from the sources. Check the sources before acting.' : 'AI is not enabled: showing the highest-ranked stories without a written summary.'}</p>
        </article>
        ${storyList(report.news, `All stories from the last 24 hours (${report.news.length} of ${report.news_total}, ranked by relevance)`)}
        ${outlook ? `<details><summary>Policy outlook from official sources (${outlook})</summary>${policySection('Today', report.today)}${policySection('Next 90 days', report.upcoming)}${policySection('On the radar · date not confirmed', report.watchlist)}</details>` : ''}
        ${monitored.length ? `<details><summary>New from monitored policy sources (${monitored.length})</summary>${monitored.map(monitoredRow).join('')}<p><a href="#governance">Policy &amp; regulation — view all monitored items</a></p></details>` : ''}
        <details><summary>Coverage &amp; warnings (${report.warnings.length})</summary>${coverageHtml(report)}</details>`;
    }

    function storyList(stories, title) {
      if (!stories || !stories.length) return '';
      return `<details><summary>${escapeHtml(title)}</summary>${stories.map(item => `<article class="research-panel"><h4>${escapeHtml(item.title)}</h4><p>${escapeHtml(item.summary)}</p><p><strong>Why it matters · analysis:</strong> ${escapeHtml(readableText(item.why_it_matters))}</p><p>${item.sources.map(source => reportSourceLink(source.article_url, source.source_name)).join(' · ')}</p></article>`).join('')}</details>`;
    }

    function renderMorning(state) {
      displayedMorningReport = state.result;
      const status = state.status === 'running' ? 'Collecting news and checking official policy sources. You can return later.' : state.error || (state.result ? 'Saved report ready.' : 'No morning report yet.');
      document.getElementById('morningStatus').textContent = status;
      document.getElementById('morningSchedule').textContent = state.schedule.enabled
        ? 'Automatic run: 06:00 Europe/Oslo, after the 05:00 news fetch has finished. The report summarises the news already fetched and uses earlier days for trends. OWIS must be running; a later startup catches up for today.'
        : 'Automatic 06:00 run is not enabled on this server. Reports can be generated here.';
      document.querySelector('[data-copy-morning]').disabled = !state.result;
      const report = state.result;
      const root = document.getElementById('morningBody');
      if (!report) { root.innerHTML = ''; return; }
      if (report.deadlines) { root.innerHTML = renderSectionReport(state, report); return; }
      root.innerHTML = `<p class="muted">${escapeHtml(report.report_date)} · Window ${osloTime(report.window_start)} – ${osloTime(report.window_end)} (Oslo).</p>
        ${state.status !== 'completed' ? '<p>Showing the previous saved result while the new attempt is running or failed.</p>' : ''}
        <h3>Summary</h3>
        ${report.brief ? briefHtml(report.brief, [...report.news, ...(report.trend_stories || [])]) : report.news.length ? '<p class="muted">This report was saved before written summaries were added.</p>' : '<p>No collected stories with a confirmed publication timestamp in this window.</p>'}
        ${storyList(report.news, `All stories from the last 24 hours (${report.news.length} of ${report.news_total}, ranked by relevance)`)}`
        + policySection('Today · policy & regulation', report.today)
        + policySection('Next 90 days · policy & regulation', report.upcoming)
        + policySection('On the radar · date not confirmed', report.watchlist) + monitoredReportHtml(report) + coverageHtml(report);
    }

    async function loadMorningReport() {
      const version = ++morningLoadVersion;
      clearTimeout(morningPollTimer);
      const date = document.getElementById('morningHistory').value;
      try {
        const [latest, history, selected] = await Promise.all([
          getJson('/api/news/morning-report'), getJson('/api/news/morning-report/history'),
          date ? getJson('/api/news/morning-report?report_date=' + encodeURIComponent(date)) : Promise.resolve(null)
        ]);
        if (version !== morningLoadVersion) return;
        const select = document.getElementById('morningHistory');
        select.innerHTML = '<option value="">Latest</option>' + history.map(row => `<option value="${escapeHtml(row.report_date)}">${escapeHtml(row.report_date)} · ${escapeHtml(row.status)}</option>`).join('');
        select.value = date;
        renderMorning(selected || latest);
        latestPolicyReport = latest.result;
        renderPolicy(latestPolicyReport);
        document.getElementById('policyStatus').textContent = latest.status === 'running' ? 'Updating the report and policy outlook…' : latest.error || '';
        document.querySelectorAll('[data-generate-morning]').forEach(button => button.disabled = latest.status === 'running');
        if (latest.status === 'running' && ['tab-morning','tab-governance'].some(id => document.getElementById(id).classList.contains('active'))) morningPollTimer = setTimeout(loadMorningReport, 3000);
      } catch (error) {
        if (version !== morningLoadVersion) return;
        for (const id of ['morningStatus','policyStatus']) document.getElementById(id).textContent = `Could not load report: ${error.message}. Reopen this tab to retry.`;
      }
    }

    async function generateMorningReport() {
      document.querySelectorAll('[data-generate-morning]').forEach(button => button.disabled = true);
      try {
        await postJson('/api/news/morning-report?refresh=true', {});
        document.getElementById('morningHistory').value = '';
        await loadMorningReport();
      } catch (error) {
        for (const id of ['morningStatus','policyStatus']) document.getElementById(id).textContent = error.message;
        document.querySelectorAll('[data-generate-morning]').forEach(button => button.disabled = false);
      }
    }

    function morningCopyText(report) {
      const lines = [`OWIS morning report · ${report.report_date}`, `Window: ${report.window_start} to ${report.window_end}`];
      const briefText = (title, brief) => {
        if (!brief) return;
        lines.push('', title, brief.headline, brief.overview);
        brief.key_developments.forEach((item, index) => lines.push('', `${index + 1}. ${item.headline}`, item.what_happened, `Why it matters: ${item.why_it_matters}`));
        if (brief.trends?.length) lines.push('', 'Trends from the past days:', ...brief.trends.map(row => `- ${row.headline}: ${row.detail}`));
        if (brief.policy.length) lines.push('', 'Policy & regulation:', ...brief.policy.map(row => `- ${row}`));
        if (brief.watch.length) lines.push('', 'Watch next:', ...brief.watch.map(row => `- ${row}`));
      };
      if (report.deadlines) {
        const brief = report.brief;
        if (brief) {
          lines.push('', 'TOP STORY', brief.headline);
          if (brief.in_brief?.length) lines.push('', 'IN BRIEF', ...brief.in_brief.map(row => `- ${row}`));
          for (const section of brief.sections || []) {
            lines.push('', section.title.toUpperCase());
            for (const item of section.items) lines.push('', item.headline, item.what_happened, item.why_it_matters ? `So what: ${item.why_it_matters}` : '', ...(item.policy || []).map(link => `${link.title}: ${link.url}`));
          }
          if (!brief.sections) brief.key_developments.forEach((item, index) => lines.push('', `${index + 1}. ${item.headline}`, item.what_happened, `Why it matters: ${item.why_it_matters}`));
        }
        lines.push('', 'DEADLINES & EVENTS · NEXT 14 DAYS', ...(report.deadlines.length ? report.deadlines.map(row => `- ${row.date} · ${row.kind} · ${row.title}${row.where ? ` (${row.where})` : ''} ${row.url}`) : ['None found.']));
        lines.push('', 'NEW TENDERS · LAST 24 HOURS', ...(report.new_tenders.length ? report.new_tenders.map(row => `- ${row.title} · ${[row.buyer, row.country].filter(Boolean).join(', ')}${row.deadline ? ` · deadline ${row.deadline.slice(0, 10)}` : ''} ${row.source_url}`) : ['None.']));
        if (brief?.watch?.length) lines.push('', 'WATCH NEXT', ...brief.watch.map(row => `- ${row}`));
        lines.push('', 'ALL STORIES');
        for (const item of report.news) lines.push('', item.title, ...item.sources.map(source => `${source.source_name}: ${source.article_url}`));
        lines.push('', 'COVERAGE', report.coverage_note, ...report.warnings);
        return lines.filter(line => line !== undefined).join('\n');
      }
      briefText('SUMMARY', report.brief);
      lines.push('', 'LAST 24 HOURS');
      for (const item of report.news) lines.push('', item.title, item.summary, `Analysis: ${item.why_it_matters}`, ...item.sources.map(source => `${source.source_name}: ${source.article_url}`));
      for (const [title, key] of [['TODAY','today'],['NEXT 90 DAYS','upcoming'],['ON THE RADAR — DATE NOT CONFIRMED','watchlist']]) {
        lines.push('', title);
        if (!report[key].length) lines.push('No findings in this report; coverage is not exhaustive.');
        for (const event of report[key]) lines.push('', `${event.event_date || 'Date unconfirmed'} · ${event.jurisdiction} · ${event.title}`, `Legal status (AI-extracted): ${event.legal_status}`, event.summary, `Analysis: ${event.implications}`, `Evidence: ${event.evidence_quote}`, event.date_quote ? `Date evidence: ${event.date_quote}` : '', `${event.source.url} (${event.source.basis})`);
      }
      lines.push('', 'COVERAGE', report.coverage_note, ...report.warnings);
      return lines.join('\n');
    }

    async function copyMorningReport() {
      if (!displayedMorningReport) return;
      const text = morningCopyText(displayedMorningReport);
      const status = document.getElementById('morningStatus');
      document.getElementById('morningCopyFallback')?.remove();
      try { await navigator.clipboard.writeText(text); status.textContent = 'Report copied.'; }
      catch (_) {
        status.textContent = 'Select and copy the report below.';
        const field = document.createElement('textarea');
        field.id = 'morningCopyFallback'; field.readOnly = true; field.rows = 12; field.style.width = '100%';
        field.setAttribute('aria-label','Morning report to copy'); field.value = text;
        status.after(field); field.focus(); field.select();
      }
    }
