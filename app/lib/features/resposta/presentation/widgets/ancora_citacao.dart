import 'package:app/core/theme/cores.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:flutter/material.dart';

/// Descrição falada da citação, ex.: `Spinosa et al. (2017), capítulo 22`.
String descricaoCitacao(Citacao c) {
  final partes = [
    c.fonte,
    if (c.capitulo != null) 'capítulo ${c.capitulo}',
    if (c.pagina != null) 'página ${c.pagina}',
  ];
  return partes.join(', ');
}

/// Âncora numerada de uma citação, com alvo de toque de 48×48 dp.
class AncoraCitacao extends StatelessWidget {
  /// Cria a âncora de [citacao]; [aoTocar] é chamado com ela.
  const new({
    required this.citacao,
    this.aoTocar,
    this.compacta = false,
    super.key,
  });

  /// Citação representada.
  final Citacao citacao;

  /// Abre o trecho; `null` desabilita o toque.
  final ValueChanged<Citacao>? aoTocar;

  /// Chip menor (22 dp), para a linha «Fonte:» do alerta; a área de toque
  /// continua de 48×48 dp.
  final bool compacta;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: aoTocar != null,
      label:
          'citação ${citacao.indice}, ${descricaoCitacao(citacao)}, '
          'abrir trecho',
      excludeSemantics: true,
      child: InkResponse(
        onTap: aoTocar == null ? null : () => aoTocar!(citacao),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
          child: Center(
            widthFactor: 1,
            heightFactor: 1,
            child: Container(
              constraints: BoxConstraints(minWidth: compacta ? 28 : 36),
              height: compacta ? 22 : 28,
              padding: EdgeInsets.symmetric(horizontal: compacta ? 6 : 8),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(compacta ? 11 : 14),
                color: context.cores.ancorado.withValues(alpha: 0.10),
                border: Border.all(color: context.cores.ancorado, width: 1.5),
              ),
              child: Center(
                widthFactor: 1,
                child: Text(
                  '${citacao.indice}',
                  style: TextStyle(
                    color: context.cores.ancorado,
                    fontWeight: FontWeight.w600,
                    fontSize: compacta ? 12 : 13,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
