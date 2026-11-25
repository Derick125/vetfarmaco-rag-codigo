import 'dart:async';

import 'package:app/core/theme/cores.dart';
import 'package:app/core/theme/tokens.dart';
import 'package:app/features/historico/domain/resposta_salva.dart';
import 'package:app/features/historico/presentation/cubit/historico_cubit.dart';
import 'package:app/features/historico/presentation/cubit/historico_state.dart';
import 'package:app/features/resposta/presentation/texto_resposta.dart';
import 'package:app/shared/widgets/entrada_em_cascata.dart';
import 'package:app/shared/widgets/ilustracao_vetfarmaco.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

/// `/historico` — consultas anteriores, para leitura offline
/// (`docs/FRONTEND_SPEC.md` §12).
class HistoricoPage extends StatefulWidget {
  /// Cria a tela.
  const new({super.key});

  @override
  State<HistoricoPage> createState() => _HistoricoPageState();
}

class _HistoricoPageState extends State<HistoricoPage> {
  @override
  void initState() {
    super.initState();
    unawaited(context.read<HistoricoCubit>().carregar());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Histórico')),
      body: BlocBuilder<HistoricoCubit, HistoricoState>(
        builder: (context, state) => Column(
          children: [
            if (state.offline) const _FaixaOffline(),
            Expanded(child: _Corpo(state: state)),
          ],
        ),
      ),
    );
  }
}

class _FaixaOffline extends StatelessWidget {
  const new();

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(12),
    color: Tokens.iodo,
    child: const Text(
      '⦿ offline — exibindo respostas salvas',
      style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
    ),
  );
}

class _Corpo extends StatelessWidget {
  const new({required this.state});

  final HistoricoState state;

  @override
  Widget build(BuildContext context) => switch (state.status) {
    StatusHistorico.carregando => const Center(
      child: CircularProgressIndicator(),
    ),
    StatusHistorico.falha => Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(state.mensagem ?? 'Não foi possível ler o histórico.'),
      ),
    ),
    StatusHistorico.vazio => const _Vazio(),
    StatusHistorico.comItens => ListView(
      children: [
        for (final (i, r) in state.itens.indexed)
          EntradaEmCascata(
            key: ValueKey('cascata-${r.chave}'),
            indice: i,
            child: _Linha(resposta: r),
          ),
      ],
    ),
  };
}

class _Vazio extends StatelessWidget {
  const new();

  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const IlustracaoVetFarmaco(cena: Cena.historicoVazio),
          const SizedBox(height: 16),
          const Text('Nenhuma consulta salva ainda.'),
          const SizedBox(height: 16),
          FilledButton(
            style: FilledButton.styleFrom(minimumSize: const Size(48, 48)),
            onPressed: () => context.go('/consulta'),
            child: const Text('Fazer a primeira consulta'),
          ),
        ],
      ),
    ),
  );
}

class _Linha extends StatelessWidget {
  const new({required this.resposta});

  final RespostaSalva resposta;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    final cubit = context.read<HistoricoCubit>();
    return Dismissible(
      key: ValueKey(resposta.chave),
      direction: DismissDirection.endToStart,
      background: Container(
        color: Tokens.contra,
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 24),
        child: const Icon(Icons.delete_outline, color: Colors.white),
      ),
      onDismissed: (_) => unawaited(cubit.remover(resposta.chave)),
      child: ListTile(
        minTileHeight: 56,
        title: Text(resumoConsulta(resposta.corpo)),
        subtitle: Text(diaMes(resposta.geradaEm), style: tema.bodySmall),
        leading: Semantics(
          label: resposta.temAlerta
              ? 'com alerta de segurança'
              : 'sem alerta de segurança',
          child: Icon(
            Icons.circle,
            size: 12,
            color: resposta.temAlerta
                ? context.cores.contra
                : context.cores.rule,
          ),
        ),
        trailing: IconButton(
          tooltip: 'Remover',
          constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
          icon: const Icon(Icons.delete_outline),
          onPressed: () => unawaited(cubit.remover(resposta.chave)),
        ),
        onTap: () => unawaited(
          context.push('/consulta/${resposta.chave}', extra: resposta),
        ),
      ),
    );
  }
}
