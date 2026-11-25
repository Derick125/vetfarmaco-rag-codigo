import 'package:flutter/material.dart';

/// Brilho próprio para esqueletos de carregamento, sem pacote externo
/// (`docs/FRONTEND_SPEC.md` §25).
///
/// Uma faixa clara de 1,2 s percorre o [child]. Com
/// `MediaQuery.disableAnimations`, o esqueleto fica estático.
class Brilho extends StatefulWidget {
  /// Cria o brilho sobre [child].
  const new({required this.child, super.key});

  /// Esqueleto sobre o qual a faixa passa.
  final Widget child;

  @override
  State<Brilho> createState() => _BrilhoState();
}

class _BrilhoState extends State<Brilho> with SingleTickerProviderStateMixin {
  late final AnimationController _controle = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1200),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context)) {
      _controle.stop();
    } else if (!_controle.isAnimating) {
      _controle.repeat();
    }
  }

  @override
  void dispose() {
    _controle.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (MediaQuery.disableAnimationsOf(context)) return widget.child;
    return AnimatedBuilder(
      animation: _controle,
      child: widget.child,
      builder: (context, filho) => ShaderMask(
        blendMode: BlendMode.srcATop,
        shaderCallback: (area) {
          final x = -1 + 3 * _controle.value;
          return LinearGradient(
            begin: Alignment(x - 1, 0),
            end: Alignment(x, 0),
            colors: const [
              Color(0x00FFFFFF),
              Color(0x99FFFFFF),
              Color(0x00FFFFFF),
            ],
          ).createShader(area);
        },
        child: filho,
      ),
    );
  }
}
