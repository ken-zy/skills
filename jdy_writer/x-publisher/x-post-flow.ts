import { assertPublished, canonicalPostUrl, type PostReceipt, type PublishedSnapshot } from './x-post-state.ts';

export interface PostDriver {
  compose(resume: boolean, beforeMutation: () => void): Promise<void>;
  submit(beforeClick: () => void): Promise<string>;
  verify(url: string): Promise<PublishedSnapshot>;
}
export async function runPostFlow(r: PostReceipt, driver: PostDriver, save: () => void, options: { submit: boolean; verifyOnly?: boolean; publishedUrl?: string }): Promise<void> {
  if (options.publishedUrl && !options.verifyOnly) throw Error('--published-url requires --verify-only.');
  if (options.publishedUrl) {
    const url = canonicalPostUrl(options.publishedUrl);
    if (r.url && r.url !== url) throw Error('Receipt already binds another published URL.');
    const candidate = { ...r, url };
    assertPublished(candidate, await driver.verify(url));
    r.url = url; r.stage = 'verified'; r.verifiedAt = new Date().toISOString(); save();
    return;
  }
  if (r.url) {
    assertPublished(r, await driver.verify(r.url));
    r.stage = 'verified'; r.verifiedAt = new Date().toISOString(); save();
    return;
  }
  if (options.verifyOnly || ['submitting','submitted','verified','complete'].includes(r.stage)) {
    throw Error('Submission outcome needs inspection. Find the post on the official profile, then use --verify-only --published-url. Never submit again with a new receipt.');
  }
  await driver.compose(r.stage !== 'waiting_login', () => { r.stage = 'composing'; save(); });
  r.stage = 'ready'; save();
  if (!options.submit) return;
  // A crash, timeout, or lost response from this point must never cause an automatic second click.
  let armed = false;
  const url = await driver.submit(() => {
    r.stage = 'submitting'; r.submittedAt = new Date().toISOString(); save(); armed = true;
  });
  if (!armed) throw Error('Driver failed to record the submission boundary. Inspect before continuing.');
  r.url = canonicalPostUrl(url);
  r.stage = 'submitted'; save();
  assertPublished(r, await driver.verify(r.url));
  r.stage = 'verified'; r.verifiedAt = new Date().toISOString(); save();
}
