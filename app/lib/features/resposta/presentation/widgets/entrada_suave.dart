import 'package:flutter/material.dart';

/// Entrada curta com *fade* e deslize, ao aparecer (`docs/FRONTEND_SPEC.md`
/// §24, §25).
///
/// É só visual: o filho já está na árvore de widgets no mesmo quadro em que o
/// estado muda, então a animação nunca atrasa evento, estado nem telemetria.
/// Sem efeito de digitação. Com `MediaQuery.disableAnimations`, não anima.
class EntradaSuave extends StatelessWidget {
  /// Cria a entrada de [child]; [deslocamento] é o deslize vertical inicial,
  /// em dp (positivo vem de baixo, negativo vem de cima).
  const new({
    required this.child,
    this.deslocamento = 8,
    this.duracao = const Duration(milliseconds: 180),
    super.key,
  });

  /// Conteúdo que entra.
  final Widget child;

  /// Deslocamento vertical inicial, em dp.
  final double deslocamento;

  /// Duração da entrada.
  final Duration duracao;

  @override
  Widget build(BuildContext context) {
    if (MediaQuery.disableAnimationsOf(context)) return child;
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: duracao,
      curve: Curves.easeOut,
      builder: (context, t, filho) => Opacity(
        opacity: t,
        child: Transform.translate(
          offset: Offset(0, (1 - t) * deslocamento),
          child: filho,
        ),
      ),
      child: child,
    );
  }
}
