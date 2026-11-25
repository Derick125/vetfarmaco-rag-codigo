import 'package:flutter/material.dart';

/// Tokens de cor e espaçamento do design system clínico.
///
/// Ver `docs/FRONTEND_SPEC.md` §2 e §17: a paleta vem do vocabulário material
/// da rotina veterinária, e cor de risco é semântica estrita — nunca
/// decorativa.
abstract final class Tokens {
  /// Fundo — branco de receituário, levemente esverdeado.
  static const paper = Color(0xFFF4F6F4);

  /// Superfícies elevadas (folhas, campos).
  static const surface = Color(0xFFFFFFFF);

  /// Texto principal — tinta verde-escura, não preto.
  static const ink = Color(0xFF1A211F);

  /// Texto secundário, metadados.
  static const inkMuted = Color(0xFF5A6663);

  /// Traços estruturais.
  static const rule = Color(0xFFD3DAD6);

  /// Ação primária, links, âncoras de citação (azul de metileno).
  static const metileno = Color(0xFF17506B);

  /// Evidência confirmada.
  static const ancorado = Color(0xFF2C6248);

  /// Cautela: ajuste de dose, uso extra-label (âmbar da povidona-iodo).
  static const iodo = Color(0xFFA65A15);

  /// Contraindicação absoluta.
  static const contra = Color(0xFF96131F);

  /// Escala de espaçamento em múltiplos de 4.
  static const espaco = [4.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0];
}
