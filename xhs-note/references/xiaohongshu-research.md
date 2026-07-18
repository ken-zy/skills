# Xiaohongshu Research

Use this reference before deciding note slots.

## Search

Create 3-6 focused queries from:

- product category: jewelry, necklace, earrings, bracelet, set, gift
- style line: new Chinese, light vintage, cafe, commute, date, gift
- visual/material keywords: glass-like, old gold, turquoise, handmade, translucent
- buyer scenario: self gift, best friend gift, date outfit, work outfit, seasonal use

Prefer examples with:

- recent publication date
- high engagement relative to niche size
- product/style match over generic prettiness
- more than 5 model images when the source will influence market-derived slot structure
- visible image order or enough media to analyze structure

If OpenCLI/smart-search has a Xiaohongshu route, use it. If login, rate limits, stale tabs, or access blocks prevent live exploration, record the exact limitation in `research/xhs-structure.md`.

## Search Escalation When Nothing Passes

Do not treat one or two weak searches as enough to justify fallback.

If the first query set finds no candidate that can pass the download gate, run a retry matrix before using `shared/model-library/styles/`:

- run at least 6 total focused query attempts unless the platform is blocked or the user explicitly asks to stop
- vary at least three axes:
  - scene: date dinner, commute, cafe, tea table, gift, self gift, seasonal use
  - component: necklace, earrings, bracelet, full set, neckline, side face, wrist, hand detail
  - style synonym: French, light vintage, new Chinese, handmade, glass-like, turquoise, old gold
  - content format: outfit, OOTD, jewelry recommendation, matching formula, try-on, unboxing
  - buyer intent: gift, affordable luxury, niche accessory, everyday styling, party/date styling
- include one adjacent search direction that still respects product positioning, but do not jump to forbidden aesthetics just to get results
- when search results show a likely candidate, open or download it enough to validate slide/video count, model-image count, and content match

Record this in `research/xhs-structure.md` as a table:

```markdown
## Search Attempt Matrix

| Attempt | Query | Axis changed | Useful candidates | Downloaded | Rejection / blocker |
|---|---|---|---|---|---|
```

Fallback is allowed only when this matrix shows that eligible candidates could not be found, downloaded, or validated, or when a hard platform blocker is recorded.

## Candidate Download Gate

Do not stop at search result links when a useful candidate is available.

Apply the gate to every candidate that may influence note structure or style baseline:

- publication date: preferably within the last 1 month
- engagement: likes greater than 100 when visible
- model-image count: more than 5 images with a visible person, face, upper body, hand, wrist, ear, neck, or other human wearing context
- content match: must serve a concrete note purpose, such as new-Chinese mood, commute jewelry wearing structure, necklace/earring close-up, bracelet wearing relation, gift/unboxing scene, or first-3-slide sequence

Do not count pure still life, product-only shots, flowers, scenery, text diagrams, or infographic grids as model images. A post with 5 or fewer model images is not eligible as primary `market-derived` structure evidence, even if it has high engagement. It may still be recorded as a weak signal, product-proof inspiration, or skipped candidate.

For candidates that pass:

1. Download media into `notes/<note>/style/xhs-ref-candidates/<source-id>/`.
2. Inspect downloaded images/video enough to determine slide count, model-image count, cover type, first 3 slide sequence, recurring shot archetypes, product proof shots, and mismatch risks.
3. Record local paths and validation result in `notes/<note>/research/xhs-structure.md`.
4. If a downloaded item is promoted into `market-derived` structure evidence for a Pre or formal slot, select the exact images that should influence generation, copy them into `style/` with explicit role names such as `xhs-<source-id>-neckline-ootd.jpg`, `xhs-<source-id>-halfbody-ootd.jpg`, or `xhs-<source-id>-hand-context.jpg`, and update `style/_ref-map.md`.
5. Add those promoted market images to the relevant prompt JSON `ref` array before generation. The market-derived reference must be visible to the generation model, not only summarized in `research/xhs-structure.md`.
6. If a candidate is useful only as written market evidence and should not influence pixels, keep it under `style/xhs-ref-candidates/`, do not cite it from prompt JSON, and do not label the resulting shot as visually `market-derived`.

For candidates that do not pass:

- Do not download old, low-engagement, or mismatched posts by default.
- Still record them as skipped or weak structure signals if they influenced the plan.
- If no candidate passes, continue with the search escalation matrix before using style-library fallback.

## Extracted Record

For each useful example, capture:

- source URL or searchable title/keyword
- engagement signal if visible
- niche/style match
- slide count
- model-image count, with a short note on what counted as a model image
- cover type
- first 3 slide sequence
- recurring shot archetypes
- product proof shots
- copywriting/visual hook if relevant
- why it should or should not influence this product

Do not copy another creator's images or exact composition. Extract structure and intent.

## Market Evidence To Prompt References

Market exploration is only useful for generation if the selected evidence reaches the actual prompt input path.

Before generating any `Pre` or formal slot that is labeled `market-derived`:

1. Pick the downloaded Xiaohongshu images that correspond to the shot's concrete role, such as neckline framing, commute halfbody palette, hand context, or first-three-slide rhythm.
2. Copy those images from `style/xhs-ref-candidates/<source-id>/...` into `style/` using explicit filenames. Do not leave the prompt pointing at a deep candidate directory as the only record.
3. Record each copied file in `style/_ref-map.md` with source id, original candidate path, role, and limitation.
4. Include the copied files in the prompt JSON `ref` list with narrow role assignments.
5. Open or otherwise load those images before calling the image generation tool, so they are actual visual inputs.

If a prompt says `source_basis` includes an XHS source but none of that source's images appear in `ref` or the current visual context, stop and fix the prompt before generating. Style-library references may supplement the market images, but they must not replace the eligible XHS images when the slot is labeled `market-derived`.

## Fallback

Use `shared/model-library/styles/` only after eligible Xiaohongshu candidates have been downloaded and validated, or after the search escalation matrix records why eligible candidates could not be found/downloaded/validated. If a hard blocker stops live search, record the blocker explicitly before fallback.

Read selectively:

- `shared/model-library/styles/INDEX.md`
- `shared/model-library/styles/INDEX-by-style.md`
- 1-3 relevant style files such as `new-chinese.md`, `commercial-jewelry.md`, `earrings-photo.md`, `bracelet.md`, `commute.md`, `french.md`, or `face-pool.md`

Label fallback outputs as `style-library-derived`, not `market-derived`.
