---
name: jewelry-product-imagegen
description: "Use when generating ecommerce jewelry and accessory model-wearing product photos from local product folders under /Users/jdy/Downloads/耳环整理图, with fixed model references, product-appropriate wearing views, OpenCLI ChatGPT web generation, or Codex imagegen generation."
---

# Jewelry Product ImageGen

Use this skill when jdy asks to batch-generate ecommerce images for the jewelry and accessory products under `/Users/jdy/Downloads/耳环整理图`, using either OpenCLI ChatGPT web image generation or Codex built-in `$imagegen`.

## Core Contract

- Speak to jdy in Chinese.
- The generation route is authoritative:
  - If jdy says OpenCLI, GPT web, ChatGPT web, or browser generation, use `opencli chatgpt image`.
  - If jdy says Codex, `$imagegen`, `imagegen`, or built-in image generation, use the Codex built-in `image_gen` route via the `imagegen` skill.
  - If no route is specified, keep the current batch's established route. For this project, OpenCLI is the default long-batch route, but switch to Codex imagegen when jdy explicitly asks or when ChatGPT web rate limits make OpenCLI unsuitable.
- Keep the selected fictional model consistent across products.
- Treat `selected-model.jpg` as a project-level visual baseline for the current batch. Before product generation, confirm that it fits the batch's season, styling, color temperature, clothing, and product mood. If it does not fit, first generate or select a new fictional model reference and update the model slug before generating products. Do not hard-code one season or outfit; derive the baseline from the current batch style brief and references.
- The requested generation scope is authoritative. Generate only the product categories jdy asks for:
  - If jdy asks for earrings, show earrings only. Do not add necklaces, rings, bracelets, bags, or other styling accessories.
  - If jdy asks for a necklace, show the necklace only unless a set is explicitly requested.
  - If jdy asks for an earring + necklace set or another set, show only those requested set pieces together.
- For earring-only products, generate exactly three final images unless jdy asks otherwise:
  1. `01-half-front-single-ear.png`
  2. `02-side-single-ear-closeup.png`
  3. `03-front-both-ears.png`
- For necklaces, bracelets, rings, or mixed jewelry sets, first define a product-appropriate view plan and stable filenames before generating. Example for an earring + necklace set: `01-front-set-wearing.png`, `02-side-earring-closeup.png`, `03-necklace-detail.png`.
- Put final outputs under:
  `/Users/jdy/Downloads/耳环整理图/generated/<product-id>/<model-slug>/final/`
- For Codex imagegen runs, use a route-specific model slug such as `<model-slug>_codex` unless jdy asks to overwrite the OpenCLI set.
- Do not overwrite existing final images unless jdy asks to regenerate.
- For single-view generation, partial regeneration, or one-off preview work, use a scoped output directory such as `<model-slug>_side_only`, `<model-slug>_front_retry`, or `<model-slug>_preview` instead of writing into an existing complete product set.

## Default Inputs

- Product root: `/Users/jdy/Downloads/耳环整理图`
- Current selected model reference:
  `/Users/jdy/Downloads/耳环整理图/generated/model_candidates/final/candidate-01.png`
- Current model slug: `model_candidate_01`
- Product folders are numeric directories such as `1`, `2`, `3`. The current source set is earrings. The workflow can support necklaces, bracelets, rings, and mixed jewelry sets only when jdy's request and the product references require those categories.

If jdy selects a different model, use that model path and update the `model-slug` in the output directory.

## Reference Image Roles

Use stable reference roles in prompts, OpenCLI `--image` order, and Codex imagegen reference labels. State these roles explicitly in every generation prompt so the generator does not mix model identity, product design, and scale guidance.

1. `selected-model.jpg` - model reference. Use only for the selected fictional model's overall feel: face type, skin tone, hair, makeup, expression restraint, styling mood, and studio taste. It does not define the jewelry product.
2. `product-design.jpg` - product design reference, usually a white-background, flat, or clean product shot. This is the authoritative product source. Use it for exact category, shape, structure, material, color, stone, clasp, chain, pendant, flower, drop, symmetry, and finish. Do not simplify or invent details.
3. `product-worn.jpg` - product wearing-scale reference. When a matching, usable wearing image exists, attach it by default for model-wearing ecommerce outputs. Use it only for product-to-body scale, wearing position, attachment point, angle, drop length, and proportion adaptation on a human body. Do not copy its model identity, face, styling, lighting, background, or unrelated jewelry.

If a product folder has both a clean product shot and a matching wearing shot, use both roles: `product-design.jpg` controls what the product is, and `product-worn.jpg` controls how large it is and where it sits on the body. Do not create cropped wearing references by default. If the wearing shot is missing, blurry, not the same product, or demonstrates a wrong wearing method, omit it and record why it was omitted.

## Generation Routes

### Route A: OpenCLI ChatGPT Web

Use this route when jdy asks for OpenCLI, GPT web, ChatGPT web, browser-based generation, or when continuing an existing OpenCLI batch.

- Load `opencli-usage` at the start of an OpenCLI session.
- Run `opencli doctor` once before a batch.
- Use `opencli chatgpt image` with `--image` references and `--op` output directories.
- Use OpenCLI trace and retry rules for `EMPTY_RESULT`, still-generating screenshots, adapter failures, and ChatGPT web rate limits.
- Use `product-worn.jpg` as the third uploaded reference by default when it is available and matches the product. The prompt must state that Reference 3 is only a scale, placement, attachment, angle, and drop-length reference, not a model or style reference.

### Route B: Codex Imagegen

Use this route when jdy asks for Codex, `$imagegen`, `imagegen`, or built-in image generation.

- Load the `imagegen` skill.
- Use the built-in `image_gen` tool by default, not the `scripts/image_gen.py` CLI fallback, unless jdy explicitly asks for CLI/API mode.
- For local reference files, call `view_image` first so the references are visible in the conversation context. Label each reference role in the prompt:
  - Reference 1: selected model reference.
  - Reference 2: product design reference.
  - Reference 3: product wearing-scale reference when attached; attach it by default when a matching usable wearing reference exists.
- Generate one view per `image_gen` call. Do not ask for multiple distinct product views in a single image generation call.
- Do not add fixed pacing delays or long cooldowns between successful Codex imagegen calls. Proceed sequentially: generate one view, validate it, copy it into the workspace, then move to the next view or product.
- Built-in Codex imagegen saves under `$CODEX_HOME/generated_images/...` by default. After each generation, copy the selected generated file into the product workspace final directory; never leave project-bound outputs only under `$CODEX_HOME`.
- Keep original Codex generated files in place unless jdy explicitly asks to delete them.
- Use route-specific final and aggregate directories, for example:
  - `/Users/jdy/Downloads/耳环整理图/generated/<product-id>/<model-slug>_codex/final/`
  - `/Users/jdy/Downloads/耳环整理图/generated/all_new_<model-slug>_codex/`
- Codex imagegen has no OpenCLI daemon, extension, browser, trace, or ChatGPT web rate-limit handling. Validation and file归档 are still required.

## Batch Workflow

1. Decide and state the generation route for the run:
   - `OpenCLI ChatGPT web` when jdy asks for OpenCLI, GPT web, ChatGPT web, browser generation, or when continuing an existing OpenCLI batch.
   - `Codex imagegen` when jdy asks for Codex, `$imagegen`, `imagegen`, or built-in image generation.
   - If jdy does not specify a route, keep the current batch's established route.

2. Run the route-specific preflight once at the start of the batch:
   - OpenCLI route:
     ```bash
     opencli doctor
     ```
     Continue only when daemon, extension, and connectivity are OK. Do not upgrade OpenCLI or the Chrome extension during every product; treat that as an exception path.
   - Codex imagegen route:
     - Load the `imagegen` skill before generating.
     - Confirm local reference paths exist.
     - Use `view_image` for `selected-model.jpg`, `product-design.jpg`, and optional `product-worn.jpg` before calling `image_gen`.
     - Plan the stable workspace copy target because the built-in tool first saves under `$CODEX_HOME/generated_images/...`.

3. Confirm the batch visual baseline before entering product folders:
   - Inspect the current `selected-model.jpg` and the batch style references.
   - Confirm the model reference matches the current season, color tone, clothing lightness, hair styling, makeup restraint, and product mood.
   - If the model reference feels mismatched, generate or select a new fictional model reference first, then set a new `model-slug`. Do not start product generation until the project-level visual baseline is settled.

4. For each product folder:
   - Inspect the product images with `find`, `file`, and `view_image`.
   - Choose the clearest product design reference image, usually a white-background, flat, pair, or clean product shot that shows the full structure.
   - If available, choose one product wearing reference image that best matches the target view and clearly shows body placement and scale. For example, use an ear close-up as the wearing reference for a side-ear close-up, a front bust image for a front necklace view, or a hand close-up for a ring view.
   - Attach the wearing reference by default when it is the same product and the wearing method is usable. Omit it only when it is missing, blurry, not the same product, shows a wrong wearing method, or would clearly mislead scale or placement. Record the omission reason in logs, manifest, or failure notes.
   - Do not auto-crop the wearing reference. If Reference 3 contains another model, keep its role limited through explicit prompt text: it provides only scale, wearing position, attachment point, and angle; it must not influence model identity, face, hair, clothing, lighting, or background.
   - Describe the product structure explicitly before prompting: product type, wearing location, clasp or stud, chain, pendant, flower, drop, stone shape, metal color, symmetry, layering, and any unusual details.
   - Before writing prompts, state the scoped product categories for this run. Do not include any product category outside that scope, even if the skill supports it.

5. Prepare references and output directories. If this is only a single view or retry, include the scope in the output root so accepted files do not collide with an existing complete final set:
   ```bash
   /Users/jdy/Documents/skills/jewelry-product-imagegen/scripts/prepare_refs.sh \
     <selected-model-path> \
     <product-design-image> \
     /Users/jdy/Downloads/耳环整理图/generated/<product-id>/<model-slug>[_<scope>] \
     [product-worn-image]
   ```
   For Codex imagegen, this reference preparation is still useful for stable local paths, but the prepared images must also be loaded with `view_image` before the `image_gen` call.

6. Read `references/prompt-templates.md`. Use the earring templates for earring-only products; for other jewelry types, adapt the view plan before prompting. Fill prompts with:
   - model description from the selected model reference,
   - exact product structure from the product image,
   - product-to-body scale, wearing position, and attachment notes from the product wearing-scale reference when available,
   - output directory for each view.

7. Generate each view separately. A single view must not block the whole batch forever; use the retry and failure-record rules below before moving on.
   - OpenCLI route command shape:
     ```bash
     opencli chatgpt image "$prompt" \
       --image "<out-root>/refs/selected-model.jpg,<out-root>/refs/product-design.jpg,<out-root>/refs/product-worn.jpg" \
       --op "<out-root>/<view-dir>" \
       --timeout 360 \
       --window foreground \
       --site-session ephemeral \
       --keep-tab false \
       --trace retain-on-failure \
       -f json
     ```
     - If no valid `product-worn.jpg` exists, omit only that third path and state in the prompt that Reference 3 is not attached.
     - Retry each view up to 3 total attempts before marking that view failed.
     - If the command exits with `EMPTY_RESULT`, no output PNG, or a timeout while the trace screenshot shows ChatGPT is still generating, do not ask jdy to intervene. Wait briefly, then retry the same view with a longer timeout and `--trace retain-on-failure`.
     - If a retry starts a fresh generation instead of retrieving the in-progress result, accept that duplicate cost as part of automation; validate only the final saved PNGs and discard bad candidates.
   - Codex imagegen route:
     - Before the first `image_gen` call for a product, use `view_image` on the prepared selected model, product design, and product wearing-scale reference when it is available and usable.
     - Call built-in `image_gen` once per view, with a prompt that labels the role of each visible reference.
     - After each generation, locate the newly saved file under `$CODEX_HOME/generated_images/...` and copy the accepted PNG into `<out-root>/final/` with the stable view filename.
     - Do not apply OpenCLI-style pacing delays after successful Codex imagegen calls. Only pause briefly when retrying a transient tool failure.
     - Do not overwrite an existing OpenCLI final set. Use a route-specific root such as `<model-slug>_codex`, unless jdy explicitly asks to overwrite.
     - If the result fails validation, retry that single view with a targeted prompt. If it still fails after the allowed attempts, write a failure record and continue.
   - For either route, if all attempts fail for one view, write a failure record and continue with the next view or next product. Do not stop the batch unless the failure is global, such as missing required local product files, logged-out ChatGPT for OpenCLI, broken OpenCLI doctor status, or repeated tool-level failure across multiple products.
   - Save failure records under `<out-root>/failures/` with one Markdown file per failed view. Include product id, view name, route, attempt count, prompt summary, selected reference paths, tool exit status or imagegen error, trace summary path if available, screenshot path if available, and the next action taken.

8. Validate every generated PNG before accepting it:
   - Run `file` and `sips -g pixelWidth -g pixelHeight`.
   - Use `view_image` to inspect the image.
   - Compare against Reference 1 (`selected-model.jpg`): confirm the output keeps the selected fictional model's general face type, skin tone, hair styling, makeup restraint, outfit mood, and studio tone. Reject heavy model-identity drift.
   - Compare against Reference 2 (`product-design.jpg`): confirm the product category, silhouette, metal color, stones, pearls, crystals, hoops, studs, links, chains, drops, pendants, symmetry, and finish remain recognizable and are not simplified into another design.
   - Compare against Reference 3 (`product-worn.jpg`) when attached: confirm the product-to-body scale, wearing position, attachment point, angle, drop length, and proportion follow the wearing reference while not copying that reference's model identity, face, hair, clothing, lighting, background, or unrelated jewelry.
   - Confirm the product is physically worn correctly: earrings must connect to the earlobe, ear hole, or ear clip area without floating, sinking into skin, or attaching to the wrong part of the ear; necklaces, bracelets, and rings must sit on the correct body part with realistic contact and scale.
   - Confirm: same model feel, product is the focus, product structure is recognizable, no text/logo/watermark, no extra jewelry.
   - For earring front views, both ears and both earrings must be visible. For necklace or set views, the key product pieces must be fully visible and not hidden by hair, clothing, or pose.
   - If a result is wrong, retry that single view with a targeted prompt; do not regenerate the whole product set unless necessary.

9. Copy accepted PNGs to `final/` with stable names. For earring-only products, use:
   ```bash
   cp <half-front-png> "<out-root>/final/01-half-front-single-ear.png"
   cp <side-closeup-png> "<out-root>/final/02-side-single-ear-closeup.png"
   cp <front-both-png> "<out-root>/final/03-front-both-ears.png"
   ```
   For necklace or mixed jewelry sets, use the filenames from the product-specific view plan.

10. For a long batch, report concise progress after each product:
   - completed product id,
   - final paths,
   - any quality caveat that needs jdy's decision.

## Exception Paths

- If `opencli doctor` fails: fix browser/daemon/extension connectivity before generating.
- If ChatGPT requires login: stop and ask jdy to log in because this is a global batch blocker.
- If `opencli chatgpt image` saves only uploaded references, returns `EMPTY_RESULT`, or exits while ChatGPT is still analyzing images:
  - do not ask for manual download or manual browser intervention;
  - inspect the trace summary and screenshot to classify whether ChatGPT is still generating, the page is logged out, the adapter is confused, or the generation actually failed;
  - retry the same view automatically up to 3 total attempts, increasing timeout when the screenshot shows generation is still in progress;
  - if one view still fails after all attempts, save a failure record under `<out-root>/failures/` and continue with the next view or product;
  - stop the batch only for global blockers such as login loss, broken `opencli doctor`, or repeated adapter-level failure across products;
  - use `opencli-autofix` only if it is an adapter issue.
- If ChatGPT web shows rate limiting such as `请求过于频繁`, `请稍等几分钟后再重试`, `rate limit`, `too frequent`, or traces show repeated `403 POST https://chatgpt.com/backend-api/f/conversation/prepare`:
  - treat it as a global pacing limit, not a product-quality failure;
  - do not keep firing immediate retries, because that worsens the limit and can make following products fail too;
  - enter a long cooldown, normally 20-30 minutes, then resume from checkpoint;
  - when resuming, skip existing valid `final/` images and continue only missing views;
  - add steady pacing for long batches, such as a delay after each successful image and a longer delay after each completed product.
- Known adapter failure mode from this workflow: uploaded user reference images can be mistaken for generated images, and Chinese UI text such as `正在分析` / `停止回答` must count as still generating. If this returns, patch only the trace-indicated `adapterSourcePath`.
- For long OpenCLI batches, use `--site-session ephemeral --keep-tab false` by default to reduce cross-product context contamination and stale-tab reuse. Treat `stale page identity` and `Could not find node with given id` as transient browser-state errors: dismiss the modal if needed, wait briefly, and retry before marking a view failed.
- If traces or output show `403` from ChatGPT conversation endpoints, `unexpected_content_type`, HTML refresh content such as `360`, or visible rate-limit text, treat it as global pacing pressure. Do not repeatedly fire immediate retries; wait, then resume from checkpoint.
- If Codex imagegen returns no usable image, saves only under `$CODEX_HOME/generated_images/...`, or the workspace copy step fails:
  - first locate the newest generated image under `$CODEX_HOME/generated_images/...` and verify whether generation actually succeeded;
  - if the generated image is usable, copy it into `<out-root>/final/` with the stable filename and continue;
  - if there is no new usable image, retry that single view with the same references and a more explicit prompt;
  - if the image exists but fails content validation, retry only that view with a targeted correction prompt;
  - do not enter an OpenCLI-style long cooldown for Codex imagegen unless the tool itself explicitly reports a persistent account or service limit;
  - if all attempts fail, save a failure record under `<out-root>/failures/` and continue with the next view or product.

## Quality Bar

Reject or retry outputs where:
- the product design changes into another product type,
- key product details disappear, such as stone, pendant, chain, flower, clasp, drop, or setting,
- the product does not match Reference 2's structure or material details closely enough for ecommerce use,
- the product-to-body scale, wearing position, attachment point, or drop length conflicts with Reference 3 when a wearing reference was attached,
- an earring floats, clips to the wrong ear area, sinks into skin, or is not visibly attached to the lobe, ear hole, or ear clip position,
- required paired pieces are hidden, such as one earring in a front earring view or the necklace in a set view,
- the face dominates so strongly that the product is secondary,
- text, logo, watermark, bag, or unrequested extra accessories appear,
- the model identity drifts heavily within the same product set.
