import 'package:app/core/theme/cores.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/resposta/presentation/texto_resposta.dart';
import 'package:flutter/material.dart';

/// Pergunta do usuário em balão à direita, com chips de espécie, peso e
/// fármacos (`docs/FRONTEND_SPEC.md` §24).
///
/// Mostra a pergunta **já sanitizada**, a de [CorpoConsulta], que é a que foi
/// enviada — nunca o texto cru. A resposta do modelo não usa balão (§4).
class BalaoPergunta extends StatelessWidget {
  /// Cria o balão de [corpo].
  const new({required this.corpo, super.key});

  /// Consulta enviada.
  final CorpoConsulta corpo;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    final largura = MediaQuery.sizeOf(context).width;
    // Em fonte muito ampliada o balão ocupa a largura toda.
    final cheio = MediaQuery.textScalerOf(context).scale(16) > 24;
    final chips = <String>[
      ?corpo.especie,
      if (corpo.pesoKg != null) pesoEmKg(corpo.pesoKg!),
      ...corpo.farmacos,
      ...corpo.comorbidades,
    ];
    return Semantics(
      container: true,
      label: 'Sua pergunta: ${corpo.pergunta}',
      child: Align(
        alignment: Alignment.centerRight,
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxWidth: cheio ? double.infinity : largura * 0.85,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 12,
                ),
                decoration: BoxDecoration(
                  color: context.cores.metileno,
                  borderRadius: const BorderRadius.only(
                    topLeft: Radius.circular(12),
                    topRight: Radius.circular(12),
                    bottomLeft: Radius.circular(12),
                    bottomRight: Radius.circular(2),
                  ),
                ),
                child: ExcludeSemantics(
                  child: Text(
                    corpo.pergunta,
                    style: tema.bodyLarge?.copyWith(
                      color: context.cores.sobreMetileno,
                    ),
                  ),
                ),
              ),
              if (chips.isNotEmpty) ...[
                const SizedBox(height: 8),
                ExcludeSemantics(
                  child: Wrap(
                    alignment: WrapAlignment.end,
                    spacing: 8,
                    runSpacing: 8,
                    children: [for (final c in chips) _Chip(texto: c)],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Chip de leitura (sem toque) com um dado da consulta.
class _Chip extends StatelessWidget {
  const new({required this.texto});

  final String texto;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
    decoration: BoxDecoration(
      border: Border.all(color: context.cores.inkMuted),
      borderRadius: BorderRadius.circular(12),
    ),
    child: Text(
      texto,
      style: Theme.of(context).textTheme.bodySmall
          ?.copyWith(color: context.cores.inkMuted),
    ),
  );
}
