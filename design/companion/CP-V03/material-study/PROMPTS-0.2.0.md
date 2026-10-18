# Hair separation revision 0.2.0 prompts

Built-in image_gen.imagegen. Every edit uses the original head-master.png as reference and transparent_background=true. PNGs retained without pixel edits; layer placement/masks are editable SVG project data.

## Complete back-hair underpaint

Use case: precise-object-edit
Asset type: SIRO Live2D preparation / COMPLETE BACK-HAIR UNDERPAINT layer, real transparent PNG.
Input: original front-facing head master, 1254x1254 canvas. Maintain the exact canvas, head position, hair outer silhouette, front projection and hair color. Do NOT turn the character around or show a back-view head.
The user's correction is essential: the back-hair layer MUST NOT have ear-shaped holes or a face-shaped hole. Reconstruct the full hidden silver-gray hair volume BEHIND the scalp, face, BOTH EARS and upper neck. The central head area must be filled with coherent opaque hair underpainting; both areas where the ears were (roughly canvas x280..390 and x890..1000, y620..830) must contain complete hair, not transparency. This is the hidden support surface that a separate skin/ear layer will occlude. It should look like a complete soft bob-shaped mass of hair in the SAME front-view projection, solid across the middle with coherent hair strands, gently curling ends and natural strand shading. No interior voids cut around facial anatomy. Only small natural spaces BETWEEN separate outer curls at the outermost silhouette may be transparent.
Remove ALL face/skin, ears, eyes, eyebrows, nose, mouth, neck and the navy hair clip. The hair clip belongs to a separate front/side component and must not be baked into the back hair. Do not draw front bangs as a facial opening; just continuous background hair texture throughout the covered head region. Keep the original outer bob silhouette approximately x50..1205 and y60..1140 with ample overlap behind ears and jaw. Outside the hair volume is true alpha-zero transparency. No person, skin, mannequin, labels, checkerboard pixels, glow, drop shadows, transparent ear cutouts or background. Neutral cel shading matching the original.

## Front fringe

Use case: precise-object-edit
Asset type: SIRO Live2D preparation / FRONT FRINGE AND CROWN layer only, RGBA PNG.
Input is the original front-view head master on a 1254x1254 canvas. Keep the exact original positions, scale, head angle, hair parting, silver-gray color, highlights and cel linework. Do not recenter or enlarge the isolated piece.
Return ONLY the front hair cap/crown and side-swept forehead bangs. Preserve the top parting and broad diagonal sweep toward viewer-left from the original; include the short curved strands that end over the forehead/near the upper eyelid, but exclude the long hanging side locks, cheek-length side hair and curled bob ends around the ears/jaw. The front fringe should form one coherent filled hair piece rooted at the crown, with strand tips over the forehead; end near the temples/forehead instead of forming a full ring around a face. The separate back-hair layer will fill all hidden volume. Complete the fringe roots under the parting with small overlap, do not cut transparent anatomical ear-shaped notches.
Remove ALL face/skin/scalp, ears, eyes, eyebrows, nose, mouth, neck, navy hairclip, all back hair and both long side-hair panels. Everything outside this front-fringe/crown shape is true alpha-zero transparency. Exact same 1254x1254 layout: original crown around y60-300 and bang tips around y600-680; don't move the hair upward or toward center to fit it in a smaller bounding box. No face-shaped wig outline, no transparent holes inside the crown, no detached ghost features. No labels, checkerboard pixels, shadows, glow, text or watermark. This is a standalone foreground hair part with hidden root overlap, not a complete hairstyle.

## Character-left side hair

Use case: precise-object-edit
Asset type: SIRO Live2D hair material / CHARACTER-LEFT SIDE HAIR panel, with hidden underpainting.
Use the supplied original front-view head master. Character-left means the hair on VIEWER-RIGHT (the side where the navy clip is located). Produce ONLY that single side-hair panel. Do not flip or rotate the view. Keep silver-gray color, original fine cel linework, slightly wavy bob ends and natural side-lock direction.
The panel should be an uninterrupted opaque hair sheet from the upper side/crown root down past the ear toward the jaw-length curled ends. Reconstruct all hair hidden behind the ear and upper cheek; there must be NO anatomical ear-shaped notch or hole in this panel. It will be placed BEHIND the skin-and-ear layer in the editable project. Complete the roots so the front crown can overlap them cleanly. Do not include the broad diagonal forehead bangs, opposite side hair or full back hair mass.
IMPORTANT layout: unchanged 1254x1254 canvas, keep this panel in the VIEWER-RIGHT third of the original canvas, approximately x840..1220 and y180..1140, matching the original hair outline. Leave the rest of the canvas alpha zero. Do not enlarge the panel to fill the frame or center it. Remove all face/skin, ear, eyes, eyebrow, mouth, neck and navy hair clip. The clip will be its own layer. No ear-shaped transparent hole, skin-colored filling, empty central cutout, labels, fake checkerboard, glow or drop shadow. Real transparent RGBA outside the complete hair panel.

## Character-right side hair

Use case: precise-object-edit
Asset type: SIRO Live2D preparation / CHARACTER-RIGHT SIDE HAIR panel, genuine RGBA with hidden underpainting.
Reference is original front-facing SIRO head, 1254x1254 canvas. Character-right means VIEWER-LEFT, the side with the long side-swept hair and no navy clip. Return only the bob's long side-hair panel on that viewer-left side. Do not mirror the character-left panel; preserve the asymmetric original strands and curls.
Keep original canvas, scale, position, silver-gray color and fine anime cel shading. Panel extends from its upper crown/temple root down past ear toward jaw-length curled ends, approximately x50..390 and y200..1140. Complete the roots under the separate front fringe, and fill the hidden hair BEHIND the ear/upper cheek. It will sit behind the separate skin-and-ear layer. No transparent ear-shaped notch or anatomical ear hole; it must be a continuous hair panel with complete hidden overlap. Natural spaces between the few outside curl tips may remain transparent. Do NOT include the broad diagonal forehead bangs, top cap, opposite side hair or whole back-hair mass.
Leave the entire rest of the unchanged canvas alpha-zero transparent. Do not center, enlarge or move the isolated panel. Remove face/skin/scalp, ears, eyes, eyebrows, mouth, neck and all accessories. No new hairstyle, skin-colored patches, labels, fake checkerboard texture, shadow or glow. Preserve the intended front view, not a back view. Standalone complete side hair, not only the visible pixels remaining after an ear-shaped cutout.

## Character-left hair clip

Use case: precise-object-edit
Asset type: SIRO material separation / HAIR CLIP ONLY, transparent RGBA PNG.
From the supplied original 1254x1254 front-head image, isolate ONLY the existing small navy rectangular hairclip on character-left (viewer-right). Keep the original clip shape, bevel, blue highlight, tilt and exact original size and position, approximately x935..1030 and y400..550 on the original canvas. Leave the canvas size unchanged 1254x1254. Do not center, enlarge, duplicate, straighten or redesign the clip. All hair, skin, face, ears, eyes and background must be alpha-zero transparent. The clip has a complete opaque blue silhouette including the small edge normally overlapping hair; it contains no hair pixels. One disconnected small clip in its original location, otherwise an empty transparent canvas. No labels, shadow, glow, checkerboard pixels or watermark.
