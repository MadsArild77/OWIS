
    async function boot() {
      document.getElementById('importBtn').addEventListener('click', importSourcesFromText);
      document.getElementById('saveEditBtn').addEventListener('click', saveEdit);
      document.getElementById('dedupeBtn').addEventListener('click', dedupeSources);
      document.getElementById('rediscoverBtn').addEventListener('click', rediscoverRSS);
      document.getElementById('healthBtn').addEventListener('click', sourceHealth);
      document.getElementById('runPipelineBtn').addEventListener('click', () => runPipeline(false));
      document.getElementById('quickFetchBtn').addEventListener('click', () => runPipeline(true));
      document.getElementById('checkAiBtn').addEventListener('click', async () => {
        setButtonBusy('checkAiBtn', true, 'Checking AI...');
        try {
          await refreshAiStatus(true);
        } catch (err) {
          console.error(err);
          setStatus('AI status check failed.', true);
        } finally {
          setButtonBusy('checkAiBtn', false);
        }
      });
      document.getElementById('runMatchBtn').addEventListener('click', runMatchReviewQueue);
      document.getElementById('mergeBtn').addEventListener('click', mergeSelected);
      document.getElementById('unmergeBtn').addEventListener('click', unmergeSelected);
      document.getElementById('relevantBtn').addEventListener('click', relevantSelected);
      document.getElementById('nonRelevantBtn').addEventListener('click', nonRelevantSelected);
      document.getElementById('clearRatingBtn').addEventListener('click', clearRatingSelected);
      function showView(settings) {
        closeDetailOverlay();
        document.getElementById('settingsView').hidden=!settings;
        document.getElementById('articlesView').hidden=settings;
        document.getElementById('showNewsView').setAttribute('aria-pressed',String(!settings));
        document.getElementById('showSettingsView').setAttribute('aria-pressed',String(settings));
      }
      document.getElementById('showNewsView').addEventListener('click',()=>showView(false));
      document.getElementById('showSettingsView').addEventListener('click',()=>showView(true));
      const settingsTabs = ['newsSettingsTab', 'regulatorySettingsTab'].map(id => document.getElementById(id));
      function selectSettingsTab(index) {
        settingsTabs.forEach((tab, i) => {
          tab.setAttribute('aria-selected', String(i === index));
          tab.tabIndex = i === index ? 0 : -1;
          document.getElementById(tab.getAttribute('aria-controls')).hidden = i !== index;
        });
      }
      settingsTabs.forEach((tab, index) => {
        tab.addEventListener('click', () => selectSettingsTab(index));
        tab.addEventListener('keydown', event => {
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
          event.preventDefault();
          const next = event.key === 'Home' ? 0 : event.key === 'End' ? 1 : 1 - index;
          selectSettingsTab(next);
          settingsTabs[next].focus();
        });
      });
      window.addEventListener('owis-source-config-saved', () => refreshSources().catch(error => setStatus(error.message, true)));
      document.getElementById('backfillBtn').addEventListener('click',async()=>{
        const button=document.getElementById('backfillBtn');button.disabled=true;
        try {
          const result=await startBackendJob('enrich_backfill',{limit:5},{title:'Expanding older stories'});
          await refreshSignals();setStatus(`Updated ${result.updated.length} stories. Errors: ${result.errors.length}.`);
        } catch(err){setStatus(err.message,true);} finally {button.disabled=false;}
      });
      document.getElementById('detailCloseBtn').addEventListener('click', closeDetailOverlay);
      document.getElementById('detailPrevBtn').addEventListener('click', () => stepDetailItem(-1));
      document.getElementById('detailNextBtn').addEventListener('click', () => stepDetailItem(1));
      document.getElementById('detailOverlay').addEventListener('click', (evt) => {
        if (evt.target === evt.currentTarget) closeDetailOverlay();
      });
      document.addEventListener('keydown', (evt) => {
        if (evt.key === 'Escape') closeDetailOverlay();
        if (document.getElementById('detailOverlay')?.classList.contains('open') && evt.key === 'ArrowLeft') stepDetailItem(-1);
        if (document.getElementById('detailOverlay')?.classList.contains('open') && evt.key === 'ArrowRight') stepDetailItem(1);
      });
      const onGlobalFilterChange = async () => {
        selectedCollectionItems.clear();
        updateSelectedCount();
        await refreshSignals();
        await refreshCollections();
        await refreshMatchReview();
      };
      document.getElementById('sourceFilter').addEventListener('change', onGlobalFilterChange);
      document.getElementById('domainFilter').addEventListener('change', onGlobalFilterChange);
      document.getElementById('interestFilter').addEventListener('change', () => refreshSignals());
      ['geographyFilter', 'companyFilter', 'storySort'].forEach(id => document.getElementById(id).addEventListener('change', () => {
        pageState.reading = 1;
        renderReadingPage();
      }));
      document.getElementById('showDismissed').addEventListener('change', () => refreshSignals());
      document.getElementById('showFeedbackHistory').onclick=async()=>{
        try {
          const rows=await getJson('/api/news/feedback/history');
          document.getElementById('editorialHistoryBody').innerHTML=rows.length ? rows.map(r=>`<p>${escapeHtml(r.title || ('Article '+r.processed_id))}<br>${escapeHtml(({relevant:'Relevant',non_relevant:'Hide',unrated:'Reset'})[r.value] || r.value)} · ${escapeHtml(r.topic)} · ${escapeHtml(r.created_at)}${r.undone ? ' · Undone' : ''}</p>`).join('') : '<p>No feedback saved yet.</p>';
          document.getElementById('editorialHistory').hidden=false;
        }catch(err){setStatus('Could not load history: '+err.message,true);}
      };
      document.getElementById('copyDraft').onclick=async()=>{try{await navigator.clipboard.writeText(document.getElementById('draftBody').value);setStatus('Draft copied.');}catch(err){setStatus('Select and copy the text manually.',true);}};

      document.getElementById('readingPrev').addEventListener('click', () => changePage('reading', -1));
      document.getElementById('readingNext').addEventListener('click', () => changePage('reading', 1));
      document.getElementById('mergedPrev').addEventListener('click', () => changePage('merged', -1));
      document.getElementById('mergedNext').addEventListener('click', () => changePage('merged', 1));
      setupTabs();

      try {
        await refreshAiStatus(false);
        await refreshSources();
        await refreshSignals();
        await refreshCollections();
        await refreshMatchReview();
      } catch (err) {
        console.error(err);
        setStatus('Failed loading data. Check API logs.', true);
      }
    }

    boot();
