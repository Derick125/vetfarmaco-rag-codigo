import 'dart:async';

import 'package:app/core/theme/cores.dart';
import 'package:app/features/onboarding/presentation/cubit/introducao_cubit.dart';
import 'package:app/features/onboarding/presentation/cubit/introducao_state.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:app/features/resposta/presentation/widgets/ancora_citacao.dart';
import 'package:app/features/resposta/presentation/widgets/trilho_evidencia.dart';
import 'package:app/shared/widgets/ilustracao_vetfarmaco.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

/// `/introducao` — três cartões de primeiro uso, mostrados uma vez, depois do
/// termo, e puláveis (`docs/FRONTEND_SPEC.md` §21).
class IntroducaoPage extends StatefulWidget {
  /// Cria a tela.
  const new({super.key});

  @override
  State<IntroducaoPage> createState() => _IntroducaoPageState();
}

class _IntroducaoPageState extends State<IntroducaoPage> {
  static const _total = 3;

  final _controle = PageController();
  int _pagina = 0;

  @override
  void initState() {
    super.initState();
    unawaited(context.read<IntroducaoCubit>().carregar());
  }

  @override
  void dispose() {
    _controle.dispose();
    super.dispose();
  }

  void _proximo() {
    if (_pagina == _total - 1) {
      unawaited(context.read<IntroducaoCubit>().concluir());
      return;
    }
    final proxima = _pagina + 1;
    if (MediaQuery.disableAnimationsOf(context)) {
      _controle.jumpToPage(proxima);
    } else {
      _controle.animateToPage(
        proxima,
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOut,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: BlocConsumer<IntroducaoCubit, IntroducaoState>(
          listener: (context, state) {
            if (state is IntroducaoJaVista || state is IntroducaoConcluida) {
              context.go('/inicio');
            }
          },
          builder: (context, state) {
            if (state is! IntroducaoExibindo) return const SizedBox.shrink();
            return Column(
              children: [
                Align(
                  alignment: Alignment.centerRight,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(0, 8, 16, 0),
                    child: TextButton(
                      style: TextButton.styleFrom(
                        minimumSize: const Size(48, 48),
                      ),
                      onPressed: () =>
                          unawaited(context.read<IntroducaoCubit>().concluir()),
                      child: const Text('Pular'),
                    ),
                  ),
                ),
                Expanded(
                  child: PageView(
                    controller: _controle,
                    onPageChanged: (p) => setState(() => _pagina = p),
                    children: const [
                      _Cartao(
                        visual: IlustracaoVetFarmaco(cena: Cena.introCartao1),
                        titulo: 'Consulta',
                        texto:
                            'Informe espécie, peso, fármacos e a pergunta '
                            'clínica. A resposta sai só dos trechos de '
                            'literatura recuperados, e cada consulta é '
                            'independente: o sistema não guarda a conversa.',
                      ),
                      _Cartao(
                        visual: _VisualTrilho(),
                        titulo: 'Trilho de evidência',
                        texto:
                            'O trilho à esquerda de cada parágrafo mostra o '
                            'lastro. Verde, com número: o parágrafo tem '
                            'citação, e tocar no número abre o trecho '
                            'original, em fonte com serifa. Hachurado: o '
                            'parágrafo não tem citação.',
                      ),
                      _Cartao(
                        visual: IlustracaoVetFarmaco(cena: Cena.introCartao3),
                        titulo: 'Modo offline',
                        texto:
                            'Respostas salvas ficam no aparelho e podem ser '
                            'relidas sem rede, com o selo de data. Uma '
                            'consulta nova precisa de conexão.',
                      ),
                    ],
                  ),
                ),
                _Indicador(pagina: _pagina, total: _total),
                Padding(
                  padding: const EdgeInsets.fromLTRB(24, 16, 24, 24),
                  child: FilledButton(
                    style: FilledButton.styleFrom(
                      minimumSize: const Size.fromHeight(48),
                    ),
                    onPressed: _proximo,
                    child: Text(_pagina == _total - 1 ? 'Começar' : 'Próximo'),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

/// Cartão de introdução: visual, título e texto.
class _Cartao extends StatelessWidget {
  const new({required this.visual, required this.titulo, required this.texto});

  final Widget visual;
  final String titulo;
  final String texto;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 480),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(child: visual),
              const SizedBox(height: 32),
              Text(titulo, style: tema.displaySmall),
              const SizedBox(height: 16),
              Text(texto, style: tema.bodyLarge),
            ],
          ),
        ),
      ),
    );
  }
}

/// Indicador de página, só leitura.
class _Indicador extends StatelessWidget {
  const new({required this.pagina, required this.total});

  final int pagina;
  final int total;

  @override
  Widget build(BuildContext context) {
    final duracao = MediaQuery.disableAnimationsOf(context)
        ? Duration.zero
        : const Duration(milliseconds: 150);
    return Semantics(
      label: 'Página ${pagina + 1} de $total',
      child: ExcludeSemantics(
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            for (var i = 0; i < total; i++)
              AnimatedContainer(
                duration: duracao,
                margin: const EdgeInsets.symmetric(horizontal: 4),
                width: i == pagina ? 24 : 8,
                height: 8,
                decoration: BoxDecoration(
                  color: i == pagina
                      ? context.cores.metileno
                      : context.cores.inkMuted,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Exemplo do trilho: um parágrafo com citação e um sem.
class _VisualTrilho extends StatelessWidget {
  const new();

  static const _exemplo = Citacao(
    chunkId: 'exemplo',
    indice: 1,
    trecho: 'Trecho de exemplo.',
    fonte: 'Exemplo',
  );

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    return ExcludeSemantics(
      child: SizedBox(
        width: 260,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TrilhoEvidencia(
              tipo: TipoTrilho.ancorado,
              child: Row(
                children: [
                  Expanded(
                    child: Text('Parágrafo com citação', style: tema.bodyLarge),
                  ),
                  const AncoraCitacao(citacao: _exemplo),
                ],
              ),
            ),
            const SizedBox(height: 16),
            TrilhoEvidencia(
              tipo: TipoTrilho.semLastro,
              child: Text('Parágrafo sem citação', style: tema.bodyLarge),
            ),
          ],
        ),
      ),
    );
  }
}
