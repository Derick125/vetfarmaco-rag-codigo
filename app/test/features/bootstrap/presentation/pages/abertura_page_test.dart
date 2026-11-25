import 'dart:async';

import 'package:app/features/bootstrap/domain/usecases/decidir_destino_inicial.dart';
import 'package:app/features/bootstrap/presentation/cubit/bootstrap_cubit.dart';
import 'package:app/features/bootstrap/presentation/pages/abertura_page.dart';
import 'package:app/shared/widgets/ilustracao_vetfarmaco.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';

class _MockDecidirDestinoInicial extends Mock implements DecidirDestinoInicial;

Widget _appDeTeste(BootstrapCubit cubit) {
  final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(
        path: '/',
        builder: (context, state) =>
            BlocProvider.value(value: cubit, child: const AberturaPage()),
      ),
      GoRoute(
        path: '/termo',
        builder: (context, state) => const Scaffold(body: Text('tela termo')),
      ),
      GoRoute(
        path: '/inicio',
        builder: (context, state) => const Scaffold(body: Text('tela início')),
      ),
      GoRoute(
        path: '/ajustes',
        builder: (context, state) => const Scaffold(body: Text('tela ajustes')),
      ),
    ],
  );
  return MaterialApp.router(routerConfig: router);
}

void main() {
  late _MockDecidirDestinoInicial decidirDestinoInicial;

  setUp(() {
    decidirDestinoInicial = _MockDecidirDestinoInicial();
    AberturaPage.reiniciarMarca();
  });

  testWidgets('não mostra texto de carregamento antes de 400 ms', (
    tester,
  ) async {
    when(decidirDestinoInicial.call)
        .thenAnswer((_) => Completer<DestinoInicial>().future);

    await tester.pumpWidget(_appDeTeste(BootstrapCubit(decidirDestinoInicial)));
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('Preparando o acervo local'), findsNothing);
  });

  testWidgets(
    'mostra "Preparando o acervo local" após 400 ms de carregamento',
    (tester) async {
      when(decidirDestinoInicial.call)
          .thenAnswer((_) => Completer<DestinoInicial>().future);

      await tester.pumpWidget(
        _appDeTeste(BootstrapCubit(decidirDestinoInicial)),
      );
      await tester.pump(const Duration(milliseconds: 450));

      expect(find.text('Preparando o acervo local'), findsOneWidget);
    },
  );

  testWidgets('FalhaConfig mostra mensagem e botão Abrir ajustes', (
    tester,
  ) async {
    when(decidirDestinoInicial.call)
        .thenAnswer((_) async => DestinoInicial.falhaConfig);

    await tester.pumpWidget(_appDeTeste(BootstrapCubit(decidirDestinoInicial)));
    await tester.pumpAndSettle();

    expect(find.text('Endereço do back-end não configurado.'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Abrir ajustes'), findsOneWidget);

    await tester.tap(find.text('Abrir ajustes'));
    await tester.pumpAndSettle();

    expect(find.text('tela ajustes'), findsOneWidget);
  });

  testWidgets('ParaTermo encaminha para /termo', (tester) async {
    when(decidirDestinoInicial.call)
        .thenAnswer((_) async => DestinoInicial.termo);

    await tester.pumpWidget(_appDeTeste(BootstrapCubit(decidirDestinoInicial)));
    // A marca segura a navegação até completar 300 ms (FRONTEND_SPEC §20).
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pumpAndSettle();

    expect(find.text('tela termo'), findsOneWidget);
  });

  testWidgets('ParaConsulta encaminha para /inicio', (tester) async {
    when(decidirDestinoInicial.call)
        .thenAnswer((_) async => DestinoInicial.consulta);

    await tester.pumpWidget(_appDeTeste(BootstrapCubit(decidirDestinoInicial)));
    // A marca segura a navegação até completar 300 ms (FRONTEND_SPEC §20).
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pumpAndSettle();

    expect(find.text('tela início'), findsOneWidget);
  });

  testWidgets('mostra a marca e só vai ao Início depois de 300 ms', (
    tester,
  ) async {
    when(decidirDestinoInicial.call)
        .thenAnswer((_) async => DestinoInicial.consulta);

    await tester.pumpWidget(_appDeTeste(BootstrapCubit(decidirDestinoInicial)));
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.byType(IlustracaoVetFarmaco), findsOneWidget);
    expect(find.text('VetFarmaco'), findsOneWidget);
    expect(find.text('tela início'), findsNothing);

    await tester.pump(const Duration(milliseconds: 250));
    await tester.pumpAndSettle();

    expect(find.text('tela início'), findsOneWidget);
  });

  testWidgets('a marca aparece uma vez por execução', (tester) async {
    when(decidirDestinoInicial.call)
        .thenAnswer((_) => Completer<DestinoInicial>().future);
    await tester.pumpWidget(_appDeTeste(BootstrapCubit(decidirDestinoInicial)));
    expect(find.byType(IlustracaoVetFarmaco), findsOneWidget);

    // Nova abertura na mesma execução (ex.: voltar de Ajustes): sem marca.
    when(decidirDestinoInicial.call)
        .thenAnswer((_) async => DestinoInicial.consulta);
    await tester.pumpWidget(const SizedBox());
    await tester.pumpWidget(_appDeTeste(BootstrapCubit(decidirDestinoInicial)));
    await tester.pump();
    await tester.pump();

    expect(find.byType(IlustracaoVetFarmaco), findsNothing);
    expect(find.text('tela início'), findsOneWidget);
  });
}
