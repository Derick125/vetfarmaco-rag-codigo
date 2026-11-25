import 'dart:async';

import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:app/features/resposta/presentation/widgets/folha_evidencia.dart';
import 'package:app/shared/widgets/entrada_em_cascata.dart';
import 'package:app/shared/widgets/pagina_animada.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

class _TelaQueIniciaTrabalho extends StatefulWidget {
  const new({required this.aoIniciar});

  final VoidCallback aoIniciar;

  @override
  State<_TelaQueIniciaTrabalho> createState() => _TelaQueIniciaTrabalhoState();
}

class _TelaQueIniciaTrabalhoState extends State<_TelaQueIniciaTrabalho> {
  @override
  void initState() {
    super.initState();
    widget.aoIniciar();
  }

  @override
  Widget build(BuildContext context) =>
      const Scaffold(body: Text('tela destino'));
}

Widget _app({
  required VoidCallback aoIniciarDestino,
  bool semAnimacao = false,
}) {
  final router = GoRouter(
    routes: [
      GoRoute(
        path: '/',
        pageBuilder: (context, state) => paginaAnimada(
          state: state,
          child: Scaffold(
            body: Builder(
              builder: (context) => TextButton(
                onPressed: () => unawaited(context.push('/destino')),
                child: const Text('ir'),
              ),
            ),
          ),
        ),
      ),
      GoRoute(
        path: '/destino',
        pageBuilder: (context, state) => paginaAnimada(
          state: state,
          child: _TelaQueIniciaTrabalho(aoIniciar: aoIniciarDestino),
        ),
      ),
    ],
  );
  return MaterialApp.router(
    routerConfig: router,
    builder: (context, child) => MediaQuery(
      data: MediaQuery.of(context).copyWith(disableAnimations: semAnimacao),
      child: child!,
    ),
  );
}

const _citacao = Citacao(
  chunkId: 'c1',
  indice: 1,
  trecho: 'Trecho literal.',
  fonte: 'Spinosa et al. (2017)',
);

void main() {
  group('transição entre telas', () {
    testWidgets('dura 220 ms e a tela destino já existe no 1º quadro', (
      tester,
    ) async {
      var iniciou = 0;
      await tester.pumpWidget(_app(aoIniciarDestino: () => iniciou++));
      await tester.tap(find.text('ir'));
      // Um único quadro, sem avançar o relógio: a tela já foi construída e
      // começou o trabalho (a transição não atrasa consulta nem telemetria).
      await tester.pump();
      expect(iniciou, 1);
      expect(find.text('tela destino', skipOffstage: false), findsOneWidget);

      await tester.pump(const Duration(milliseconds: 110));
      expect(find.text('ir'), findsOneWidget, reason: 'meio da transição');

      await tester.pumpAndSettle();
      expect(duracaoTransicaoTela, const Duration(milliseconds: 220));
      expect(find.text('tela destino'), findsOneWidget);
    });

    testWidgets('sem animação, a troca é imediata', (tester) async {
      await tester.pumpWidget(_app(aoIniciarDestino: () {}, semAnimacao: true));
      await tester.tap(find.text('ir'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 1));
      expect(find.text('tela destino'), findsOneWidget);
      expect(find.byType(FadeTransition), findsNothing);
    });
  });

  group('EntradaEmCascata', () {
    Widget lista({bool semAnimacao = false, int itens = 10}) => MaterialApp(
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(disableAnimations: semAnimacao),
        child: child!,
      ),
      home: Scaffold(
        body: ListView(
          children: [
            for (var i = 0; i < itens; i++)
              EntradaEmCascata(
                key: ValueKey(i),
                indice: i,
                child: SizedBox(height: 20, child: Text('item $i')),
              ),
          ],
        ),
      ),
    );

    double opacidade(WidgetTester tester, String texto) => tester
        .widget<AnimatedOpacity>(
          find
              .ancestor(
                of: find.text(texto),
                matching: find.byType(AnimatedOpacity),
              )
              .first,
        )
        .opacity;

    testWidgets('itens entram escalonados em 40 ms, só os 8 primeiros', (
      tester,
    ) async {
      await tester.pumpWidget(lista());
      // Todos estão na árvore desde o primeiro quadro.
      expect(find.text('item 3'), findsOneWidget);
      expect(opacidade(tester, 'item 3'), 0);
      // O 9º item (índice 8) não espera: passou do limite.
      expect(opacidade(tester, 'item 8'), 1);

      await tester.pump(const Duration(milliseconds: 1));
      expect(opacidade(tester, 'item 0'), 1);
      expect(opacidade(tester, 'item 1'), 0);

      await tester.pump(const Duration(milliseconds: 130));
      expect(opacidade(tester, 'item 3'), 1);
      expect(opacidade(tester, 'item 7'), 0);

      await tester.pump(const Duration(milliseconds: 200));
      expect(opacidade(tester, 'item 7'), 1);
      await tester.pumpAndSettle();
    });

    testWidgets('anima só na primeira carga, não ao reconstruir', (
      tester,
    ) async {
      await tester.pumpWidget(lista());
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();
      await tester.pumpWidget(lista());
      expect(opacidade(tester, 'item 5'), 1);
    });

    testWidgets('com animações desligadas todos aparecem de imediato', (
      tester,
    ) async {
      await tester.pumpWidget(lista(semAnimacao: true));
      for (var i = 0; i < 8; i++) {
        expect(opacidade(tester, 'item $i'), 1);
      }
    });
  });

  group('folha de evidência', () {
    Future<double> topoDaFolha(
      WidgetTester tester, {
      required bool semAnimacao,
      Duration? depois,
    }) async {
      await tester.pumpWidget(
        MaterialApp(
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context)
                .copyWith(disableAnimations: semAnimacao),
            child: child!,
          ),
          home: Scaffold(
            body: Builder(
              builder: (context) => TextButton(
                onPressed: () =>
                    unawaited(abrirFolhaEvidencia(context, _citacao)),
                child: const Text('abrir'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('abrir'));
      await tester.pump();
      if (depois != null) await tester.pump(depois);
      return tester.getTopLeft(find.byType(FolhaEvidencia)).dy;
    }

    testWidgets('desliza de baixo em 220 ms', (tester) async {
      final meio = await topoDaFolha(
        tester,
        semAnimacao: false,
        depois: const Duration(milliseconds: 80),
      );
      await tester.pumpAndSettle();
      final fim = tester.getTopLeft(find.byType(FolhaEvidencia)).dy;
      expect(meio, greaterThan(fim), reason: 'ainda subindo aos 80 ms');
    });

    testWidgets('sem animação aparece direto na posição final', (tester) async {
      final topo = await topoDaFolha(
        tester,
        semAnimacao: true,
        depois: const Duration(milliseconds: 1),
      );
      await tester.pumpAndSettle();
      expect(tester.getTopLeft(find.byType(FolhaEvidencia)).dy, topo);
    });
  });
}
