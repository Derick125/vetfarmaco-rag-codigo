import 'dart:async';

import 'package:app/core/theme/cores.dart';
import 'package:app/features/termo/presentation/cubit/termo_cubit.dart';
import 'package:app/features/termo/presentation/cubit/termo_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

/// `/termo` — Termo de uso clínico (`docs/FRONTEND_SPEC.md` §8).
///
/// O botão só habilita depois da rolagem até o fim.
class TermoPage extends StatefulWidget {
  /// Cria a tela.
  const new({super.key});

  @override
  State<TermoPage> createState() => _TermoPageState();
}

class _TermoPageState extends State<TermoPage> {
  bool _chegouAoFim = false;

  bool _atualizar(ScrollMetrics m) {
    if (!_chegouAoFim && m.extentAfter <= 1) {
      // Pode ser chamado durante o layout; adia para depois do frame.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) setState(() => _chegouAoFim = true);
      });
    }
    return false;
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    return Scaffold(
      body: SafeArea(
        child: BlocConsumer<TermoCubit, TermoState>(
          listener: (context, state) {
            if (state is Aceito) context.go('/introducao');
          },
          builder: (context, state) {
            final falha = state is NaoAceito ? state.falha : null;
            return Column(
              children: [
                Expanded(
                  child: NotificationListener<ScrollMetricsNotification>(
                    onNotification: (n) => _atualizar(n.metrics),
                    child: NotificationListener<ScrollNotification>(
                      onNotification: (n) => _atualizar(n.metrics),
                      child: SingleChildScrollView(
                        padding: const EdgeInsets.all(24),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Antes de começar', style: tema.displaySmall),
                            const SizedBox(height: 16),
                            Text(
                              'Este aplicativo é uma prova de conceito '
                              'acadêmica. Ele não emite prescrição e não '
                              'substitui o julgamento do médico veterinário '
                              'responsável.',
                              style: tema.bodyLarge,
                            ),
                            const SizedBox(height: 16),
                            Container(
                              width: double.infinity,
                              padding: const EdgeInsets.all(16),
                              decoration: BoxDecoration(
                                border: Border(
                                  left: BorderSide(
                                    color: context.cores.iodo,
                                    width: 3,
                                  ),
                                ),
                                color: context.cores.iodo.withValues(
                                  alpha: 0.12,
                                ),
                              ),
                              child: Text(
                                'As respostas são geradas a partir de '
                                'trechos de literatura recuperados '
                                'automaticamente. Confira sempre a fonte '
                                'citada antes de qualquer conduta.',
                                style: tema.bodyLarge,
                              ),
                            ),
                            const SizedBox(height: 16),
                            Text(
                              'Nenhum dado de tutor ou de paciente é enviado '
                              'ao servidor: identificações são removidas no '
                              'próprio aparelho.',
                              style: tema.bodyLarge,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      if (falha != null)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: Text(
                            falha.mensagem,
                            style: tema.bodySmall?.copyWith(
                              color: context.cores.contra,
                            ),
                          ),
                        ),
                      FilledButton(
                        style: FilledButton.styleFrom(
                          minimumSize: const Size.fromHeight(48),
                        ),
                        onPressed: _chegouAoFim
                            ? () => unawaited(
                                context.read<TermoCubit>().aceitar(),
                              )
                            : null,
                        child: const Text('Entendi e aceito'),
                      ),
                    ],
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
