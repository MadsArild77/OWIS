    function caseHeadline(group) {
      const c = group[0].case || {};
      return c.account?.title || (c.name ? `${c.name}: ${group.length} developments` : `${group.length} developments in this story`);
    }

    function caseBrief(group) {
      const account = group[0].case?.account;
      if (account?.summary) return shortText(account.summary, 340);
      const day = value => value ? new Date(value).toLocaleDateString('en-GB', {day: 'numeric', month: 'short'}) : '';
      return [...group].sort((a, b) => String(b.latest_published_at || '').localeCompare(String(a.latest_published_at || '')))
        .map(c => `${day(c.latest_published_at)}: ${cleanTitle(c.master?.title)}`).join(' · ');
    }

    // A case: its developments (merged events) on a timeline, newest first.
    function showCaseDetails(group) {
      const developments = [...group].sort((a, b) => String(b.latest_published_at || '').localeCompare(String(a.latest_published_at || '')));
      const latest = developments[0];
      activeDetailCollectionKey = String(latest.collection_key || '');
      activeDetailItemId = null;
      updateDetailCollectionNavButtons(activeDetailCollectionKey);
      openDetailOverlay();
      const articles = developments.reduce((sum, c) => sum + Number(c.article_count || 1), 0);
      const day = value => value ? new Date(value).toLocaleDateString('en-GB', {day: 'numeric', month: 'short'}) : '';
      document.getElementById('detailTitle').textContent = latest.case?.name || cleanTitle(latest.master?.title);
      document.getElementById('detailMeta').textContent = [`${developments.length} developments`, `${articles} articles`,
        `${day(developments[developments.length - 1].latest_published_at)} – ${day(latest.latest_published_at)}`].join(' · ');
      const account = latest.case?.account;
      document.getElementById('detailTitle').textContent = caseHeadline(developments);
      // The story comes first: the written account, or until it exists the latest development in full.
      document.getElementById('detailContent').innerHTML = `
        <div id="caseStory">${account ? caseAccountHtml(account) : `<div class="detail-summary">
          <strong>Latest development</strong>
          <div>${textBlockHtml(latest.master?.summary || 'n/a')}</div>
        </div>
        <div class="detail-why">
          <strong>Why it matters</strong>
          <div>${textBlockHtml(readableText(latest.master?.why_it_matters) || 'n/a')}</div>
        </div>`}</div>
        <p id="caseStoryStatus" class="muted" role="status" aria-live="polite"></p>
        <div class="detail-summary">
          <strong>Developments</strong>
          <ol class="case-timeline">${developments.map(c => `<li>
            <time datetime="${escapeHtml(c.latest_published_at || '')}">${escapeHtml(day(c.latest_published_at))}</time>
            <button type="button" data-case-development="${escapeHtml(c.collection_key)}">${escapeHtml(cleanTitle(c.master?.title))}</button>
            <p>${escapeHtml(shortText(c.master?.summary || '', 320))}</p>
            <div class="muted">${escapeHtml((c.master?.sources || []).join(', '))}</div>
          </li>`).join('')}</ol>
        </div>
        <div id="publicRecords"></div>`;
      loadPublicRecords(developments.flatMap(c => (c.items || []).map(i => Number(i.id))), String(latest.collection_key || ''));
      document.getElementById('detailContent').querySelectorAll('[data-case-development]').forEach(button => {
        button.addEventListener('click', () => showCollectionDetails(button.dataset.caseDevelopment));
      });
      if (!account?.complete) writeCaseStory(latest);
    }

    // eInnsyn cases naming the same project or company as this story (see /einnsyn).
    async function loadPublicRecords(itemIds, key) {
      const ids = itemIds.filter(Number.isFinite);
      if (!ids.length) return;
      try {
        const data = await getJson('/api/einnsyn/related?' + ids.map(id => `item_ids=${id}`).join('&'));
        const el = document.getElementById('publicRecords');
        if (!el || String(activeDetailCollectionKey || '') !== key || !data.items?.length) return;
        el.innerHTML = `<div class="detail-why">
          <strong>Public records (eInnsyn)</strong>
          <ul>${data.items.map(c => `<li><a href="/einnsyn?case=${encodeURIComponent(c.url || '')}">${escapeHtml(c.title)}</a>
            <span class="muted">${escapeHtml(c.case_number)} · ${escapeHtml(c.status)} · via ${escapeHtml(c.matched_on.join(', '))}</span></li>`).join('')}</ul>
        </div>`;
      } catch (error) { /* eInnsyn not configured: show nothing */ }
    }

    function caseAccountHtml(account) {
      return `<div class="detail-summary">
          <strong>The story so far</strong>
          <div>${textBlockHtml(account.summary)}</div>
        </div>
        <div class="detail-why">
          <strong>Why it matters</strong>
          <div>${textBlockHtml(account.why_it_matters || 'n/a')}</div>
          ${account.next_steps ? `<p><strong>What to watch:</strong> ${escapeHtml(account.next_steps)}</p>` : ''}
        </div>`;
    }

    // Opening a story without an up-to-date account writes it now (a few seconds) and keeps it.
    async function writeCaseStory(latest) {
      const key = String(latest.collection_key || '');
      const status = document.getElementById('caseStoryStatus');
      status.textContent = 'Writing the story from all developments…';
      try {
        const account = await postJson('/api/news/cases/account',
          {signature: latest.case.signature, domain_bucket: document.getElementById('domainFilter')?.value || 'core'});
        if (String(activeDetailCollectionKey || '') !== key) return;
        for (const col of mergedItems) if (col.case?.signature === latest.case.signature) col.case.account = account;
        document.getElementById('caseStory').innerHTML = caseAccountHtml(account);
        document.getElementById('detailTitle').textContent = account.title || document.getElementById('detailTitle').textContent;
        status.textContent = '';
        renderReadingPage();
      } catch (error) {
        if (String(activeDetailCollectionKey || '') === key) status.textContent = 'The full story is written at the next fetch.';
      }
    }

    function showCollectionDetails(collectionKey) {
      const collection = findCollectionByKey(collectionKey);
      if (!collection) return;

      activeDetailCollectionKey = String(collection.collection_key || '');
      activeDetailItemId = null;
      updateDetailCollectionNavButtons(activeDetailCollectionKey);
      openDetailOverlay();

      const master = collection.master || {};
      const items = Array.isArray(collection.items) ? collection.items : [];
      const imageUrl = cssImageUrl(master.image_url);
      const imageHtml = imageUrl
        ? `<img class="detail-preview-image" src="${escapeHtml(imageUrl)}" alt="${escapeHtml(master.title || 'Story image')}" onerror="this.remove()" />`
        : '';
      const sourceRows = items.length
        ? items.map(item => `
            <div class="collection-item">
              <a href="${escapeHtml(item.article_url || '#')}" target="_blank" rel="noopener noreferrer"><strong>${escapeHtml(item.title || 'Untitled')}</strong></a>
              <div class="meta">${escapeHtml(item.source_name || 'Unknown source')} · Relevance score ${escapeHtml(item.signal_score ?? 'n/a')} · ${escapeHtml(relevanceLabel(item.relevance_status))}</div>
              <button type="button" class="btn-secondary" data-open-story-item="${Number(item.id)}">Read article</button>
            </div>
          `).join('')
        : '<p class="muted">No source articles loaded for this story.</p>';

      document.getElementById('detailTitle').textContent = master.title ? cleanTitle(master.title) : `${readableLabel(collection.primary_theme || 'general_news')} / ${collection.primary_geography || 'Global'}`;
      const articleCount = collection.article_count || items.length || 0;
      document.getElementById('detailMeta').textContent = [
        (master.sources || []).join(', ') || 'Unknown source',
        `${articleCount} ${articleCount === 1 ? 'article' : 'articles'}`,
        ...(accessStatus(collection) === 'open_copy' ? ['Open version found'] : accessStatus(collection) === 'subscriber' ? ['Subscriber article'] : []),
        `Relevance score ${collection.top_signal_score ?? 'n/a'}`,
      ].join(' · ');
      showAlsoCoveredBy(collection);
      showProjectThread(items.map(item => item.id), () => String(activeDetailCollectionKey || '') === String(collection.collection_key || ''));
      const reasons = (collection.signal_reasons || []).filter(Boolean);
      if (reasons.length) {
        document.getElementById('detailMeta').insertAdjacentHTML('beforeend',
          `<div class="signal-reasons"><span>Ranked for:</span>${reasons.map(reason => `<span class="chip-tag">${escapeHtml(reason)}</span>`).join('')}</div>`);
      }
      document.getElementById('detailContent').innerHTML = `
        ${moreInfoLink(master.title || items[0]?.title)}
        <div class="detail-topline ${imageHtml ? 'has-image' : 'no-image'}">
          <div class="detail-summary">
            <strong>Case description</strong>
            <div>${textBlockHtml(master.summary || 'n/a')}</div>
          </div>
          ${imageHtml ? `<div>${imageHtml}</div>` : ''}
        </div>
        <div class="detail-why">
          <strong>Why it matters</strong>
          <div>${textBlockHtml(readableText(master.why_it_matters) || 'n/a')}</div>
        </div>
        <details><summary>Article details</summary><div class="detail-meta-strip">
          ${detailMetaChip('Themes', (master.themes || []).map(readableLabel).join(', ') || 'n/a')}
          ${detailMetaChip('Geography', (master.geographies || []).join(', ') || 'n/a')}
          ${detailMetaChip('Actors', (master.actors || []).join(', ') || 'n/a')}
          ${detailMetaChip('Sources', (master.sources || []).join(', ') || 'n/a')}
        </div></details>
        <div class="detail-why">
          <strong>Source articles in this merged story</strong>
          <div>${sourceRows}</div>
        </div>
        <div id="publicRecords"></div>
      `;
      loadPublicRecords(items.map(item => Number(item.id)), String(collection.collection_key || ''));
      document.getElementById('detailContent').querySelectorAll('[data-open-story-item]').forEach(button => {
        button.addEventListener('click', () => showItemDetails(Number(button.dataset.openStoryItem)));
      });
      const leadId = Number(master.lead_item_id || items[0]?.id);
      mountResearch(leadId);
      mountStoryCopy({...master, id: leadId, source_name: (master.sources || []).join(', '), article_url: items.map(item => item.article_url).filter(Boolean).join('\n')});
    }

    async function showItemDetails(itemId) {
      if (!Number.isFinite(itemId) || itemId <= 0) return;

      activeDetailItemId = itemId;
      activeDetailCollectionKey = null;
      updateDetailNavButtons(itemId);
      openDetailOverlay();
      document.getElementById('detailMeta').textContent = `Item #${itemId}`;
      document.getElementById('detailContent').innerHTML = '<p class="muted">Loading detail...</p>';

      try {
        const [item, preview] = await Promise.all([
          getJson(`/api/news/item/${itemId}`),
          getJson(`/api/news/item/${itemId}/preview`)
        ]);
        if (activeDetailItemId !== itemId) return;

        const meta = [
          preview.site_name || item.source_name || 'Unknown source',
          readableDate(preview.published_at || item.published_at),
          `Relevance score ${item.signal_score ?? 'n/a'}`,
          `Confidence ${item.confidence ?? 'n/a'}`,
        ].join(' · ');
        const summaryText = item.summary || preview.description || '';
        const caseDescription = buildCaseDescription(
          summaryText,
          preview.description,
          preview.preview_excerpt,
          item.cleaned_text,
          preview.source_context,
        );
        const detailImageUrl = preview.image_url || item.image_url || '';
        const imageHtml = detailImageUrl
          ? `<img class="detail-preview-image" src="${escapeHtml(detailImageUrl)}" alt="${escapeHtml(item.title || 'Article image')}" onerror="this.remove()" />`
          : '';
        const imagePanelHtml = imageHtml ? `<div>${imageHtml}</div>` : '';

        document.getElementById('detailTitle').textContent = item.title || 'Untitled';
        document.getElementById('detailMeta').textContent = meta;
        updateDetailNavButtons(itemId);
        document.getElementById('detailContent').innerHTML = `
          ${moreInfoLink(item.title)}
          <div class="detail-topline ${imageHtml ? 'has-image' : 'no-image'}">
            <div class="detail-summary">
              <strong>Case description</strong>
              <div>${textBlockHtml(caseDescription)}</div>
            </div>
            ${imagePanelHtml}
          </div>
          <div class="detail-why">
            <strong>Why it matters</strong>
            <div>${escapeHtml(readableText(item.why_it_matters) || 'n/a')}</div>
          </div>
          <details><summary>Article details</summary><div class="detail-meta-strip">
            ${detailMetaChip('Themes', parseCsvTags(item.theme_tags).map(readableLabel).join(', ') || 'n/a')}
            ${detailMetaChip('Geography', formatCsv(item.geography_tags))}
            ${detailMetaChip('Actors', formatCsv(item.actors))}
            ${preview.author ? detailMetaChip('Author', preview.author) : ''}
            ${detailMetaChip('Relevance score', String(item.signal_score ?? 'n/a'))}
            ${detailMetaChip('Confidence', String(item.confidence ?? 'n/a'))}
          </div></details>
          <div class="detail-source-link"><a href="${escapeHtml(item.article_url || '#')}" target="_blank" rel="noopener noreferrer">Open original source</a></div>
          <div class="card-actions-inline">
            <button type="button" class="btn-secondary" data-editorial="${itemId}" data-vote="relevant">👍 Relevant</button>
            <button type="button" class="btn-secondary" data-editorial="${itemId}" data-vote="non_relevant">👎 Hide</button>
            <button type="button" class="btn-secondary" data-enrich="${itemId}">Expand description</button>
          </div>
        `;
        bindInlineActions(document.getElementById('detailContent'));
        mountResearch(itemId);
        mountStoryCopy(item);
        showProjectThread([itemId], () => activeDetailItemId === itemId);
      } catch (error) {
        if (activeDetailItemId !== itemId) return;
        document.getElementById('detailContent').innerHTML = '<p class="muted">Failed to load detail for this item.</p>';
      }
    }

    function renderAiStatus(data) {
      const el = document.getElementById('aiStatus');
      if (!el) return;
      if (!data) {
        el.textContent = 'AI: status unavailable';
        return;
      }
      const enabled = !!data.enabled;
      const keyConfigured = !!data.api_key_configured;
      const probePart = data.probe_ok === null || data.probe_ok === undefined ? '' : `, probe=${data.probe_ok ? 'ok' : 'fail'}`;
      const errorPart = data.last_error ? `, error=${String(data.last_error).slice(0, 120)}` : '';
      el.textContent = `AI: enabled=${enabled}, key=${keyConfigured}, provider=${data.provider || '-'}, model=${data.model || '-'}${probePart}${errorPart}`;
    }

    async function refreshAiStatus(probe = false) {
      const result = await getJson(`/api/news/ai/status?probe=${probe ? 'true' : 'false'}`);
      renderAiStatus(result);
      return result;
    }
    function currentSourceFilter() {
      const el = document.getElementById('sourceFilter');
      return (el?.value || '').trim();
    }

    function currentDomainFilter() {
      const el = document.getElementById("domainFilter");
      return (el?.value || "core").trim() || "core";
    }

    function sourceFilterQuery() {
      const source = currentSourceFilter();
      const domain = currentDomainFilter();
      const srcPart = source ? `&source_name=${encodeURIComponent(source)}` : "";
      return `${srcPart}&domain_bucket=${encodeURIComponent(domain)}`;
    }

    function renderSourceFilterOptions() {
      const select = document.getElementById('sourceFilter');
      if (!select) return;

      const selected = (select.value || '').trim();
      const names = Array.from(new Set((currentSources || []).map(x => (x.name || '').trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b));

      select.innerHTML = '<option value="">All sources</option>';
      for (const name of names) {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        if (name === selected) opt.selected = true;
        select.appendChild(opt);
      }
    }
    function setActiveTab(tabName) {
      const normalized = ['review', 'researched', 'morning', 'governance', 'sources'].includes(tabName) ? tabName : 'reading';
      if (normalized === 'researched') loadResearchedStories();
      if (normalized === 'sources') loadSourceAdvice();
      document.getElementById('newsFilters').hidden = !['reading', 'review'].includes(normalized);
      if (['morning', 'governance'].includes(normalized)) loadMorningReport();
      if (normalized === 'governance') loadMonitoredPolicy();
      setViewMode(normalized);
      document.querySelectorAll('.tab-btn').forEach(btn => {
        const isActive = btn.getAttribute('data-tab') === normalized;
        btn.classList.toggle('active', isActive);
      });
      document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.classList.toggle('active', panel.id === `tab-${normalized}`);
      });
    }

    function setupTabs() {
      document.querySelectorAll('[data-generate-morning]').forEach(button => button.onclick = generateMorningReport);
      document.querySelector('[data-copy-morning]').onclick = copyMorningReport;
      document.getElementById('morningHistory').onchange = () => loadMorningReport();
      document.getElementById('policyRegion').onchange = () => { renderPolicy(latestPolicyReport); loadMonitoredPolicy(); };
      document.querySelectorAll('[data-policy-type]').forEach(button => button.onclick = () => {
        monitoredType = button.dataset.policyType;
        document.querySelectorAll('[data-policy-type]').forEach(other => other.setAttribute('aria-pressed', String(other === button)));
        loadMonitoredPolicy();
      });
      document.getElementById('monitoredMore').onclick = () => loadMonitoredPolicy(true);

      document.querySelectorAll('.tab-btn[data-tab]').forEach(btn => {
        btn.addEventListener('click', () => {
          const tab = btn.getAttribute('data-tab') || 'reading';
          setActiveTab(tab);
        });
      });
      document.querySelectorAll('[data-reading-layout]').forEach(btn => {
        btn.addEventListener('click', () => setReadingLayout(btn.getAttribute('data-reading-layout') || 'list'));
      });
      document.querySelectorAll('[data-reading-unit]').forEach(btn => {
        btn.addEventListener('click', () => setReadingUnit(btn.getAttribute('data-reading-unit')));
      });
      setReadingUnit(readingUnit, false);
      setReadingLayout(readingLayout);
      setActiveTab('reading');
    }

    function setReadingUnit(unit, render = true) {
      readingUnit = unit === 'news' ? 'news' : 'stories';
      localStorage.setItem('owisReadingUnit', readingUnit);
      document.querySelectorAll('[data-reading-unit]').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-reading-unit') === readingUnit);
      });
      pageState.reading = 1;
      if (render) renderReadingPage();
    }

    function setReadingLayout(layout) {
      readingLayout = layout === 'cards' ? 'cards' : 'list';
      localStorage.setItem('owisReadingLayout', readingLayout);
      document.querySelectorAll('[data-reading-layout]').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-reading-layout') === readingLayout);
      });
      renderReadingPage();
    }
    function getPageSlice(kind, items) {
      const size = pageSize[kind] || 12;
      const totalPages = Math.max(1, Math.ceil((items.length || 0) / size));
      pageState[kind] = Math.min(Math.max(pageState[kind] || 1, 1), totalPages);
      const start = (pageState[kind] - 1) * size;
      const end = start + size;
      return {
        totalPages,
        pageItems: items.slice(start, end),
      };
    }

    function updatePager(kind, totalItems) {
      const size = pageSize[kind] || 12;
      const totalPages = Math.max(1, Math.ceil((totalItems || 0) / size));
      const prev = document.getElementById(`${kind}Prev`);
      const next = document.getElementById(`${kind}Next`);
      const info = document.getElementById(`${kind}PageInfo`);
      if (!prev || !next || !info) return;

      const page = Math.min(Math.max(pageState[kind] || 1, 1), totalPages);
      pageState[kind] = page;
      prev.disabled = page <= 1;
      next.disabled = page >= totalPages;
      info.textContent = `Page ${page}/${totalPages} (${totalItems} ${kind === 'reading' ? 'stories' : 'articles'})`;
    }

    function renderLatestPage() {
      const { pageItems } = getPageSlice('latest', latestItems);
      renderCards('latest', pageItems);
      updatePager('latest', latestItems.length);
    }

    function renderTopPage() {
      const { pageItems } = getPageSlice('top', topItems);
      renderCards('top', pageItems);
      updatePager('top', topItems.length);
    }

    function visibleArticles(items) {
      const scope=document.getElementById('interestFilter')?.value || 'all';
      const hidden=document.getElementById('showDismissed')?.checked;
      return items.filter(item => (scope==='all' || (item.interest_topics||[]).includes(scope)) &&
        (hidden || (item.editorial?.[scope]?.value!=='non_relevant' && item.content_basis?.relevance!=='excluded')));
    }
    // Stories (merged events) on the same case - one project, or linked follow-ups - are shown as one row.
    function groupIntoCases(items) {
      const order = [], byKey = new Map();
      for (const col of items) {
        const key = col.case?.size > 1 ? col.case.key : `story:${col.collection_key}`;
        if (!byKey.has(key)) { byKey.set(key, []); order.push(key); }
        byKey.get(key).push(col);
      }
      return order.map(key => byKey.get(key));
    }

    function renderReadingPage() {
      const cases=groupIntoCases(visibleCollections());
      caseGroups=new Map(cases.filter(group=>group.length>1).map(group=>[group[0].case.key,group]));
      // News: every item on its own, newest first; Stories: one row per case.
      const visible=readingUnit==='news'
        ? visibleCollections().slice().sort((a,b)=>String(b.latest_published_at||'').localeCompare(String(a.latest_published_at||''))).map(col=>[col])
        : cases;
      const {pageItems}=getPageSlice('reading',visible);
      const root=document.getElementById('readingStories');
      if(root){root.classList.toggle('grid',readingLayout==='cards');root.classList.toggle('story-list',readingLayout==='list');}
      renderStoryRows(root,pageItems);
      updatePager('reading',visible.length);
      if(!collectionsLoaded) return;
      if(root) root.setAttribute('aria-busy','false');
      const count=document.getElementById('navNewsCount');
      if(count) count.textContent=visible.length ? String(visible.length) : '';
      const summary=document.getElementById('readingSummary');
      if(summary){
        const query=(document.getElementById('storySearch')?.value||'').trim();
        const unit=readingUnit==='news'?(visible.length===1?'news item':'news items'):(visible.length===1?'story':'stories');
        summary.textContent=`${visible.length} ${unit}${query?` matching “${query}”`:''}`;
      }
    }

    function visibleCollections() {
      const current = new Map(latestItems.map(item => [Number(item.id), item]));
      const geography = document.getElementById('geographyFilter')?.value;
      const company = document.getElementById('companyFilter')?.value;
      const query = (document.getElementById('storySearch')?.value || '').trim().toLowerCase();
      const matchesQuery = col => !query || [col.master?.title, col.master?.summary, ...(col.master?.sources || []),
        ...(col.master?.actors || []), ...(col.master?.geographies || [])].join(' ').toLowerCase().includes(query);
      const visible = mergedItems.filter(col => matchesQuery(col) &&
        (!geography || (col.master?.geographies || []).includes(geography)) &&
        (!company || (col.master?.actors || []).includes(company)) &&
        visibleArticles((col.items || []).map(item => current.get(Number(item.id)) || item)).length);
      const timestamp = col => Date.parse(col.latest_published_at) || 0;
      const day = col => dayHeading(col.latest_published_at);
      const score = col => Number(col.top_signal_score) || 0;
      // Newest days first; inside a day the strongest signals lead, as in a daily briefing.
      return visible.sort(document.getElementById('storySort')?.value === 'relevance'
        ? (a,b) => (score(b) - score(a)) || timestamp(b) - timestamp(a)
        : (a,b) => (day(a) === day(b) ? (score(b) - score(a)) : 0) || timestamp(b) - timestamp(a));
    }

    function updateStoryFilters() {
      for (const [id, field, label] of [['geographyFilter','geographies','All geographies'], ['companyFilter','actors','All companies']]) {
        const select = document.getElementById(id);
        const previous = select.value;
        const values = [...new Set(mergedItems.flatMap(col => col.master?.[field] || []))].sort((a,b) => a.localeCompare(b));
        select.replaceChildren(new Option(label, ''), ...values.map(value => new Option(value, value)));
        if (values.includes(previous)) select.value = previous;
      }
    }

    function storyBrief(col) {
      const text = (col.master?.summary || '').replace(/\s+/g, ' ').trim();
      // Prefer complete sentences, without inventing missing details from a feed excerpt.
      const sentences = [...new Intl.Segmenter('en', {granularity:'sentence'}).segment(text)].map(part => part.segment.trim());
      const complete = sentences.filter(sentence => /[.!?][”"')]*$/.test(sentence) && !/(?:\.{2,}|…)[”"')]*$/.test(sentence));
      let brief = '';
      for (const sentence of complete.slice(0, 2)) {
        if (brief && (brief.length + sentence.length > 320)) break;
        brief += (brief ? ' ' : '') + sentence;
      }
      return brief || text;
    }

    // Paywall status of a story: an open copy found elsewhere beats the lock.
    function accessStatus(col) {
      const items = col.items || [];
      if (items.some(item => item.content_basis?.basis === 'alternative_fulltext')) return 'open_copy';
      const title = col.master?.title || '';
      if (/^\[paywalled\]/i.test(title) || items.some(item => item.content_basis?.access === 'restricted')) return 'subscriber';
      return '';
    }

    function cleanTitle(title) {
      return String(title || 'Untitled').replace(/^\[paywalled\]\s*/i, '');
    }

    // Other stories about the same project (separate events, e.g. two stake sales), from the stored event cards.
    async function showProjectThread(itemIds, isCurrent) {
      const seen = new Set(itemIds.map(Number));
      const rows = [];
      for (const id of [...seen].slice(0, 5)) {
        try {
          for (const row of await getJson(`/api/news/item/${id}/thread`)) {
            if (!seen.has(row.id) && !rows.some(r => r.title === row.title)) rows.push(row);
          }
        } catch (error) { /* the thread is optional */ }
      }
      if (!rows.length || !isCurrent()) return;
      rows.sort((a, b) => String(b.published_at || '').localeCompare(String(a.published_at || '')));
      const content = document.getElementById('detailContent');
      content.insertAdjacentHTML('beforeend', `<div class="detail-why project-thread">
        <strong>Same project</strong>
        <ul>${rows.slice(0, 8).map(row => `<li><button type="button" class="btn-ghost" style="margin:0;padding:0;text-align:left" data-thread-item="${Number(row.id)}">${escapeHtml(cleanTitle(row.title))}</button>
          <span class="muted"> · ${escapeHtml(row.source_name || '')} · ${escapeHtml(relativeTime(row.published_at))}</span></li>`).join('')}</ul>
      </div>`);
      content.querySelectorAll('[data-thread-item]').forEach(button => {
        button.onclick = () => showItemDetails(Number(button.dataset.threadItem));
      });
    }

    // Other outlets' verified coverage of the same story, found by search (not collected articles).
    async function showAlsoCoveredBy(collection) {
      const key = String(collection.collection_key || '');
      const ids = [collection.master?.lead_item_id, ...(collection.items || []).map(item => item.id)].filter(Boolean);
      const seen = new Set((collection.items || []).map(item => item.article_url));
      const found = [];
      for (const id of [...new Set(ids)].slice(0, 5)) {
        try {
          for (const row of await getJson(`/api/news/item/${id}/sources`)) {
            if (['additional_coverage', 'alternative_fulltext'].includes(row.basis) && !seen.has(row.url)) { seen.add(row.url); found.push(row); }
          }
        } catch (error) { /* evidence is optional */ }
      }
      if (!found.length || String(activeDetailCollectionKey || '') !== key) return;
      const host = url => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch (error) { return ''; } };
      document.getElementById('detailContent').insertAdjacentHTML('beforeend', `<div class="detail-why also-covered">
        <strong>Also covered by</strong>
        <ul>${found.map(row => `<li><a href="${escapeHtml(row.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(row.title)}</a>
          <span class="muted"> · ${escapeHtml(host(row.url))}${row.basis === 'alternative_fulltext' ? ' · open version' : ''}</span></li>`).join('')}</ul>
      </div>`);
    }

    function relativeTime(value) {
      const date = new Date(value || '');
      if (!value || Number.isNaN(date.getTime())) return 'Date unavailable';
      const minutes = Math.round((Date.now() - date.getTime()) / 60000);
      if (minutes < 1) return 'Just now';
      if (minutes < 60) return `${minutes} min ago`;
      if (minutes < 24 * 60) return `${Math.round(minutes / 60)} h ago`;
      return date.toLocaleDateString('en-GB', {day: 'numeric', month: 'short'});
    }

    function dayHeading(value) {
      const date = new Date(value || '');
      if (!value || Number.isNaN(date.getTime())) return 'Undated';
      const startOfDay = d => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
      const days = Math.round((startOfDay(new Date()) - startOfDay(date)) / 86400000);
      if (days === 0) return 'Today';
      if (days === 1) return 'Yesterday';
      return date.toLocaleDateString('en-GB', {weekday: 'long', day: 'numeric', month: 'long'});
    }

    function renderStoryRows(root, items) {
      if (!root || !collectionsLoaded) return;
      root.innerHTML = '';
      if (!items.length) {
        const filtered = (document.getElementById('storySearch')?.value || '').trim() || document.getElementById('geographyFilter')?.value
          || document.getElementById('companyFilter')?.value || (document.getElementById('interestFilter')?.value || 'all') !== 'all';
        root.innerHTML = filtered
          ? '<div class="empty-state"><strong>No stories match these filters</strong>Try another topic, clear the search or include hidden stories.</div>'
          : '<div class="empty-state"><strong>No stories yet</strong>Fetch news under Settings → News sources to fill your feed.</div>';
        return;
      }
      const groupByDay = document.getElementById('storySort')?.value !== 'relevance';
      let lastDay = null;
      for (const group of items) {
        const col = group[0];
        const isCase = group.length > 1;
        const master = col.master || {};
        const days = new Set(group.map(c => String(c.latest_published_at || '').slice(0, 10)).filter(Boolean));
        const updated = days.size > 1;
        if (groupByDay) {
          const day = dayHeading(col.latest_published_at);
          if (day !== lastDay) {
            const head = document.createElement('h3');
            head.className = 'day-head';
            head.textContent = day;
            root.appendChild(head);
            lastDay = day;
          }
        }
        const sources = master.sources || [];
        const caseSources = isCase ? [...new Set(group.flatMap(c => c.master?.sources || []))] : [];
        const sourceName = isCase
          ? caseSources.slice(0, 3).join(', ') + (caseSources.length > 3 ? ` +${caseSources.length - 3}` : '')
          : sources[0] || 'Unknown source';
        const articleCount = group.reduce((sum, c) => sum + Number(c.article_count || (c.items || []).length || 1), 0);
        const imageUrl = cssImageUrl(master.image_url);
        const tags = [
          ...(master.geographies || []).filter(tag => tag !== 'Global').slice(0, 2).map(tag => `<span class="chip-tag is-geo">${escapeHtml(tag)}</span>`),
          ...(master.actors || []).slice(0, 3).map(tag => `<span class="chip-tag is-actor">${escapeHtml(tag)}</span>`),
        ].join('');
        const row = document.createElement('article');
        row.className = 'story';
        row.dataset.key = String(col.collection_key || '');
        row.innerHTML = `<div class="story-main">
            <div class="story-source">
              <span class="source-avatar" aria-hidden="true">${escapeHtml(sourceName.charAt(0).toUpperCase())}</span>
              <span class="source-name">${escapeHtml(sourceName)}</span>
              <span aria-hidden="true">·</span>
              <time datetime="${escapeHtml(col.latest_published_at || '')}">${escapeHtml(relativeTime(col.latest_published_at))}</time>
              ${updated ? '<span class="focus-badge" title="This case has developed over more than one day">Updated</span>' : ''}
              ${!isCase && caseGroups.has(col.case?.key) ? `<button type="button" class="sources-badge case-link" title="Open the whole story">${escapeHtml(col.case.name || 'Story')} · ${caseGroups.get(col.case.key).length} developments</button>` : ''}
              ${isCase ? `<span class="sources-badge">${group.length} developments · ${articleCount} articles</span>`
                : articleCount > 1 ? `<span class="sources-badge">${articleCount} sources</span>` : ''}
              ${col.domain_bucket === 'offshore_wind' ? '<span class="focus-badge">Offshore wind</span>' : ''}
              ${accessStatus(col) === 'open_copy' ? '<span class="access-badge is-open" title="An open article about the same story was found and is used as the basis">Open version found</span>'
                : accessStatus(col) === 'subscriber' ? '<span class="access-badge" title="Subscriber article; OWIS shows the excerpt and looks for open coverage of the same story">Subscriber</span>' : ''}
            </div>
            <h3>${isCase && col.case.name ? `<span class="case-name">${escapeHtml(col.case.name)}</span>` : ''}<button type="button" class="story-open">${escapeHtml(isCase ? caseHeadline(group) : cleanTitle(master.title))}</button></h3>
            <p class="story-description">${escapeHtml(isCase ? caseBrief(group) : storyBrief(col))}</p>
            ${tags ? `<div class="story-tags">${tags}</div>` : ''}
          </div>
          ${imageUrl ? `<div class="story-image" style="background-image:url('${imageUrl}')" aria-hidden="true"></div>` : ''}`;
        row.querySelector('.story-open').addEventListener('click', () => isCase ? showCaseDetails(group) : showCollectionDetails(col.collection_key));
        row.querySelector('.case-link')?.addEventListener('click', () => showCaseDetails(caseGroups.get(col.case.key)));
        root.appendChild(row);
      }
      markActiveStory();
    }

    function renderMergedPage() {
      const { pageItems } = getPageSlice('merged', mergedItems);
      renderCollections('collections', pageItems, { showItems: true, pulseManual: viewMode === 'review' });
      updatePager('merged', mergedItems.length);
    }

    function changePage(kind, delta) {
      pageState[kind] = (pageState[kind] || 1) + delta;
      if (kind === 'latest') renderLatestPage();
      if (kind === 'top') renderTopPage();
      if (kind === 'reading') renderReadingPage();
      if (kind === 'merged') renderMergedPage();
    }
    function isPaywalled(item) {
      const title = (item.title || '').toLowerCase();
      const summary = (item.summary || '').toLowerCase();
      return title.includes('[paywalled]') || summary.includes('paywalled');
    }

    function renderCards(elId, items) {
      const root = document.getElementById(elId);
      if (!root) return;
      root.innerHTML = '';
      if (!items.length) {
        root.innerHTML = '<p class="muted">No data yet. Run fetch + processing.</p>';
        return;
      }

      const scope = document.getElementById('interestFilter')?.value || 'all';
      const showHidden = document.getElementById('showDismissed')?.checked;
      items = items.filter(item => {
        if (scope !== 'all' && !(item.interest_topics || []).includes(scope)) return false;
        const vote = item.editorial?.[scope]?.value;
        return showHidden || (vote !== 'non_relevant' && item.content_basis?.relevance !== 'excluded');
      });
      if (!items.length) root.innerHTML = '<p class="muted">No articles match. Try another topic or include hidden articles.</p>';
      const relatedPool = elId === 'top' ? topItems : latestItems;
      for (const item of items) {
        const paywalled = isPaywalled(item);
        const div = document.createElement('article');
        div.className = 'card compact-card is-clickable';
        const imageUrl = cssImageUrl(item.image_url);
        const showCardImage = viewMode !== 'review' && Boolean(imageUrl);
        if (showCardImage) div.classList.add('has-image');
        const imageHtml = showCardImage
          ? `<img class="compact-image" src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.title || 'Article image')}" onerror="this.remove()" />`
          : '';
        const itemId = Number(item.id || 0);
        const relevance = relevanceLabel(item.relevance_status);
        const leadText = viewMode === 'review'
          ? (item.why_it_matters || item.linkedin_angle || item.summary || 'No details')
          : (item.summary || 'No summary');
        const themeTags = parseCsvTags(item.theme_tags).slice(0, 3);
        const geoTags = parseCsvTags(item.geography_tags).slice(0, 2);
        const actorTags = parseCsvTags(item.actors).slice(0, 2);
        const inlineTagsHtml = [
          tagBadgeHtml(themeTags),
          tagBadgeHtml(geoTags, 'is-geo'),
          tagBadgeHtml(actorTags, 'is-actor'),
        ].join('');
        const related = viewMode === 'review' ? relatedItemsFor(item, relatedPool, 3) : [];
        const basis=item.content_basis || {};
        const accessLabel=({open:'Open',restricted:'Subscription',blocked:'Access blocked',unknown:'Access unknown'})[basis.access] || 'Access unknown';
        const basisLabel=({fulltext:'Full text available',alternative_fulltext:'Open alternative source',feed_text:'RSS text',feed_excerpt:'RSS excerpt'})[basis.basis] || 'Short excerpt';
        const learningActions = `
          <div class="compact-meta-row">${escapeHtml(accessLabel)} · ${escapeHtml(basisLabel)}</div>
          <div class="card-actions-inline">
            <button type="button" class="btn-secondary" data-editorial="${itemId}" data-vote="relevant" aria-pressed="${item.editorial?.[scope]?.value==='relevant'}">👍 Relevant</button>
            <button type="button" class="btn-secondary" data-editorial="${itemId}" data-vote="non_relevant">👎 Hide</button>
            <button type="button" class="btn-secondary" data-draft="${itemId}">${item.draft ? 'View draft' : 'Create draft'}</button>
            <button type="button" class="btn-secondary" data-enrich="${itemId}">Expand description</button>
          </div>
          ${(basis.alternatives||[]).map(a=>`<a href="${escapeHtml(a.url)}" target="_blank" rel="noopener noreferrer">Open source: ${escapeHtml(a.title)}</a>`).join('<br>')}
          ${basis.reason?.includes('Begrenset kildegrunnlag') ? '<p class="muted">Limited coverage: no verified open alternative found.</p>' : ''}
        `;
        const relatedHtml = related.length
          ? `
            <div class="related-strip">
              <div class="related-strip-title">Related by tags</div>
              ${related.map(row => `
                <div class="related-item">
                  <div>
                    <div class="related-item-title">${escapeHtml(row.item.title || 'Untitled')}</div>
                    <div class="related-item-meta">${escapeHtml(row.item.source_name || 'Unknown source')} · Relevance score ${row.item.signal_score || 0} · Match ${row.score}</div>
                  </div>
                  <button class="btn-warning" type="button" data-merge-pair="${itemId},${Number(row.item.id || 0)}">Merge</button>
                </div>
              `).join('')}
            </div>
          `
          : '';

        div.innerHTML = `
          ${imageHtml}
          <h3>${escapeHtml(item.title)}${paywalled ? '<span class="badge-paywall">Paywall</span>' : ''}</h3>
          <p class="compact-summary">${escapeHtml(shortText(leadText, 340))}</p>
          <div class="compact-meta-row">
            <span>${escapeHtml(item.source_name || 'Unknown source')}</span>
            <span>${escapeHtml(readableDate(item.published_at))}</span>
            <span>Relevance score ${escapeHtml(item.signal_score ?? 'n/a')}</span>
            <span>${escapeHtml(relevance)}</span>
          </div>
          <div class="inline-tags">${inlineTagsHtml || '<span class="inline-tag is-geo">No tags</span>'}</div>
          <div class="compact-meta-row"><button type="button" class="btn-secondary" data-sources="${itemId}">Source coverage</button> · <a href="${escapeHtml(item.article_url)}" target="_blank" rel="noopener noreferrer">Open source</a></div>
          ${learningActions}
          ${relatedHtml}
          <div class="selection-row"><label><input type="checkbox" data-collection-item="${itemId}" ${selectedCollectionItems.has(itemId) ? 'checked' : ''} /> Select</label></div>
        `;
        div.title = 'Click card to view basis';
        div.addEventListener('click', (evt) => {
          if (evt.target.closest('a') || evt.target.closest('input') || evt.target.closest('button')) return;
          if (itemId > 0) {
            showItemDetails(itemId);
            return;
          }
          const url = item.article_url || '';
          if (url) window.open(url, '_blank', 'noopener,noreferrer');
        });
        root.appendChild(div);
      }

      bindCollectionCheckboxes(root);
      bindInlineActions(root);
    }

    function updateSelectedCount() {
      document.getElementById('selectedCount').value = String(selectedCollectionItems.size);
    }

    function bindCollectionCheckboxes(scope) {
      const root = scope || document;
      root.querySelectorAll('[data-collection-item]').forEach(chk => {
        chk.addEventListener('change', () => {
          const id = Number(chk.getAttribute('data-collection-item'));
          if (Number.isNaN(id) || id <= 0) return;
          if (chk.checked) selectedCollectionItems.add(id);
          else selectedCollectionItems.delete(id);
          document.querySelectorAll(`[data-collection-item="${id}"]`).forEach(other => {
            if (other !== chk) other.checked = chk.checked;
          });
          updateSelectedCount();
        });
      });
      updateSelectedCount();
    }

    function renderCollections(elId, items, options = {}) {
      const root = document.getElementById(elId);
      if (!root) return;
      const showItems = options.showItems !== false;
      const pulseManual = Boolean(options.pulseManual);
      root.innerHTML = '';

      if (!items.length) {
        root.innerHTML = '<p class="muted">No collections yet. Run fetch + processing first.</p>';
        return;
      }

      for (const col of items) {
        const div = document.createElement('article');
        div.className = `card story-card${pulseManual && col.is_manual ? ' is-updated' : ''}`;
        const master = col.master || {};
        const masterImage = cssImageUrl(master.image_url);
        const showMasterImage = !showItems && Boolean(masterImage);
        const masterTagsHtml = [
          tagBadgeHtml((master.themes || []).slice(0, 4)),
          tagBadgeHtml((master.geographies || []).slice(0, 3), 'is-geo'),
          tagBadgeHtml((master.actors || []).slice(0, 3), 'is-actor'),
        ].join('');
        const isReadingPreview = elId === 'readingStories';
        const summaryText = isReadingPreview ? shortText(master.summary, 230) : (master.summary || '');
        const whyText = isReadingPreview ? shortText(readableText(master.why_it_matters), 130) : readableText(master.why_it_matters);
        const thumbStyle = showMasterImage ? ` style="background-image:url('${masterImage}')"` : '';
        const rows = showItems ? (col.items || []).map(item => {
          const id = Number(item.id || 0);
          const checked = selectedCollectionItems.has(id) ? 'checked' : '';
          const titleHtml = item.article_url
            ? `<a href="${item.article_url}" target="_blank" rel="noopener noreferrer"><strong>${item.title}</strong></a>`
            : `<strong>${item.title}</strong>`;
          return `<div class="collection-item"><label><input type="checkbox" data-collection-item="${id}" ${checked} /> ${titleHtml} (${item.source_name || 'Unknown'} | ${relevanceLabel(item.relevance_status)})</label></div>`;
        }).join('') : '';

        div.innerHTML = `
          <div class="master-card ${showMasterImage ? 'has-image' : ''}">
            <div class="master-content">
              <div class="muted">Master view | ${escapeHtml((master.sources || []).join(', ') || 'Sources')}</div>
              <div class="master-title">${escapeHtml(master.title || `${readableLabel(col.primary_theme || 'general_news')} / ${col.primary_geography || 'Global'}`)}</div>
              ${summaryText ? `<div class="master-summary">${escapeHtml(summaryText)}</div>` : ''}
              ${whyText ? `<div class="master-why"><strong>Why it matters:</strong> ${escapeHtml(whyText)}</div>` : ''}
              <div class="master-tags">${masterTagsHtml || '<span class="inline-tag is-geo">No tags</span>'}</div>
            </div>
            ${showMasterImage ? `<div class="story-thumb"${thumbStyle}></div>` : ''}
          </div>
          <div class="collection-head">
            <div>
              <strong>${escapeHtml(readableLabel(col.primary_theme || 'general_news'))} / ${escapeHtml(col.primary_geography || 'Global')}</strong>
              <div class="collection-key">${col.collection_key}</div>
            </div>
            <div class="meta">${col.article_count} ${Number(col.article_count) === 1 ? 'article' : 'articles'} · Average relevance ${col.avg_signal_score} · Highest ${col.top_signal_score}</div>
          </div>
          ${showItems ? rows : `<div class="collection-item muted">${col.article_count} source article${Number(col.article_count || 0) === 1 ? '' : 's'} grouped into this story.</div>`}
        `;
        div.title = 'Click story to view merged master story';
        div.classList.add('is-clickable');
        div.addEventListener('click', (evt) => {
          if (evt.target.closest('a') || evt.target.closest('input') || evt.target.closest('button')) return;
          showCollectionDetails(col.collection_key);
        });
        root.appendChild(div);
      }

      bindCollectionCheckboxes(root);
    }
