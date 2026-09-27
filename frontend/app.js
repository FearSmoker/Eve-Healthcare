/* ══════════════════════════════════════════════════════════════
   EVE HEALTHCARE — Single-Page Application
   ══════════════════════════════════════════════════════════════ */

'use strict';

/* ─────────────────────────────────────────────────────
   STATE
───────────────────────────────────────────────────── */
const App = {
  token: localStorage.getItem('eve_token') || null,
  user:  JSON.parse(localStorage.getItem('eve_user') || 'null'),

  setAuth(token, user) {
    this.token = token;
    this.user  = user;
    localStorage.setItem('eve_token', token);
    localStorage.setItem('eve_user', JSON.stringify(user));
  },
  clearAuth() {
    this.token = null;
    this.user  = null;
    localStorage.removeItem('eve_token');
    localStorage.removeItem('eve_user');
  },
  isAdmin() { return this.user?.role === 'ADMIN'; },
  isLoggedIn() { return !!this.token; },
};

/* ─────────────────────────────────────────────────────
   API CLIENT
───────────────────────────────────────────────────── */
const api = {
  async req(method, path, body = null, authRequired = true) {
    const headers = { 'Content-Type': 'application/json' };
    if (authRequired && App.token) headers['Authorization'] = `Bearer ${App.token}`;

    const opts = { method, headers };
    if (body !== null) opts.body = JSON.stringify(body);

    let res;
    try { res = await fetch(path, opts); }
    catch (e) { throw { detail: 'Network error — is the server running?', error_code: 'NETWORK_ERROR' }; }

    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw data;
    return data;
  },
  get:    (p, auth = true)    => api.req('GET',    p, null, auth),
  post:   (p, b, auth = true) => api.req('POST',   p, b,    auth),
  delete: (p, auth = true)    => api.req('DELETE', p, null, auth),
};

/* ─────────────────────────────────────────────────────
   TOAST NOTIFICATIONS
───────────────────────────────────────────────────── */
const toast = {
  show(type, title, msg = '') {
    const icons = { success: '✅', error: '❌', info: 'ℹ️' };
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.innerHTML = `
      <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
      <div class="toast-body">
        <div class="toast-title">${esc(title)}</div>
        ${msg ? `<div class="toast-msg">${esc(msg)}</div>` : ''}
      </div>
    `;
    const container = document.getElementById('toast-container');
    container.appendChild(el);
    setTimeout(() => {
      el.style.opacity = '0'; el.style.transition = 'opacity 300ms';
      setTimeout(() => el.remove(), 300);
    }, 3500);
  },
  success: (t, m) => toast.show('success', t, m),
  error:   (t, m) => toast.show('error',   t, m),
  info:    (t, m) => toast.show('info',    t, m),
  apiErr(e, fallback = 'Something went wrong.') {
    const msg = e?.detail || e?.message || fallback;
    toast.error('Error', msg);
  },
};

/* ─────────────────────────────────────────────────────
   MODAL
───────────────────────────────────────────────────── */
const modal = {
  open(html) {
    const root = document.getElementById('modal-root');
    root.innerHTML = `<div class="modal-overlay" id="modal-overlay">${html}</div>`;
    root.querySelector('.modal-overlay').addEventListener('click', e => {
      if (e.target.id === 'modal-overlay') modal.close();
    });
  },
  close() {
    document.getElementById('modal-root').innerHTML = '';
  },
};

/* ─────────────────────────────────────────────────────
   UTILITIES
───────────────────────────────────────────────────── */
function esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtINR(paise) {
  return '₹' + (paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: true,
  });
}

function statusBadge(status) {
  const map = {
    PENDING:   'badge-pending',
    CONFIRMED: 'badge-confirmed',
    FAILED:    'badge-failed',
    CANCELLED: 'badge-cancelled',
  };
  return `<span class="badge ${map[status] || 'badge-cancelled'}">${esc(status)}</span>`;
}

function loading() {
  return `<div class="loading-state"><div class="spinner"></div><p>Loading…</p></div>`;
}

function empty(icon, title, subtitle = '') {
  return `<div class="empty-state">
    <span class="empty-icon">${icon}</span>
    <h3>${esc(title)}</h3>
    ${subtitle ? `<p>${esc(subtitle)}</p>` : ''}
  </div>`;
}

function minFutureDate() {
  const d = new Date(Date.now() + 30 * 60 * 1000);
  return d.toISOString().slice(0, 16);
}

/* ─────────────────────────────────────────────────────
   ROUTER (hash-based SPA)
───────────────────────────────────────────────────── */
const router = {
  routes: [],

  on(pattern, handler) {
    this.routes.push({ pattern, handler });
  },

  navigate(path) {
    window.location.hash = '#' + path;
  },

  current() {
    return window.location.hash.slice(1) || '/';
  },

  dispatch() {
    const path = router.current();
    for (const route of router.routes) {
      if (typeof route.pattern === 'string') {
        if (path === route.pattern) { route.handler({}); return; }
      } else if (route.pattern instanceof RegExp) {
        const m = path.match(route.pattern);
        if (m) { route.handler({ id: m[1] }); return; }
      }
    }
    // Default fallback
    router.navigate(App.isLoggedIn() ? '/home' : '/login');
  },

  init() {
    window.addEventListener('hashchange', () => router.dispatch());
    router.dispatch();
  },
};

/* ─────────────────────────────────────────────────────
   NAVBAR
───────────────────────────────────────────────────── */
function renderNavbar(activePage = '') {
  if (!App.isLoggedIn()) return '';

  const u = App.user;
  const initials = (u?.full_name || 'U').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  const roleBadge = App.isAdmin() ? `<span class="badge badge-admin">Admin</span>` : '';

  const links = [
    { href: '/home',     label: 'Home',        page: 'home'     },
    { href: '/centres',  label: 'Centres',     page: 'centres'  },
    { href: '/bookings', label: 'My Bookings', page: 'bookings' },
    ...(App.isAdmin() ? [{ href: '/admin', label: 'Admin', page: 'admin' }] : []),
  ];

  return `
    <nav class="navbar">
      <div class="navbar-inner">
        <div class="navbar-brand" onclick="router.navigate('/home')">
          <span class="brand-icon">🏥</span>
          <div>
            EVE Healthcare
            <span class="brand-sub">Diagnostics Platform</span>
          </div>
        </div>
        ${links.map(l => `
          <button class="nav-link ${activePage === l.page ? 'active' : ''}"
                  onclick="router.navigate('${l.href}')">
            ${l.label}
          </button>
        `).join('')}
        <div class="nav-divider"></div>
        ${roleBadge}
        <div class="nav-avatar" title="${esc(u?.full_name)}">${esc(initials)}</div>
        <button class="btn btn-ghost btn-sm" onclick="doLogout()">Logout</button>
      </div>
    </nav>`;
}

function doLogout() {
  App.clearAuth();
  toast.info('Signed out', 'See you again!');
  router.navigate('/login');
}

/* ─────────────────────────────────────────────────────
   PAGE: AUTH (Login / Signup)
───────────────────────────────────────────────────── */
function renderAuth(tab = 'login') {
  document.getElementById('app').innerHTML = `
    <div class="auth-page">
      <div class="auth-card">
        <div class="auth-logo">
          <span class="logo-icon">🏥</span>
          <h1>EVE Healthcare</h1>
          <p>Your health, our priority</p>
        </div>
        <div class="auth-tabs">
          <button class="auth-tab ${tab === 'login' ? 'active' : ''}" id="tab-login" onclick="renderAuth('login')">Login</button>
          <button class="auth-tab ${tab === 'signup' ? 'active' : ''}" id="tab-signup" onclick="renderAuth('signup')">Sign Up</button>
        </div>
        <div id="auth-form-container">
          ${tab === 'login' ? loginForm() : signupForm()}
        </div>
      </div>
    </div>`;
}

function loginForm() {
  return `
    <form class="auth-form" id="login-form" onsubmit="submitLogin(event)">
      <div class="form-group">
        <label class="form-label">Email <span class="required">*</span></label>
        <input type="email" class="form-input" id="login-email" placeholder="you@example.com" required autocomplete="email" />
      </div>
      <div class="form-group">
        <label class="form-label">Password <span class="required">*</span></label>
        <input type="password" class="form-input" id="login-pwd" placeholder="Your password" required autocomplete="current-password" />
      </div>
      <div id="auth-error"></div>
      <button type="submit" class="btn btn-primary btn-full btn-lg" id="login-btn">Login →</button>
      <p class="auth-footer">Don't have an account? <a onclick="renderAuth('signup')">Sign up</a></p>
    </form>`;
}

function signupForm() {
  return `
    <form class="auth-form" id="signup-form" onsubmit="submitSignup(event)">
      <div class="form-group">
        <label class="form-label">Full Name <span class="required">*</span></label>
        <input type="text" class="form-input" id="su-name" placeholder="Priya Sharma" required minlength="2" maxlength="255" autocomplete="name" />
      </div>
      <div class="form-group">
        <label class="form-label">Email <span class="required">*</span></label>
        <input type="email" class="form-input" id="su-email" placeholder="priya@example.com" required autocomplete="email" />
      </div>
      <div class="form-group">
        <label class="form-label">Password <span class="required">*</span></label>
        <input type="password" class="form-input" id="su-pwd" placeholder="Min 8 characters" required minlength="8" maxlength="72" autocomplete="new-password" />
      </div>
      <div class="form-group">
        <label class="form-label">Phone (optional)</label>
        <input type="tel" class="form-input" id="su-phone" placeholder="+91 98765 43210" maxlength="30" autocomplete="tel" />
      </div>
      <div id="auth-error"></div>
      <button type="submit" class="btn btn-primary btn-full btn-lg" id="signup-btn">Create Account →</button>
      <p class="auth-footer">Already have an account? <a onclick="renderAuth('login')">Login</a></p>
    </form>`;
}

async function submitLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('login-btn');
  const errEl = document.getElementById('auth-error');
  errEl.innerHTML = '';
  btn.disabled = true; btn.textContent = 'Logging in…';
  try {
    const data = await api.post('/api/v1/auth/login', {
      email: document.getElementById('login-email').value.trim(),
      password: document.getElementById('login-pwd').value,
    }, false);
    App.setAuth(data.access_token, data.user);
    toast.success('Welcome back!', data.user.full_name);
    router.navigate('/home');
  } catch(err) {
    errEl.innerHTML = `<p class="form-error">⚠️ ${esc(err.detail || 'Login failed.')}</p>`;
    btn.disabled = false; btn.textContent = 'Login →';
  }
}

async function submitSignup(e) {
  e.preventDefault();
  const btn = document.getElementById('signup-btn');
  const errEl = document.getElementById('auth-error');
  errEl.innerHTML = '';
  btn.disabled = true; btn.textContent = 'Creating account…';
  const phone = document.getElementById('su-phone').value.trim();
  try {
    await api.post('/api/v1/auth/signup', {
      email: document.getElementById('su-email').value.trim(),
      password: document.getElementById('su-pwd').value,
      full_name: document.getElementById('su-name').value.trim(),
      ...(phone ? { phone } : {}),
    }, false);
    toast.success('Account created!', 'Please log in.');
    renderAuth('login');
  } catch(err) {
    errEl.innerHTML = `<p class="form-error">⚠️ ${esc(err.detail || 'Signup failed.')}</p>`;
    btn.disabled = false; btn.textContent = 'Create Account →';
  }
}

/* ─────────────────────────────────────────────────────
   PAGE: HOME / DASHBOARD
───────────────────────────────────────────────────── */
async function renderHome() {
  document.getElementById('app').innerHTML = renderNavbar('home') + `
    <div class="page-wrapper">
      <div class="page-header">
        <h2>Welcome back, ${esc(App.user?.full_name?.split(' ')[0])}</h2>
        <p>Manage your health appointments all in one place</p>
      </div>
      <div class="stats-row" id="stats-row">${loading()}</div>
      <div class="quick-actions">
        <button class="quick-action-btn" onclick="router.navigate('/centres')">
          <span class="quick-action-icon">🏥</span>
          <span class="quick-action-text"><strong>Browse Centres</strong><small>Find nearby labs</small></span>
        </button>
        <button class="quick-action-btn" onclick="router.navigate('/bookings')">
          <span class="quick-action-icon">📋</span>
          <span class="quick-action-text"><strong>My Bookings</strong><small>View appointments</small></span>
        </button>
        ${App.isAdmin() ? `
        <button class="quick-action-btn" onclick="router.navigate('/admin')">
          <span class="quick-action-icon">⚙️</span>
          <span class="quick-action-text"><strong>Admin Panel</strong><small>Manage centres & tests</small></span>
        </button>` : ''}
      </div>
      <div class="section-header">
        <span class="section-title">Recent Bookings</span>
        <button class="btn btn-ghost btn-sm" onclick="router.navigate('/bookings')">View all →</button>
      </div>
      <div id="recent-bookings">${loading()}</div>
    </div>`;

  try {
    const scope = App.isAdmin() ? '' : '';
    const data = await api.get('/api/v1/bookings?page=1&page_size=50');
    const items = data.items || [];
    const counts = { total: items.length, CONFIRMED: 0, PENDING: 0, FAILED: 0, CANCELLED: 0 };
    items.forEach(b => { if (b.status in counts) counts[b.status]++; });

    document.getElementById('stats-row').innerHTML = `
      <div class="stat-card stat-total"><div class="stat-value">${counts.total}</div><div class="stat-label">Total Bookings</div></div>
      <div class="stat-card stat-confirmed"><div class="stat-value">${counts.CONFIRMED}</div><div class="stat-label">Confirmed</div></div>
      <div class="stat-card stat-pending"><div class="stat-value">${counts.PENDING}</div><div class="stat-label">Pending</div></div>
      <div class="stat-card stat-cancelled"><div class="stat-value">${counts.CANCELLED}</div><div class="stat-label">Cancelled</div></div>`;

    const recent = items.slice(0, 5);
    document.getElementById('recent-bookings').innerHTML = recent.length
      ? `<div style="display:flex;flex-direction:column;gap:12px">${recent.map(bookingCard).join('')}</div>`
      : empty('📭', 'No bookings yet', 'Book your first diagnostic test from Browse Centres');
  } catch(e) {
    document.getElementById('stats-row').innerHTML = `<p class="form-error">Failed to load stats.</p>`;
    document.getElementById('recent-bookings').innerHTML = empty('⚠️', 'Could not load bookings');
  }
}

/* ─────────────────────────────────────────────────────
   PAGE: CENTRES LIST
───────────────────────────────────────────────────── */
async function renderCentres() {
  document.getElementById('app').innerHTML = renderNavbar('centres') + `
    <div class="page-wrapper">
      <div class="page-header">
        <h2>Diagnostic Centres</h2>
        <p>Find a centre near you and book a test</p>
      </div>
      <div class="filter-bar">
        <input type="text" class="form-input" id="f-search" placeholder="🔍 Search by name…" oninput="debouncedLoadCentres()" />
        <input type="text" class="form-input" id="f-city"   placeholder="📍 Filter by city…"  oninput="debouncedLoadCentres()" />
      </div>
      <div id="centres-grid">${loading()}</div>
    </div>`;
  loadCentres();
}

let centreDebounce;
function debouncedLoadCentres() {
  clearTimeout(centreDebounce);
  centreDebounce = setTimeout(loadCentres, 300);
}

async function loadCentres() {
  const grid = document.getElementById('centres-grid');
  if (!grid) return;
  grid.innerHTML = loading();
  const search = document.getElementById('f-search')?.value.trim() || '';
  const city   = document.getElementById('f-city')?.value.trim() || '';
  const params = new URLSearchParams({ page: 1, page_size: 50 });
  if (search) params.set('search', search);
  if (city)   params.set('city', city);
  try {
    const data = await api.get(`/api/v1/centres?${params}`, false);
    const items = data.items || [];
    if (!items.length) { grid.innerHTML = empty('🏥', 'No centres found', 'Try a different search or city filter'); return; }
    grid.innerHTML = `<div class="grid-2">${items.map(centreCard).join('')}</div>`;
  } catch(e) {
    grid.innerHTML = empty('⚠️', 'Could not load centres', e.detail || '');
  }
}

function centreCard(c) {
  return `
    <div class="centre-card" onclick="router.navigate('/centres/${c.id}')">
      <div class="centre-card-name">${esc(c.name)}</div>
      <div class="centre-card-meta">
        <span>📍 ${esc(c.city)}${c.state ? ', ' + esc(c.state) : ''} — ${esc(c.pincode)}</span>
        ${c.contact_phone ? `<span>📞 ${esc(c.contact_phone)}</span>` : ''}
      </div>
      <div class="centre-card-footer">
        <span class="badge ${c.is_active ? 'badge-active' : 'badge-cancelled'}">${c.is_active ? 'Active' : 'Inactive'}</span>
        <button class="btn btn-primary btn-sm" onclick="event.stopPropagation();router.navigate('/centres/${c.id}')">View Tests →</button>
      </div>
    </div>`;
}

/* ─────────────────────────────────────────────────────
   PAGE: CENTRE DETAIL
───────────────────────────────────────────────────── */
async function renderCentreDetail({ id }) {
  document.getElementById('app').innerHTML = renderNavbar('centres') + `
    <div class="page-wrapper">
      <button class="back-btn" onclick="router.navigate('/centres')">← Back to Centres</button>
      <div id="centre-detail">${loading()}</div>
    </div>`;

  try {
    const c = await api.get(`/api/v1/centres/${id}`, false);
    const tests = c.centre_tests || [];
    const available = tests.filter(t => t.is_available);

    document.getElementById('centre-detail').innerHTML = `
      <div class="centre-hero">
        <h2>${esc(c.name)}</h2>
        <div class="meta">
          <span>📍 ${esc(c.address)}, ${esc(c.city)}${c.state ? ', ' + esc(c.state) : ''} — ${esc(c.pincode)}</span>
          ${c.contact_phone ? `<span>📞 ${esc(c.contact_phone)}</span>` : ''}
        </div>
      </div>
      <div class="section-header">
        <span class="section-title">Available Tests (${available.length})</span>
      </div>
      ${available.length
        ? `<div style="display:flex;flex-direction:column;gap:12px">${available.map(ct => testRow(ct)).join('')}</div>`
        : empty('🔬', 'No tests available', 'This centre has no active test offerings.')}`;
  } catch(e) {
    document.getElementById('centre-detail').innerHTML = empty('⚠️', 'Could not load centre', e.detail || '');
  }
}

function testRow(ct) {
  const t = ct.test;
  return `
    <div class="test-row">
      <div class="test-row-info">
        <h4>${esc(t.name)}</h4>
        <div style="display:flex;gap:6px;margin:6px 0;flex-wrap:wrap">
          <span class="badge badge-category">${esc(t.category)}</span>
          <span class="badge ${t.code ? 'badge-admin' : ''}">${esc(t.code)}</span>
        </div>
        ${t.description ? `<p class="test-desc">${esc(t.description)}</p>` : ''}
        ${t.preparation_instructions ? `<p class="test-prep">📋 ${esc(t.preparation_instructions)}</p>` : ''}
      </div>
      <div class="test-row-price">
        <div class="price-tag">${fmtINR(ct.price_paise)}<span>per test</span></div>
        ${App.isLoggedIn()
          ? `<button class="btn btn-primary btn-sm" onclick="openBookModal('${ct.id}','${esc(t.name)}',${ct.price_paise})">Book Now</button>`
          : `<button class="btn btn-outline btn-sm" onclick="router.navigate('/login')">Login to Book</button>`}
      </div>
    </div>`;
}

/* ─────────────────────────────────────────────────────
   BOOKING MODAL
───────────────────────────────────────────────────── */
function openBookModal(centreTestId, testName, pricePaise) {
  modal.open(`
    <div class="modal modal-wrapper">
      <h3 class="modal-title">Book Appointment</h3>
      <p class="modal-subtitle">You are booking: <strong>${esc(testName)}</strong></p>
      <div class="modal-form" id="book-modal-form">
        <div class="price-info-box">
          <span class="price-label">Total Payable</span>
          <span class="price-value">${fmtINR(pricePaise)}</span>
        </div>
        <div class="form-group">
          <label class="form-label">Appointment Date & Time <span class="required">*</span></label>
          <input type="datetime-local" class="form-input" id="bk-datetime" min="${minFutureDate()}" required />
          <span class="form-hint">Must be at least 30 minutes from now</span>
        </div>
        <div class="form-group">
          <label class="form-label">Notes (optional)</label>
          <textarea class="form-textarea" id="bk-notes" maxlength="1000" placeholder="Any special instructions or medical notes…"></textarea>
        </div>
        <div id="book-error"></div>
        <div class="modal-actions">
          <button class="btn btn-ghost" onclick="modal.close()">Cancel</button>
          <button class="btn btn-primary" id="bk-submit-btn" onclick="submitBooking('${centreTestId}', ${pricePaise})">Confirm Booking</button>
        </div>
      </div>
    </div>`);
}

async function submitBooking(centreTestId, pricePaise) {
  const btn = document.getElementById('bk-submit-btn');
  const errEl = document.getElementById('book-error');
  const dt = document.getElementById('bk-datetime').value;
  const notes = document.getElementById('bk-notes').value.trim();
  if (!dt) { errEl.innerHTML = `<p class="form-error">Please select an appointment date and time.</p>`; return; }

  btn.disabled = true; btn.textContent = 'Booking…';
  errEl.innerHTML = '';
  try {
    const booking = await api.post('/api/v1/bookings', {
      centre_test_id: centreTestId,
      appointment_datetime: new Date(dt).toISOString(),
      ...(notes ? { notes } : {}),
    });
    modal.close();
    toast.success('Booking confirmed!', `Appointment on ${fmtDate(dt)}`);
    openPaymentModal(booking.id, booking.test_name || 'Diagnostic Test', pricePaise, true);
  } catch(e) {
    errEl.innerHTML = `<p class="form-error">⚠️ ${esc(e.detail || 'Booking failed.')}</p>`;
    btn.disabled = false; btn.textContent = 'Confirm Booking';
  }
}

/* ─────────────────────────────────────────────────────
   PAYMENT MODAL
───────────────────────────────────────────────────── */
function openPaymentModal(bookingId, testName, pricePaise, afterBooking = false) {
  modal.open(`
    <div class="modal modal-wrapper">
      <h3 class="modal-title">Simulate Payment</h3>
      <p class="modal-subtitle">Complete payment for: <strong>${esc(testName)}</strong></p>
      <div class="modal-form">
        <div class="price-info-box">
          <span class="price-label">Amount Due</span>
          <span class="price-value">${fmtINR(pricePaise)}</span>
        </div>
        <div class="form-group">
          <label class="form-label">Payment Method</label>
          <select class="form-select" id="pay-method">
            <option value="SIMULATED_CARD">💳 Credit / Debit Card</option>
            <option value="UPI">📱 UPI</option>
            <option value="NET_BANKING">🏦 Net Banking</option>
          </select>
        </div>
        <div class="toggle-row">
          <div class="toggle-label">
            Simulate Failure
            <small>Toggle ON to test failed payment handling</small>
          </div>
          <label class="toggle">
            <input type="checkbox" id="pay-fail" />
            <span class="toggle-track"></span>
          </label>
        </div>
        <div class="info-box info-box-info">
          <span class="info-box-icon">ℹ️</span>
          <span>This is a simulated payment — no real transaction occurs.</span>
        </div>
        <div id="pay-error"></div>
        <div class="modal-actions">
          <button class="btn btn-ghost" onclick="modal.close();${afterBooking ? "router.navigate('/bookings')" : ''}">
            ${afterBooking ? 'Pay Later' : 'Cancel'}
          </button>
          <button class="btn btn-primary" id="pay-submit-btn" onclick="submitPayment('${bookingId}')">Pay Now</button>
        </div>
      </div>
    </div>`);
}

async function submitPayment(bookingId) {
  const btn = document.getElementById('pay-submit-btn');
  const errEl = document.getElementById('pay-error');
  const method = document.getElementById('pay-method').value;
  const fail   = document.getElementById('pay-fail').checked;

  btn.disabled = true; btn.textContent = 'Processing…';
  errEl.innerHTML = '';
  try {
    const result = await api.post('/api/v1/payments', {
      booking_id: bookingId,
      payment_method: method,
      simulate_failure: fail,
    });
    modal.close();
    if (result.booking_status === 'CONFIRMED') {
      toast.success('Payment successful! ✅', `Booking confirmed — ${fmtINR(result.amount_paise)}`);
    } else {
      toast.error('Payment failed', 'The payment was declined. Your booking remains in PENDING state.');
    }
    if (router.current() === '/bookings') renderBookings();
    else router.navigate('/bookings');
  } catch(e) {
    errEl.innerHTML = `<p class="form-error">⚠️ ${esc(e.detail || 'Payment failed.')}</p>`;
    btn.disabled = false; btn.textContent = 'Pay Now';
  }
}

/* ─────────────────────────────────────────────────────
   PAGE: MY BOOKINGS
───────────────────────────────────────────────────── */
async function renderBookings() {
  document.getElementById('app').innerHTML = renderNavbar('bookings') + `
    <div class="page-wrapper">
      <div class="page-header">
        <h2>${App.isAdmin() ? 'All Bookings' : 'My Bookings'}</h2>
        <p>${App.isAdmin() ? 'Viewing all patient bookings' : 'Track your diagnostic appointments'}</p>
      </div>
      <div class="filter-bar">
        <select class="form-select" id="b-status" style="max-width:200px" onchange="loadBookings()">
          <option value="">All Statuses</option>
          <option value="PENDING">Pending</option>
          <option value="CONFIRMED">Confirmed</option>
          <option value="CANCELLED">Cancelled</option>
          <option value="FAILED">Failed</option>
        </select>
      </div>
      <div id="bookings-list">${loading()}</div>
    </div>`;
  loadBookings();
}

async function loadBookings() {
  const listEl = document.getElementById('bookings-list');
  if (!listEl) return;
  listEl.innerHTML = loading();
  const status = document.getElementById('b-status')?.value || '';
  const params = new URLSearchParams({ page: 1, page_size: 50 });
  if (status) params.set('status', status);
  try {
    const data = await api.get(`/api/v1/bookings?${params}`);
    const items = data.items || [];
    listEl.innerHTML = items.length
      ? `<div style="display:flex;flex-direction:column;gap:12px">${items.map(bookingCard).join('')}</div>`
      : empty('📭', 'No bookings found', 'Try a different status filter or book a test.');
  } catch(e) { listEl.innerHTML = empty('⚠️', 'Could not load bookings', e.detail || ''); }
}

function bookingCard(b) {
  const canPay    = b.status === 'PENDING';
  const canCancel = b.status === 'PENDING' || b.status === 'CONFIRMED';
  return `
    <div class="booking-card">
      <div class="booking-card-left">
        <div class="booking-card-title">${esc(b.test_name || 'Diagnostic Test')}</div>
        <div class="booking-card-centre">🏥 ${esc(b.centre_name || 'Diagnostic Centre')}</div>
        <div class="booking-meta-row">
          ${statusBadge(b.status)}
          <span class="booking-meta-item">📅 ${fmtDate(b.appointment_datetime)}</span>
          <span class="booking-meta-item">🕐 Booked ${fmtDate(b.created_at)}</span>
        </div>
        ${b.notes ? `<p style="margin-top:8px;font-size:0.8rem;color:var(--text-muted)">📝 ${esc(b.notes)}</p>` : ''}
      </div>
      <div class="booking-card-right">
        <div class="booking-amount">${fmtINR(b.amount_paise)}</div>
        ${canPay ? `<button class="btn btn-primary btn-sm" onclick="openPaymentModal('${b.id}','${esc(b.test_name || 'Test')}',${b.amount_paise})">Pay Now</button>` : ''}
        ${canCancel ? `<button class="btn btn-danger-outline btn-sm" onclick="cancelBookingAction('${b.id}')">Cancel</button>` : ''}
      </div>
    </div>`;
}

async function cancelBookingAction(bookingId) {
  if (!confirm('Are you sure you want to cancel this booking?')) return;
  try {
    await api.post(`/api/v1/bookings/${bookingId}/cancel`);
    toast.success('Booking cancelled', 'Your appointment has been cancelled.');
    loadBookings();
  } catch(e) { toast.apiErr(e, 'Could not cancel booking.'); }
}

/* ─────────────────────────────────────────────────────
   PAGE: ADMIN PANEL
───────────────────────────────────────────────────── */
let adminTab = 'centres';

async function renderAdmin() {
  if (!App.isAdmin()) { router.navigate('/home'); return; }
  document.getElementById('app').innerHTML = renderNavbar('admin') + `
    <div class="page-wrapper">
      <div class="page-header">
        <h2>Admin Panel</h2>
        <p>Manage diagnostic centres and tests</p>
      </div>
      <div class="tab-bar">
        <button class="tab-btn ${adminTab === 'centres' ? 'active' : ''}" onclick="switchAdminTab('centres')">Centres</button>
        <button class="tab-btn ${adminTab === 'tests'   ? 'active' : ''}" onclick="switchAdminTab('tests')">Tests</button>
        <button class="tab-btn ${adminTab === 'bookings'? 'active' : ''}" onclick="switchAdminTab('bookings')">All Bookings</button>
      </div>
      <div id="admin-content">${loading()}</div>
    </div>`;
  loadAdminTab();
}

function switchAdminTab(tab) {
  adminTab = tab;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('admin-content').innerHTML = loading();
  loadAdminTab();
}

async function loadAdminTab() {
  const el = document.getElementById('admin-content');
  if (!el) return;
  if (adminTab === 'centres')  await adminCentresTab(el);
  if (adminTab === 'tests')    await adminTestsTab(el);
  if (adminTab === 'bookings') await adminBookingsTab(el);
}

/* Admin → Centres tab */
async function adminCentresTab(el) {
  try {
    const data = await api.get('/api/v1/centres?page=1&page_size=100');
    el.innerHTML = `
      <div class="section-header">
        <span class="section-title">Diagnostic Centres (${data.total})</span>
        <button class="btn btn-primary btn-sm" onclick="openCreateCentreModal()">+ Add Centre</button>
      </div>
      ${data.items.length
        ? `<div style="overflow-x:auto"><table class="admin-table">
            <thead><tr>
              <th>Name</th><th>City</th><th>State</th><th>Pincode</th><th>Phone</th><th>Status</th><th>Actions</th>
            </tr></thead>
            <tbody>${data.items.map(c => `
              <tr>
                <td><strong>${esc(c.name)}</strong></td>
                <td>${esc(c.city)}</td>
                <td>${esc(c.state || '—')}</td>
                <td>${esc(c.pincode)}</td>
                <td>${esc(c.contact_phone || '—')}</td>
                <td><span class="badge ${c.is_active ? 'badge-active' : 'badge-cancelled'}">${c.is_active ? 'Active' : 'Inactive'}</span></td>
                <td><button class="btn btn-ghost btn-sm" onclick="router.navigate('/centres/${c.id}')">View →</button></td>
              </tr>`).join('')}
            </tbody></table></div>`
        : empty('🏥', 'No centres yet', 'Add your first diagnostic centre')}`;
  } catch(e) { el.innerHTML = empty('⚠️', 'Failed to load centres'); }
}

function openCreateCentreModal() {
  modal.open(`
    <div class="modal modal-wrapper">
      <h3 class="modal-title">Add Diagnostic Centre</h3>
      <p class="modal-subtitle">Fill in the centre details below</p>
      <div class="modal-form">
        <div class="form-grid">
          <div class="form-group">
            <label class="form-label">Centre Name <span class="required">*</span></label>
            <input type="text" class="form-input" id="cn-name" placeholder="Apollo Diagnostics" required />
          </div>
          <div class="form-group">
            <label class="form-label">Phone</label>
            <input type="tel" class="form-input" id="cn-phone" placeholder="+91 80 1234 5678" />
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">Address <span class="required">*</span></label>
          <input type="text" class="form-input" id="cn-addr" placeholder="100 Feet Road, Indiranagar" required />
        </div>
        <div class="form-grid">
          <div class="form-group">
            <label class="form-label">City <span class="required">*</span></label>
            <input type="text" class="form-input" id="cn-city" placeholder="Bengaluru" required />
          </div>
          <div class="form-group">
            <label class="form-label">State</label>
            <input type="text" class="form-input" id="cn-state" placeholder="Karnataka" />
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">Pincode <span class="required">*</span></label>
          <input type="text" class="form-input" id="cn-pin" placeholder="560038" required minlength="4" maxlength="10" />
        </div>
        <div id="cn-error"></div>
        <div class="modal-actions">
          <button class="btn btn-ghost" onclick="modal.close()">Cancel</button>
          <button class="btn btn-primary" id="cn-submit" onclick="submitCreateCentre()">Create Centre</button>
        </div>
      </div>
    </div>`);
}

async function submitCreateCentre() {
  const btn = document.getElementById('cn-submit');
  const errEl = document.getElementById('cn-error');
  errEl.innerHTML = '';
  btn.disabled = true; btn.textContent = 'Creating…';
  const phone = document.getElementById('cn-phone').value.trim();
  const state = document.getElementById('cn-state').value.trim();
  try {
    await api.post('/api/v1/centres', {
      name: document.getElementById('cn-name').value.trim(),
      address: document.getElementById('cn-addr').value.trim(),
      city: document.getElementById('cn-city').value.trim(),
      pincode: document.getElementById('cn-pin').value.trim(),
      ...(state ? { state } : {}),
      ...(phone ? { contact_phone: phone } : {}),
    });
    modal.close();
    toast.success('Centre created!', 'The new diagnostic centre is now active.');
    loadAdminTab();
  } catch(e) {
    errEl.innerHTML = `<p class="form-error">⚠️ ${esc(e.detail || 'Failed.')}</p>`;
    btn.disabled = false; btn.textContent = 'Create Centre';
  }
}

/* Admin → Tests tab */
async function adminTestsTab(el) {
  try {
    const data = await api.get('/api/v1/tests?page=1&page_size=100');
    el.innerHTML = `
      <div class="section-header">
        <span class="section-title">Diagnostic Tests (${data.total})</span>
        <button class="btn btn-primary btn-sm" onclick="openCreateTestModal()">+ Add Test</button>
      </div>
      ${data.items.length
        ? `<div style="overflow-x:auto"><table class="admin-table">
            <thead><tr><th>Name</th><th>Code</th><th>Category</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>${data.items.map(t => `
              <tr>
                <td><strong>${esc(t.name)}</strong></td>
                <td><code>${esc(t.code)}</code></td>
                <td><span class="badge badge-category">${esc(t.category)}</span></td>
                <td><span class="badge ${t.is_active ? 'badge-active' : 'badge-cancelled'}">${t.is_active ? 'Active' : 'Inactive'}</span></td>
                <td><button class="btn btn-ghost btn-sm" onclick="openLinkTestModal('${t.id}','${esc(t.name)}')">Link to Centre</button></td>
              </tr>`).join('')}
            </tbody></table></div>`
        : empty('🔬', 'No tests yet', 'Add your first diagnostic test')}`;
  } catch(e) { el.innerHTML = empty('⚠️', 'Failed to load tests'); }
}

function openCreateTestModal() {
  modal.open(`
    <div class="modal modal-wrapper">
      <h3 class="modal-title">Add Diagnostic Test</h3>
      <p class="modal-subtitle">Create a new test in the catalogue</p>
      <div class="modal-form">
        <div class="form-grid">
          <div class="form-group">
            <label class="form-label">Test Name <span class="required">*</span></label>
            <input type="text" class="form-input" id="nt-name" placeholder="Complete Blood Count" required />
          </div>
          <div class="form-group">
            <label class="form-label">Code <span class="required">*</span></label>
            <input type="text" class="form-input" id="nt-code" placeholder="CBC" required maxlength="50" />
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">Category <span class="required">*</span></label>
          <input type="text" class="form-input" id="nt-cat" placeholder="Pathology" required />
        </div>
        <div class="form-group">
          <label class="form-label">Description</label>
          <textarea class="form-textarea" id="nt-desc" placeholder="Brief description of the test…"></textarea>
        </div>
        <div class="form-group">
          <label class="form-label">Preparation Instructions</label>
          <textarea class="form-textarea" id="nt-prep" placeholder="e.g. 10–12 hours fasting required"></textarea>
        </div>
        <div id="nt-error"></div>
        <div class="modal-actions">
          <button class="btn btn-ghost" onclick="modal.close()">Cancel</button>
          <button class="btn btn-primary" id="nt-submit" onclick="submitCreateTest()">Create Test</button>
        </div>
      </div>
    </div>`);
}

async function submitCreateTest() {
  const btn = document.getElementById('nt-submit');
  const errEl = document.getElementById('nt-error');
  errEl.innerHTML = '';
  btn.disabled = true; btn.textContent = 'Creating…';
  const desc = document.getElementById('nt-desc').value.trim();
  const prep = document.getElementById('nt-prep').value.trim();
  try {
    await api.post('/api/v1/tests', {
      name: document.getElementById('nt-name').value.trim(),
      code: document.getElementById('nt-code').value.trim().toUpperCase(),
      category: document.getElementById('nt-cat').value.trim(),
      ...(desc ? { description: desc } : {}),
      ...(prep ? { preparation_instructions: prep } : {}),
    });
    modal.close();
    toast.success('Test created!', 'New test added to the catalogue.');
    loadAdminTab();
  } catch(e) {
    errEl.innerHTML = `<p class="form-error">⚠️ ${esc(e.detail || 'Failed.')}</p>`;
    btn.disabled = false; btn.textContent = 'Create Test';
  }
}

async function openLinkTestModal(testId, testName) {
  // Load centres first
  let centres = [];
  try { const d = await api.get('/api/v1/centres?page=1&page_size=100'); centres = d.items || []; } catch(e) {}
  modal.open(`
    <div class="modal modal-wrapper">
      <h3 class="modal-title">Link Test to Centre</h3>
      <p class="modal-subtitle"><strong>${esc(testName)}</strong> — set pricing at a specific centre</p>
      <div class="modal-form">
        <div class="form-group">
          <label class="form-label">Select Centre <span class="required">*</span></label>
          <select class="form-select" id="lk-centre" required>
            <option value="">— Choose a centre —</option>
            ${centres.map(c => `<option value="${c.id}">${esc(c.name)} (${esc(c.city)})</option>`).join('')}
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Price (₹) <span class="required">*</span></label>
          <input type="number" class="form-input" id="lk-price" placeholder="500" min="1" step="0.01" required />
          <span class="form-hint">Enter price in rupees (e.g. 500 for ₹500.00)</span>
        </div>
        <div id="lk-error"></div>
        <div class="modal-actions">
          <button class="btn btn-ghost" onclick="modal.close()">Cancel</button>
          <button class="btn btn-primary" id="lk-submit" onclick="submitLinkTest('${testId}')">Link Test</button>
        </div>
      </div>
    </div>`);
}

async function submitLinkTest(testId) {
  const btn = document.getElementById('lk-submit');
  const errEl = document.getElementById('lk-error');
  errEl.innerHTML = '';
  const centreId = document.getElementById('lk-centre').value;
  const priceRs  = parseFloat(document.getElementById('lk-price').value);
  if (!centreId) { errEl.innerHTML = `<p class="form-error">Please select a centre.</p>`; return; }
  if (!priceRs || priceRs <= 0) { errEl.innerHTML = `<p class="form-error">Please enter a valid price.</p>`; return; }

  btn.disabled = true; btn.textContent = 'Linking…';
  try {
    await api.post(`/api/v1/centres/${centreId}/tests`, {
      test_id: testId,
      price_paise: Math.round(priceRs * 100),
      is_available: true,
    });
    modal.close();
    toast.success('Test linked!', 'Test is now available at the selected centre.');
    loadAdminTab();
  } catch(e) {
    errEl.innerHTML = `<p class="form-error">⚠️ ${esc(e.detail || 'Failed.')}</p>`;
    btn.disabled = false; btn.textContent = 'Link Test';
  }
}

/* Admin → All Bookings tab */
async function adminBookingsTab(el) {
  try {
    const data = await api.get('/api/v1/bookings?page=1&page_size=100');
    el.innerHTML = `
      <div class="section-header">
        <span class="section-title">All Bookings (${data.total})</span>
      </div>
      ${data.items.length
        ? `<div style="display:flex;flex-direction:column;gap:10px">${data.items.map(bookingCard).join('')}</div>`
        : empty('📭', 'No bookings yet')}`;
  } catch(e) { el.innerHTML = empty('⚠️', 'Failed to load bookings'); }
}

/* ─────────────────────────────────────────────────────
   GUARDS & ROUTER SETUP
───────────────────────────────────────────────────── */
function requireAuth(fn) {
  return (params) => {
    if (!App.isLoggedIn()) { router.navigate('/login'); return; }
    fn(params);
  };
}

function requireGuest(fn) {
  return (params) => {
    if (App.isLoggedIn()) { router.navigate('/home'); return; }
    fn(params);
  };
}

/* ─────────────────────────────────────────────────────
   BOOTSTRAP
───────────────────────────────────────────────────── */
router.on('/login',            requireGuest(() => renderAuth('login')));
router.on('/signup',           requireGuest(() => renderAuth('signup')));
router.on('/home',             requireAuth(renderHome));
router.on('/centres',          (p) => renderCentres(p));
router.on(/^\/centres\/(.+)$/, (p) => renderCentreDetail(p));
router.on('/bookings',         requireAuth(renderBookings));
router.on('/admin',            requireAuth(renderAdmin));
router.on('/',                 (p) => App.isLoggedIn() ? router.navigate('/home') : router.navigate('/login'));

router.init();
