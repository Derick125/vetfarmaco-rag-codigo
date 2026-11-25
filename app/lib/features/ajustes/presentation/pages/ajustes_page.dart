import 'dart:async';

import 'package:app/core/theme/cores.dart';
import 'package:app/features/ajustes/presentation/cubit/ajustes_cubit.dart';
import 'package:app/features/ajustes/presentation/cubit/ajustes_state.dart';
import 'package:app/features/telemetria/domain/condicao_campanha.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

/// `/ajustes` — por ora, só o endereço do back-end
/// (`docs/PLANO_DE_FASES.md`, etapa 4.2).
class AjustesPage extends StatefulWidget {
  /// Cria a tela.
  const new({super.key});

  @override
  State<AjustesPage> createState() => _AjustesPageState();
}

class _AjustesPageState extends State<AjustesPage> {
  final _campo = TextEditingController();

  @override
  void initState() {
    super.initState();
    unawaited(context.read<AjustesCubit>().carregar());
  }

  @override
  void dispose() {
    _campo.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Ajustes')),
      body: BlocConsumer<AjustesCubit, AjustesState>(
        listenWhen: (a, b) => a.endereco != b.endereco || b.salvo,
        listener: (context, state) {
          if (_campo.text != state.endereco) _campo.text = state.endereco;
          if (state.salvo) context.go('/');
        },
        builder: (context, state) {
          final testando = state.status == StatusTeste.testando;
          return ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Text('Endereço do back-end', style: tema.titleLarge),
              const SizedBox(height: 8),
              TextField(
                controller: _campo,
                keyboardType: TextInputType.url,
                autocorrect: false,
                decoration: const InputDecoration(
                  hintText: 'http://10.0.2.2:8000',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              _Resultado(state: state),
              const SizedBox(height: 16),
              OutlinedButton(
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(48),
                ),
                onPressed: testando
                    ? null
                    : () => unawaited(
                        context.read<AjustesCubit>().testar(_campo.text),
                      ),
                child: const Text('Testar'),
              ),
              const SizedBox(height: 8),
              FilledButton(
                style: FilledButton.styleFrom(
                  minimumSize: const Size.fromHeight(48),
                ),
                onPressed: testando
                    ? null
                    : () => unawaited(
                        context.read<AjustesCubit>().salvar(_campo.text),
                      ),
                child: const Text('Salvar'),
              ),
              const SizedBox(height: 24),
              Text('Condição de rede da campanha', style: tema.titleLarge),
              const SizedBox(height: 8),
              SegmentedButton<CondicaoCampanha>(
                emptySelectionAllowed: true,
                showSelectedIcon: false,
                style: const ButtonStyle(
                  minimumSize: WidgetStatePropertyAll(Size(0, 48)),
                ),
                segments: [
                  for (final c in CondicaoCampanha.values)
                    if (c != CondicaoCampanha.naoInformada)
                      ButtonSegment(value: c, label: Text(c.titulo)),
                ],
                selected: {
                  if (state.condicao != CondicaoCampanha.naoInformada)
                    state.condicao,
                },
                onSelectionChanged: (s) => unawaited(
                  // Tocar na já marcada devolve o conjunto vazio.
                  context.read<AjustesCubit>().alterarCondicao(
                    s.isEmpty ? state.condicao : s.first,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Gravada em cada registro de telemetria e exportada no CSV.',
                style: tema.bodySmall,
              ),
              const SizedBox(height: 24),
              ListTile(
                contentPadding: EdgeInsets.zero,
                minTileHeight: 48,
                title: const Text('Telemetria das consultas'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => unawaited(context.push('/telemetria')),
              ),
              ListTile(
                contentPadding: EdgeInsets.zero,
                minTileHeight: 48,
                title: const Text('Sobre o aplicativo'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => unawaited(context.push('/sobre')),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _Resultado extends StatelessWidget {
  const new({required this.state});

  final AjustesState state;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme.bodyLarge;
    return switch (state.status) {
      StatusTeste.ocioso => const SizedBox.shrink(),
      StatusTeste.testando => Text('Testando…', style: tema),
      StatusTeste.ok => Text(
        'Back-end respondeu.',
        style: tema?.copyWith(color: context.cores.ancorado),
      ),
      StatusTeste.falha => Text(
        state.mensagem ?? 'Falha ao testar.',
        style: tema?.copyWith(color: context.cores.contra),
      ),
    };
  }
}
