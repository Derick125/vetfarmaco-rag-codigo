import 'package:app/core/theme/cores.dart';
import 'package:app/features/inicio/presentation/pages/inicio_page.dart';
import 'package:app/shared/widgets/ilustracao_vetfarmaco.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

Widget _app({ThemeData? tema}) {
  GoRoute destino(String caminho, String texto) => GoRoute(
    path: caminho,
    builder: (_, _) => Scaffold(body: Text(texto)),
  );
  return MaterialApp.router(
    theme: tema,
    routerConfig: GoRouter(
      initialLocation: '/inicio',
      routes: [
        GoRoute(path: '/inicio', builder: (_, _) => const InicioPage()),
        destino('/consulta', 'tela consulta'),
        destino('/historico', 'tela histórico'),
        destino('/ajustes', 'tela ajustes'),
        destino('/sobre', 'tela sobre'),
      ],
    ),
  );
}

void main() {
  testWidgets('mostra a marca, a frase, os atalhos e o aviso', (tester) async {
    await tester.pumpWidget(_app());
    await tester.pumpAndSettle();
    expect(find.text('VetFarmaco'), findsOneWidget);
    expect(
      find.text('Apoio à decisão farmacológica para cães e gatos.'),
      findsOneWidget,
    );
    expect(find.text('Nova consulta'), findsOneWidget);
    expect(find.text('Histórico'), findsOneWidget);
    expect(find.text('Ajustes'), findsOneWidget);
    expect(find.text('Sobre o aplicativo'), findsOneWidget);
    expect(find.textContaining('não substitui o julgamento clínico'), findsOne);
  });

  testWidgets('tem uma só ilustração: a pequena do cabeçalho', (tester) async {
    await tester.pumpWidget(_app());
    final ilustracao = tester.widget<IlustracaoVetFarmaco>(
      find.byType(IlustracaoVetFarmaco),
    );
    expect(ilustracao.cena, Cena.inicioCabecalho);
  });

  for (final (texto, destino) in [
    ('Nova consulta', 'tela consulta'),
    ('Histórico', 'tela histórico'),
    ('Ajustes', 'tela ajustes'),
    ('Sobre o aplicativo', 'tela sobre'),
  ]) {
    testWidgets('«$texto» leva a $destino', (tester) async {
      await tester.pumpWidget(_app());
      await tester.pumpAndSettle();
      await tester.tap(find.text(texto));
      await tester.pumpAndSettle();
      expect(find.text(destino), findsOneWidget);
    });
  }

  testWidgets('«Nova consulta» empilha a tela: voltar retorna ao Início', (
    tester,
  ) async {
    await tester.pumpWidget(_app());
    await tester.pumpAndSettle();
    await tester.tap(find.text('Nova consulta'));
    await tester.pumpAndSettle();
    final contexto = tester.element(find.text('tela consulta'));
    expect(GoRouter.of(contexto).canPop(), isTrue);
    GoRouter.of(contexto).pop();
    await tester.pumpAndSettle();
    expect(find.text('Sobre o aplicativo'), findsOneWidget);
  });

  testWidgets('alvos de toque têm ao menos 48 dp', (tester) async {
    await tester.pumpWidget(_app());
    await tester.pumpAndSettle();
    for (final texto in [
      'Nova consulta',
      'Histórico',
      'Ajustes',
      'Sobre o aplicativo',
    ]) {
      final alvo = find.ancestor(
        of: find.text(texto),
        matching: find.byWidgetPredicate(
          (w) => w is InkWell || w is FilledButton,
        ),
      );
      expect(tester.getSize(alvo.first).height, greaterThanOrEqualTo(48));
    }
  });

  testWidgets('tema escuro e fonte 2.0 não estouram a tela', (tester) async {
    tester.view
      ..physicalSize = const Size(380, 800)
      ..devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.pumpWidget(
      _app(
        tema: ThemeData(
          brightness: Brightness.dark,
          extensions: const [CoresVetFarmaco.escuro],
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    await tester.drag(find.byType(ListView), const Offset(0, -600));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
