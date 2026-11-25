import 'dart:async';

import 'package:app/core/theme/cores.dart';
import 'package:app/shared/widgets/icone_vetfarmaco.dart';
import 'package:app/shared/widgets/ilustracao_vetfarmaco.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

/// `/inicio` — tela inicial: marca, ilustração e atalhos
/// (`docs/FRONTEND_SPEC.md` §28).
///
/// Depois da abertura e da introdução o app cai aqui. Fica **fora** do caminho
/// medido: o caminho começa em `Nova consulta` (`/consulta`), que não tem
/// imagem nem animação. Não há estado nem cubit: só navegação.
class InicioPage extends StatelessWidget {
  /// Cria a tela.
  const new({super.key});

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    final cores = context.cores;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 24),
              children: [
                const _Cabecalho(),
                const SizedBox(height: 20),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      FilledButton.icon(
                        style: FilledButton.styleFrom(
                          minimumSize: const Size.fromHeight(60),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(14),
                          ),
                          textStyle: tema.titleMedium?.copyWith(fontSize: 18),
                        ),
                        onPressed: () => unawaited(context.push('/consulta')),
                        icon: const Icon(Icons.add),
                        label: const Text('Nova consulta'),
                      ),
                      const SizedBox(height: 12),
                      _Atalho(
                        icone: Icons.history,
                        titulo: 'Histórico',
                        subtitulo: 'Respostas salvas, para ler sem rede',
                        aoTocar: () => unawaited(context.push('/historico')),
                      ),
                      const SizedBox(height: 12),
                      _Atalho(
                        icone: Icons.settings_outlined,
                        titulo: 'Ajustes',
                        subtitulo: 'Endereço do back-end e rede da campanha',
                        aoTocar: () => unawaited(context.push('/ajustes')),
                      ),
                      const SizedBox(height: 12),
                      _Atalho(
                        icone: Icons.info_outline,
                        titulo: 'Sobre o aplicativo',
                        subtitulo: 'Fontes, limites e privacidade',
                        aoTocar: () => unawaited(context.push('/sobre')),
                      ),
                      const SizedBox(height: 28),
                      Text(
                        'Prova de conceito acadêmica. Não emite prescrição e '
                        'não substitui o julgamento clínico do médico '
                        'veterinário.',
                        style: tema.bodySmall?.copyWith(color: cores.inkMuted),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Faixa do topo: ícone, nome, frase de apresentação e a ilustração pequena.
class _Cabecalho extends StatelessWidget {
  const new();

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    final escuro = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
      decoration: BoxDecoration(
        color: const Color(0xFF86C7A2).withValues(alpha: escuro ? 0.10 : 0.20),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const ExcludeSemantics(child: IconeVetFarmaco(tamanho: 44)),
              const SizedBox(width: 12),
              Expanded(
                child: Semantics(
                  header: true,
                  child: Text('VetFarmaco', style: tema.headlineSmall),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 6, right: 8),
                  child: Text(
                    'Apoio à decisão farmacológica para cães e gatos.',
                    style: tema.bodyLarge?.copyWith(
                      color: context.cores.inkMuted,
                    ),
                  ),
                ),
              ),
              const IlustracaoVetFarmaco(cena: Cena.inicioCabecalho),
            ],
          ),
        ],
      ),
    );
  }
}

/// Atalho em linha: ícone, título, descrição e seta; alvo de toque ≥ 48 dp.
class _Atalho extends StatelessWidget {
  const new({
    required this.icone,
    required this.titulo,
    required this.subtitulo,
    required this.aoTocar,
  });

  final IconData icone;
  final String titulo;
  final String subtitulo;
  final VoidCallback aoTocar;

  @override
  Widget build(BuildContext context) {
    final cores = context.cores;
    final tema = Theme.of(context).textTheme;
    final forma = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(14),
      side: BorderSide(color: cores.rule),
    );
    return Material(
      color: cores.surface,
      shape: forma,
      child: InkWell(
        customBorder: forma,
        onTap: aoTocar,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 64),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            child: Row(
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: cores.metileno.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(icone, color: cores.metileno),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(titulo, style: tema.titleMedium),
                      Text(
                        subtitulo,
                        style: tema.bodySmall?.copyWith(color: cores.inkMuted),
                      ),
                    ],
                  ),
                ),
                Icon(Icons.chevron_right, color: cores.inkMuted),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
