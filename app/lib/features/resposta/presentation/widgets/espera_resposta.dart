import 'package:app/core/theme/cores.dart';
import 'package:app/shared/widgets/brilho.dart';
import 'package:flutter/material.dart';

/// Espera até o primeiro parágrafo: indicador de duas etapas e esqueleto
/// (`docs/FRONTEND_SPEC.md` §24).
///
/// As etapas seguem os estados reais da resposta: a 1 vale até o evento
/// `recuperacao` ([chunks] ainda nulo); a 2, até o primeiro `paragrafo`. Os
/// textos são os do `ROTEIRO_MODO_AVIAO.md`.
class EsperaResposta extends StatelessWidget {
  /// Cria a espera; [chunks] é o número de trechos recuperados, se já veio.
  const new({required this.chunks, super.key});

  /// Trechos recuperados, depois do evento `recuperacao`.
  final int? chunks;

  @override
  Widget build(BuildContext context) {
    final etapa = chunks == null ? 1 : 2;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Semantics(
          label: 'Etapa $etapa de 2',
          child: ExcludeSemantics(
            child: Row(
              children: [
                const Expanded(child: _Segmento(ativo: true)),
                const SizedBox(width: 8),
                Expanded(child: _Segmento(ativo: etapa == 2)),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Semantics(
          liveRegion: true,
          child: Text(
            chunks == null
                ? 'Buscando na literatura…'
                : '$chunks trechos recuperados. Redigindo…',
          ),
        ),
        const SizedBox(height: 16),
        const ExcludeSemantics(child: _Esqueleto()),
      ],
    );
  }
}

class _Segmento extends StatelessWidget {
  const new({required this.ativo});

  final bool ativo;

  @override
  Widget build(BuildContext context) => AnimatedContainer(
    duration: MediaQuery.disableAnimationsOf(context)
        ? Duration.zero
        : const Duration(milliseconds: 120),
    height: 4,
    decoration: BoxDecoration(
      color: ativo ? context.cores.metileno : context.cores.rule,
      borderRadius: BorderRadius.circular(2),
    ),
  );
}

class _Esqueleto extends StatelessWidget {
  const new();

  @override
  Widget build(BuildContext context) => const Brilho(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _Barra(fator: 1),
        SizedBox(height: 10),
        _Barra(fator: 0.92),
        SizedBox(height: 10),
        _Barra(fator: 0.6),
      ],
    ),
  );
}

class _Barra extends StatelessWidget {
  const new({required this.fator});

  final double fator;

  @override
  Widget build(BuildContext context) => FractionallySizedBox(
    widthFactor: fator,
    child: Container(
      height: 14,
      decoration: BoxDecoration(
        color: context.cores.rule,
        borderRadius: BorderRadius.circular(4),
      ),
    ),
  );
}
