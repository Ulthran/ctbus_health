const _rawDomain = window.CTBUS_COGNITO_DOMAIN || '';
const COGNITO_DOMAIN = _rawDomain === 'CTBUS_COGNITO_DOMAIN_PLACEHOLDER' || !_rawDomain ? null : _rawDomain;
const CLIENT_ID = (window.CTBUS_CLIENT_ID || '') === 'CTBUS_CLIENT_ID_PLACEHOLDER' ? null : (window.CTBUS_CLIENT_ID || null);
const REDIRECT_URI = window.location.origin + '/callback';

const KEY_ID_TOKEN = 'ctbus_id_token';
const KEY_REFRESH  = 'ctbus_refresh_token';
const KEY_EXPIRY   = 'ctbus_token_expiry';

// ── PKCE helpers ──────────────────────────────────────────────────────────────

async function _sha256(plain) {
  return crypto.subtle.digest('SHA-256', new TextEncoder().encode(plain));
}

function _b64url(buf) {
  return btoa(String.fromCharCode(...new Uint8Array(buf)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}

function _random(n) {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
  const arr = new Uint8Array(n);
  crypto.getRandomValues(arr);
  return Array.from(arr, b => chars[b % chars.length]).join('');
}

// ── Token storage ─────────────────────────────────────────────────────────────

function _storedToken() {
  const t = localStorage.getItem(KEY_ID_TOKEN);
  const exp = parseInt(localStorage.getItem(KEY_EXPIRY) || '0');
  // treat as expired 5 min early to avoid edge races
  if (!t || Date.now() >= exp - 5 * 60 * 1000) return null;
  return t;
}

function _storeTokens(idToken, refreshToken, expiresIn) {
  localStorage.setItem(KEY_ID_TOKEN, idToken);
  localStorage.setItem(KEY_EXPIRY, String(Date.now() + expiresIn * 1000));
  if (refreshToken) localStorage.setItem(KEY_REFRESH, refreshToken);
}

async function _refresh() {
  const rt = localStorage.getItem(KEY_REFRESH);
  if (!rt || !COGNITO_DOMAIN) return false;
  try {
    const resp = await fetch(`https://${COGNITO_DOMAIN}/oauth2/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ grant_type: 'refresh_token', client_id: CLIENT_ID, refresh_token: rt }),
    });
    if (!resp.ok) return false;
    const d = await resp.json();
    _storeTokens(d.id_token, d.refresh_token, d.expires_in);
    return true;
  } catch { return false; }
}

// ── Public API ────────────────────────────────────────────────────────────────

export async function getIdToken() {
  const t = _storedToken();
  if (t) return t;
  if (await _refresh()) return localStorage.getItem(KEY_ID_TOKEN);
  return null;
}

export function redirectToLogin() {
  if (!COGNITO_DOMAIN) return;
  (async () => {
    const verifier = _random(64);
    const challenge = _b64url(await _sha256(verifier));
    sessionStorage.setItem('pkce_verifier', verifier);
    const params = new URLSearchParams({
      response_type: 'code',
      client_id: CLIENT_ID,
      redirect_uri: REDIRECT_URI,
      code_challenge: challenge,
      code_challenge_method: 'S256',
      scope: 'email openid profile',
      identity_provider: 'Google',
    });
    window.location.href = `https://${COGNITO_DOMAIN}/oauth2/authorize?${params}`;
  })();
}

async function _handleCallback() {
  const code = new URLSearchParams(window.location.search).get('code');
  const verifier = sessionStorage.getItem('pkce_verifier');
  sessionStorage.removeItem('pkce_verifier');

  if (!code || !verifier) { window.location.replace('/'); return; }

  const resp = await fetch(`https://${COGNITO_DOMAIN}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: CLIENT_ID,
      redirect_uri: REDIRECT_URI,
      code,
      code_verifier: verifier,
    }),
  });

  if (!resp.ok) {
    localStorage.clear();
    redirectToLogin();
    return;
  }

  const d = await resp.json();
  _storeTokens(d.id_token, d.refresh_token, d.expires_in);
  window.location.replace('/');
}

export async function ensureAuth() {
  if (!COGNITO_DOMAIN) return true; // local dev — always authenticated

  if (window.location.pathname === '/callback') {
    await _handleCallback();
    await new Promise(() => {}); // block — page is redirecting
    return false;
  }

  const token = await getIdToken();
  return !!token;
}

export function signOut() {
  localStorage.removeItem(KEY_ID_TOKEN);
  localStorage.removeItem(KEY_REFRESH);
  localStorage.removeItem(KEY_EXPIRY);
  if (COGNITO_DOMAIN && CLIENT_ID) {
    window.location.href = `https://${COGNITO_DOMAIN}/logout?client_id=${CLIENT_ID}&logout_uri=${encodeURIComponent(window.location.origin)}`;
  } else {
    window.location.href = '/';
  }
}
