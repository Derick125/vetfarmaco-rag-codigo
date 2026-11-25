import 'package:app/features/termo/domain/usecases/aceitar_termo.dart';
import 'package:app/features/termo/domain/usecases/consultar_aceite_termo.dart';
import 'package:app/features/termo/presentation/cubit/termo_cubit.dart';
import 'package:app/features/termo/presentation/pages/termo_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';

class _MockConsultar extends Mock implements ConsultarAceiteTermo;

class _MockAceitar extends Mock implements AceitarTermo;

Widget _app(TermoCubit cubit) => MaterialApp.router(
  routerConfig: GoRouter(
    routes: [
      GoRoute(
        path: '/',
        builder: (_, _) =>
            BlocProvider.value(value: cubit, child: const TermoPage()),
      ),
      GoRoute(
        path: '/introducao',
        builder: (_, _) => const Scaffold(body: Text('tela introdução')),
      ),
    ],
  ),
);

void main() {
  late _MockAceitar aceitar;
  late TermoCubit cubit;

  setUp(() {
    aceitar = _MockAceitar();
    cubit = TermoCubit(_MockConsultar(), aceitar);
    when(aceitar.call).thenAnswer((_) async => Right(DateTime(2026)));
  });

  tearDown(() => cubit.close());

  testWidgets('botão só habilita após rolar até o fim, e aceitar navega', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(380, 400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(_app(cubit));
    await tester.pump();

    final botao = find.widgetWithText(FilledButton, 'Entendi e aceito');
    expect(tester.widget<FilledButton>(botao).onPressed, isNull);

    await tester.drag(
      find.byType(SingleChildScrollView),
      const Offset(0, -2000),
    );
    await tester.pumpAndSettle();
    expect(tester.widget<FilledButton>(botao).onPressed, isNotNull);

    await tester.tap(botao);
    await tester.pumpAndSettle();
    expect(find.text('tela introdução'), findsOneWidget);
    verify(aceitar.call).called(1);
  });

  testWidgets('conteúdo que cabe na tela habilita o botão de imediato', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(_app(cubit));
    await tester.pump();
    await tester.pump();
    final botao = find.widgetWithText(FilledButton, 'Entendi e aceito');
    expect(tester.widget<FilledButton>(botao).onPressed, isNotNull);
  });
}
