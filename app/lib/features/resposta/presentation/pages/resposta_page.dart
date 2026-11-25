import 'dart:async';

import 'package:app/core/theme/cores.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/historico/domain/resposta_salva.dart';
import 'package:app/features/resposta/domain/dose.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:app/features/resposta/presentation/cubit/resposta_cubit.dart';
import 'package:app/features/resposta/presentation/cubit/resposta_state.dart';
import 'package:app/features/resposta/presentation/texto_resposta.dart';
import 'package:app/features/resposta/presentation/widgets/ancora_citacao.dart';
import 'package:app/features/resposta/presentation/widgets/balao_pergunta.dart';
import 'package:app/features/resposta/presentation/widgets/cartao_alerta.dart';
import 'package:app/features/resposta/presentation/widgets/entrada_suave.dart';
import 'package:app/features/resposta/presentation/widgets/espera_resposta.dart';
import 'package:app/features/resposta/presentation/widgets/folha_evidencia.dart';
import 'package:app/features/resposta/presentation/widgets/rodape_resposta.dart';
import 'package:app/features/resposta/presentation/widgets/trecho_serifado.dart';
import 'package:app/features/resposta/presentation/widgets/trilho_evidencia.dart';
import 'package:app/shared/widgets/icone_vetfarmaco.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

/// `/consulta/:id` — resposta em SSE com proveniência visível
/// (`docs/FRONTEND_SPEC.md` §10).
class RespostaPage extends StatefulWidget {
  /// Cria a tela para [corpo].
  const new({required this.corpo, this.salva, this.aoAbrirCitacao, super.key});

  /// Consulta a enviar.
  final CorpoConsulta corpo;

  /// Resposta do histórico a exibir, sem consultar o servidor.
  final RespostaSalva? salva;

  /// Abre o trecho de uma citação; por padrão, a folha de evidência.
  final ValueChanged<Citacao>? aoAbrirCitacao;

  @override
  State<RespostaPage> createState() => _RespostaPageState();
}

class _RespostaPageState extends State<RespostaPage> {
  final ScrollController _rolagem = ScrollController();
  final GlobalKey _chaveLista = GlobalKey();
  final GlobalKey _chaveAlerta = GlobalKey();

  /// O cartão de alerta saiu da tela pela rolagem: mostra a barra compacta.
  bool _alertaFora = false;

  @override
  void initState() {
    super.initState();
    _rolagem.addListener(_aoRolar);
    final cubit = context.read<RespostaCubit>();
    final salva = widget.salva;
    unawaited(
      salva == null ? cubit.iniciar(widget.corpo) : cubit.exibirSalva(salva),
    );
  }

  @override
  void dispose() {
    _rolagem
      ..removeListener(_aoRolar)
      ..dispose();
    super.dispose();
  }

  /// O cartão é o primeiro item da lista: fora da tela quando a base dele fica
  /// acima do topo da lista, ou quando a lista já o descartou.
  bool _cartaoForaDaTela() {
    if (!_rolagem.hasClients) return false;
    final cartao = _chaveAlerta.currentContext?.findRenderObject();
    final lista = _chaveLista.currentContext?.findRenderObject();
    if (cartao is! RenderBox || !cartao.attached) return _rolagem.offset > 0;
    if (lista is! RenderBox || !lista.attached) return false;
    final base = cartao.localToGlobal(Offset(0, cartao.size.height)).dy;
    return base <= lista.localToGlobal(Offset.zero).dy;
  }

  /// Ao rolar, avalia já e de novo depois do quadro: o listener roda antes do
  /// novo layout, quando o cartão ainda parece visível.
  void _aoRolar() {
    _atualizarAlertaFora();
    WidgetsBinding.instance.addPostFrameCallback((_) => _atualizarAlertaFora());
  }

  void _atualizarAlertaFora() {
    final fora = _cartaoForaDaTela();
    if (mounted && fora != _alertaFora) setState(() => _alertaFora = fora);
  }

  /// Rola de volta até o cartão, que é o topo da lista.
  void _voltarAoAlerta() {
    if (MediaQuery.disableAnimationsOf(context)) {
      _rolagem.jumpTo(0);
    } else {
      _rolagem.animateTo(
        0,
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOut,
      );
    }
  }

  void _abrir(Citacao c) {
    final aoAbrir = widget.aoAbrirCitacao;
    if (aoAbrir != null) {
      aoAbrir(c);
    } else {
      unawaited(abrirFolhaEvidencia(context, c));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(resumoConsulta(widget.corpo))),
      body: BlocBuilder<RespostaCubit, RespostaState>(
        builder: (context, state) {
          final alertas = state.fase == FaseResposta.semEvidencia
              ? const <ItemAlerta>[]
              : [
                  if (state.alerta != null)
                    ItemAlerta(
                      severidade: state.alerta!.severidade,
                      texto: state.alerta!.texto,
                      fontes: citacoesPorChunk(
                        state.alerta!.chunkIds,
                        state.citacoes,
                      ),
                    ),
                ];
          // O cartão pode entrar com a lista já rolada: reavalia no quadro.
          if (alertas.isNotEmpty) {
            WidgetsBinding.instance.addPostFrameCallback(
              (_) => _atualizarAlertaFora(),
            );
          }
          return Column(
            children: [
              _Fixos(
                state: state,
                alertas: alertas,
                alertaFora: _alertaFora && alertas.isNotEmpty,
                aoVoltar: _voltarAoAlerta,
              ),
              Expanded(
                child: ListView(
                  key: _chaveLista,
                  controller: _rolagem,
                  padding: const EdgeInsets.all(24),
                  children: [
                    if (alertas.isNotEmpty) ...[
                      KeyedSubtree(
                        key: _chaveAlerta,
                        child: EntradaSuave(
                          child: CartaoAlerta(
                            itens: alertas,
                            aoAbrirCitacao: _abrir,
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                    ],
                    BalaoPergunta(corpo: widget.corpo),
                    const SizedBox(height: 16),
                    _LinhaResposta(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (state.fase == FaseResposta.offlineSemCache)
                            _OfflineSemCache(corpo: widget.corpo),
                          if (state.fase == FaseResposta.recuperando)
                            EsperaResposta(chunks: state.chunks),
                          if (state.fase == FaseResposta.semEvidencia)
                            _SemEvidencia(corpo: widget.corpo)
                          else
                            for (final (i, p) in state.paragrafos.indexed)
                              EntradaSuave(
                                key: ValueKey('paragrafo-$i'),
                                child: _Paragrafo(
                                  paragrafo: p,
                                  citacoes: state.citacoes,
                                  aoAbrir: _abrir,
                                ),
                              ),
                          if (state.fase == FaseResposta.transmitindo)
                            Text(
                              'Alertas de segurança aparecem ao final da '
                              'resposta.',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          if (state.fase == FaseResposta.falha)
                            _Falha(state: state, corpo: widget.corpo),
                        ],
                      ),
                    ),
                    if (state.fase == FaseResposta.concluida) ...[
                      _Evidencias(citacoes: state.citacoes, aoAbrir: _abrir),
                      RodapeResposta(
                        fim: state.fim!,
                        geradaEm: state.geradaEm,
                        incompleta: state.incompleta,
                      ),
                      const _FimDaConsulta(),
                      _Acoes(corpo: widget.corpo),
                    ],
                    if (state.fase == FaseResposta.semEvidencia &&
                        state.fim != null)
                      RodapeResposta(
                        fim: state.fim!,
                        geradaEm: state.geradaEm,
                        incompleta: state.incompleta,
                      ),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

/// Parte fixa acima da rolagem: o selo de cache e, quando o cartão de alerta
/// já saiu da tela, a barra compacta que leva de volta a ele
/// (`docs/FRONTEND_SPEC.md` §24).
class _Fixos extends StatelessWidget {
  const new({
    required this.state,
    required this.alertas,
    required this.alertaFora,
    required this.aoVoltar,
  });

  final RespostaState state;
  final List<ItemAlerta> alertas;
  final bool alertaFora;
  final VoidCallback aoVoltar;

  @override
  Widget build(BuildContext context) {
    final semAnimacao = MediaQuery.disableAnimationsOf(context);
    return AnimatedSize(
      duration: semAnimacao ? Duration.zero : const Duration(milliseconds: 180),
      alignment: Alignment.topCenter,
      child: Column(
        children: [
          if (state.origemCache)
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 16, 24, 0),
              child: _SeloCache(geradaEm: state.geradaEm),
            ),
          if (alertaFora)
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 8, 24, 0),
              child: BarraAlertaCompacta(
                quantidade: alertas.length,
                severidade: severidadeMaisGrave(alertas),
                aoTocar: aoVoltar,
              ),
            ),
        ],
      ),
    );
  }
}

/// Fala do sistema: avatar do app à esquerda e a coluna da resposta, sem
/// balão (`docs/FRONTEND_SPEC.md` §24).
class _LinhaResposta extends StatelessWidget {
  const new({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const Padding(
        padding: EdgeInsets.only(top: 2),
        child: AvatarVetFarmaco(),
      ),
      const SizedBox(width: 12),
      Expanded(child: child),
    ],
  );
}

/// Deixa claro que a consulta acabou: não há continuação de conversa.
class _FimDaConsulta extends StatelessWidget {
  const new();

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 8),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Divider(color: context.cores.rule),
        Text(
          'Cada consulta é independente: o sistema não guarda a conversa.',
          style: Theme.of(context).textTheme.bodyMedium
              ?.copyWith(color: context.cores.inkMuted),
        ),
      ],
    ),
  );
}

class _Paragrafo extends StatelessWidget {
  const new({
    required this.paragrafo,
    required this.citacoes,
    required this.aoAbrir,
  });

  final EventoParagrafo paragrafo;
  final List<Citacao> citacoes;
  final ValueChanged<Citacao>? aoAbrir;

  @override
  Widget build(BuildContext context) {
    final semLastro = paragrafo.chunkIds.isEmpty;
    // Regra de segurança nº 2: dose só aparece com lastro documental.
    final omitido = semLastro && contemDose(paragrafo.texto);
    final ancoras = citacoesDoParagrafo(paragrafo, citacoes);
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: TrilhoEvidencia(
        tipo: semLastro ? TipoTrilho.semLastro : TipoTrilho.ancorado,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (omitido)
              Text(
                'Parágrafo omitido: continha valor de dose sem lastro '
                'documental.',
                style: Theme.of(context).textTheme.bodyLarge
                    ?.copyWith(fontStyle: FontStyle.italic),
              )
            else
              SelectableText(
                paragrafo.texto,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
            if (semLastro)
              Text(
                'sem lastro documental',
                style: TextStyle(color: context.cores.iodo, fontSize: 12),
              ),
            if (ancoras.isNotEmpty)
              Wrap(
                children: [
                  for (final c in ancoras)
                    AncoraCitacao(citacao: c, aoTocar: aoAbrir),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

class _Evidencias extends StatelessWidget {
  const new({required this.citacoes, required this.aoAbrir});

  final List<Citacao> citacoes;
  final ValueChanged<Citacao>? aoAbrir;

  @override
  Widget build(BuildContext context) {
    if (citacoes.isEmpty) return const SizedBox.shrink();
    final tema = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Divider(color: context.cores.rule),
          Text(
            'Evidência recuperada',
            style: tema.bodyMedium?.copyWith(color: context.cores.inkMuted),
          ),
          const SizedBox(height: 12),
          for (final c in citacoes)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  AncoraCitacao(citacao: c, aoTocar: aoAbrir),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        TrechoSerifado('“${c.trecho}”'),
                        const SizedBox(height: 4),
                        Text(descricaoCitacao(c), style: tema.bodySmall),
                      ],
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _Acoes extends StatelessWidget {
  const new({required this.corpo});

  final CorpoConsulta corpo;

  @override
  Widget build(BuildContext context) {
    final estado = context.watch<RespostaCubit>().state;
    final tamanho = OutlinedButton.styleFrom(minimumSize: const Size(48, 48));
    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (estado.origemCache)
                OutlinedButton(
                  style: tamanho,
                  onPressed: () =>
                      unawaited(context.read<RespostaCubit>().iniciar(corpo)),
                  child: const Text('Atualizar'),
                )
              else
                OutlinedButton(
                  style: tamanho,
                  onPressed: estado.salva
                      ? null
                      : () => unawaited(context.read<RespostaCubit>().salvar()),
                  child: Text(estado.salva ? 'Salva' : 'Salvar'),
                ),
              OutlinedButton(
                style: tamanho,
                onPressed: () => unawaited(
                  Clipboard.setData(
                    ClipboardData(text: textoParaCopiar(estado)),
                  ),
                ),
                child: const Text('Copiar com citações'),
              ),
              FilledButton(
                style: FilledButton.styleFrom(minimumSize: const Size(48, 48)),
                onPressed: () => context.go('/consulta'),
                child: const Text('Nova consulta'),
              ),
            ],
          ),
          if (estado.mensagem != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                estado.mensagem!,
                style: TextStyle(color: context.cores.contra),
              ),
            ),
        ],
      ),
    );
  }
}

/// Selo permanente: resposta do cache nunca se disfarça de resposta nova.
class _SeloCache extends StatelessWidget {
  const new({required this.geradaEm});

  final DateTime? geradaEm;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 16),
    child: Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(border: Border.all(color: context.cores.iodo)),
      child: Text(
        'Resposta armazenada em ${geradaEm == null ? '—' : diaMes(geradaEm!)}'
        ' · pode estar desatualizada',
        style: TextStyle(
          color: context.cores.iodo,
          fontWeight: FontWeight.w600,
        ),
      ),
    ),
  );
}

class _OfflineSemCache extends StatelessWidget {
  const new({required this.corpo});

  final CorpoConsulta corpo;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        'Sem conexão. Esta consulta precisa da rede.',
        style: Theme.of(context).textTheme.titleLarge,
      ),
      const SizedBox(height: 12),
      Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          OutlinedButton(
            style: OutlinedButton.styleFrom(minimumSize: const Size(48, 48)),
            onPressed: () => unawaited(context.push('/historico')),
            child: const Text('Ver histórico'),
          ),
          OutlinedButton(
            style: OutlinedButton.styleFrom(minimumSize: const Size(48, 48)),
            onPressed: () =>
                unawaited(context.read<RespostaCubit>().iniciar(corpo)),
            child: const Text('Tentar de novo'),
          ),
        ],
      ),
    ],
  );
}

class _SemEvidencia extends StatelessWidget {
  const new({required this.corpo});

  final CorpoConsulta corpo;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    // Sucesso, não erro: sem cor de falha (`FRONTEND_SPEC.md` §15).
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Sem evidência suficiente no acervo.', style: tema.titleLarge),
        const SizedBox(height: 8),
        Text(
          'O sistema deixou de responder deliberadamente: os trechos '
          'recuperados não sustentam uma resposta.',
          style: tema.bodyLarge,
        ),
        const SizedBox(height: 16),
        OutlinedButton(
          style: OutlinedButton.styleFrom(minimumSize: const Size(48, 48)),
          onPressed: () => context.go('/consulta'),
          child: const Text('Refazer a pergunta'),
        ),
      ],
    );
  }
}

class _Falha extends StatelessWidget {
  const new({required this.state, required this.corpo});

  final RespostaState state;
  final CorpoConsulta corpo;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      if (state.incompleta)
        Text(
          'resposta incompleta',
          style: TextStyle(color: context.cores.iodo, fontSize: 12),
        ),
      Text(state.mensagem ?? 'Não foi possível concluir a consulta.'),
      const SizedBox(height: 12),
      Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          OutlinedButton(
            style: OutlinedButton.styleFrom(minimumSize: const Size(48, 48)),
            onPressed: () =>
                unawaited(context.read<RespostaCubit>().iniciar(corpo)),
            child: const Text('Tentar de novo'),
          ),
          TextButton(
            style: TextButton.styleFrom(minimumSize: const Size(48, 48)),
            onPressed: () => context.go('/consulta'),
            child: const Text('Voltar'),
          ),
        ],
      ),
    ],
  );
}
