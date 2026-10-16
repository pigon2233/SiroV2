/** Compute bounded native input rectangles from our own transparent WebView, never the screen. */
export function inputMask(pixels, width, height, stride, channels, step = 6) {
  if (![width, height, stride, channels, step].every(Number.isSafeInteger) || width < 1 || height < 1 || width > 4096 || height > 4096 || ![3, 4].includes(channels) || step < 1 || step > 16 || stride < width * channels || pixels.length < stride * height)
    throw new Error('Invalid desktop pixel geometry');
  const rectangles = [];
  let occupied = 0;
  for (let y = 0; y < height; y += step) {
    let begin = -1;
    for (let x = 0; x < width + step; x += step) {
      let hit = false;
      if (x < width) {
        for (let dy = 0; dy < step && y + dy < height && !hit; dy++)
          for (let dx = 0; dx < step && x + dx < width; dx++)
            if (channels < 4 || pixels[(y + dy) * stride + (x + dx) * channels + 3] > 28) { hit = true; break; }
      }
      if (hit && begin < 0) begin = x;
      if (!hit && begin >= 0) {
        const r = {x: begin, y, width: Math.min(x, width) - begin, height: Math.min(step, height - y)};
        rectangles.push(r); occupied += r.width * r.height; begin = -1;
      }
    }
  }
  return {rectangles, occupied};
}
