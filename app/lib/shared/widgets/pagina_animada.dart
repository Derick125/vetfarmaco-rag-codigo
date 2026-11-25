import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

/// Duração das transições entre telas (`docs/FRONTEND_SPEC.md` §25).
const duracaoTransicaoTela = Duration(milliseconds: 220);

/// Página de rota com transição curta: *fade* e deslize lateral de 4%.
///
/// A tela é construída no primeiro quadro, como numa rota comum; a transição
/// roda por cima e nunca atrasa o início de uma consulta nem a telemetria.
/// Com `MediaQuery.disableAnimations`, não há transição.
CustomTransitionPage<void> paginaAnimada({
  required GoRouterState state,
  required Widget child,
}) => CustomTransitionPage<void>(
  key: state.pageKey,
  child: child,
  transitionDuration: duracaoTransicaoTela,
  reverseTransitionDuration: duracaoTransicaoTela,
  transitionsBuilder: (context, animacao, secundaria, filho) {
    if (MediaQuery.disableAnimationsOf(context)) return filho;
    final curva = CurvedAnimation(parent: animacao, curve: Curves.easeOut);
    return FadeTransition(
      opacity: curva,
      child: SlideTransition(
        position: Tween(
          begin: const Offset(0.04, 0),
          end: Offset.zero,
        ).animate(curva),
        child: filho,
      ),
    );
  },
);
