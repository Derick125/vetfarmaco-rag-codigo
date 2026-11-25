import 'package:app/core/theme/cores.dart';
import 'package:flutter/material.dart';

/// Tipo de segmento do trilho (`docs/FRONTEND_SPEC.md` §3).
enum TipoTrilho {
  /// Sólido verde: o parágrafo tem citação validada.
  ancorado,

  /// Hachurado âmbar: o parágrafo não tem citação.
  semLastro,

  /// Sólido vermelho: alerta de segurança.
  alerta,
}

/// Trilho vertical de 3 px à esquerda de um parágrafo.
///
/// O risco nunca vai só na cor: a forma também muda (sólido × hachurado) e
/// quem usa o trilho acrescenta a palavra correspondente.
class TrilhoEvidencia extends StatelessWidget {
  /// Cria o trilho em volta de [child].
  const new({required this.tipo, required this.child, super.key});

  /// Tipo do segmento.
  final TipoTrilho tipo;

  /// Conteúdo ao lado do trilho.
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ExcludeSemantics(
            child: CustomPaint(
              size: const Size(3, double.infinity),
              painter: _PintorTrilho(tipo, switch (tipo) {
                TipoTrilho.ancorado => context.cores.ancorado,
                TipoTrilho.semLastro => context.cores.iodo,
                TipoTrilho.alerta => context.cores.contra,
              }),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(child: child),
        ],
      ),
    );
  }
}

class _PintorTrilho extends CustomPainter {
  const new(this.tipo, this.cor);

  final TipoTrilho tipo;
  final Color cor;

  @override
  void paint(Canvas canvas, Size size) {
    final tinta = Paint()..color = cor;
    if (tipo != TipoTrilho.semLastro) {
      canvas.drawRect(Offset.zero & size, tinta);
      return;
    }
    // Hachura: traços de 4 px com 3 px de intervalo.
    for (var y = 0.0; y < size.height; y += 7) {
      canvas.drawRect(
        Rect.fromLTWH(0, y, size.width, 4.0.clamp(0, size.height - y)),
        tinta,
      );
    }
  }

  @override
  bool shouldRepaint(_PintorTrilho antigo) =>
      antigo.tipo != tipo || antigo.cor != cor;
}
