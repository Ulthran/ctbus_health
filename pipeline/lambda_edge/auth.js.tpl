'use strict';
const https = require('https');
const crypto = require('crypto');

const ISSUER = '${issuer}';
const JWKS_URL = '${jwks_url}';
const CLIENT_ID = '${client_id}';

let cachedJwks = null;

function fetchJwks() {
  return new Promise(function(resolve, reject) {
    https.get(JWKS_URL, function(res) {
      let data = '';
      res.on('data', function(chunk) { data += chunk; });
      res.on('end', function() {
        try { resolve(JSON.parse(data)); } catch (e) { reject(e); }
      });
    }).on('error', reject);
  });
}

function b64urlToBuffer(s) {
  return Buffer.from(s.replace(/-/g, '+').replace(/_/g, '/'), 'base64');
}

async function verifyToken(token) {
  const parts = token.split('.');
  if (parts.length !== 3) throw new Error('malformed');

  const header = JSON.parse(b64urlToBuffer(parts[0]));
  const payload = JSON.parse(b64urlToBuffer(parts[1]));

  const now = Math.floor(Date.now() / 1000);
  if (payload.exp < now) throw new Error('expired');
  if (payload.iss !== ISSUER) throw new Error('bad issuer');
  // id_token: aud === client_id; access_token: client_id claim instead of aud
  if (payload.aud !== CLIENT_ID && payload.client_id !== CLIENT_ID) throw new Error('bad audience');

  if (!cachedJwks) cachedJwks = await fetchJwks();
  const jwk = cachedJwks.keys.find(function(k) { return k.kid === header.kid; });
  if (!jwk) {
    cachedJwks = null;
    throw new Error('unknown kid');
  }

  const publicKey = crypto.createPublicKey({ key: jwk, format: 'jwk' });
  const verifier = crypto.createVerify('RSA-SHA256');
  verifier.update(parts[0] + '.' + parts[1]);
  if (!verifier.verify(publicKey, b64urlToBuffer(parts[2]))) throw new Error('bad sig');
}

exports.handler = async function(event) {
  const request = event.Records[0].cf.request;
  const authHeaders = request.headers.authorization;

  if (!authHeaders || !authHeaders[0] || !authHeaders[0].value.startsWith('Bearer ')) {
    return {
      status: '401',
      statusDescription: 'Unauthorized',
      headers: { 'www-authenticate': [{ key: 'WWW-Authenticate', value: 'Bearer' }] },
      body: ''
    };
  }

  try {
    await verifyToken(authHeaders[0].value.slice(7));
    return request;
  } catch (e) {
    return {
      status: '401',
      statusDescription: 'Unauthorized',
      headers: {},
      body: JSON.stringify({ error: e.message })
    };
  }
};
