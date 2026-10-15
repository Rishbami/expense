const el = (id) => document.getElementById(id);
let registering = false;
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
  if (!user) {
    el('claims').replaceChildren();
    el('expense-form').reset();
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
  const claims = await api('/api/expenses');
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

async function busy(button, action) {
  button.disabled = true;
  try { await action(); }
  catch (error) { message(error.message || 'Unable to connect. Please try again.', true); }
  finally { button.disabled = false; }
}

el('auth-toggle').addEventListener('click', () => {
  registering = !registering;
  el('auth-title').textContent = registering ? 'Create your account' : 'Welcome back';
  el('auth-copy').textContent = registering ? 'Keep your expense claims together in one place.' : 'Log in to submit expenses and track your claims.';
  el('auth-submit').textContent = registering ? 'Create account' : 'Log in';
  el('auth-toggle').textContent = registering ? 'Already have an account? Log in' : 'New here? Create an account';
  el('password').autocomplete = registering ? 'new-password' : 'current-password';
  message('');
});

el('auth-form').addEventListener('submit', (event) => {
  event.preventDefault();
  busy(el('auth-submit'), async () => {
    message('');
    const data = Object.fromEntries(new FormData(event.target));
    const account = await api(`/api/auth/${registering ? 'register' : 'login'}`, 'POST', data);
    event.target.reset();
    showUser(account);
    await loadClaims();
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
    await loadClaims();
  } catch (error) {
    if (!user) showUser(null);
    message(error.message || 'Unable to connect. Please reload the page.', true);
  }
}
start();
