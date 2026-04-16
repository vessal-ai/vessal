/**
 * renderer.js — Component DOM renderer.
 * Receives render spec, updates #components via morphdom diff.
 */
(function() {
  if (typeof morphdom === 'undefined') {
    console.error('[vessal] morphdom not loaded — component renderer disabled');
    return;
  }

  let _lastInteractions = null;

  const RENDERERS = {
    text(props) {
      const el = document.createElement('p');
      el.className = 'text-gray-200';
      el.textContent = props.content || '';
      if (props.bold) el.classList.add('font-bold');
      return el;
    },

    card(props, children) {
      const el = document.createElement('div');
      el.className = 'bg-gray-800 rounded-lg p-4 shadow-md';
      if (props.title) {
        const h = document.createElement('h3');
        h.className = 'text-lg font-semibold mb-2 text-gray-100';
        h.textContent = props.title;
        el.appendChild(h);
      }
      children.forEach(c => el.appendChild(c));
      return el;
    },

    button(props) {
      const el = document.createElement('button');
      el.className = 'bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded transition-colors';
      el.textContent = props.label || '';
      el.dataset.id = props.id || '';
      el.addEventListener('click', () => {
        window.sendEvent({ event: 'click', id: props.id, ts: Date.now() / 1000 });
      });
      return el;
    },

    input(props) {
      const wrapper = document.createElement('div');
      const el = document.createElement('input');
      el.type = 'text';
      el.placeholder = props.placeholder || '';
      el.className = 'bg-gray-700 text-gray-100 px-3 py-2 rounded w-full focus:outline-none focus:ring-2 focus:ring-blue-500';
      el.dataset.id = props.id || '';
      el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          window.sendEvent({
            event: 'input_submit',
            id: props.id,
            value: el.value,
            ts: Date.now() / 1000,
          });
          el.value = '';
        }
      });
      wrapper.appendChild(el);
      return wrapper;
    },

    panel(props, children) {
      const el = document.createElement('section');
      el.className = 'bg-gray-900 border border-gray-700 rounded-lg p-4';
      if (props.id) el.id = props.id;
      const h = document.createElement('h2');
      h.className = 'text-xl font-bold mb-3 text-gray-50';
      h.textContent = props.title || '';
      el.appendChild(h);
      const content = document.createElement('div');
      content.className = 'space-y-3';
      children.forEach(c => content.appendChild(c));
      el.appendChild(content);
      return el;
    },

    chart(props) {
      // v0.1.0: simple text representation
      const el = document.createElement('div');
      el.className = 'bg-gray-800 p-3 rounded font-mono text-sm';
      const data = props.data || [];
      const max = Math.max(...data, 1);
      data.forEach((v, i) => {
        const row = document.createElement('div');
        row.className = 'flex items-center gap-2 mb-1';
        const bar = document.createElement('div');
        bar.className = 'bg-blue-500 h-4 rounded';
        bar.style.width = `${(v / max) * 100}%`;
        const label = document.createElement('span');
        label.className = 'text-gray-400 text-xs w-8';
        label.textContent = v;
        row.appendChild(bar);
        row.appendChild(label);
        el.appendChild(row);
      });
      return el;
    },
  };

  function renderComponent(spec) {
    if (!spec || !spec.type) return document.createTextNode('');
    const renderer = RENDERERS[spec.type];
    if (!renderer) {
      const el = document.createElement('div');
      el.className = 'text-red-400';
      el.textContent = `[Unknown: ${spec.type}]`;
      return el;
    }
    const children = (spec.children || []).map(renderComponent);
    return renderer(spec.props || {}, children);
  }

  function renderComponents(components) {
    const container = document.getElementById('components');
    if (!container) return;
    const newContainer = document.createElement('div');
    newContainer.id = 'components';
    newContainer.className = 'grid gap-4';
    components.forEach(c => newContainer.appendChild(renderComponent(c)));
    // v0.1.0: replace instead of morphdom to avoid event listener accumulation on interactive elements
    container.replaceWith(newContainer);
  }

  function renderInteractions(interactions) {
    const container = document.getElementById('interactions');
    if (!container) return;

    // Skip rebuild if interactions unchanged (preserves user's typed text)
    const interactionsKey = JSON.stringify(interactions);
    if (interactionsKey === _lastInteractions) return;
    _lastInteractions = interactionsKey;

    container.innerHTML = '';
    if (!interactions || interactions.length === 0) return;

    interactions.forEach(inter => {
      if (inter.type === 'choices') {
        const div = document.createElement('div');
        div.className = 'flex gap-2 justify-center';
        inter.options.forEach(opt => {
          const btn = document.createElement('button');
          btn.className = 'bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded-full shadow-lg transition-all';
          btn.textContent = opt;
          btn.addEventListener('click', () => {
            window.sendEvent({ event: 'choice', value: opt, ts: Date.now() / 1000 });
            container.innerHTML = '';
          });
          div.appendChild(btn);
        });
        container.appendChild(div);
      } else if (inter.type === 'ask') {
        const div = document.createElement('div');
        div.className = 'bg-gray-800 rounded-lg p-3 shadow-lg flex gap-2 min-w-[300px]';
        const input = document.createElement('input');
        input.type = 'text';
        input.placeholder = inter.prompt || '';
        input.className = 'bg-gray-700 text-gray-100 px-3 py-2 rounded flex-1 focus:outline-none focus:ring-2 focus:ring-purple-500';
        const btn = document.createElement('button');
        btn.className = 'bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded';
        btn.textContent = '→';
        const submit = () => {
          if (input.value.trim()) {
            window.sendEvent({ event: 'avatar_input', content: input.value.trim(), ts: Date.now() / 1000 });
            container.innerHTML = '';
          }
        };
        input.addEventListener('keydown', e => { if (e.key === 'Enter') submit(); });
        btn.addEventListener('click', submit);
        div.appendChild(input);
        div.appendChild(btn);
        container.appendChild(div);
        input.focus();
      }
    });
  }

  // Main render handler
  window.onRenderSpec = function(spec) {
    if (spec.components) renderComponents(spec.components);
    if (spec.interactions) renderInteractions(spec.interactions);
    if (spec.body && window.onBodySpec) window.onBodySpec(spec.body);
  };
})();
