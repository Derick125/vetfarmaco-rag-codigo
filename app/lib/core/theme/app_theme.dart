import 'package:app/core/theme/cores.dart';
import 'package:app/core/theme/tokens.dart';
import 'package:flutter/material.dart';

/// Família da interface e do texto gerado pelo modelo (IBM Plex Sans, OFL 1.1),
/// embarcada em `assets/fonts/`.
const familiaSans = 'IBMPlexSans';

/// Família exclusiva dos trechos literais do acervo (IBM Plex Serif, OFL 1.1).
const familiaSerif = 'IBMPlexSerif';

/// Tema claro do app — ver `docs/FRONTEND_SPEC.md` §17.
final ThemeData appTheme = _construirTema(
  cores: CoresVetFarmaco.claro,
  brilho: Brightness.light,
  secundarioContido: const Color(0xFFD3E4EC),
);

/// Tema escuro do app — ver `docs/FRONTEND_SPEC.md` §23.
final ThemeData temaEscuro = _construirTema(
  cores: CoresVetFarmaco.escuro,
  brilho: Brightness.dark,
  secundarioContido: const Color(0xFF254556),
);

ThemeData _construirTema({
  required CoresVetFarmaco cores,
  required Brightness brilho,
  required Color secundarioContido,
}) {
  final base = ThemeData(brightness: brilho).textTheme.apply(
    fontFamily: familiaSans,
    bodyColor: cores.ink,
    displayColor: cores.ink,
  );
  final esquema =
      (brilho == Brightness.light
              ? const ColorScheme.light()
              : const ColorScheme.dark())
          .copyWith(
            primary: cores.metileno,
            onPrimary: cores.sobreMetileno,
            secondary: cores.metileno,
            onSecondary: cores.sobreMetileno,
            secondaryContainer: secundarioContido,
            onSecondaryContainer: cores.ink,
            error: cores.contra,
            onError: cores.sobreMetileno,
            surface: cores.surface,
            onSurface: cores.ink,
            onSurfaceVariant: cores.inkMuted,
            outline: brilho == Brightness.light
                ? cores.inkMuted
                : const Color(0xFF6F7E78),
            outlineVariant: cores.rule,
          );
  final textos = _escalaTipografica(base, cores);
  final raio12 = RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(12),
  );
  final raio8 = BorderRadius.circular(8);
  return ThemeData(
    brightness: brilho,
    fontFamily: familiaSans,
    scaffoldBackgroundColor: cores.paper,
    colorScheme: esquema,
    extensions: [cores],
    dividerColor: cores.rule,
    appBarTheme: AppBarTheme(
      backgroundColor: cores.paper,
      foregroundColor: cores.ink,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: cores.surface,
      modalBackgroundColor: cores.surface,
      surfaceTintColor: Colors.transparent,
    ),
    textTheme: textos,
    // Acabamento: botões e cartões em raio 12, campos em raio 8, alvos de toque
    // de 48 dp ou mais (`docs/FRONTEND_SPEC.md` §18, §28).
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(48, 52),
        shape: raio12,
        textStyle: textos.labelLarge,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(48, 52),
        shape: raio12,
        textStyle: textos.labelLarge,
        side: BorderSide(color: cores.metileno, width: 1.5),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        minimumSize: const Size(48, 48),
        shape: raio12,
        textStyle: textos.labelLarge,
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      border: OutlineInputBorder(borderRadius: raio8),
      focusedBorder: OutlineInputBorder(
        borderRadius: raio8,
        borderSide: BorderSide(color: cores.metileno, width: 2),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
    ),
    chipTheme: ChipThemeData(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      labelStyle: textos.labelMedium,
      side: BorderSide(color: esquema.outline, width: 1.5),
    ),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: ButtonStyle(
        textStyle: WidgetStatePropertyAll(
          textos.labelMedium?.copyWith(fontSize: 16, height: 24 / 16),
        ),
        shape: WidgetStatePropertyAll(
          RoundedRectangleBorder(borderRadius: raio8),
        ),
      ),
    ),
  );
}

/// Escala tipográfica (razão ~1,25: 12 / 14 / 16 / 20 / 25 / 31; `docs/FRONTEND_SPEC.md`
/// §2): corpo em 16/24, rótulos e botões em semibold, metadados em 12/16.
TextTheme _escalaTipografica(TextTheme base, CoresVetFarmaco cores) {
  TextStyle e(double tamanho, double altura, FontWeight peso, {Color? cor}) =>
      TextStyle(
        fontFamily: familiaSans,
        fontSize: tamanho,
        height: altura / tamanho,
        fontWeight: peso,
        color: cor ?? cores.ink,
      );
  return base.copyWith(
    displaySmall: e(31, 38, FontWeight.w600),
    headlineSmall: e(25, 32, FontWeight.w600),
    titleLarge: e(20, 28, FontWeight.w600),
    titleMedium: e(16, 24, FontWeight.w600),
    titleSmall: e(14, 20, FontWeight.w600),
    bodyLarge: e(16, 24, FontWeight.w400),
    bodyMedium: e(14, 20, FontWeight.w400),
    bodySmall: e(12, 16, FontWeight.w400, cor: cores.inkMuted),
    labelLarge: e(16, 24, FontWeight.w600),
    labelMedium: e(14, 20, FontWeight.w500),
    labelSmall: e(12, 16, FontWeight.w500),
  );
}

/// Estilo exclusivo dos trechos recuperados do acervo.
///
/// A cor é a do tema; quem usa deve aplicar `context.cores.ink`.
const TextStyle estiloEvidencia = TextStyle(
  fontFamily: familiaSerif,
  fontSize: 16,
  height: 1.6,
  color: Tokens.ink,
);

/// Valores de dose: figuras tabulares.
const TextStyle estiloDose = TextStyle(
  fontFamily: familiaSans,
  fontSize: 16,
  fontFeatures: [FontFeature.tabularFigures()],
);
