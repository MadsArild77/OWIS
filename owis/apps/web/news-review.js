
    function renderMatchReview() {
      const root = document.getElementById("matchReview");
      if (!root) return;
      root.innerHTML = "";
      if (viewMode !== "review") {
        root.innerHTML = "<p class=\"muted\">Open Review to handle AI match suggestions.</p>";
        return;
      }
      if (storyLinks.length) {
        const section = document.createElement("section");
        section.innerHTML = '<h3>Linked updates</h3>' + storyLinks.map(link =>
          `<p>${escapeHtml(link.title_a)} ↔ ${escapeHtml(link.title_b)} <span class="muted">(separate events)</span></p>`
        ).join('');
        root.appendChild(section);
      }
      if (!matchReviewItems.length) {
        root.insertAdjacentHTML('beforeend', "<p class=\"muted\">No suggested matches.</p>");
        return;
      }
      for (const pair of matchReviewItems) {
        const div = document.createElement("article");
        div.className = "card";
        const entities = Array.isArray(pair.overlap_entities) ? pair.overlap_entities.join(", ") : "";
        div.innerHTML = `
          <h3>${escapeHtml(({same_event:"Same event",update:"Story update",uncertain:"Uncertain match"})[pair.relationship] || "Possible connection")} (${Math.round((Number(pair.ai_confidence || 0)) * 100)}%)</h3>
          <div class="meta">${escapeHtml(pair.reason_short || "No reason")}</div>
          <div class="meta">Entities: ${escapeHtml(entities || "n/a")}</div>
          <div class="meta"><a href="${escapeHtml(/^https?:\/\//i.test(pair.item_a_url || "") ? pair.item_a_url : "#")}" target="_blank" rel="noopener noreferrer">A: ${escapeHtml(pair.item_a_title || "Untitled")}</a></div>
          <div class="meta"><a href="${escapeHtml(/^https?:\/\//i.test(pair.item_b_url || "") ? pair.item_b_url : "#")}" target="_blank" rel="noopener noreferrer">B: ${escapeHtml(pair.item_b_title || "Untitled")}</a></div>
          <div style="display:flex;gap:8px;margin-top:10px;">
            <button class="btn-secondary" type="button" data-match-accept="${pair.id}" data-relationship="${escapeHtml(pair.relationship || "uncertain")}">${pair.relationship === "update" ? "Link update" : "Same story"}</button>
            <button class="btn-warning" type="button" data-match-reject="${pair.id}">Different stories</button>
          </div>
        `;
        root.appendChild(div);
      }
      root.querySelectorAll("[data-match-accept]").forEach(btn => {
        btn.addEventListener("click", async () => {
          const id = Number(btn.getAttribute("data-match-accept"));
          if (!Number.isFinite(id) || id <= 0) return;
          await decideMatchReview(id, btn.getAttribute("data-relationship") === "update" ? "link_update" : "accept");
        });
      });
      root.querySelectorAll("[data-match-reject]").forEach(btn => {
        btn.addEventListener("click", async () => {
          const id = Number(btn.getAttribute("data-match-reject"));
          if (!Number.isFinite(id) || id <= 0) return;
          await decideMatchReview(id, "reject");
        });
      });
    }

    async function refreshMatchReview() {
      const result = await getJson(`/api/news/match-review?status=pending&limit=40${sourceFilterQuery()}`);
      matchReviewItems = Array.isArray(result.items) ? result.items : [];
      const linked = await getJson("/api/news/story-links");
      storyLinks = Array.isArray(linked.items) ? linked.items : [];
      renderMatchReview();
    }

    async function decideMatchReview(pairId, decision) {
      const result = await postJson("/api/news/match-review/decide", { pair_id: pairId, decision });
      setStatus(`Match review ${result.decision} for pair #${result.pair_id}`);
      await refreshMatchReview();
      await refreshCollections();
      await refreshSignals();
    }

    async function refreshCollections() {
      let result;
      try {
        result = await getJson(`/api/news/collections?limit=120&items_per_collection=400${sourceFilterQuery()}`);
      } catch (error) {
        const root = document.getElementById('readingStories');
        if (root && !collectionsLoaded) {
          root.setAttribute('aria-busy', 'false');
          root.innerHTML = '<div class="empty-state"><strong>Could not load stories</strong>Check your connection and reload the page.</div>';
        }
        throw error;
      }
      mergedItems = Array.isArray(result.items) ? result.items : [];
      collectionsLoaded = true;
      updateStoryFilters();
      pageState.reading = 1;
      pageState.merged = 1;
      renderReadingPage();
      renderMergedPage();
    }

    async function mergeSelected() {
      const ids = Array.from(selectedCollectionItems.values());
      if (ids.length < 2) {
        setStatus('Select at least 2 cards to merge.', true);
        return;
      }

      const keyInput = document.getElementById('collectionKey').value.trim();
      const payload = { item_ids: ids };
      if (keyInput) payload.collection_key = keyInput;

      const result = await postJson('/api/news/collections/merge', payload);
      setStatus(`Merged ${result.updated_count} cards into ${result.collection_key}`);
      selectedCollectionItems.clear();
      updateSelectedCount();
      await refreshCollections();
      await refreshSignals();
    }

    async function unmergeSelected() {
      const ids = Array.from(selectedCollectionItems.values());
      if (!ids.length) {
        setStatus('Select at least 1 card to unmerge.', true);
        return;
      }

      const result = await postJson('/api/news/collections/unmerge', { item_ids: ids });
      setStatus(`Unmerged ${result.updated_count} cards back to automatic grouping.`);
      selectedCollectionItems.clear();
      updateSelectedCount();
      await refreshCollections();
      await refreshSignals();
    }

    async function setRelevanceForIds(ids, relevance, clearSelection = false) {
      if (!ids.length) {
        setStatus('Select at least 1 card to update relevance.', true);
        return;
      }

      const result = await postJson('/api/news/items/relevance', { item_ids: ids, relevance });
      const label = relevanceLabel(result.relevance_status);
      setStatus(`${label} ${result.updated_count} cards.`);
      if (clearSelection) {
        selectedCollectionItems.clear();
        updateSelectedCount();
      }
      await refreshSignals();
      await refreshCollections();
    }

    async function setRelevanceForSelected(relevance) {
      const ids = Array.from(selectedCollectionItems.values());
      await setRelevanceForIds(ids, relevance, true);
    }

    async function relevantSelected() {
      await setRelevanceForSelected('relevant');
    }

    async function nonRelevantSelected() {
      await setRelevanceForSelected('non_relevant');
    }

    async function clearRatingSelected() {
      await setRelevanceForSelected('unrated');
    }

    async function mergeIds(ids) {
      if (ids.length < 2) {
        const first = Number(ids[0] || 0);
        if (first > 0) {
          selectedCollectionItems.add(first);
          updateSelectedCount();
          setStatus('Select one more card, then merge again.', true);
          return;
        }
        setStatus('Select at least 2 cards to merge.', true);
        return;
      }
      const result = await postJson('/api/news/collections/merge', { item_ids: ids });
      setStatus(`Merged ${result.updated_count} cards into ${result.collection_key}`);
      await refreshCollections();
      await refreshSignals();
    }

    async function unmergeIds(ids) {
      if (!ids.length) {
        setStatus('Select at least 1 card to unmerge.', true);
        return;
      }
      const result = await postJson('/api/news/collections/unmerge', { item_ids: ids });
      setStatus(`Unmerged ${result.updated_count} cards back to automatic grouping.`);
      await refreshCollections();
      await refreshSignals();
    }

    function bindInlineActions(scope) {
      const root = scope || document;
      root.querySelectorAll('[data-sources]').forEach(btn=>btn.addEventListener('click',async e=>{
        e.stopPropagation();
        try {
          const rows=await getJson(`/api/news/item/${btn.dataset.sources}/sources`);
          const body=document.getElementById('editorialHistoryBody');
          body.innerHTML='<h4>Source coverage</h4>'+ (rows.length ? rows.map(r=>`<p><a href="${escapeHtml(r.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(r.title)}</a><br>${escapeHtml(r.publisher)} · ${escapeHtml(r.checked_at)}</p>`).join('') : '<p>Only the original RSS source is available. Use “Expand description” to retrieve additional context.</p>');
          document.getElementById('editorialHistory').hidden=false;
          document.getElementById('editorialHistory').scrollIntoView({behavior:'smooth'});
        }catch(err){setStatus('Could not load sources: '+err.message,true);}
      }));
      root.querySelectorAll('[data-editorial]').forEach(btn => btn.addEventListener('click', async e => {
        e.stopPropagation(); btn.disabled=true;
        const notice=document.getElementById('feedbackNotice');
        const topic=document.getElementById('interestFilter').value;
        try {
          const saved=await postJson(`/api/news/item/${btn.dataset.editorial}/feedback`, {topic,value:btn.dataset.vote});
          closeDetailOverlay();
          notice.innerHTML='Saved. <button type="button" id="undoFeedback">Undo</button>' + (btn.dataset.vote==='non_relevant' ? ' <span>Optional reason:</span> '+[['wrong_topic','Wrong topic'],['promotion','Promotion'],['geography','Wrong geography'],['not_now','Not relevant now']].map(([v,l])=>`<button type="button" data-reason="${v}">${l}</button>`).join(' ') : '');
          document.getElementById('undoFeedback').onclick=async () => {
            try {await postJson(`/api/news/feedback/${saved.event_id}/undo`,{});notice.textContent='Undone and saved.';await refreshSignals();}
            catch(err){notice.textContent='Could not undo: '+err.message;}
          };
          notice.querySelectorAll('[data-reason]').forEach(b=>b.onclick=async()=>{
            try {await postJson(`/api/news/feedback/${saved.event_id}/reason`,{reason:b.dataset.reason}); b.textContent='✓ Saved';}
            catch(err){setStatus('Reason not saved: '+err.message,true);}
          });
          await refreshSignals();
        } catch(err){notice.textContent='Not saved. Try again: '+err.message;}
        finally{btn.disabled=false;}
      }));
      root.querySelectorAll('[data-draft], [data-enrich]').forEach(btn=>btn.addEventListener('click',async e=>{
        e.stopPropagation();btn.disabled=true;const old=btn.textContent;btn.textContent='Working…';
        try {
          if(btn.dataset.draft){
            const result=await postJson(`/api/news/item/${btn.dataset.draft}/draft`,{});
            document.getElementById('draftBody').value=result.body;
            closeDetailOverlay();
            document.getElementById('editorialDraft').hidden=false;
            document.getElementById('editorialDraft').scrollIntoView({behavior:'smooth',block:'center'});
          } else {await postJson(`/api/news/item/${btn.dataset.enrich}/enrich?refresh=true`,{}); await showItemDetails(Number(btn.dataset.enrich));}
          await refreshSignals();setStatus('Saved.');
        } catch(err){setStatus('Could not complete: '+err.message,true);}
        finally{btn.disabled=false;btn.textContent=old;}
      }));
      root.querySelectorAll('[data-relevance-item]').forEach(btn => {
        btn.addEventListener('click', async (evt) => {
          evt.preventDefault();
          evt.stopPropagation();
          const id = Number(btn.getAttribute('data-relevance-item'));
          const relevance = String(btn.getAttribute('data-relevance-value') || 'unrated');
          if (!Number.isFinite(id) || id <= 0) return;
          await setRelevanceForIds([id], relevance, false);
        });
      });

      root.querySelectorAll('[data-merge-item]').forEach(btn => {
        btn.addEventListener('click', async (evt) => {
          evt.preventDefault();
          evt.stopPropagation();
          const id = Number(btn.getAttribute('data-merge-item'));
          if (!Number.isFinite(id) || id <= 0) return;
          const selected = Array.from(selectedCollectionItems.values());
          const ids = selected.length >= 2 ? selected : [id];
          await mergeIds(ids);
        });
      });

      root.querySelectorAll('[data-unmerge-item]').forEach(btn => {
        btn.addEventListener('click', async (evt) => {
          evt.preventDefault();
          evt.stopPropagation();
          const id = Number(btn.getAttribute('data-unmerge-item'));
          if (!Number.isFinite(id) || id <= 0) return;
          await unmergeIds([id]);
        });
      });

      root.querySelectorAll('[data-merge-pair]').forEach(btn => {
        btn.addEventListener('click', async (evt) => {
          evt.preventDefault();
          evt.stopPropagation();
          const raw = String(btn.getAttribute('data-merge-pair') || '');
          const ids = raw.split(',').map(x => Number(x)).filter(x => Number.isFinite(x) && x > 0);
          if (ids.length < 2) return;
          await mergeIds(ids);
        });
      });
    }
