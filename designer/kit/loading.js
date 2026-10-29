// Shared, local loading feedback. Existing content stays usable beneath/alongside it.
// Capture begin()'s token and pass it to every asynchronous completion:
// const token=status.begin('Loading robot…'); ... status.ready(token);
// status.fail('The robot could not load.', {token,onRetry:loadRobot});
// A stale completion (including a finally block) cannot dismiss a newer operation.
export function createLoadingStatus(host, { label = '', onRetry, onCancel, overlay = false, id } = {}) {
  const cssUrl = new URL('./loading.css', import.meta.url);
  cssUrl.search = new URL(import.meta.url).search;
  if (!document.querySelector('link[data-gyropup-loading]')) {
    const css = document.createElement('link');
    css.rel = 'stylesheet'; css.href = cssUrl.href; css.dataset.gyropupLoading = '';
    document.head.append(css);
  }
  const element = document.createElement('div');
  element.className = `gp-loading${overlay ? ' gp-loading--overlay' : ''}`;
  if (id) element.id = id;
  element.hidden = true;
  element.setAttribute('role', 'status'); element.setAttribute('aria-live', 'polite');
  element.innerHTML = '<span class="gp-loading-icon" aria-hidden="true"></span><span class="gp-loading-message"></span><span class="gp-loading-actions"><button type="button" data-retry>Try again</button><button type="button" data-cancel>Keep playing</button></span>';
  const message = element.querySelector('.gp-loading-message');
  const retry = element.querySelector('[data-retry]'), cancel = element.querySelector('[data-cancel]');
  host.append(element);
  let generation = 0, disposed = false, retryAction = onRetry, cancelAction = onCancel;
  const valid = token => !disposed && token === generation;
  const paint = (state, text) => {
    element.dataset.state = state; element.hidden = false;
    element.setAttribute('aria-busy', String(state === 'loading')); message.textContent = text;
    retry.hidden = state === 'loading' || !retryAction;
    cancel.hidden = !cancelAction;
  };
  const invoke = action => {
    if (!action) return;
    const token = generation;
    Promise.resolve().then(action).catch(error => {
      if (!valid(token)) return;
      console.warn('Loading action failed:', error.message);
      api.fail('That did not finish. Please try again.');
    });
  };
  retry.onclick = () => invoke(retryAction);
  cancel.onclick = () => { const action = cancelAction; api.dismiss(); invoke(action); };
  const finish = (state, text, opts = {}) => {
    if (!valid(opts.token ?? generation)) return false;
    ++generation;
    retryAction = Object.hasOwn(opts, 'onRetry') ? opts.onRetry : onRetry;
    cancelAction = Object.hasOwn(opts, 'onCancel') ? opts.onCancel : onCancel;
    paint(state, text); return true;
  };
  const api = {
    element,
    begin(text = label, opts = {}) {
      if (disposed) return null;
      const token = ++generation;
      retryAction = Object.hasOwn(opts, 'onRetry') ? opts.onRetry : onRetry;
      cancelAction = Object.hasOwn(opts, 'onCancel') ? opts.onCancel : onCancel;
      paint('loading', text); return token;
    },
    update(text, token = generation) { if (!valid(token)) return false; message.textContent = text; return true; },
    ready(token = generation) { if (!valid(token)) return false; ++generation; element.hidden = true; element.dataset.state = 'ready'; element.setAttribute('aria-busy', 'false'); return true; },
    fail(text, opts) { return finish('error', text, opts); },
    unavailable(text, opts) { return finish('unavailable', text, opts); },
    dismiss() { if (!disposed) { ++generation; element.hidden = true; element.setAttribute('aria-busy', 'false'); } },
    dispose() { ++generation; disposed = true; element.remove(); },
  };
  if (label) api.begin(label);
  return api;
}
