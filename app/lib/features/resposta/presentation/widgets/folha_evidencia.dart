import 'package:app/core/theme/cores.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:app/features/resposta/presentation/widgets/trecho_serifado.dart';
import 'package:app/shared/widgets/pagina_animada.dart';
import 'package:flutter/material.dart';

/// Abre a [FolhaEvidencia] de [citacao] sobre a resposta, sem perder o
/// contexto (`docs/FRONTEND_SPEC.md` §11).
Future<void> abrirFolhaEvidencia(BuildContext context, Citacao citacao) =>
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: context.cores.surface,
      // Desliza de baixo em 220 ms; sem animação se o sistema pedir
      // (`docs/FRONTEND_SPEC.md` §25).
      sheetAnimationStyle: MediaQuery.disableAnimationsOf(context)
          ? AnimationStyle.noAnimation
          : const AnimationStyle(
              duration: duracaoTransicaoTela,
              reverseDuration: Duration(milliseconds: 180),
            ),
      builder: (_) => FolhaEvidencia(citacao: citacao),
    );

/// Trecho literal que sustenta uma afirmação, com a proveniência completa.
class FolhaEvidencia extends StatelessWidget {
  /// Cria a folha de [citacao].
  const new({required this.citacao, super.key});

  /// Citação exibida.
  final Citacao citacao;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.6,
      minChildSize: 0.35,
      maxChildSize: 0.95,
      builder: (context, controle) => ListView(
        controller: controle,
        padding: const EdgeInsets.all(24),
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Trecho recuperado ${citacao.indice}',
                  style: tema.titleLarge,
                ),
              ),
              IconButton(
                tooltip: 'Fechar',
                constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                icon: const Icon(Icons.close),
                onPressed: () => Navigator.of(context).maybePop(),
              ),
            ],
          ),
          const SizedBox(height: 12),
          TrechoSerifado(citacao.trecho),
          const SizedBox(height: 24),
          Divider(color: context.cores.rule),
          _Metadado(rotulo: 'Fonte', valor: citacao.fonte),
          if (citacao.capitulo != null)
            _Metadado(rotulo: 'Capítulo', valor: citacao.capitulo!),
          if (citacao.pagina != null)
            _Metadado(rotulo: 'Página', valor: '${citacao.pagina}'),
          _Metadado(rotulo: 'chunk_id', valor: citacao.chunkId, mono: true),
        ],
      ),
    );
  }
}

class _Metadado extends StatelessWidget {
  const new({required this.rotulo, required this.valor, this.mono = false});

  final String rotulo;
  final String valor;
  final bool mono;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Wrap(
        spacing: 12,
        children: [
          Text(rotulo, style: tema.bodySmall),
          SelectableText(
            valor,
            style: tema.bodyMedium?.copyWith(
              fontFamily: mono ? 'monospace' : null,
            ),
          ),
        ],
      ),
    );
  }
}
