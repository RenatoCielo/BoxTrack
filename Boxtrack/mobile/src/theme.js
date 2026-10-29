export const colors = {
  ink: '#19191c',
  inkSoft: '#626269',
  canvas: '#f1f1f3',
  paper: '#ffffff',
  line: '#dedee3',
  dark: '#151518',
  darkSoft: '#202024',
  red: '#c51f35',
  redDark: '#9c1628',
  redSoft: '#fff1f3',
  redLine: '#efd2d7',
  green: '#1f7a4d',
  greenSoft: '#edf5ef',
  greenLine: '#d4e4da',
  gold: '#a67825',
  goldSoft: '#fbf4e4',
  sky: '#485a72',
  skySoft: '#eef1f5',
  white: '#ffffff',
  primaryText: '#ffffff',
  accentText: '#ffffff'
};

function validHex(value, fallback) {
  return /^#[0-9a-f]{6}$/i.test(value || '') ? value : fallback;
}

function contrastColor(hex) {
  const channels = hex.slice(1).match(/.{2}/g).map((part) => parseInt(part, 16) / 255);
  const luminance = channels.map((channel) => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4)
    .reduce((sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index], 0);
  return luminance > 0.42 ? '#161616' : '#ffffff';
}

export function applyClubBranding(club) {
  colors.red = validHex(club?.primary_color, '#c51f35');
  colors.primaryText = contrastColor(colors.red);
  colors.dark = validHex(club?.accent_color, '#151518');
  colors.accentText = contrastColor(colors.dark);
  font.eyebrow.color = colors.red;
}

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 };
export const radius = { sm: 6, md: 10, lg: 14, pill: 999 };

export const font = {
  title: { fontSize: 22, fontWeight: '800', color: colors.ink },
  heading: { fontSize: 17, fontWeight: '700', color: colors.ink },
  body: { fontSize: 14, color: colors.ink },
  small: { fontSize: 12, color: colors.inkSoft },
  eyebrow: { fontSize: 11, fontWeight: '700', letterSpacing: 1.2, color: colors.red }
};

export const shadow = {
  shadowColor: '#000',
  shadowOpacity: 0.06,
  shadowRadius: 8,
  shadowOffset: { width: 0, height: 2 },
  elevation: 2
};
