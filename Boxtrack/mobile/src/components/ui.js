import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radius, shadow, spacing } from '../theme';

export function Screen({ children, onRefresh, refreshing = false, title, subtitle, eyebrow, scroll = true, footer }) {
  const header = title ? (
    <View style={styles.header}>
      {eyebrow ? <Text style={font.eyebrow}>{eyebrow}</Text> : null}
      <Text style={font.title} accessibilityRole="header">{title}</Text>
      {subtitle ? <Text style={[font.small, { marginTop: 2 }]}>{subtitle}</Text> : null}
    </View>
  ) : null;
  return (
    <SafeAreaView style={styles.screen} edges={['top']}>
      {scroll ? (
        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.red} /> : undefined}
        >
          {header}
          {children}
        </ScrollView>
      ) : (
        <View style={styles.content}>
          {header}
          {children}
        </View>
      )}
      {footer}
    </SafeAreaView>
  );
}

export function Card({ children, style, tone }) {
  const toneStyle = tone === 'warn' ? styles.cardWarn : tone === 'bad' ? styles.cardBad : null;
  return <View style={[styles.card, toneStyle, style]}>{children}</View>;
}

export function SectionTitle({ children, action }) {
  return (
    <View style={styles.sectionTitle}>
      <Text style={font.heading}>{children}</Text>
      {action}
    </View>
  );
}

export function Button({ title, onPress, variant = 'primary', loading = false, disabled = false, icon, small, style, testID }) {
  const inactive = disabled || loading;
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityState={{ disabled: inactive, busy: loading }}
      disabled={inactive}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        small && styles.buttonSmall,
        variantStyles[variant],
        inactive && styles.buttonDisabled,
        pressed && !inactive && { opacity: 0.85 },
        style
      ]}
    >
      {loading ? (
        <ActivityIndicator color={variant === 'primary' || variant === 'danger' ? colors.white : colors.red} />
      ) : (
        <>
          {icon ? <Ionicons name={icon} size={small ? 14 : 16} color={textColors[variant]} style={{ marginRight: 6 }} /> : null}
          <Text style={[styles.buttonText, small && { fontSize: 13 }, { color: textColors[variant] }]}>{title}</Text>
        </>
      )}
    </Pressable>
  );
}

export function Field({ label, error, style, ...inputProps }) {
  return (
    <View style={[{ marginBottom: spacing.md }, style]}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      <TextInput
        placeholderTextColor="#9a9aa2"
        accessibilityLabel={label}
        {...inputProps}
        style={[styles.input, error && { borderColor: colors.red }, inputProps.multiline && { minHeight: 80, textAlignVertical: 'top' }]}
      />
      {error ? <Text style={styles.fieldError}>{error}</Text> : null}
    </View>
  );
}

const toneColors = {
  ok: [colors.greenSoft, colors.green],
  warn: [colors.goldSoft, colors.gold],
  bad: [colors.redSoft, colors.red],
  info: [colors.skySoft, colors.sky],
  neutral: ['#ececf0', colors.inkSoft]
};

export function Badge({ text, tone = 'neutral' }) {
  const [bg, fg] = toneColors[tone] || toneColors.neutral;
  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      <Text style={[styles.badgeText, { color: fg }]}>{text}</Text>
    </View>
  );
}

export function Banner({ type = 'error', children, onClose }) {
  if (!children) return null;
  const palette = type === 'success'
    ? { bg: colors.greenSoft, border: colors.greenLine, fg: colors.green }
    : type === 'warn'
      ? { bg: colors.goldSoft, border: '#ead9b0', fg: colors.gold }
      : { bg: colors.redSoft, border: colors.redLine, fg: colors.redDark };
  return (
    <View style={[styles.banner, { backgroundColor: palette.bg, borderColor: palette.border }]} accessibilityRole="alert">
      <Text style={{ color: palette.fg, flex: 1, fontSize: 13 }}>{children}</Text>
      {onClose ? (
        <Pressable onPress={onClose} accessibilityLabel="Cerrar aviso" hitSlop={10}>
          <Ionicons name="close" size={18} color={palette.fg} />
        </Pressable>
      ) : null}
    </View>
  );
}

export function EmptyState({ icon = 'file-tray-outline', title, message, action }) {
  return (
    <View style={styles.empty}>
      <Ionicons name={icon} size={36} color={colors.line} />
      <Text style={[font.heading, { marginTop: spacing.sm, textAlign: 'center' }]}>{title}</Text>
      {message ? <Text style={[font.small, { textAlign: 'center', marginTop: 4 }]}>{message}</Text> : null}
      {action ? <View style={{ marginTop: spacing.md }}>{action}</View> : null}
    </View>
  );
}

export function Loading({ text = 'Cargando…' }) {
  return (
    <View style={styles.loading}>
      <ActivityIndicator size="large" color={colors.red} />
      <Text style={[font.small, { marginTop: spacing.sm }]}>{text}</Text>
    </View>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <View style={styles.empty}>
      <Ionicons name="cloud-offline-outline" size={36} color={colors.red} />
      <Text style={[font.heading, { marginTop: spacing.sm, textAlign: 'center' }]}>No se pudo cargar</Text>
      <Text style={[font.small, { textAlign: 'center', marginTop: 4 }]}>{message}</Text>
      {onRetry ? <View style={{ marginTop: spacing.md }}><Button title="Reintentar" onPress={onRetry} variant="secondary" icon="refresh" /></View> : null}
    </View>
  );
}

// Renderiza carga / error / vacío / contenido con el resultado de useResource.
export function ResourceView({ resource, isEmpty, empty, children }) {
  if (resource.loading && resource.data === null) return <Loading />;
  if (resource.error && resource.data === null) return <ErrorState message={resource.error} onRetry={resource.reload} />;
  return (
    <>
      {resource.error ? <Banner>{resource.error}</Banner> : null}
      {isEmpty ? empty : children}
    </>
  );
}

export function KeyValue({ label, value }) {
  return (
    <View style={styles.kv}>
      <Text style={font.small}>{label}</Text>
      <Text style={[font.body, { flex: 1, textAlign: 'right', marginLeft: spacing.md }]}>{value ?? '—'}</Text>
    </View>
  );
}

export function Segmented({ options, value, onChange }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: spacing.md }} contentContainerStyle={{ gap: 8 }}>
      {options.map((option) => {
        const active = option.value === value;
        return (
          <Pressable
            key={option.value}
            onPress={() => onChange(option.value)}
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
            style={[styles.chip, active && styles.chipActive]}
          >
            <Text style={[styles.chipText, active && { color: colors.white }]}>{option.label}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const variantStyles = StyleSheet.create({
  primary: { backgroundColor: colors.red },
  secondary: { backgroundColor: colors.paper, borderWidth: 1, borderColor: colors.line },
  danger: { backgroundColor: colors.redDark },
  ghost: { backgroundColor: 'transparent' }
});
const textColors = { primary: colors.white, secondary: colors.ink, danger: colors.white, ghost: colors.red };

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.canvas },
  content: { padding: spacing.lg, paddingBottom: 40, flexGrow: 1 },
  header: { marginBottom: spacing.lg },
  card: { backgroundColor: colors.paper, borderRadius: radius.lg, padding: spacing.lg, marginBottom: spacing.md, ...shadow },
  cardWarn: { borderLeftWidth: 3, borderLeftColor: colors.gold },
  cardBad: { borderLeftWidth: 3, borderLeftColor: colors.red },
  sectionTitle: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.sm, marginTop: spacing.sm },
  button: { minHeight: 46, borderRadius: radius.md, paddingHorizontal: spacing.lg, flexDirection: 'row', alignItems: 'center', justifyContent: 'center' },
  buttonSmall: { minHeight: 38, paddingHorizontal: spacing.md },
  buttonDisabled: { opacity: 0.5 },
  buttonText: { fontSize: 15, fontWeight: '700' },
  label: { fontSize: 12, fontWeight: '700', color: colors.inkSoft, marginBottom: 6 },
  input: { minHeight: 46, borderWidth: 1, borderColor: colors.line, borderRadius: radius.md, paddingHorizontal: spacing.md, backgroundColor: colors.paper, fontSize: 15, color: colors.ink },
  fieldError: { color: colors.red, fontSize: 12, marginTop: 4 },
  badge: { alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 3, borderRadius: radius.pill },
  badgeText: { fontSize: 11, fontWeight: '700' },
  banner: { flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.md },
  empty: { alignItems: 'center', paddingVertical: 40, paddingHorizontal: spacing.xl },
  loading: { alignItems: 'center', paddingVertical: 60 },
  kv: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6 },
  chip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: radius.pill, backgroundColor: colors.paper, borderWidth: 1, borderColor: colors.line },
  chipActive: { backgroundColor: colors.red, borderColor: colors.red },
  chipText: { fontSize: 13, fontWeight: '600', color: colors.ink }
});
