    // App shell: page heading per section, topic chips, search and keyboard shortcuts.
    (function () {
      const sections = {
        reading: ['News', 'Energy, maritime and electrification — what is happening and who is involved.'],
        morning: ['Morning brief', 'The last 24 hours and what is coming up.'],
        governance: ['Policy & regulation', 'Laws, consultations and political milestones.'],
        researched: ['Researched', 'Stories you have looked into, with saved findings.'],
        review: ['Review queue', 'Merge, rate and train how stories are grouped.'],
        sources: ['Source advisor', 'Which sources to add, pause or rely on, learned from what they deliver.'],
        settings: ['Settings', 'Sources, fetching and configuration.'],
      };
      const settingsView = document.getElementById('settingsView');
      const search = document.getElementById('storySearch');
      let currentSection = 'reading';

      function showSection(key) {
        currentSection = key;
        const [title, subtitle] = sections[key] || sections.reading;
        document.getElementById('pageTitle').textContent = title;
        document.getElementById('pageSubtitle').textContent = subtitle;
        document.title = `${title} · OWIS`;
        document.getElementById('searchBox').hidden = key !== 'reading';
        document.body.classList.toggle('settings-open', key === 'settings');
      }

      document.querySelectorAll('.nav-item.tab-btn').forEach(button => button.addEventListener('click', () => {
        if (!settingsView.hidden) document.getElementById('showNewsView').click();
        showSection(button.dataset.tab);
        window.scrollTo({top: 0});
      }));
      document.getElementById('showSettingsView').addEventListener('click', () => {
        showSection('settings');
        window.scrollTo({top: 0});
      });

      const interest = document.getElementById('interestFilter');
      document.querySelectorAll('#topicChips [data-topic]').forEach(chip => chip.addEventListener('click', () => {
        document.querySelectorAll('#topicChips [data-topic]').forEach(other => other.setAttribute('aria-pressed', String(other === chip)));
        interest.value = chip.dataset.topic;
        interest.dispatchEvent(new Event('change'));
      }));

      let searchTimer;
      search.addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => { pageState.reading = 1; renderReadingPage(); }, 120);
      });
      search.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
          event.stopPropagation();
          if (search.value) { search.value = ''; search.dispatchEvent(new Event('input')); } else search.blur();
        }
      });

      function isTyping(target) {
        return target instanceof HTMLElement && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName));
      }

      document.addEventListener('keydown', event => {
        if (event.ctrlKey || event.metaKey || event.altKey || isTyping(event.target)) return;
        const drawerOpen = document.getElementById('detailOverlay').classList.contains('open');
        if (event.key === '/' && !drawerOpen) {
          event.preventDefault();
          if (currentSection !== 'reading') document.querySelector('.nav-item[data-tab="reading"]').click();
          search.focus();
          return;
        }
        if (event.key !== 'j' && event.key !== 'k') return;
        const delta = event.key === 'j' ? 1 : -1;
        if (drawerOpen) { stepDetailItem(delta); return; }
        if (currentSection !== 'reading') return;
        const links = [...document.querySelectorAll('#readingStories .story-open')];
        if (!links.length) return;
        const index = links.indexOf(document.activeElement);
        const next = index < 0 ? (delta > 0 ? 0 : links.length - 1) : Math.min(Math.max(index + delta, 0), links.length - 1);
        links[next].focus();
        links[next].closest('.story')?.scrollIntoView({block: 'nearest'});
      });

      showSection('reading');
    })();
