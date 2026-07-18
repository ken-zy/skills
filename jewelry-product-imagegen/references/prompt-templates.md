# Prompt Templates

Use these as starting points, not a rigid rule for every jewelry type.

- For earring-only products, use the three earring templates below.
- For necklace, bracelet, ring, or mixed jewelry sets, first define product-appropriate views and adapt the composition lines. Keep the same model/reference/product constraints.
- The requested generation scope is authoritative. If the current run is earring-only, prompts must explicitly exclude necklaces, bracelets, rings, bags, and other accessories. If the current run is necklace-only, prompts must explicitly exclude earrings and unrelated accessories. For sets, include only the requested set pieces.

Fill `<MODEL_DESCRIPTION>` and `<PRODUCT_DESCRIPTION>` for each product. Keep prompts direct and product-focused.

Always label attached reference roles inside the prompt:

- Reference 1: selected model reference. Use only for the fictional model's overall feel, face type, skin tone, hair, makeup, restrained expression, styling mood, and studio taste. It does not define the jewelry product.
- Reference 2: product design reference, usually a white-background, flat, or clean product shot. Use as the exact product truth for category, shape, structure, material, color, stone, clasp, chain, pendant, flower, drop, symmetry, and finish.
- Reference 3: product wearing-scale reference. Use only for product-to-body scale, wearing position, attachment point, angle, drop length, and proportion adaptation. Do not copy its model identity, face, styling, lighting, background, or unrelated jewelry.

Attach Reference 3 by default when a matching, usable wearing reference exists. If Reference 3 is not available or is unsuitable, remove that line and state that scale should be realistic for the product category.

## Earring 1. Half-Front Single Ear

```text
Generate a premium ecommerce jewelry model photo using the attached references.
Reference 1 is the selected model reference. Use only for the same fictional model feel and styling: <MODEL_DESCRIPTION>.
Reference 2 is the product design reference. Use it as the exact earring design truth: <PRODUCT_DESCRIPTION>.
Reference 3 is the product wearing-scale reference. Use it only for earring-to-ear scale, lobe attachment position, drop length, and wearing angle. Do not copy the model, face, styling, lighting, background, or unrelated jewelry from Reference 3.
Preserve the exact earring structure clearly.

Composition: half-front single-ear wearing image. The model turns slightly so one ear is fully visible and wearing one earring. Crop from upper chest to head. Face is partially included, calm, understated, and not dominant. The earring is the main commercial subject: sharp, bright, near the center-right of the frame, large enough to inspect details, realistic scale, clean attachment to the earlobe. The earring must be physically worn on the lobe, ear hole, or ear clip position, not floating, not sinking into the skin, and not attached to the wrong ear area.

No logo, no text, no watermark, no other jewelry, no ring, no necklace, no extra accessories. Do not change the earring into a different design. Photorealistic refined ecommerce editorial, vertical 4:5.
```

## Earring 2. Side Single-Ear Close-Up

```text
Generate a premium ecommerce jewelry close-up using the attached references.
Reference 1 is the selected model reference. Use only for the same fictional model feel and styling: <MODEL_DESCRIPTION>.
Reference 2 is the product design reference. Use it as the exact earring design truth: <PRODUCT_DESCRIPTION>.
Reference 3 is the product wearing-scale reference. Use it only for earring-to-ear scale, lobe attachment position, drop length, and wearing angle. Do not copy the model, face, styling, lighting, background, or unrelated jewelry from Reference 3.
Preserve the full earring structure and material details.

Composition: side-profile single-ear close-up. Show one ear fully visible with hair pulled back. Crop close around ear, cheek edge, jawline, neck, and a small part of shoulder. Reduce facial-feature dominance: keep eyes and lips outside the frame when possible, or cropped and visually subdued when included. The model's face should function as a quiet wearing context, not the subject. The earring is the hero: near the visual center, sharp focus, high clarity, realistic scale, full product visible, clean attachment to the lobe. The earring must be physically worn on the lobe, ear hole, or ear clip position, not floating, not sinking into the skin, and not attached to the wrong ear area.

Use warm soft studio light, shallow depth of field, refined ecommerce editorial. No logo, no text, no watermark, no other jewelry, no ring, no necklace, no extra accessories. Do not change the earring into a different design. Vertical 4:5.
```

## Earring 3. Front Both Ears

```text
Generate a premium ecommerce jewelry model photo using the attached references.
Reference 1 is the selected model reference. Use only for the same fictional model feel and styling: <MODEL_DESCRIPTION>.
Reference 2 is the product design reference. Use it as the exact earring pair design truth: each ear wears the same product, with this exact structure: <PRODUCT_DESCRIPTION>.
Reference 3 is the product wearing-scale reference. Use it only for earring-to-ear scale, lobe attachment position, drop length, and wearing angle. Do not copy the model, face, styling, lighting, background, or unrelated jewelry from Reference 3.
Preserve the pair structure clearly and symmetrically.

Composition: front-facing or near-front double-ear wearing image. The model faces camera with both ears visible and hair pulled back behind both ears. Crop from collarbone or upper chest to head. Face is calm and refined but not too attention-grabbing. Earrings are the commercial focus: sharp, bright, complete on both sides, realistic size, unobstructed by hair. Both earrings must be physically worn on the lobes, ear holes, or ear clip positions, not floating, not sinking into the skin, and not attached to the wrong ear area.

Keep the background simple and low-saturation. No logo, no text, no watermark, no other jewelry, no necklace, no ring, no extra accessories. Do not change the earrings into a different design. Photorealistic refined ecommerce editorial, vertical 4:5.
```

## Adapting For Necklaces Or Mixed Sets

For a necklace-only product, prefer views such as:

```text
01-front-necklace-wearing.png: front bust portrait, necklace fully visible on neckline and collarbone.
02-three-quarter-necklace-wearing.png: three-quarter bust portrait, pendant/chain catches light, face subdued.
03-necklace-detail.png: close crop from lower face to collarbone, pendant or chain detail is the hero.
```

For an earring + necklace set, prefer views such as:

```text
01-front-set-wearing.png: front bust portrait showing necklace and both earrings together.
02-side-earring-closeup.png: side close-up for one earring, necklace only if naturally visible.
03-necklace-detail.png: collarbone crop focused on necklace detail, face subdued.
```
