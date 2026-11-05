
    function currentVisibleItems() {
      const reviewOpen = document.getElementById('tab-review')?.classList.contains('active');
      if (reviewOpen) return latestItems;
      return latestItems;
    }

    function currentVisibleCollections() {
      return viewMode === 'review' ? mergedItems : visibleCollections();
    }

    function findCollectionByKey(collectionKey) {
      return currentVisibleCollections().find(col => String(col.collection_key || '') === String(collectionKey || ''));
    }

    function currentVisibleIndex(itemId) {
      const items = currentVisibleItems();
      return items.findIndex(x => Number(x.id || 0) === Number(itemId || 0));
    }

    function stepDetailItem(delta) {
      if (activeDetailCollectionKey) {
        stepDetailCollection(delta);
        return;
      }
      const items = currentVisibleItems();
      if (!items.length || !activeDetailItemId) return;
      const index = currentVisibleIndex(activeDetailItemId);
      if (index < 0) return;
      const nextIndex = index + delta;
      if (nextIndex < 0 || nextIndex >= items.length) return;
      const nextId = Number(items[nextIndex].id || 0);
      if (nextId > 0) showItemDetails(nextId);
    }

    function stepDetailCollection(delta) {
      const collections = currentVisibleCollections();
      if (!collections.length || !activeDetailCollectionKey) return;
      const index = collections.findIndex(col => String(col.collection_key || '') === String(activeDetailCollectionKey || ''));
      if (index < 0) return;
      const nextIndex = index + delta;
      if (nextIndex < 0 || nextIndex >= collections.length) return;
      showCollectionDetails(collections[nextIndex].collection_key);
    }

    function updateDetailNavButtons(itemId) {
      const prev = document.getElementById('detailPrevBtn');
      const next = document.getElementById('detailNextBtn');
      const items = currentVisibleItems();
      const index = items.findIndex(x => Number(x.id || 0) === Number(itemId || 0));
      if (!prev || !next) return;
      prev.disabled = index <= 0;
      next.disabled = index < 0 || index >= items.length - 1;
    }

    function updateDetailCollectionNavButtons(collectionKey) {
      const prev = document.getElementById('detailPrevBtn');
      const next = document.getElementById('detailNextBtn');
      const collections = currentVisibleCollections();
      const index = collections.findIndex(col => String(col.collection_key || '') === String(collectionKey || ''));
      if (!prev || !next) return;
      prev.disabled = index <= 0;
      next.disabled = index < 0 || index >= collections.length - 1;
    }

    function scoreRelatedness(item, other) {
      if (!item || !other) return 0;
      const leftTheme = parseCsvTags(item.theme_tags);
      const rightTheme = parseCsvTags(other.theme_tags);
      const leftGeo = parseCsvTags(item.geography_tags);
      const rightGeo = parseCsvTags(other.geography_tags);
      const leftActors = parseCsvTags(item.actors);
      const rightActors = parseCsvTags(other.actors);

      const intersectCount = (a, b) => a.filter(x => b.includes(x)).length;
      let score = 0;
      score += intersectCount(leftTheme, rightTheme) * 4;
      score += intersectCount(leftGeo, rightGeo) * 3;
      score += intersectCount(leftActors, rightActors) * 2;
      if ((item.source_name || '') === (other.source_name || '')) score += 1;
      return score;
    }

    function relatedItemsFor(item, allItems, limit = 3) {
      const itemId = Number(item?.id || 0);
      return (allItems || [])
        .filter(other => Number(other.id || 0) > 0 && Number(other.id || 0) !== itemId)
        .map(other => ({ item: other, score: scoreRelatedness(item, other) }))
        .filter(row => row.score > 0)
        .sort((a, b) => {
          if (b.score !== a.score) return b.score - a.score;
          return Number(b.item.signal_score || 0) - Number(a.item.signal_score || 0);
        })
        .slice(0, limit);
    }

    function normalizeDetailText(value) {
      return String(value || '')
        .replace(/\s+/g, ' ')
        .replace(/[.,;:!?]+$/g, '')
        .trim()
        .toLowerCase();
    }

    function isDuplicateDetailText(candidate, existing) {
      const text = normalizeDetailText(candidate);
      if (!text) return true;
      return existing.some(prev => {
        const other = normalizeDetailText(prev);
        if (!other) return false;
        return text === other || text.includes(other) || other.includes(text);
      });
    }

    function uniqueDetailBlocks(...values) {
      const seen = [];
      const out = [];
      for (const value of values) {
        const text = String(value || '').trim();
        if (!text || isDuplicateDetailText(text, seen)) continue;
        seen.push(text);
        out.push(text);
      }
      return out;
    }

    function truncateDetailText(value, maxLength = 1200) {
      const text = String(value || '').trim();
      if (text.length <= maxLength) return text;
      const clipped = text.slice(0, maxLength);
      const sentenceEnd = Math.max(clipped.lastIndexOf('. '), clipped.lastIndexOf('! '), clipped.lastIndexOf('? '));
      return `${clipped.slice(0, sentenceEnd > 420 ? sentenceEnd + 1 : maxLength).trim()} ...`;
    }

    function buildCaseDescription(summaryText, ...contextValues) {
      const summary = String(summaryText || '').trim();
      const [context = ''] = uniqueDetailBlocks(...contextValues);
      if (!summary) return truncateDetailText(context || 'n/a');
      if (!context || isDuplicateDetailText(context, [summary])) return summary;
      if (summary.length >= 520) return summary;
      return `${summary}\n\n${truncateDetailText(context, 850)}`;
    }

    function openDetailOverlay() {
      const overlay = document.getElementById('detailOverlay');
      overlay?.classList.add('open');
      overlay?.setAttribute('aria-hidden', 'false');
      markActiveStory();
    }

    function markActiveStory() {
      document.querySelectorAll('#readingStories .story').forEach(row => {
        const active = Boolean(activeDetailCollectionKey) && row.dataset.key === String(activeDetailCollectionKey);
        row.classList.toggle('is-active', active);
        if (active) row.scrollIntoView({block: 'nearest'});
      });
    }

    function closeDetailOverlay() {
      const overlay = document.getElementById('detailOverlay');
      overlay?.classList.remove('open');
      overlay?.setAttribute('aria-hidden', 'true');
      activeDetailItemId = null;
      activeDetailCollectionKey = null;
      markActiveStory();
    }

    function moreInfoLink(title) {
      const query = String(title || '').replace(/\s+/g, ' ').trim();
      if (!query) return '';
      const url = 'https://www.google.com/search?q=' + encodeURIComponent(query);
      return `<div class="detail-action-row"><a class="info-search" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" aria-label="Find more info (opens Google search in a new tab)">Find more info ↗</a></div>`;
    }

    function researchCopyText(result, title) {
      const lines = [title || result.query || 'Story research', `Research saved: ${result.generated_at}`, ''];
      for (const [heading, key] of [['What happened','what_happened'], ['Key developments','key_developments'], ['Why it matters (analysis)','why_it_matters'], ["What's new",'whats_new']]) {
        lines.push(heading);
        for (const claim of result[key] || []) {
          lines.push(`- ${claim.text} ${(claim.source_ids || []).map(id => `[${id}]`).join(' ')}`.trim());
        }
        if (!result[key]?.length) lines.push('No additional findings.');
        lines.push('');
      }
      lines.push('LinkedIn potential', 'Editorial judgement, not a prediction of reach or virality.');
      for (const [heading, key] of [['Brand fit','brand_fit'], ['Conversation potential','conversation_potential']]) {
        lines.push(`${heading}: ${result[key].level}`, result[key].reason, '');
      }
      lines.push('Why this fits you', result.why_this_fits_you, '', 'Possible angles',
        ...result.suggested_angles.map(angle => `- ${angle}`), '',
        'What would strengthen it', result.what_would_strengthen_it, '', 'Limitations', result.limitations, '', 'Sources');
      for (const source of result.sources) {
        lines.push(`[${source.id}] ${source.title} (${source.relationship.replaceAll('_',' ')}; ${source.basis.replaceAll('_',' ')})`);
        if (/^https?:\/\//i.test(source.url || '')) lines.push(source.url);
      }
      return lines.join('\n');
    }
