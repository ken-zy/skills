# Review And Scoring

Use this reference before scoring drafts, selecting finals, or claiming a note is complete.

## Candidate Review

After each formal candidate:

1. Move selected generated images from `$CODEX_HOME/generated_images/` into `drafts/<slot-id>/`.
2. Run `python3 scripts/sync_review_csv.py <note-dir>`.
3. Review and score each draft against the prompt, product refs, and structure-map purpose.
4. Fill `score`, `status`, `final_file`, and `notes` in `review.csv`.
5. Copy, not move, qualified images into `final/`.
6. Promote a generated candidate into top-level `style/` only if it qualified for `final`; otherwise keep it only in `drafts/<slot-id>/` and `review.csv`.
7. Decide next action from the scores: stop if final-ready, generate another candidate only for named fixable issues, or revise prompt/refs if failure is systemic.

## Final Gate

Use this gate before copying any candidate into `final/`, promoting it into top-level `style/`, or defending an existing final after the user challenges it.

Do not treat "fixed the previous issue" as enough for `final`. Each final decision must be a fresh review of the current image against the actual product refs and all visible core components. Re-open the relevant product images and verify the complete structure, not just the last corrected defect.

For jewelry and other component-heavy products, check each visible core component separately:

- component presence: the expected necklace, earrings, bracelet, ring, pendant, clasp, or charm is visible when the slot requires it
- local sequence and rhythm: bead order, spacer groups, connector count, pendant position, color accents, and left/right repetition match the product refs closely enough for purchase judgment
- shape and material: transparent/fluted/smooth beads, old-gold parts, stones, fabric, metal, and color accents are not replaced by style-similar approximations
- wearing proportion: scale on the model, drop length, necklace curve, earring height, bracelet fit, and occlusion match the product's real wearing refs

Only assign `final` when no hard cap below applies. If any visible core component is only a plausible or attractive approximation, cap the score first, then set `status` from the capped score. The `review.csv` note for a final candidate must state why the main hard caps do not apply; a note that only says what improved from the prior candidate is not sufficient.

When the user asks why an image is in `final`, re-review from the files on disk instead of defending the old score. If the fresh review finds a hard cap, withdraw the image from `final`, clear `final_file`, update `status` and `notes`, then run the repo validator.

## Scoring

Start from 100 and deduct by:

| Dimension | Weight | What to check |
|---|---:|---|
| Product fidelity | 40 | visible product components match actual refs 1:1 |
| Slot hit | 20 | image completes the slot's stated task |
| Series consistency | 15 | model, outfit, light, background, mood match the accepted baseline |
| Composition and commercial usability | 15 | product readability, crop, occlusion, Xiaohongshu usability |
| Technical quality | 10 | hands, anatomy, broken jewelry, blur, fake text, AI artifacts |

## Hard Caps

Hard caps override total score:

- complex product generated without actual product refs: max `84`
- product missing, swapped, or structurally/color wrong: max `74`
- product visible but not enough for purchase judgment: max `82`
- visible core component not 1:1 to refs, only style-similar: max `87`
- local size/rhythm/new elements conflict with refs: max `83`
- slot task missed: max `84`
- composition/action duplicates an existing final: max `83`
- obvious bad hands, broken jewelry, anatomy issue, or readable fake text: max `79`

## Status Bands

- `88-100`: can enter `final` only without hard caps and with 1:1 product fidelity for visible core components
- `85-87`: shortlist only
- `75-84`: shortlist or anchor candidate
- `<75`: skip

## Completion

An active note is not complete until `final/` has at least 9 qualified images. Do not call a 3-image validation run a complete note.
