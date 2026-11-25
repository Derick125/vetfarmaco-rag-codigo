import 'dart:async';

import 'package:app/core/theme/cores.dart';
import 'package:app/features/bootstrap/presentation/cubit/bootstrap_cubit.dart';
import 'package:app/features/bootstrap/presentation/cubit/bootstrap_state.dart';
import 'package:app/shared/widgets/ilustracao_vetfarmaco.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

/// `/` — Abertura (`docs/FRONTEND_SPEC.md` §7).
///
/// A marca aparece uma vez por execução do app e só segura a navegação até
/// completar 300 ms, sem atraso artificial além disso (§20). Se a
/// inicialização passar de 400 ms, exibe `Preparando o acervo local`.
class AberturaPage extends StatefulWidget {
  /// Cria a tela de abertura.
  const new({super.key});

  /// A marca é mostrada uma única vez por execução do app.
  static bool _marcaJaMostrada = false;

  /// Só para testes: faz a próxima abertura mostrar a marca de novo.
  @visibleForTesting
  static void reiniciarMarca() => _marcaJaMostrada = false;

  @override
  State<AberturaPage> createState() => _AberturaPageState();
}

class _AberturaPageState extends State<AberturaPage> {
  static const _limiarTextoLento = Duration(milliseconds: 400);
  static const _permanenciaMinimaMarca = Duration(milliseconds: 300);

  Timer? _temporizador;
  Timer? _temporizadorMarca;
  bool _mostrarTextoLento = false;
  late final bool _mostrarMarca;
  bool _permanenciaCumprida = true;
  String? _destinoPendente;

  @override
  void initState() {
    super.initState();
    _mostrarMarca = !AberturaPage._marcaJaMostrada;
    AberturaPage._marcaJaMostrada = true;
    if (_mostrarMarca) {
      _permanenciaCumprida = false;
      _temporizadorMarca = Timer(_permanenciaMinimaMarca, () {
        _permanenciaCumprida = true;
        final destino = _destinoPendente;
        if (mounted && destino != null) context.go(destino);
      });
    }
    unawaited(context.read<BootstrapCubit>().iniciar());
    _temporizador = Timer(_limiarTextoLento, () {
      if (mounted) setState(() => _mostrarTextoLento = true);
    });
  }

  @override
  void dispose() {
    _temporizador?.cancel();
    _temporizadorMarca?.cancel();
    super.dispose();
  }

  void _irPara(String rota) {
    if (_permanenciaCumprida) {
      context.go(rota);
    } else {
      _destinoPendente = rota;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: BlocListener<BootstrapCubit, BootstrapState>(
        listener: (context, state) {
          switch (state) {
            case ParaTermo():
              _irPara('/termo');
            case ParaConsulta():
              _irPara('/inicio');
            case Carregando():
            case FalhaConfig():
              break;
          }
        },
        child: BlocBuilder<BootstrapCubit, BootstrapState>(
          builder: (context, state) => switch (state) {
            Carregando() => _CarregandoView(
              mostrarMarca: _mostrarMarca,
              mostrarTexto: _mostrarTextoLento,
            ),
            FalhaConfig() => const _FalhaConfigView(),
            // A marca fica até a navegação, que espera os 300 ms mínimos.
            ParaTermo() || ParaConsulta() =>
              _mostrarMarca
                  ? const _CarregandoView(
                      mostrarMarca: true,
                      mostrarTexto: false,
                    )
                  : const SizedBox.shrink(),
          },
        ),
      ),
    );
  }
}

class _CarregandoView extends StatelessWidget {
  const new({required this.mostrarMarca, required this.mostrarTexto});

  final bool mostrarMarca;
  final bool mostrarTexto;

  @override
  Widget build(BuildContext context) {
    final semAnimacao = MediaQuery.disableAnimationsOf(context);
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (mostrarMarca)
            TweenAnimationBuilder<double>(
              tween: Tween(begin: semAnimacao ? 1 : 0, end: 1),
              duration: semAnimacao
                  ? Duration.zero
                  : const Duration(milliseconds: 120),
              builder: (context, opacidade, filho) =>
                  Opacity(opacity: opacidade, child: filho),
              child: const _MarcaAbertura(),
            ),
          if (mostrarMarca) const SizedBox(height: 24),
          AnimatedOpacity(
            opacity: mostrarTexto ? 1 : 0,
            duration: const Duration(milliseconds: 120),
            child: mostrarTexto
                ? Text(
                    'Preparando o acervo local',
                    style: Theme.of(context).textTheme.bodyLarge,
                  )
                : const SizedBox.shrink(),
          ),
        ],
      ),
    );
  }
}

class _FalhaConfigView extends StatelessWidget {
  const new();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Endereço do back-end não configurado.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'Defina o endereço do servidor em Ajustes antes de continuar.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyLarge
                  ?.copyWith(color: context.cores.inkMuted),
            ),
            const SizedBox(height: 24),
            FilledButton(
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(48),
              ),
              onPressed: () => context.go('/ajustes'),
              child: const Text('Abrir ajustes'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Ilustração da abertura (cão e gato com o ícone da marca) e o nome do app.
class _MarcaAbertura extends StatelessWidget {
  const new();

  @override
  Widget build(BuildContext context) => Column(
    mainAxisSize: MainAxisSize.min,
    children: [
      const IlustracaoVetFarmaco(cena: Cena.abertura),
      const SizedBox(height: 4),
      Semantics(
        label: 'VetFarmaco',
        excludeSemantics: true,
        child: Text(
          'VetFarmaco',
          style: Theme.of(context).textTheme.displaySmall,
        ),
      ),
    ],
  );
}
