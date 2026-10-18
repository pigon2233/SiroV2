# Material-study generation prompts

Built-in image_gen.imagegen edits; transparent_background=true. Original pixels are retained in PNG files. The SVG only stores editable layer placement.

## Front master

Use case: identity-preserve
Asset type: SIRO production-art preparation, single full-body front master PNG with real transparency.
Input image: approved SIRO reference sheet version 0.2.0. Use ONLY the leftmost full-body FRONT character as the edit target and identity source; ignore the other views, portraits, stool, notebook and swatches.
Primary request: extract and redraw a clean, high-resolution SINGLE full-body front A-pose master of exactly that approved character, centered on a portrait 1024x1536 canvas, isolated with a genuine transparent background. Feet fully visible and grounded at the same baseline, head fully visible, generous margin. Arms slightly away from torso, hands open relaxed, shoulders level, face straight toward camera, no perspective twist. Preserve her exact silver-gray bob with asymmetrical side part, teal eyes, character-left navy rectangular clip, warm adult face, cream open cardigan with pockets and ribbed hems, mist-blue round-neck top, restrained straight navy culotte shorts with two leg openings, opaque dark tights and flat navy ankle boots. Keep the approved restrained hip/shorts silhouette; do not widen hips or create an hourglass waist. Maintain existing adult body proportions, hair length, cardigan length, leg length and outfit details. No redesign or new accessories.
Art quality: crisp clean anime lineart, restrained cel shading, sRGB-like palette, all fingers and ankle boots coherent, no fragments of other views. Clothing/limb junctions must be clear for future material separation. Do not pretend to supply layers; this is a flat FRONT reference master only. No cast shadow, floor, white matte, checkerboard pixels, labels, swatches, watermark, glow or background. Preserve genuine alpha transparency, clean edges, no white halo.

## Head master

Use case: identity-preserve
Asset type: SIRO head master for material separation, RGBA PNG, square 1024x1024.
Input: the same approved SIRO front A-pose character. Extract and enlarge ONLY her head plus short visible neck, directly facing the viewer. Preserve the adult face exactly: silver-gray asymmetrical bob, character-left navy rectangular clip (viewer-right), teal eyes, tiny relaxed smile, same chin, brows, hairline and existing anime linework. No redesign, no added accessories. Reference only this one head.
Composition for later aligned layer separation: square 1024x1024 canvas. Head is centered at x512; entire outer hair silhouette fits approximately x140..884 and y70..880. Chin around y730, neck base around y935. Hair clip around viewer-right temple. Hair, ears and neck fully inside frame. No shoulders, cardigan, chest, body, other poses or sheets. Neutral straight-on front, head level with eyes on the same horizontal line. Hair retains the side-swept fringe and slightly wavy bob ends, with closed complete shapes useful for separation.
Clean crisp cel-shaded anime artwork, accurate reference colors, no extra texture. Genuine transparent background, alpha zero outside the actual head and neck; no drop shadows, halo, atmospheric vignette, ground, checkerboard pixels, labels or watermark. Character interior near opaque. This is a single flat head reference, not a rig or a layered file.

## Face underpaint

Use case: precise-object-edit
Asset type: SIRO head material-separation prototype / FACE UNDERPAINT PNG.
Input image: the supplied SIRO head master. This is the exact canvas and alignment reference. Keep output on the SAME 1254x1254 canvas, do not zoom, shift, recenter or resize the face or neck.
Change only the layer contents: produce ONLY her complete SKIN head, ears and neck underpaint. Remove ALL silver hair and ALL hairclip pixels. Reconstruct a natural complete bald scalp and the forehead hidden behind the original bangs, with smooth skin-colored filling and the same original anime contour/shading. Keep the exact cheek, chin, ear and neck geometry, position and colors from the reference. This is a technical hidden surface, not a new character.
Also remove the painted eyes (eyelids/eyelashes, sclera/irises/pupils/highlights), eyebrows and mouth marks; fill these regions with smooth normal face skin so future independent features can overlay them. Preserve the small nose shape/shading and natural facial blush. A calm featureless animation base, no wounds or uncanny texture. Do not leave holes, sockets, transparency or outlines where the eyes/brows/mouth were. Complete full skin surface under the hair. The visible outer ears and ear roots must be fully filled.
Only the head/ears/neck skin is opaque; all hair, clip, shoulders, background and other areas must be alpha zero. No hair stubble, no wig outline, no labels, no fake checkerboard, no glow or shadows. Preserve original face anchors, ear positions, chin and neck base exactly. Real transparent RGBA. No other objects.

## Hair group

Use case: precise-object-edit
Asset type: SIRO material-separation prototype / HAIR GROUP foreground overlay.
Input: the supplied original complete SIRO head master. Keep the EXACT 1254x1254 canvas, original hair geometry and position. Do not zoom, shift, resize or recenter anything.
Return ONLY the existing silver-gray hair and its navy rectangular hairclip, as a genuine transparent RGBA overlay. Preserve every existing strand and highlight of the complete bob, including back silhouette, curled ends, left/right side locks, side-swept front bangs, top parting and the clip. Preserve the shape of all inner openings where the face, ears and neck show through. Remove all skin, scalp, ears, eyes, eyebrows, nose, mouth, neck, shoulders and background, replacing them with alpha zero, not black/white/skin fill. Any face feature visible through strands must be removed; the hair strands themselves stay. Do NOT paint hair across the face opening. Do not produce a wig on a mannequin or show a face. No new unseen hair surfaces in this foreground group; preserve original visible hair only. Clip stays in exact viewer-right temple position.
The goal is that placing this unchanged overlay at x0/y0 above the face-underpaint base restores the original hair arrangement. This is a grouped prototype layer, not individually separated strands. No labels, frame, checkerboard pixels, glow or drop shadow. Exact original alignment and clean genuine alpha are more important than redesigning the art.

## Facial features group

Use case: precise-object-edit
Asset type: SIRO material-separation prototype / FACIAL FEATURES grouped overlay, genuine transparent PNG.
Input: the supplied complete SIRO head master. Preserve the exact input canvas 1254x1254 and exact feature positions. Do not move, scale, recenter or redesign anything.
Return ONLY the two eyes including upper/lower lash lines, whites, teal irises, pupils and highlights; the two eyebrows; and the small neutral smile line. Preserve those exact original features in their original coordinates and original size. Where hair covers part of the character-right brow (viewer-left), reconstruct the missing brow arc naturally in place because the hair overlay will cover it again. The facial-feature group should consist of several disconnected shapes located exactly where they were in the reference.
Remove all hair/clip, skin, face silhouette, ears, nose, blush, cheek shading, chin, neck and background to alpha zero. NO skin-colored rectangular patches around the eyes or mouth. Keep inner white eye areas opaque but everything outside feature shapes genuinely transparent. No mannequin, no face background, no ghost head or hair outline, no added features. Do not replace transparency with black or white. No labels, frame, drop shadow, glow, checkerboard texture or watermark. This is a grouped alignment prototype, not individually rigged eyes or mouth. The unchanged overlay at x0/y0 must restore the original eye/brow/smile locations above the face-underpaint layer.
