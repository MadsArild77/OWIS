/* Shared source configuration UI. It does not start collection jobs. */
(() => {
  const byId = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const words = value => String(value || '').split(',').map(v => v.trim()).filter(Boolean);
  let state = null, selected = 'NO', importData = null, editorRevision = null;
  const models = {
    jurisdictions: ['id','name','enabled','code','kind','groups'],
    organisations: ['id','name','enabled','jurisdiction_id','parent_id','kind','follow','topics','people'],
    sources: ['id','name','enabled','jurisdiction_id','organisation_id','url','content_types','method','topics','follow','interval_minutes','selector','notes'],
  };
  const clean = (kind, value) => Object.fromEntries(models[kind].filter(k => k in value).map(k => [k, value[k]]));
  const status = text => { byId('cfgStatus').textContent = text; };
  const request = async (path = '', body) => {
    const response = await fetch('/api/source-config' + path, body === undefined ? {} : {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Invalid configuration. Check the fields and try again.');
    return data;
  };
  function button(label, action, extra = '') {
    return `<button type="button" class="btn-secondary" data-cfg-action="${action}" ${extra}>${esc(label)}</button>`;
  }
  function sourceCard(source) {
    const states = {news_pipeline:'Ready for existing news pipeline', adapter_pending:'Configured · collection adapter pending', paused:'Paused by source or parent settings'};
    const last = source.last_test;
    return `<article class="research-panel"><h4>${esc(source.name)}</h4>
      <p>${esc(source.content_types.join(', '))} · ${esc(source.method.replaceAll('_',' '))}</p>
      <p class="muted" style="overflow-wrap:anywhere">${esc(source.url)}</p>
      <p>${esc(states[source.collection_status])}</p>
      ${last ? `<p class="muted">Last preview: ${esc(last.status)} · ${esc(new Date(last.checked_at).toLocaleString())} — ${esc(last.message)}</p>` : '<p class="muted">Not tested yet</p>'}
      <div class="card-actions-inline" style="flex-wrap:wrap">
        ${button('Edit','edit-source',`data-id="${source.id}"`)}
        ${button(source.enabled ? '− Pause' : '+ Resume','toggle-source',`data-id="${source.id}"`)}
        ${button('Test source','test-source',`data-id="${source.id}"`)}
      </div><div data-test-result="${source.id}" aria-live="polite"></div></article>`;
  }
  function render() {
    const select = byId('cfgJurisdiction');
    const jurisdictions = [...state.jurisdictions].sort((a,b) => ({NO:0,EU:1}[a.id] ?? 2)-({NO:0,EU:1}[b.id] ?? 2) || a.name.localeCompare(b.name));
    select.innerHTML = '<option value="unassigned">Unassigned sources</option>' + jurisdictions.map(j => {
      const sources = state.sources.filter(s => s.jurisdiction_id === j.id);
      const ready = sources.some(s => s.collection_status === 'news_pipeline');
      return `<option value="${esc(j.id)}">${esc(j.name)}${!j.enabled ? ' · Paused' : !ready ? ' · Not monitored' : ''} (${sources.length} sources)</option>`;
    }).join('');
    if (selected !== 'unassigned' && !jurisdictions.some(j => j.id === selected)) selected = jurisdictions[0]?.id || 'unassigned';
    select.value = selected;
    const jurisdiction = state.jurisdictions.find(j => j.id === selected);
    byId('cfgJurisdictionActions').innerHTML = (jurisdiction ?
      button('Edit jurisdiction','edit-jurisdiction') + button(jurisdiction.enabled ? '− Pause jurisdiction' : '+ Resume jurisdiction','toggle-jurisdiction') + button('+ Organisation','add-org') : '')
      + button('+ Source','add-source');
    const sources = state.sources.filter(s => (s.jurisdiction_id || 'unassigned') === selected);
    const orgs = state.organisations.filter(o => o.jurisdiction_id === selected);
    const orgCard = org => `<section class="research-panel"><h3>${esc(org.name)}</h3>
      <p class="muted">${esc(org.kind)} · ${!org.enabled ? 'Paused' : {all:'Follow all',topics:'Topic matches',off:'Off'}[org.follow]}</p>
      ${button('Edit','edit-org',`data-id="${org.id}"`)} ${button(org.enabled ? '− Pause' : '+ Resume','toggle-org',`data-id="${org.id}"`)}
      ${button('+ Source','add-source',`data-org="${org.id}"`)} ${button('+ Child organisation','add-org',`data-parent="${org.id}"`)}
      ${sources.filter(s => s.organisation_id === org.id).map(sourceCard).join('')}
      ${orgs.filter(child => child.parent_id === org.id).map(orgCard).join('')}
    </section>`;
    byId('cfgTree').innerHTML = `${jurisdiction ? `<p class="muted">${esc(jurisdiction.code)} · ${esc(jurisdiction.groups.join(', '))}</p>` : '<p>Existing sources are kept here until you assign a jurisdiction. No country has been inferred.</p>'}
      <p class="muted">RSS and HTML-list news sources use the existing news pipeline. Other sources are configured for later adapters. Intervals, topic priorities and person overrides are saved here; the shared scheduler and filtering arrive in steps 2–3. Pausing a parent already pauses its news collection.</p>
      ${sources.filter(s => !s.organisation_id).map(sourceCard).join('')}
      ${orgs.filter(o => !o.parent_id).map(orgCard).join('')}
      ${!sources.length && !orgs.length ? '<p>No organisations or sources configured yet.</p>' : ''}`;
  }
  async function load() {
    status('Loading source configuration…');
    try {
      state = await request(); render(); status('Configuration loaded.');
      byId('cfgEditor').hidden = true;
    } catch (error) { status(error.message); }
  }
  const input = (label, name, value = '', attrs = '') => `<label>${esc(label)}<input name="${name}" value="${esc(value)}" ${attrs}></label>`;
  const options = (label, name, values, value) => `<label>${esc(label)}<select name="${name}">${values.map(([key,text]) => `<option value="${esc(key)}" ${key === value ? 'selected' : ''}>${esc(text)}</option>`).join('')}</select></label>`;
  const followChoices = [['all','Follow all'],['topics','Only topic matches'],['off','Off']];

  function edit(kind, existing = {}, context = {}) {
    if (!state) return;
    editorRevision = state.revision;
    const value = clean(kind, existing);
    const jid = value.jurisdiction_id || (selected === 'unassigned' ? '' : selected);
    let fields = input('Name','name',value.name || '', 'required maxlength="160"');
    if (kind === 'jurisdictions') {
      fields += input('Code (for example NO or EU)','code',value.code || '', 'required pattern="[A-Z0-9_-]{2,12}" maxlength="12"')
        + options('Type','kind',[['country','Country'],['supranational','Supranational (EU)']],value.kind || 'country')
        + input('Display groups, comma-separated','groups',(value.groups || ['Europe']).join(', '));
    } else {
      fields += options('Jurisdiction','jurisdiction_id', [['','Unassigned'],...state.jurisdictions.map(j => [j.id,j.name])],jid);
      if (kind === 'organisations') {
        fields += options('Organisation type','kind',['government','ministry','parliament','committee','authority','other'].map(v => [v,v]),value.kind || 'other')
          + options('Parent organisation','parent_id',[['','None'],...state.organisations.filter(o => o.jurisdiction_id === jid && o.id !== value.id).map(o => [o.id,o.name])],value.parent_id || context.parent || '')
          + options('Priority','follow',followChoices,value.follow || 'topics')
          + input('Topics, comma-separated','topics',(value.topics || []).join(', '));
        for (const [mode,label] of followChoices) fields += input(`People: ${label.toLowerCase()} (comma-separated)`,'people_' + mode,(value.people || []).filter(p => p.follow === mode).map(p => p.person).join(', '));
      } else {
        fields += options('Organisation','organisation_id',[['','None'],...state.organisations.filter(o => o.jurisdiction_id === jid).map(o => [o.id,o.name])],value.organisation_id || context.org || '')
          + input('Source URL','url',value.url || '', 'type="url" required maxlength="2048"')
          + options('Fetch method','method',[['rss','RSS / Atom'],['html_list','Web page · list of links'],['html_page','Web page · text'],['ics','ICS calendar (adapter pending)'],['api','API (adapter pending)']],value.method || 'rss')
          + `<fieldset><legend>Content</legend>${['news','regulation','consultation','calendar'].map(v => `<label style="display:inline-block;margin-right:12px"><input type="checkbox" name="content_types" value="${v}" ${(value.content_types || ['news']).includes(v) ? 'checked' : ''}> ${v}</label>`).join('')}</fieldset>`
          + input('Topics, comma-separated','topics',(value.topics || []).join(', '))
          + options('Priority','follow',[['inherit','Inherit organisation priority'],...followChoices],value.follow || 'inherit')
          + input('Requested check interval (minutes)','interval_minutes',value.interval_minutes || 360, 'type="number" required min="15" max="43200"')
          + '<p class="muted">Intervals and topic/person rules are configuration for the next implementation steps. Existing news collection keeps its current schedule. Test previews do not create articles or run AI.</p>'
          + `<details><summary>Advanced</summary>${input('CSS selector for HTML preview','selector',value.selector || '', 'maxlength="500"')}<p class="muted">A selector limits this preview. The existing news collector does not use it yet.</p>${input('Notes','notes',value.notes || '', 'maxlength="2000"')}</details>`;
      }
    }
    const root = byId('cfgEditor');
    root.hidden = false;
    root.innerHTML = `<h3>${value.id ? 'Edit' : 'Add'} ${esc(kind === 'jurisdictions' ? 'jurisdiction' : kind === 'organisations' ? 'organisation' : 'source')}</h3>
      <form id="cfgForm"><div class="two-col">${fields}</div><label><input type="checkbox" name="enabled" ${value.enabled !== false ? 'checked' : ''}> Enabled</label>
      <div class="card-actions-inline"><button type="submit">Save</button>${kind === 'sources' ? '<button type="button" id="cfgTestDraft">Test source</button>' : ''}<button type="button" id="cfgCancelEdit">Cancel</button></div>
      <p id="cfgFormStatus" role="status" aria-live="polite"></p><div id="cfgDraftPreview"></div></form>`;
    const form = byId('cfgForm');
    const payload = () => {
      const data = new FormData(form);
      const item = {id:value.id || null, name:data.get('name'), enabled:data.has('enabled')};
      if (kind === 'jurisdictions') return {...item,code:data.get('code'),kind:data.get('kind'),groups:words(data.get('groups'))};
      item.jurisdiction_id = data.get('jurisdiction_id') || null;
      item.topics = words(data.get('topics')); item.follow = data.get('follow');
      if (kind === 'organisations') return {...item,kind:data.get('kind'),parent_id:data.get('parent_id') || null,
        people:followChoices.flatMap(([mode]) => words(data.get('people_' + mode)).map(person => ({person,follow:mode})))};
      return {...item,organisation_id:data.get('organisation_id') || null,url:data.get('url'),method:data.get('method'),
        content_types:data.getAll('content_types'),interval_minutes:Number(data.get('interval_minutes')),selector:data.get('selector'),notes:data.get('notes')};
    };
    form.elements.jurisdiction_id?.addEventListener('change', () => {
      const target = form.elements[kind === 'sources' ? 'organisation_id' : 'parent_id'];
      target.innerHTML = '<option value="">None</option>' + state.organisations.filter(o => o.jurisdiction_id === form.elements.jurisdiction_id.value && o.id !== value.id).map(o => `<option value="${o.id}">${esc(o.name)}</option>`).join('');
    });
    byId('cfgCancelEdit').onclick = () => { root.hidden = true; };
    form.onsubmit = async event => {
      event.preventDefault(); const save = form.querySelector('[type="submit"]'); save.disabled = true;
      try {
        const item = payload();
        state = await request('/' + kind,{revision:editorRevision,item});
        if (kind === 'jurisdictions') selected = state.jurisdictions.find(j => j.code === item.code).id;
        else selected = item.jurisdiction_id || 'unassigned';
        root.hidden = true; render(); status('Configuration saved.');
        window.dispatchEvent(new Event('owis-source-config-saved'));
      } catch (error) { byId('cfgFormStatus').textContent = error.message; }
      finally { save.disabled = false; }
    };
    if (kind === 'sources') byId('cfgTestDraft').onclick = async event => {
      if (!form.reportValidity()) return;
      const btn = event.currentTarget; btn.disabled = true;
      try { byId('cfgDraftPreview').innerHTML = previewHtml(await request('/test',payload())); }
      catch (error) { byId('cfgFormStatus').textContent = error.message; }
      finally { btn.disabled = false; }
    };
    root.scrollIntoView({block:'start',behavior:'smooth'});
  }
  function previewHtml(result) {
    return `<p><strong>${esc(result.status)}</strong> — ${esc(result.message)}</p>${result.items.map(item => `<div class="research-panel"><strong>${esc(item.title)}</strong><p style="overflow-wrap:anywhere">${esc(item.url)}</p><p style="white-space:pre-wrap">${esc(item.text)}</p></div>`).join('')}`;
  }
  byId('sourceConfig').addEventListener('click', async event => {
    const btn = event.target.closest('[data-cfg-action]');
    if (!btn || !state) return;
    const action = btn.dataset.cfgAction, id = btn.dataset.id;
    const kind = action.includes('jurisdiction') ? 'jurisdictions' : action.includes('org') ? 'organisations' : 'sources';
    const item = state[kind].find(v => v.id === (kind === 'jurisdictions' ? selected : id));
    if (action.startsWith('edit')) { edit(kind,item); return; }
    if (action.startsWith('add')) { edit(kind,{}, {org:btn.dataset.org,parent:btn.dataset.parent}); return; }
    btn.disabled = true;
    try {
      if (action === 'test-source') {
        const target = byId('cfgTree').querySelector(`[data-test-result="${id}"]`);
        target.textContent = 'Reading source…';
        const result = await request('/test',clean('sources',item));
        target.innerHTML = previewHtml(result);
      } else if (action.startsWith('toggle')) {
        state = await request('/' + kind,{revision:state.revision,item:{...clean(kind,item),enabled:!item.enabled}});
        render(); status('Saved. Existing history is preserved.');
        window.dispatchEvent(new Event('owis-source-config-saved'));
      }
    } catch (error) { status(error.message); }
    finally { btn.disabled = false; }
  });
  byId('showSettingsView').addEventListener('click',load);
  byId('cfgReload').onclick = load;
  byId('cfgJurisdiction').onchange = () => { selected = byId('cfgJurisdiction').value; byId('cfgEditor').hidden = true; render(); };
  byId('cfgAddJurisdiction').onclick = () => edit('jurisdictions');
  byId('cfgExport').onclick = async () => {
    try {
      const data = await request('/export');
      const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
      const link = document.createElement('a'); link.href = url; link.download = 'owis-source-configuration.json'; link.click();
      setTimeout(() => URL.revokeObjectURL(url),1000); status('Configuration exported. Authentication settings are excluded.');
    } catch (error) { status(error.message); }
  };
  byId('cfgImportToggle').onclick = () => { byId('cfgImportPanel').hidden = !byId('cfgImportPanel').hidden; };
  byId('cfgImportFile').onchange = async () => {
    importData = null; byId('cfgImportApply').disabled = true;
    try {
      const file = byId('cfgImportFile').files[0];
      if (!file) return;
      if (file.size > 2_000_000) throw new Error('Configuration import is limited to 2 MB.');
      const data = JSON.parse(await file.text());
      if (data.version !== 1 || !['jurisdictions','organisations','sources'].every(k => Array.isArray(data[k]))) throw new Error('Unsupported configuration format.');
      importData = data;
      byId('cfgImportSummary').textContent = `${data.jurisdictions.length} jurisdictions, ${data.organisations.length} organisations, ${data.sources.length} sources. Matching IDs will be updated.`;
      byId('cfgImportApply').disabled = !state;
    } catch (error) { byId('cfgImportSummary').textContent = error.message; }
  };
  byId('cfgImportApply').onclick = async () => {
    if (!state || !importData) return;
    byId('cfgImportApply').disabled = true;
    try {
      state = await request('/import',{revision:state.revision,configuration:importData});
      byId('cfgEditor').hidden = true; render(); status('Configuration imported. Records not in the file were preserved.');
      window.dispatchEvent(new Event('owis-source-config-saved'));
    } catch (error) { status(error.message); }
    finally { byId('cfgImportApply').disabled = false; }
  };
})();
