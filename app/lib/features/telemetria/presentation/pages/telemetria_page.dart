import 'dart:async';

import 'package:app/core/theme/cores.dart';
import 'package:app/features/telemetria/presentation/cubit/telemetria_cubit.dart';
import 'package:app/features/telemetria/presentation/cubit/telemetria_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

/// `/telemetria` — versão reduzida: contagem e `Exportar CSV`
/// (`docs/PLANO_DE_FASES.md`, etapa 4.9). Percentis e gráficos saem do CSV,
/// fora do app.
class TelemetriaPage extends StatefulWidget {
  /// Cria a tela.
  const new({super.key});

  @override
  State<TelemetriaPage> createState() => _TelemetriaPageState();
}

class _TelemetriaPageState extends State<TelemetriaPage> {
  @override
  void initState() {
    super.initState();
    unawaited(context.read<TelemetriaCubit>().carregar());
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Telemetria')),
      body: BlocBuilder<TelemetriaCubit, TelemetriaState>(
        builder: (context, state) {
          final ocupado =
              state.status == StatusTelemetria.carregando ||
              state.status == StatusTelemetria.exportando;
          return ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Text('Consultas registradas', style: tema.titleLarge),
              const SizedBox(height: 8),
              Text(
                '${state.total}',
                style: tema.displaySmall?.copyWith(
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Cada consulta guarda o tempo até o primeiro evento, o TTFT '
                'do contrato (primeiro parágrafo validado), os tempos do '
                'servidor, '
                'os tokens, o custo, a versão do modelo e a data.',
                style: tema.bodySmall,
              ),
              if (state.status == StatusTelemetria.falha)
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: Text(
                    state.mensagem ?? 'Falha.',
                    style: TextStyle(color: context.cores.contra),
                  ),
                ),
              const SizedBox(height: 24),
              FilledButton(
                style: FilledButton.styleFrom(
                  minimumSize: const Size.fromHeight(48),
                ),
                onPressed: ocupado || state.total == 0
                    ? null
                    : () =>
                          unawaited(context.read<TelemetriaCubit>().exportar()),
                child: const Text('Exportar CSV'),
              ),
            ],
          );
        },
      ),
    );
  }
}
