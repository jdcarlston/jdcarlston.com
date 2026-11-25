/**
 * jdcarlston.com — runs automatically on every verified Netlify form submission.
 * (Netlify calls any function named "submission-created" this way; spam caught
 * by the honeypot never reaches it.)
 *
 * For the "consulting" form it:
 *   1. emails the person a reply with JD's Calendly link (through Resend),
 *   2. emails JD a notification with tap-to-text and reply links,
 *   3. adds the person to Kit, only if they ticked "occasional updates".
 *
 * Same setup as red-thread-labs.com. Environment variables
 * (Netlify → Site configuration → Environment variables):
 *   RESEND_API_KEY  — required; the same Resend key the Red Thread Labs site uses
 *   EMAIL_FROM      — optional, defaults to "JD Carlston <contact@red-thread-labs.com>"
 *   EMAIL_REPLY_TO  — optional, defaults to contact@red-thread-labs.com
 *   NOTIFY_TO       — optional, where inquiry alerts go; defaults to contact@red-thread-labs.com
 *   KIT_API_KEY     — optional; only needed for the updates opt-in
 *   KIT_FORM_ID     — optional; the Kit form people who opt in are added to
 */
// Written from _data/consulting.yml by every Eleventy build (see eleventy.config.js).
import consulting from './consulting.generated.json' with { type: 'json' };

const SITE = 'https://www.jdcarlston.com';
const FROM = () => process.env.EMAIL_FROM || 'JD Carlston <contact@red-thread-labs.com>';
const REPLY_TO = () => process.env.EMAIL_REPLY_TO || 'contact@red-thread-labs.com';
const NOTIFY_TO = () => process.env.NOTIFY_TO || 'contact@red-thread-labs.com';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const yes = (v) => /^(on|yes|true|1)$/i.test(String(v ?? '').trim());

export function normPhone(p) {
  const d = String(p || '').replace(/\D/g, '');
  if (d.length === 10) return '+1' + d;
  if (d.length === 11 && d.startsWith('1')) return '+' + d;
  return d.length >= 10 ? '+' + d : '';
}

export function serviceName(id) {
  const o = consulting.offers.find((x) => x.id === id);
  return o ? o.name : '';
}

/** The reply the person gets. */
export function replyEmail({ name, service }) {
  const raw = String(name || '').trim().split(/\s+/)[0] || '';
  const first = raw ? raw[0].toUpperCase() + raw.slice(1) : 'there';
  const svc = serviceName(service);
  const about = svc ? ` about ${svc}` : '';
  const cal = consulting.calendly;
  const subject = svc ? `Thanks for reaching out about ${svc}` : 'Thanks for reaching out';

  const text = `Hi ${first},

Thank you for reaching out${about}. I read every inquiry myself, and I'll reply personally within two business days.

If you'd like to talk sooner, grab a time for a free preliminary consult:
${cal}

Bring whatever's on your mind: the system, the team, the decision you keep circling. We'll work out together whether one of my packages fits, or whether something else would serve you better.

Talk soon,
JD Carlston
${SITE}
`;

  const html = `<!doctype html><html><body style="margin:0;padding:0;background:#F4F1EC;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F4F1EC;"><tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#FFFFFF;border-radius:6px;border-top:6px solid #74150C;font-family:Arial,Helvetica,sans-serif;color:#1D1C1A;">
<tr><td style="padding:28px 32px 0;font-size:16px;line-height:1.6;">
<p style="margin:0 0 14px;">Hi ${esc(first)},</p>
<p style="margin:0 0 14px;">Thank you for reaching out${esc(about)}. I read every inquiry myself, and I’ll reply personally within two business days.</p>
<p style="margin:0 0 20px;">If you’d like to talk sooner, grab a time for a free preliminary consult:</p>
</td></tr>
<tr><td align="center" style="padding:0 32px 8px;">
<a href="${cal}" style="display:inline-block;background:#2E6B6E;color:#FFFFFF;text-decoration:none;font-weight:bold;font-size:16px;padding:14px 26px;border-radius:999px;">Book a free consult</a>
</td></tr>
<tr><td style="padding:20px 32px 0;font-size:16px;line-height:1.6;">
<p style="margin:0 0 20px;">Bring whatever’s on your mind: the system, the team, the decision you keep circling. We’ll work out together whether one of my packages fits, or whether something else would serve you better.</p>
<p style="margin:0 0 4px;">Talk soon,</p>
<p style="margin:0 0 28px;">JD Carlston<br><a href="${SITE}" style="color:#2E6B6E;">jdcarlston.com</a></p>
</td></tr>
</table>
<p style="font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#867E77;margin:14px 0 0;">You’re getting this because you sent an inquiry at jdcarlston.com/consulting.</p>
</td></tr></table></body></html>`;

  return { subject, text, html };
}

/** The alert JD gets. */
export function notifyEmail(d) {
  const svc = serviceName(d.service) || 'Not sure yet';
  const phone = normPhone(d.phone);
  const canText = phone && yes(d.text_ok);
  const subject = `Consulting inquiry: ${d.name || 'someone'} · ${svc}`;
  const rows = [
    ['Name', d.name],
    ['Email', d.email],
    ['Organization', d.organization],
    ['Interested in', svc],
    ['Mobile', phone ? `${phone}${canText ? ' (OK to text)' : ' (no text permission)'}` : ''],
    ['Updates', yes(d.updates) ? 'Yes, added to Kit' : 'No'],
  ].filter(([, v]) => v);
  const text = `${rows.map(([k, v]) => `${k}: ${v}`).join('\n')}\n\nWhat's going on:\n${d.message || ''}\n\nThey were sent your Calendly link automatically.\n`;
  const links = [
    `<a href="mailto:${esc(d.email)}?subject=${encodeURIComponent('Re: ' + svc)}" style="color:#2E6B6E;">Reply by email</a>`,
    canText ? `<a href="sms:${phone}" style="color:#2E6B6E;">Text ${esc(String(d.name || '').split(/\s+/)[0] || 'them')}</a>` : '',
    phone ? `<a href="tel:${phone}" style="color:#2E6B6E;">Call</a>` : '',
  ].filter(Boolean).join(' &nbsp;·&nbsp; ');
  const html = `<!doctype html><html><body style="margin:0;padding:24px;background:#F4F1EC;font-family:Arial,Helvetica,sans-serif;color:#1D1C1A;">
<div style="max-width:560px;margin:0 auto;background:#fff;border-radius:6px;border-top:6px solid #74150C;padding:24px 28px;">
<p style="margin:0 0 6px;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#4A4744;">New consulting inquiry</p>
<h2 style="margin:0 0 16px;font-size:22px;">${esc(d.name)} · ${esc(svc)}</h2>
<table role="presentation" cellpadding="0" cellspacing="0" style="font-size:15px;line-height:1.6;">
${rows.map(([k, v]) => `<tr><td style="padding:2px 16px 2px 0;color:#4A4744;vertical-align:top;">${esc(k)}</td><td style="padding:2px 0;">${esc(v)}</td></tr>`).join('')}
</table>
<p style="margin:18px 0 6px;color:#4A4744;font-size:13px;">What’s going on</p>
<p style="margin:0 0 18px;font-size:15px;line-height:1.6;white-space:pre-wrap;">${esc(d.message)}</p>
<p style="margin:0 0 6px;font-size:15px;">${links}</p>
<p style="margin:14px 0 0;font-size:13px;color:#867E77;">They were sent your Calendly link automatically.</p>
</div></body></html>`;
  return { subject, text, html };
}

async function resend({ to, subject, text, html, replyTo, idempotencyKey }) {
  const key = process.env.RESEND_API_KEY;
  if (!key) throw new Error('RESEND_API_KEY is not set');
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      Authorization: 'Bearer ' + key,
      'Content-Type': 'application/json',
      ...(idempotencyKey ? { 'Idempotency-Key': String(idempotencyKey).slice(0, 256) } : {}),
    },
    body: JSON.stringify({ from: FROM(), to: [to], reply_to: replyTo || REPLY_TO(), subject, text, html }),
  });
  const body = await res.text();
  if (!res.ok) throw new Error(`Resend ${res.status}: ${body}`);
  return body;
}

async function addToKit({ email, name, organization }) {
  const apiKey = process.env.KIT_API_KEY;
  const formId = process.env.KIT_FORM_ID;
  if (!apiKey || !formId) {
    console.warn('Updates opt-in skipped: KIT_API_KEY or KIT_FORM_ID not set.');
    return;
  }
  const headers = { 'X-Kit-Api-Key': apiKey, 'Content-Type': 'application/json', Accept: 'application/json' };
  const first = String(name || '').trim().split(/\s+/)[0] || '';
  const KIT = 'https://api.kit.com/v4';
  // New people start inactive so Kit's own confirmation (double opt-in) email goes out,
  // the same way the Red Thread Labs list works.
  let existing = null;
  try {
    const r = await fetch(`${KIT}/subscribers?status=all&email_address=${encodeURIComponent(email)}`, { headers });
    if (r.ok) existing = ((await r.json()).subscribers || [])[0] || null;
  } catch {}
  const create = await fetch(`${KIT}/subscribers`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ email_address: email, ...(existing ? {} : { state: 'inactive' }), ...(first ? { first_name: first } : {}) }),
  });
  if (!create.ok) throw new Error(`Kit create ${create.status}: ${await create.text()}`);
  const add = await fetch(`${KIT}/forms/${formId}/subscribers`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ email_address: email, referrer: `${SITE}/consulting/` + (organization ? ` (${String(organization).slice(0, 100)})` : '') }),
  });
  if (!add.ok) throw new Error(`Kit add-to-form ${add.status}: ${await add.text()}`);
}

export default async (req) => {
  let payload;
  try {
    ({ payload } = await req.json());
  } catch {
    return;
  }
  if (!payload || payload.form_name !== 'consulting') return;

  const d = payload.data || {};
  const email = String(d.email || '').trim();
  const id = payload.id || `${email}-${payload.created_at || ''}`;

  // Each step runs on its own, so one failing doesn't stop the others.
  const steps = [];
  if (email) {
    const r = replyEmail({ name: d.name, service: d.service });
    steps.push(['reply', resend({ to: email, ...r, idempotencyKey: `reply-${id}` })]);
  }
  const n = notifyEmail(d);
  steps.push(['notify', resend({ to: NOTIFY_TO(), ...n, replyTo: email || undefined, idempotencyKey: `notify-${id}` })]);
  if (email && yes(d.updates)) steps.push(['kit', addToKit({ email, name: d.name, organization: d.organization })]);

  const results = await Promise.allSettled(steps.map(([, p]) => p));
  results.forEach((r, i) => {
    if (r.status === 'rejected') console.error(`consulting ${steps[i][0]} failed:`, r.reason?.message || r.reason);
  });
};
