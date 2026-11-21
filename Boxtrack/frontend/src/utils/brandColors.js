function parseHexColor(color) {
  if (!/^#[\da-f]{6}$/i.test(color || '')) return null;
  return [1, 3, 5].map((position) => parseInt(color.slice(position, position + 2), 16) / 255);
}

function linearize(channel) {
  return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
}

function relativeLuminance(rgb) {
  const [red, green, blue] = rgb.map(linearize);
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

export function brandColorOnLightSurface(color, fallback) {
  const rgb = parseHexColor(color);
  if (!rgb) return fallback;
  const luminance = relativeLuminance(rgb);
  if (1.05 / (luminance + 0.05) >= 4.5) return color;

  let low = 0;
  let high = 1;
  for (let iteration = 0; iteration < 24; iteration += 1) {
    const amount = (low + high) / 2;
    const darker = rgb.map((channel) => channel * (1 - amount));
    if (1.05 / (relativeLuminance(darker) + 0.05) >= 4.5) high = amount;
    else low = amount;
  }
  return `#${rgb.map((channel) => Math.round(channel * (1 - high) * 255).toString(16).padStart(2, '0')).join('')}`.toUpperCase();
}

export function brandSurfaceWithReadableText(color, fallback) {
  return brandColorOnLightSurface(color, fallback);
}
