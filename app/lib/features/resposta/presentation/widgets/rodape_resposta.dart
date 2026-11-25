import 'package:app/core/theme/cores.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:app/features/resposta/presentation/texto_resposta.dart';
import 'package:flutter/material.dart';

/// Rodapé da resposta: a linha `Confiança … · modelo · data · tempos` do
/// roteiro, sempre visível e idêntica, e, se houver, detalhes técnicos
/// recolhíveis (`docs/FRONTEND_SPEC.md` §24).
class RodapeResposta extends StatefulWidget {
  /// Cria o rodapé de [fim].
  const new({
    required this.fim,
    this.geradaEm,
    this.incompleta = false,
    super.key,
  });

  /// Evento `fim` da resposta.
  final EventoFim fim;

  /// Quando o `fim` chegou.
  final DateTime? geradaEm;

  /// A conexão caiu no meio.
  final bool incompleta;

  @override
  State<RodapeResposta> createState() => _RodapeRespostaState();
}

class _RodapeRespostaState extends State<RodapeResposta> {
  bool _aberto = false;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    final detalhes = detalhesRodape(widget.fim);
    final linha = Text(
      rodapeResposta(
        fim: widget.fim,
        geradaEm: widget.geradaEm,
        incompleta: widget.incompleta,
      ),
      style: tema.bodySmall,
    );
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Divider(color: context.cores.rule),
          if (detalhes.isEmpty)
            linha
          else
            Semantics(
              button: true,
              expanded: _aberto,
              label: 'Detalhes da resposta',
              child: InkWell(
                onTap: () => setState(() => _aberto = !_aberto),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(minHeight: 48),
                  child: Row(
                    children: [
                      Expanded(child: linha),
                      Icon(
                        _aberto ? Icons.expand_less : Icons.expand_more,
                        color: context.cores.inkMuted,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          AnimatedSize(
            duration: MediaQuery.disableAnimationsOf(context)
                ? Duration.zero
                : const Duration(milliseconds: 150),
            alignment: Alignment.topCenter,
            child: _aberto
                ? Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        for (final d in detalhes)
                          Text(d, style: tema.bodySmall),
                      ],
                    ),
                  )
                : const SizedBox(width: double.infinity),
          ),
        ],
      ),
    );
  }
}
