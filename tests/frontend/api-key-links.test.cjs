const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');

test('each API key has its own direct official link, independent of Drive', () => {
  const html = fs.readFileSync('static/index.html', 'utf8');
  for (const [id, url, label] of [
    ['getGroqApiKey', 'https://console.groq.com/keys', 'Obtener clave de Groq'],
    ['getGeminiApiKey', 'https://aistudio.google.com/apikey', 'Obtener clave de Gemini'],
  ]) {
    const tag = html.match(new RegExp('<a\\b[^>]*id="' + id + '"[^>]*>[\\s\\S]*?</a>'))?.[0];
    assert.ok(tag, `Missing ${label}`);
    assert.ok(tag.includes(`href="${url}"`));
    assert.match(tag, /target="_blank"/);
    assert.match(tag, /rel="[^"]*noopener[^"]*noreferrer[^"]*"/);
    assert.ok(tag.includes(label));
    assert.doesNotMatch(tag, /onclick|userGroqKeyInput\.value|userGeminiKeyInput\.value/);
  }
});
