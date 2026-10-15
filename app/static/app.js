const el = (id) => document.getElementById(id);
let registering = false;
let registeringManager = false;
let user = null;

function message(text, error = false) {
  el('message').textContent = text;
  el('message').className = error ? 'error' : '';
  el('message').hidden = !text;
}

function showUser(value) {
  user = value;
  el('auth').hidden = !!user;
  el('dashboard').hidden = !user;
  el('account').hidden = !user;
  el('username').textContent = user ? user.username : '';
  el('manager-dashboard').hidden = !user?.is_manager;
  el('reviews').replaceChildren();
  el('reviews-empty').hidden = true;
  if (!user) {
    el('claims').replaceChildren();
    el('expense-form').reset();
    setAuthMode('login');
  }
}

async function api(path, method = 'GET', data) {
  const response = await fetch(path, {
    method,
    headers: data ? { 'Content-Type': 'application/json' } : {},
    body: data ? JSON.stringify(data) : undefined,
  });
  if (response.status === 204) return null;
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 401 && user) showUser(null);
    const detail = Array.isArray(result.detail)
      ? result.detail.map((item) => `${item.loc.at(-1)}: ${item.msg}`).join(' ')
      : result.detail;
    throw new Error(detail || 'The request failed. Please try again.');
  }
  return result;
}

function node(tag, text, className) {
  const element = document.createElement(tag);
  element.textContent = text;
  if (className) element.className = className;
  return element;
}

async function loadClaims() {
  const account = user;
  const claims = await api('/api/expenses');
  if (user !== account) return;
  el('claims').replaceChildren();
  el('empty').hidden = claims.length > 0;
  for (const claim of claims) {
    const article = node('article', '', 'claim');
    const heading = node('div', '', 'claim-heading');
    heading.append(node('h3', claim.description), node('strong', `£${claim.amount}`));
    const submitted = new Date(claim.submitted_at).toLocaleString('en-GB');
    const meta = node('p', `Claim #${claim.id} · Expense date: ${claim.expense_date} · Submitted: ${submitted}`, 'claim-meta');
    article.append(heading, meta, node('span', claim.status, `badge ${claim.status.toLowerCase()}`));
    el('claims').append(article);
  }
}

async function loadReviews() {
  if (!user?.is_manager) return;
  const account = user;
  // Clear stale details and actions while fetching fresh permissions and claims.
  el('reviews').replaceChildren();
  el('reviews-empty').hidden = true;
  const claims = await api('/api/reviews');
  if (user !== account) return;
  for (const claim of claims) {
    const article = node('article', '', 'claim');
    const heading = node('div', '', 'claim-heading');
    heading.append(node('h3', claim.description), node('strong', `£${claim.amount}`));
    const submitted = new Date(claim.submitted_at).toLocaleString('en-GB');
    article.append(heading, node('p', `Claim #${claim.id} · Claimant: ${claim.claimant_username} · Expense date: ${claim.expense_date} · Submitted: ${submitted}`, 'claim-meta'), node('span', claim.status, 'badge'));
    const actions = node('div', '', 'review-actions');
    for (const status of ['Approved', 'Rejected']) {
      const button = node('button', status === 'Approved' ? 'Approve' : 'Reject', status === 'Rejected' ? 'reject' : '');
      button.type = 'button';
      button.addEventListener('click', () => {
        if (!window.confirm(`${status === 'Approved' ? 'Approve' : 'Reject'} claim #${claim.id} from ${claim.claimant_username} for £${claim.amount}? This decision is final.`)) return;
        const buttons = [...actions.querySelectorAll('button')];
        buttons.forEach((item) => { item.disabled = true; });
        busy(button, async () => {
          message('');
          try {
            await api(`/api/reviews/${claim.id}`, 'POST', { status });
          } catch (error) {
            // A competing manager may have decided this claim already.
            try { await loadReviews(); } catch { /* Preserve the decision error. */ }
            throw error;
          }
          article.remove();
          message(`Claim #${claim.id} ${status.toLowerCase()}.`);
          try { await loadReviews(); }
          catch { message(`Claim #${claim.id} ${status.toLowerCase()}. Refresh the queue to see the latest claims.`); }
        }).finally(() => buttons.forEach((item) => { item.disabled = false; }));
      });
      actions.append(button);
    }
    article.append(actions);
    el('reviews').append(article);
  }
  el('reviews-empty').hidden = claims.length > 0;
}

async function loadDashboard() {
  await loadClaims();
  await loadReviews();
}

async function busy(button, action) {
  button.disabled = true;
  try { await action(); }
  catch (error) { message(error.message || 'Unable to connect. Please try again.', true); }
  finally { button.disabled = false; }
}

function setAuthMode(mode) {
  registering = mode !== 'login';
  registeringManager = mode === 'manager';
  el('auth-title').textContent = registeringManager ? 'Create manager account' : registering ? 'Create your account' : 'Welcome back';
  el('auth-copy').textContent = registeringManager ? 'Verify your manager access to review expense claims.' : registering ? 'Keep your expense claims together in one place.' : 'Log in to submit expenses and track your claims.';
  el('auth-submit').textContent = registeringManager ? 'Create manager account' : registering ? 'Create account' : 'Log in';
  el('auth-toggle').textContent = registering ? 'Already have an account? Log in' : 'New here? Create an account';
  el('manager-register').hidden = registeringManager;
  el('manager-code-field').hidden = !registeringManager;
  el('manager-code').disabled = !registeringManager;
  el('manager-code').required = registeringManager;
  el('manager-code').value = '';
  el('password').autocomplete = registering ? 'new-password' : 'current-password';
  message('');
}

el('auth-toggle').addEventListener('click', () => setAuthMode(registering ? 'login' : 'register'));
el('manager-register').addEventListener('click', () => setAuthMode('manager'));

el('auth-form').addEventListener('submit', (event) => {
  event.preventDefault();
  busy(el('auth-submit'), async () => {
    message('');
    const data = Object.fromEntries(new FormData(event.target));
    const endpoint = registeringManager ? 'register-manager' : registering ? 'register' : 'login';
    const account = await api(`/api/auth/${endpoint}`, 'POST', data);
    event.target.reset();
    showUser(account);
    await loadDashboard();
  });
});

el('expense-form').addEventListener('submit', (event) => {
  event.preventDefault();
  busy(event.target.querySelector('button'), async () => {
    message('');
    const claim = await api('/api/expenses', 'POST', Object.fromEntries(new FormData(event.target)));
    event.target.reset();
    message(`Claim #${claim.id} submitted successfully.`);
    // Keep submission success visible if refreshing fails; do not encourage resubmission.
    try { await loadClaims(); }
    catch { message(`Claim #${claim.id} was submitted. Refresh the list to see it.`); }
  });
});

el('refresh').addEventListener('click', () => busy(el('refresh'), async () => {
  message('');
  await loadClaims();
  message('Claim statuses are up to date.');
}));

el('refresh-reviews').addEventListener('click', () => busy(el('refresh-reviews'), async () => {
  message('');
  await loadReviews();
  message('Review queue is up to date.');
}));

el('logout').addEventListener('click', () => busy(el('logout'), async () => {
  await api('/api/auth/logout', 'POST');
  showUser(null);
  message('You have logged out.');
}));

function updateDateLimits() {
  // Use UTC and clamp leap day to February 28, matching server validation.
  const today = new Date();
  const year = today.getUTCFullYear() - 1;
  const month = today.getUTCMonth();
  const lastDay = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const earliest = new Date(Date.UTC(year, month, Math.min(today.getUTCDate(), lastDay)));
  el('expense-date').min = earliest.toISOString().slice(0, 10);
  el('expense-date').max = today.toISOString().slice(0, 10);
}

el('expense-date').addEventListener('focus', updateDateLimits);

async function start() {
  updateDateLimits();
  try {
    const response = await fetch('/api/auth/me');
    if (response.status === 401) { showUser(null); return; }
    if (!response.ok) throw new Error('Unable to load your account. Please reload the page.');
    showUser(await response.json());
    await loadDashboard();
  } catch (error) {
    if (!user) showUser(null);
    message(error.message || 'Unable to connect. Please reload the page.', true);
  }
}
start();
