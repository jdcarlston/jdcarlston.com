/**
 * Consulting inquiries — TEXT the people who said it's OK, from JD's own number,
 * through the Mac Messages app. Same approach as the Love Lab texts on red-thread-labs.com.
 *
 * Run from the jdcarlston.com folder on the Mac (Messages must be signed in, and the
 * Netlify CLI logged in and linked to this site: `netlify login`, then `netlify link`):
 *   node scripts/text-inquiries.mjs                    → preview: who gets which text, sends nothing
 *   node scripts/text-inquiries.mjs --test 8014770497  → sends ONE sample to that number
 *   node scripts/text-inquiries.mjs --send             → texts everyone not already in the sent log
 * Options:
 *   --sms        send as SMS (green) instead of iMessage (needs Text Message Forwarding on your iPhone)
 *   --only 8015551234,8015556789   limit to these numbers
 *   --resend     ignore the sent log
 *
 * Only people who gave a mobile number AND ticked "It's OK to text me" are included.
 * The sent log lives in ~/Documents, never in this public repo.
 */
import { execSync, execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const consulting = require('../_data/consulting.js');

const SENT_LOG = path.join(os.homedir(), 'Documents', 'consulting-texts-sent.csv');
const SKIP_EMAILS = []; // add emails here to hold someone back

const args = process.argv.slice(2);
const mode = args.includes('--send') ? 'send' : args.includes('--test') ? 'test' : 'preview';
const argAfter = (flag) => (args.includes(flag) ? String(args[args.indexOf(flag) + 1] || '') : '');
const useSms = args.includes('--sms');

// ---------- the text ----------
function textFor({ name, service }) {
  const raw = String(name || '').trim().split(/\s+/)[0] || '';
  const first = raw ? raw[0].toUpperCase() + raw.slice(1) : 'there';
  const offer = consulting.offers.find((o) => o.id === service);
  const about = offer ? ` about ${offer.name}` : '';
  return `Hi ${first}, it's JD Carlston. Thanks for reaching out${about}! If it's easier to talk it through, here's my calendar for a free consult: ${consulting.calendly}`;
}

// ---------- helpers ----------
const sh = (cmd) => execSync(cmd, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
const yes = (v) => /^(on|yes|true|1)$/i.test(String(v ?? '').trim());
function normPhone(p) {
  const d = String(p || '').replace(/\D/g, '');
  if (d.length === 10) return '+1' + d;
  if (d.length === 11 && d.startsWith('1')) return '+' + d;
  return d.length >= 10 ? '+' + d : '';
}
function readCsv(file) {
  if (!fs.existsSync(file)) return [];
  const [head, ...rows] = fs.readFileSync(file, 'utf8').split(/\r?\n/).filter((l) => l.trim());
  const cols = head.split(',').map((c) => c.trim().toLowerCase());
  return rows.map((r) => { const v = r.split(',').map((x) => x.trim()); return Object.fromEntries(cols.map((c, i) => [c, v[i] || ''])); });
}
function logSent(phone, name) {
  if (!fs.existsSync(SENT_LOG)) fs.writeFileSync(SENT_LOG, 'phone,name,sent_at\n');
  fs.appendFileSync(SENT_LOG, `${phone},${String(name).replace(/,/g, ' ')},${new Date().toISOString()}\n`);
}
function siteId() {
  if (process.env.NETLIFY_SITE_ID) return process.env.NETLIFY_SITE_ID;
  const state = path.join(process.cwd(), '.netlify', 'state.json');
  if (fs.existsSync(state)) return JSON.parse(fs.readFileSync(state, 'utf8')).siteId;
  console.error('This folder is not linked to Netlify yet. Run: netlify link');
  process.exit(1);
}

// ---------- who gets it ----------
function people() {
  const forms = JSON.parse(sh(`netlify api listSiteForms --data '{"site_id":"${siteId()}"}'`));
  const form = forms.find((f) => f.name === 'consulting');
  if (!form) { console.error('No "consulting" form found on this site yet.'); process.exit(1); }
  const subs = JSON.parse(sh(`netlify api listFormSubmissions --data '{"form_id":"${form.id}","per_page":100}'`));
  const byPhone = new Map();
  for (const s of subs) {
    const d = s.data || {};
    const phone = normPhone(d.phone);
    const email = String(d.email || '').trim().toLowerCase();
    if (!phone || !yes(d.text_ok) || SKIP_EMAILS.includes(email)) continue;
    if (!byPhone.has(phone)) byPhone.set(phone, { name: d.name, phone, service: d.service });
  }
  return [...byPhone.values()];
}

function sendText(phone, body) {
  const service = useSms ? 'SMS' : 'iMessage';
  const script = `on run argv
  set targetPhone to item 1 of argv
  set msg to item 2 of argv
  tell application "Messages"
    set svc to 1st account whose service type = ${service}
    send msg to participant targetPhone of svc
  end tell
end run`;
  execFileSync('osascript', ['-e', script, phone, body], { stdio: ['ignore', 'pipe', 'pipe'] });
}

// ---------- run ----------
if (mode === 'test') {
  const to = normPhone(argAfter('--test'));
  if (!to) { console.error('Usage: --test 8015551234'); process.exit(1); }
  sendText(to, textFor({ name: 'Alex', service: 'domain-boundary-splits' }));
  console.log(`Sent a sample to ${to}. Check Messages for a blue (iMessage) or green (SMS) bubble, and any red "Not Delivered".\n`);
  process.exit(0);
}

const only = argAfter('--only').split(',').map(normPhone).filter(Boolean);
const sent = new Set(readCsv(SENT_LOG).map((r) => r.phone));
const all = people();
const list = all
  .filter((p) => !only.length || only.includes(p.phone))
  .filter((p) => args.includes('--resend') || !sent.has(p.phone));

console.log(`\n${list.length} text(s) to send${sent.size && !args.includes('--resend') ? ` (skipping ${all.length - list.length} already texted)` : ''}:\n`);
for (const p of list) console.log(`  ${p.name} ${p.phone}\n    "${textFor(p)}"\n`);

if (mode === 'preview') { console.log('Preview only. Nothing was sent.\nNext: --test YOURNUMBER to see it on your phone, then --send.\n'); process.exit(0); }

let ok = 0;
for (const p of list) {
  try { sendText(p.phone, textFor(p)); logSent(p.phone, p.name); ok++; console.log(`  texted → ${p.name} ${p.phone}`); }
  catch (e) { console.error(`  FAILED → ${p.name} ${p.phone}: ${String(e.stderr || e.message).trim()}`); }
  await new Promise((r) => setTimeout(r, 1500));
}
console.log(`\nDone: ${ok} of ${list.length} texted. Open Messages and look for any red "Not Delivered" (those numbers may need --sms).\n`);
