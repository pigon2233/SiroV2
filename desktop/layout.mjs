/** Keep the role and its existing conversation in disjoint, monitor-bounded areas. */
export function desktopLayout(scale, chat, workWidth, workHeight, controlsHeight = 132) {
    if (!Number.isFinite(scale) || scale < .6 || scale > 1.5 || typeof chat !== 'boolean' ||
        ![workWidth, workHeight].every(value => Number.isSafeInteger(value) && value >= 64) ||
        !Number.isSafeInteger(controlsHeight) || controlsHeight < 64 || controlsHeight > 320)
        throw new Error('Invalid desktop layout');
    // The pet pane is taller than the standing body: the transparent band above the head holds a
    // hand raised in a wave, so gestures are not cut off and the character keeps her size.
    const gap = 12, aspect = 640 / 360;
    const footer = Math.min(controlsHeight, Math.floor(workHeight / 2), chat && workWidth < 574 ? workHeight - Math.floor(workHeight * .36) - gap - 1 : workHeight);
    let availablePetHeight = Math.max(1, workHeight - footer);
    if (chat && workWidth < 574) availablePetHeight = Math.max(1, workHeight - footer - Math.floor(workHeight * .36) - gap);
    let petWidth = Math.max(1, Math.floor(Math.min(360 * scale, workWidth, availablePetHeight / aspect)));
    let petHeight = Math.max(1, Math.floor(petWidth * aspect));
    let paneWidth = Math.min(workWidth, Math.max(282, petWidth)), paneX = 0;
    let width = paneWidth, height = petHeight + footer, petX = Math.floor((paneWidth - petWidth) / 2);
    let chatX = paneWidth + gap, chatY = 8, chatWidth = 380, chatHeight = Math.max(1, height - 16);
    if (chat && workWidth >= 574) {
        petWidth = Math.min(petWidth, workWidth - 292);
        petHeight = Math.max(1, Math.floor(petWidth * aspect));
        paneWidth = Math.max(282, petWidth);
        petX = Math.floor((paneWidth - petWidth) / 2);
        chatX = paneWidth + gap;
        chatWidth = Math.min(380, workWidth - chatX);
        width = chatX + chatWidth;
        height = Math.min(workHeight, Math.max(petHeight + footer, 520));
        chatHeight = Math.max(1, height - 16);
    } else if (chat) {
        chatWidth = Math.min(380, workWidth);
        chatHeight = Math.max(1, Math.floor(workHeight * .36));
        width = Math.max(paneWidth, chatWidth);
        paneX = Math.floor((width - paneWidth) / 2);
        petX = paneX + Math.floor((paneWidth - petWidth) / 2);
        chatX = 0; chatY = petHeight + footer + gap;
        height = chatY + chatHeight;
    }
    return {width, height, petX, petWidth, petHeight, chatX, chatY, chatWidth, chatHeight,
        paneX, paneWidth, controlsY: petHeight + 10, scale: petWidth / 360};
}
