
    async function loadResearchedStories() {
      const root = document.getElementById('researchedStories');
      root.textContent = 'Loading…';
      try {
        const rows = await getJson('/api/news/researched');
        root.innerHTML = rows.length ? rows.map(item => `<article class="research-panel">
          <h3>${escapeHtml(item.title)}</h3>
          <p class="muted">${escapeHtml(item.source_name)} · ${escapeHtml(item.research_status)} · ${escapeHtml(new Date(item.started_at).toLocaleString('en-GB'))}${item.has_result ? ' · Saved result available' : ''}</p>
          ${item.research_error ? `<p>${escapeHtml(item.research_error)}</p>` : ''}
          <button type="button" data-open-researched="${item.id}">Open story</button></article>`).join('') : '<p>No researched stories yet. Open a story and choose Research this story.</p>';
        root.querySelectorAll('[data-open-researched]').forEach(button => button.onclick = () => showItemDetails(Number(button.dataset.openResearched)));
      } catch (error) { root.textContent = `Could not load researched stories: ${error.message}. Use Refresh to retry.`; }
    }

    function storyCopyText(item, result) {
      const lines = ['Use the evidence below to draft a professional LinkedIn post. Separate facts from analysis, preserve source references, and do not invent facts or personal experiences.',
        '', item.title || 'Story', `Source: ${item.source_name || ''}`, item.article_url || '',
        `Published: ${item.published_at || 'Unknown'}`, '', 'Article summary', item.summary || '',
        '', 'Why it matters (analysis)', item.why_it_matters || ''];
      if (item.cleaned_text) lines.push('', 'Available article text (may be an excerpt)', item.cleaned_text);
      if (result) lines.push('', researchCopyText(result, item.title));
      else lines.push('', 'No saved research available. Use only the article material above.');
      return lines.join('\n');
    }

    function mountStoryCopy(item) {
      const bar = document.createElement('div');
      bar.className = 'detail-action-row';
      bar.innerHTML = '<button type="button" class="btn-secondary">Copy info</button><span role="status" aria-live="polite"></span>';
      document.getElementById('detailContent').prepend(bar);
      bar.querySelector('button').onclick = async () => {
        const status = bar.querySelector('[role="status"]');
        status.textContent = ' Preparing…';
        try {
          const state = await getJson(`/api/news/item/${item.id}/research`);
          if (!bar.isConnected) return;
          const text = storyCopyText(item, state.result);
          bar.querySelector('textarea')?.remove();
          try { await navigator.clipboard.writeText(text); status.textContent = ' Info copied.'; }
          catch (_) {
            status.textContent = ' Select and copy below.';
            const field = document.createElement('textarea');
            field.readOnly = true; field.rows = 10; field.style.width = '100%';
            field.setAttribute('aria-label', 'Story information to copy'); field.value = text;
            bar.append(field); field.focus(); field.select();
          }
        } catch (error) { status.textContent = ` Could not prepare info: ${error.message}. Try again.`; }
      };
    }

    function mountResearch(itemId) {
      if (!Number.isFinite(itemId) || itemId <= 0) return;
      const panel = document.createElement('section');
      panel.className = 'research-panel';
      panel.setAttribute('aria-label', 'Story research and LinkedIn potential');
      panel.innerHTML = '<h3>Story research</h3><p role="status">Loading saved research…</p>';
      document.getElementById('detailContent').append(panel);
      const endpoint = `/api/news/item/${itemId}/research`;
      let timer;
      function render(state) {
        if (!panel.isConnected) return;
        const result = state.result;
        const running = state.status === 'running';
        panel.innerHTML = `<h3>Story research</h3>
          <p class="muted">Research this article and assess its fit for your LinkedIn voice. Results are saved.</p>
          <button type="button" class="btn-secondary" data-research ${running || !state.available ? 'disabled' : ''}>${running ? 'Researching…' : result ? 'Refresh research' : 'Research this story'}</button>
          <p role="status">${escapeHtml(running ? 'Searching and analysing. You can close this view and return later.' : state.error || '')}</p>
          ${!state.available ? `<p class="muted">Research is not set up on this server yet, so this button is unavailable. You can still use Find more info.</p><details><summary>What needs to be configured</summary><p class="muted">${escapeHtml(state.setup_required)}</p></details>` : ''}
          <div data-research-result></div>`;
        if (result) {
          const sources = new Map(result.sources.map(source => [source.id, source]));
          const sourceLink = id => {
            const source = sources.get(id);
            if (!source || !/^https?:\/\//i.test(source.url || '')) return '';
            return `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(source.title)}">[${id}]</a>`;
          };
          const section = (title, claims, empty='') => `<h4>${title}</h4>${claims.length ? '<ul>'+claims.map(claim => `<li>${escapeHtml(claim.text)} ${claim.source_ids.map(sourceLink).join(' ')}</li>`).join('')+'</ul>' : `<p>${empty}</p>`}`;
          const rating = (title, value) => `<div><strong>${title}: ${escapeHtml(value.level)}</strong><p>${escapeHtml(value.reason)}</p></div>`;
          panel.querySelector('[data-research-result]').innerHTML = `
            <p class="muted">Saved ${escapeHtml(new Date(result.generated_at).toLocaleString('en-GB'))}${running || state.status === 'failed' ? ' · Previous saved result' : ''}</p>
            ${section('What happened',result.what_happened)}
            ${section('Key developments',result.key_developments,'No additional developments identified.')}
            ${section('Why it matters · analysis',result.why_it_matters,'No supported implications identified.')}
            ${section('What’s new',result.whats_new,'No additional facts found beyond the original article.')}
            <details><summary>Post angles and editorial fit</summary><p class="muted">Qualitative editorial judgement, not a prediction of reach or virality.</p>
            <div class="research-ratings">${rating('Brand fit',result.brand_fit)}${rating('Conversation potential',result.conversation_potential)}</div>
            <h4>Why this fits you</h4><p>${escapeHtml(result.why_this_fits_you)}</p>
            <h4>Possible angles</h4><ul>${result.suggested_angles.map(angle=>`<li>${escapeHtml(angle)}</li>`).join('')}</ul>
            <h4>What would strengthen it</h4><p>${escapeHtml(result.what_would_strengthen_it)}</p>
            </details><h4>Limitations</h4><p>${escapeHtml(result.limitations)}</p>
            <details><summary>Sources (${result.sources.length})</summary><ul>${result.sources.map(source=>`<li>${sourceLink(source.id)} ${escapeHtml(source.title)} — ${escapeHtml(source.relationship.replaceAll('_',' '))} · ${escapeHtml(source.basis.replaceAll('_',' '))}</li>`).join('')}</ul></details>`;
        }
        panel.querySelector('[data-research]').onclick = async event => {
          event.currentTarget.disabled = true;
          try { render(await postJson(endpoint + (result ? '?refresh=true' : ''), {})); }
          catch (error) { render({...state, error:error.message}); }
        };
        clearTimeout(timer);
        if (running) timer = setTimeout(load, 2000);
      }
      async function load() {
        if (!panel.isConnected) return;
        try { render(await getJson(endpoint)); }
        catch (error) {
          panel.innerHTML = `<h3>Story research</h3><p role="status">Could not load research: ${escapeHtml(error.message)}</p><button type="button">Retry</button>`;
          panel.querySelector('button').onclick = load;
        }
      }
      load();
    }

    // A case is written as one story: the AI account's title and summary once written,
    // until then the case name and its developments - never just the newest article's headline.
