import 'package:app/core/theme/app_theme.dart';
import 'package:app/core/theme/cores.dart';
import 'package:flutter/material.dart';

/// Texto literal do acervo, em serifa — só trechos recuperados usam este
/// estilo, o que separa visualmente a evidência da afirmação.
class TrechoSerifado extends StatelessWidget {
  /// Cria o trecho.
  const new(this.texto, {super.key});

  /// Texto literal do acervo.
  final String texto;

  @override
  Widget build(BuildContext context) => SelectableText(
    texto,
    style: estiloEvidencia.copyWith(color: context.cores.ink),
  );
}
