# Face separation 0.3.0 generation prompts

Mode: built-in image_gen.imagegen, transparent_background=true. Raw PNGs unchanged. Paired/atlas pieces are separated and positioned non-destructively in SVG project data. The eye-white prompt below is recovered verbatim from the prior interrupted turn's tool call; that generated PNG was preserved and reused.

## Eye-white underpaint

Use case: precise-object-edit
Asset type: SIRO Live2D preparation / paired EYE-WHITE UNDERPAINT, genuine transparent PNG.
Input is the approved-direction SIRO front head. Keep the original 1254x1254 canvas and the two eyes in their original original locations, not enlarged or centered as a new illustration. Viewer-left eye centered around (475,685), viewer-right around (777,680).
Return ONLY the complete two almond-shaped sclera whites of the original anime eyes, with the same white-to-soft-gray shading and shape. Remove the teal irises, pupils and specular highlights, FILLING their entire previously occupied region with continuous opaque eye white. The eye whites must be solid uninterrupted surfaces under the future movable irises: no iris-shaped holes, no transparent pupils, no clipping around eyelids. Include modest hidden white overlap just beyond the original lid edges so blinking masks can cover it. No upper/lower lash ink, no eyebrows, no skin, no hair or face.
Precisely retain the original left/right eye shapes and placement, including their slight asymmetry. Each white is a separate disconnected shape on the otherwise empty transparent canvas. No text, no frames, no checkerboard pixels, no new eyes, no shadows outside the white shape. The goal is a technical UNDERPAINT layer, not a finished pair of eyes. Do not draw irises or pupil marks.

## Irises

Use case: precise-object-edit
Asset type: SIRO eye material / TWO COMPLETE IRIS DISCS with pupil and highlight, transparent RGBA PNG.
Use the supplied SIRO original head as the identity/color reference. Keep its 1254x1254 canvas. Return only the two teal iris discs from the eyes, each reconstructed as a COMPLETE round-to-slightly-oval disc including the portion normally hidden behind the upper/lower eyelid. Each disc contains its original dark central pupil, subtle teal radial shading and small white specular highlights; iris, pupil and highlights remain one movable texture unit in this prototype.
No eye whites, no lash lines or eyelids, no eyebrows, no skin, hair, nose or mouth. No almond-shaped cutouts or flat clipped upper edges: the irises must be complete filled discs so they can move behind an independent eyelid aperture. No transparent pupil holes. Match SIRO's muted blue-green hue, no intense neon or new sparkle design. Preserve the slight difference between her left and right iris.
Keep the two discs at original eye positions roughly (475,685) and (777,680), approximately 90-105 pixels wide and 120 pixels tall each, on an otherwise empty genuine transparent 1254x1254 canvas. Do not enlarge or center the discs in the frame. No detached outside sparkles, labels, checkerboard texture, glow or cast shadow. Fully drawn iris interiors, alpha zero outside the two discs.

## Lid contours

Use case: precise-object-edit
Asset type: SIRO material separation / upper and lower EYELID LASH CONTOURS only.
Reference is SIRO's original straight-on head, 1254x1254 canvas. Preserve the character's exact two eye shapes and brown-black anime lash style, including the subtle left/right asymmetry. Return ONLY the upper eyelid/lash contour for each eye, and the thin lower eyelid contour for each eye, in the original eye positions centered near (475,685) and (777,680). Keep the original natural gentle expression; do not add exaggerated eyeliner.
Four disconnected stroke groups total: viewer-left upper lashes; viewer-left lower rim; viewer-right upper lashes; viewer-right lower rim. Keep upper and lower groups visibly separated by empty transparent space; do not connect the eye corners into a closed almond ring. Upper lashes include their original dark taper and a small natural lid crease just above them. Lower rims are thin warm-brown lines, no dark under-eye bags. Remove ALL sclera whites, teal irises/pupils/highlights, eyebrows, skin and blush, hair, nose, mouth and neck. The eye interiors and surrounding areas must be alpha zero, not skin-colored fills.
Keep unchanged original 1254x1254 canvas and do not center, enlarge or move the isolated eye shapes. No labels, background, checkerboard pixels, glow or shadows. This is an editable part source for eyelid movement, not a complete face or painted eyes.

## Closed lids

Use case: precise-object-edit
Asset type: SIRO eye material / TWO CLOSED EYELID LINES, transparent RGBA PNG.
Reference is SIRO's original gentle adult anime face. Produce only the two relaxed fully-closed eyelid curves with their short tapered outer eyelashes. Keep the same warm dark-brown lash color and original eye widths/asymmetry. These are neutral natural blink-closed eyes, not a happy squeezed expression, not a squint or angry frown. No open eye outlines.
Original 1254x1254 canvas, viewer-left line approximately x355..560 around y685, viewer-right line x685..900 around y680. Keep the small eyelash fan on the outer corners. No iris, pupil, sclera white, skin, brows, lid skin patches, nose, mouth, hair, face silhouette or background. Only two thin curved lash marks and otherwise genuine alpha-zero transparency. Do not enlarge or recenter the isolated lines. No labels, checkerboard texture, glow or cast shadow.

## Mouth internals

Use case: stylized-concept
Asset type: SIRO Live2D mouth material separation atlas, real transparent RGBA PNG, 1254x1254 square.
Use the supplied SIRO face ONLY for the restrained clean anime rendering style; do NOT draw a face, lips, head or finished mouth. Create exactly THREE separate technical mouth-interior pieces in a vertical column, with large transparent gaps between them, no labels.
TOP piece centered approximately (627,350): a complete dark warm burgundy mouth-cavity ellipse, about 240 pixels wide and 150 high, smoothly filled and subtly shaded, unbroken interior with no holes, NO teeth and NO tongue baked into it. This hidden base will be revealed through a mouth aperture.
MIDDLE piece centered approximately (627,650): only a narrow natural upper-teeth strip, warm off-white, about 220 pixels wide and 55 high, slightly curved, no individual-tooth black divisions, no lips/gums or mouth background. Complete upper-teeth underpaint with transparent outside.
BOTTOM piece centered approximately (627,950): only a small rounded muted pink tongue surface, about 190 pixels wide and 100 high, a subtle central crease and soft cel shading, no mouth background, no lips or teeth. Complete solid tongue patch with transparent outside.
Exactly three isolated pieces in these top/middle/bottom bands, no duplicated mouths, no human skin, no lower jaw, no mannequin. Preserve gentle non-realistic anime style suitable for a small talking character. No cutouts in the dark cavity, no letter shapes, gore, gloss, saliva or exaggerated detail. No outlines around the whole atlas, no checkerboard texture, no text, glow or cast shadows. Transparent background between all three components and outside them. These parts will be placed independently in an editable source project.

## Lip edges

Use case: stylized-concept
Asset type: SIRO mouth material / SEPARATE UPPER AND LOWER LIP EDGE ATLAS, transparent RGBA PNG.
Use the supplied SIRO original face for the same thin warm-brown anime line quality and gentle small-mouth design. Do not draw a face or a complete mouth.
Make exactly TWO separate delicate contour pieces on an otherwise empty 1254x1254 transparent canvas, arranged vertically with generous empty space:
TOP at center (627,420): the upper lip edge only, a very shallow inverted-U arch approximately 270px wide, center rising only slightly above the ends, fine warm dark-brown stroke with softly tapered corners; no moustache shape or thick lipstick.
BOTTOM at center (627,830): the lower lip edge only, a shallow U-shaped curve approximately 270px wide, center a little lower than the corners, fine warm-brown stroke and a minimal natural pale lip highlight just beneath the center if needed.
No connection between upper and lower pieces, no mouth-cavity fill, teeth, tongue, pink lipstick, skin-colored patches, nose, chin, eyes or hair. These are small natural anime mouth-edge textures for independent opening/closing, not a human-realistic lip illustration. Keep both pieces fully inside their own top/bottom bands. Alpha zero outside the two contours. No labels, checkerboard pixels, glow, shadows or text.

## Additional lower-lid request — no output

Use case: precise-object-edit
Asset type: SIRO material separation / LOWER EYELID CONTOUR PAIR ONLY.
Use the supplied SIRO head for the eye expression and lash color, and the paired eye-white underpaint for the almond shapes. Draw ONLY the two delicate LOWER eyelid lines that trace the bottom rims of those eye whites. Thin warm dark-brown anime contours with lightly tapered outer ends, calm natural open eyes. No upper eyelashes or lid crease, no iris, no pupil, no white eye fill, no eyebrow, face skin, under-eye shading or tear bags.
Use an unchanged 1254x1254 transparent canvas; viewer-left lower contour roughly x385..560 around y720, viewer-right roughly x690..865 around y712. Each line should be a continuous shallow U curve, not a collection of short dashes or a thick eyeliner ring. Keep modest natural asymmetry and match the original SIRO linework. Do not enlarge, recenter or add extra detached strokes. Exactly two isolated thin curves, rest of canvas alpha zero. No highlights, text, checkerboard pixels, glow or background.

The image service rejected this extra request (moderation_blocked); no output was produced or counted as completed. Existing contours were retained as partial lower rims. No CLI fallback or retry to bypass the rejection was performed.
