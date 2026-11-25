import 'package:app/core/theme/tokens.dart';
import 'package:flutter/material.dart';

/// Cores do design system que mudam entre o tema claro e o escuro
/// (`docs/FRONTEND_SPEC.md` §23).
///
/// O significado das cores não muda: `iodo` é cautela, `contra` é
/// contraindicação, `ancorado` é evidência. Blocos de alerta sólidos, com
/// texto branco, e a marca usam as cores fixas de [Tokens] nos dois temas.
@immutable
class CoresVetFarmaco extends ThemeExtension<CoresVetFarmaco> {
  /// Cria um conjunto de cores.
  const new({
    required this.paper,
    required this.surface,
    required this.ink,
    required this.inkMuted,
    required this.rule,
    required this.metileno,
    required this.sobreMetileno,
    required this.ancorado,
    required this.iodo,
    required this.contra,
  });

  /// Tema claro: os valores de [Tokens].
  static const claro = CoresVetFarmaco(
    paper: Tokens.paper,
    surface: Tokens.surface,
    ink: Tokens.ink,
    inkMuted: Tokens.inkMuted,
    rule: Tokens.rule,
    metileno: Tokens.metileno,
    sobreMetileno: Colors.white,
    ancorado: Tokens.ancorado,
    iodo: Tokens.iodo,
    contra: Tokens.contra,
  );

  /// Tema escuro: contrastes calculados no `FRONTEND_SPEC.md` §23.
  static const escuro = CoresVetFarmaco(
    paper: Color(0xFF101614),
    surface: Color(0xFF1A2220),
    ink: Color(0xFFE6ECE9),
    inkMuted: Color(0xFFA2B0AA),
    rule: Color(0xFF3A4743),
    metileno: Color(0xFF86C1DE),
    sobreMetileno: Color(0xFF101614),
    ancorado: Color(0xFF86C7A2),
    iodo: Color(0xFFE3A862),
    contra: Color(0xFFF28B93),
  );

  /// Fundo da tela.
  final Color paper;

  /// Superfícies elevadas (folhas, campos).
  final Color surface;

  /// Texto principal.
  final Color ink;

  /// Texto secundário e metadados.
  final Color inkMuted;

  /// Traços estruturais.
  final Color rule;

  /// Ação primária e links (azul de metileno).
  final Color metileno;

  /// Texto e ícone sobre um fundo [metileno].
  final Color sobreMetileno;

  /// Evidência confirmada.
  final Color ancorado;

  /// Cautela.
  final Color iodo;

  /// Contraindicação.
  final Color contra;

  @override
  CoresVetFarmaco copyWith({
    Color? paper,
    Color? surface,
    Color? ink,
    Color? inkMuted,
    Color? rule,
    Color? metileno,
    Color? sobreMetileno,
    Color? ancorado,
    Color? iodo,
    Color? contra,
  }) => CoresVetFarmaco(
    paper: paper ?? this.paper,
    surface: surface ?? this.surface,
    ink: ink ?? this.ink,
    inkMuted: inkMuted ?? this.inkMuted,
    rule: rule ?? this.rule,
    metileno: metileno ?? this.metileno,
    sobreMetileno: sobreMetileno ?? this.sobreMetileno,
    ancorado: ancorado ?? this.ancorado,
    iodo: iodo ?? this.iodo,
    contra: contra ?? this.contra,
  );

  @override
  CoresVetFarmaco lerp(CoresVetFarmaco? other, double t) {
    if (other == null) return this;
    return CoresVetFarmaco(
      paper: Color.lerp(paper, other.paper, t)!,
      surface: Color.lerp(surface, other.surface, t)!,
      ink: Color.lerp(ink, other.ink, t)!,
      inkMuted: Color.lerp(inkMuted, other.inkMuted, t)!,
      rule: Color.lerp(rule, other.rule, t)!,
      metileno: Color.lerp(metileno, other.metileno, t)!,
      sobreMetileno: Color.lerp(sobreMetileno, other.sobreMetileno, t)!,
      ancorado: Color.lerp(ancorado, other.ancorado, t)!,
      iodo: Color.lerp(iodo, other.iodo, t)!,
      contra: Color.lerp(contra, other.contra, t)!,
    );
  }
}

/// Acesso às [CoresVetFarmaco] do tema; sem a extensão, usa o tema claro.
extension CoresNoContexto on BuildContext {
  /// Cores do tema atual.
  CoresVetFarmaco get cores =>
      Theme.of(this).extension<CoresVetFarmaco>() ?? CoresVetFarmaco.claro;
}
