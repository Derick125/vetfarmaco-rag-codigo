import 'dart:math' as math;

import 'package:app/core/theme/tokens.dart';
import 'package:flutter/material.dart';

/// Verde-evidência claro da metade direita da cápsula (`assets/brand/icone.svg`).
const _evidenciaClara = Color(0xFF86C7A2);

/// Ícone do app: cápsula com marca de pata, desenhado em código a partir de
/// `assets/brand/icone.svg` (`docs/FRONTEND_SPEC.md` §20, §27).
///
/// Até [limiteCompacto] dp usa só a cápsula ampliada, sem a pata.
class IconeVetFarmaco extends StatelessWidget {
  /// Cria o ícone com [tamanho] dp de lado.
  const new({required this.tamanho, this.circular = false, super.key});

  /// Tamanho máximo, em dp, em que o ícone perde a pata.
  static const limiteCompacto = 32.0;

  /// Lado do ícone, em dp.
  final double tamanho;

  /// `true` recorta em círculo (avatar); `false`, em quadrado arredondado.
  final bool circular;

  @override
  Widget build(BuildContext context) {
    final desenho = SizedBox.square(
      dimension: tamanho,
      child: CustomPaint(
        painter: PintorIconeVetFarmaco(compacto: tamanho <= limiteCompacto),
      ),
    );
    return ExcludeSemantics(
      child: circular
          ? ClipOval(child: desenho)
          : ClipRRect(
              borderRadius: BorderRadius.circular(tamanho * 0.22),
              child: desenho,
            ),
    );
  }
}

/// Avatar da resposta: o ícone em círculo (`docs/FRONTEND_SPEC.md` §24).
class AvatarVetFarmaco extends StatelessWidget {
  /// Cria o avatar com [tamanho] dp de lado.
  const new({this.tamanho = 32, super.key});

  /// Lado do avatar, em dp.
  final double tamanho;

  @override
  Widget build(BuildContext context) =>
      IconeVetFarmaco(tamanho: tamanho, circular: true);
}

/// Marca da abertura: ícone e nome (`docs/FRONTEND_SPEC.md` §20).
class MarcaVetFarmaco extends StatelessWidget {
  /// Cria a marca.
  const new({super.key});

  @override
  Widget build(BuildContext context) => Semantics(
    label: 'VetFarmaco',
    excludeSemantics: true,
    // Wrap: com fonte muito ampliada o nome desce para baixo do ícone.
    child: Wrap(
      alignment: WrapAlignment.center,
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 16,
      runSpacing: 8,
      children: [
        const IconeVetFarmaco(tamanho: 72),
        Text('VetFarmaco', style: Theme.of(context).textTheme.displaySmall),
      ],
    ),
  );
}

/// Pinta o ícone numa tela de 1024 × 1024, escalada para o tamanho do widget.
class PintorIconeVetFarmaco extends CustomPainter {
  /// Cria o pintor; [compacto] omite a pata e amplia a cápsula.
  const new({required this.compacto});

  /// Versão para 32 dp ou menos: só a cápsula.
  final bool compacto;

  @override
  void paint(Canvas canvas, Size size) {
    canvas
      ..scale(size.width / 1024)
      ..drawRect(
        const Rect.fromLTWH(0, 0, 1024, 1024),
        Paint()..color = Tokens.metileno,
      );
    _capsula(canvas);
    if (!compacto) _pata(canvas);
  }

  void _capsula(Canvas canvas) {
    final area = compacto
        ? const Rect.fromLTWH(112, 352, 800, 320)
        : const Rect.fromLTWH(212, 377, 600, 270);
    final capsula = RRect.fromRectAndRadius(
      area,
      Radius.circular(compacto ? 160 : 135),
    );
    final meio = compacto ? 8.0 : 4.0;
    canvas
      ..save()
      ..translate(512, 512)
      ..rotate(-math.pi / 4)
      ..translate(-512, -512)
      ..save()
      ..clipRect(Rect.fromLTRB(area.left, area.top, 512, area.bottom))
      ..drawRRect(capsula, Paint()..color = Tokens.paper)
      ..restore()
      ..save()
      ..clipRect(Rect.fromLTRB(512, area.top, area.right, area.bottom))
      ..drawRRect(capsula, Paint()..color = _evidenciaClara)
      ..restore()
      ..drawRect(
        Rect.fromLTWH(512 - meio, area.top, meio * 2, area.height),
        Paint()..color = Tokens.metileno,
      )
      ..restore();
  }

  void _pata(Canvas canvas) {
    final tinta = Paint()..color = Tokens.metileno;
    _elipse(canvas, tinta, 406, 650, 54, 42, 0);
    _elipse(canvas, tinta, 344, 598, 20, 27, -25);
    _elipse(canvas, tinta, 385, 566, 20, 28, -8);
    _elipse(canvas, tinta, 437, 566, 20, 28, 8);
    _elipse(canvas, tinta, 478, 598, 20, 27, 25);
  }

  void _elipse(
    Canvas canvas,
    Paint tinta,
    double cx,
    double cy,
    double rx,
    double ry,
    double graus,
  ) {
    canvas
      ..save()
      ..translate(cx, cy)
      ..rotate(graus * math.pi / 180)
      ..drawOval(
        Rect.fromCenter(center: Offset.zero, width: rx * 2, height: ry * 2),
        tinta,
      )
      ..restore();
  }

  @override
  bool shouldRepaint(PintorIconeVetFarmaco antigo) =>
      antigo.compacto != compacto;
}
