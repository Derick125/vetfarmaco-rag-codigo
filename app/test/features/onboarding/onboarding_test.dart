import 'dart:io';

import 'package:app/core/error/failures.dart';
import 'package:app/features/onboarding/data/repositories/onboarding_repository_impl.dart';
import 'package:app/features/onboarding/domain/usecases/consultar_introducao_vista.dart';
import 'package:app/features/onboarding/domain/usecases/marcar_introducao_vista.dart';
import 'package:app/features/onboarding/onboarding_module.dart';
import 'package:app/features/onboarding/presentation/cubit/introducao_cubit.dart';
import 'package:app/features/onboarding/presentation/cubit/introducao_state.dart';
import 'package:app/features/onboarding/presentation/pages/introducao_page.dart';
import 'package:app/shared/widgets/ilustracao_vetfarmaco.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:hive_ce/hive_ce.dart';
import 'package:mocktail/mocktail.dart';

class _MockConsultar extends Mock implements ConsultarIntroducaoVista;

class _MockMarcar extends Mock implements MarcarIntroducaoVista;

void main() {
  group('OnboardingRepositoryImpl (caixa nova do hive_ce)', () {
    late Directory dir;
    late Box<dynamic> caixa;

    setUp(() async {
      dir = Directory.systemTemp.createTempSync('onboarding_test');
      Hive.init(dir.path);
      caixa = await Hive.openBox<dynamic>(nomeCaixaOnboarding);
    });

    tearDown(() async {
      await Hive.close();
      dir.deleteSync(recursive: true);
    });

    test('primeira vez: não vista; depois de marcar, vista', () async {
      final repo = OnboardingRepositoryImpl(caixa);
      expect(await repo.introducaoVista(), const Right<Failure, bool>(false));
      expect(
        await repo.marcarIntroducaoVista(),
        const Right<Failure, Unit>(unit),
      );
      expect(await repo.introducaoVista(), const Right<Failure, bool>(true));
    });

    test('guarda só um booleano, em caixa própria', () async {
      await OnboardingRepositoryImpl(caixa).marcarIntroducaoVista();
      expect(nomeCaixaOnboarding, 'onboarding');
      expect(caixa.keys, [chaveIntroducaoVista]);
      expect(caixa.get(chaveIntroducaoVista), true);
    });

    test('caixa fechada vira FalhaCache, sem lançar', () async {
      final repo = OnboardingRepositoryImpl(caixa);
      await caixa.close();
      expect((await repo.introducaoVista()).isLeft(), isTrue);
      expect((await repo.marcarIntroducaoVista()).isLeft(), isTrue);
    });

    test('registrarOnboarding abre a caixa e é idempotente', () async {
      final gi = GetIt.asNewInstance();
      await registrarOnboarding(gi);
      await registrarOnboarding(gi);
      final cubit = gi<IntroducaoCubit>();
      expect(cubit.state, isA<IntroducaoCarregando>());
      await cubit.close();
    });
  });

  group('IntroducaoCubit', () {
    late _MockConsultar consultar;
    late _MockMarcar marcar;

    setUp(() {
      consultar = _MockConsultar();
      marcar = _MockMarcar();
      when(marcar.call).thenAnswer((_) async => const Right(unit));
    });

    blocTest<IntroducaoCubit, IntroducaoState>(
      'primeira vez mostra os cartões',
      setUp: () =>
          when(consultar.call).thenAnswer((_) async => const Right(false)),
      build: () => IntroducaoCubit(consultar, marcar),
      act: (c) => c.carregar(),
      expect: () => [const IntroducaoExibindo()],
    );

    blocTest<IntroducaoCubit, IntroducaoState>(
      'já vista segue direto',
      setUp: () =>
          when(consultar.call).thenAnswer((_) async => const Right(true)),
      build: () => IntroducaoCubit(consultar, marcar),
      act: (c) => c.carregar(),
      expect: () => [const IntroducaoJaVista()],
    );

    blocTest<IntroducaoCubit, IntroducaoState>(
      'falha de leitura mostra a introdução',
      setUp: () =>
          when(consultar.call)
              .thenAnswer((_) async => const Left(FalhaCache('x'))),
      build: () => IntroducaoCubit(consultar, marcar),
      act: (c) => c.carregar(),
      expect: () => [const IntroducaoExibindo()],
    );

    blocTest<IntroducaoCubit, IntroducaoState>(
      'concluir grava a marca e segue',
      build: () => IntroducaoCubit(consultar, marcar),
      act: (c) => c.concluir(),
      expect: () => [const IntroducaoConcluida()],
      verify: (_) => verify(marcar.call).called(1),
    );

    blocTest<IntroducaoCubit, IntroducaoState>(
      'falha ao gravar não trava o usuário',
      setUp: () =>
          when(marcar.call)
              .thenAnswer((_) async => const Left(FalhaCache('x'))),
      build: () => IntroducaoCubit(consultar, marcar),
      act: (c) => c.concluir(),
      expect: () => [const IntroducaoConcluida()],
    );
  });

  group('IntroducaoPage', () {
    late _MockConsultar consultar;
    late _MockMarcar marcar;

    setUp(() {
      consultar = _MockConsultar();
      marcar = _MockMarcar();
      when(consultar.call).thenAnswer((_) async => const Right(false));
      when(marcar.call).thenAnswer((_) async => const Right(unit));
    });

    Future<void> abrir(WidgetTester tester, {bool semAnimacao = false}) async {
      final cubit = IntroducaoCubit(consultar, marcar);
      addTearDown(cubit.close);
      await tester.pumpWidget(
        MaterialApp.router(
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context)
                .copyWith(disableAnimations: semAnimacao),
            child: child!,
          ),
          routerConfig: GoRouter(
            initialLocation: '/introducao',
            routes: [
              GoRoute(
                path: '/introducao',
                builder: (_, _) => BlocProvider.value(
                  value: cubit,
                  child: const IntroducaoPage(),
                ),
              ),
              GoRoute(
                path: '/inicio',
                builder: (_, _) => const Scaffold(body: Text('tela início')),
              ),
            ],
          ),
        ),
      );
      await tester.pumpAndSettle();
    }

    testWidgets('três cartões, na ordem, terminando em Começar', (
      tester,
    ) async {
      await abrir(tester);
      expect(find.text('Consulta'), findsOneWidget);
      expect(find.textContaining('independente'), findsOneWidget);
      expect(find.byType(IlustracaoVetFarmaco), findsOneWidget); // cartão 1
      expect(find.text('Próximo'), findsOneWidget);

      await tester.tap(find.text('Próximo'));
      await tester.pumpAndSettle();
      expect(find.text('Trilho de evidência'), findsOneWidget);
      expect(find.textContaining('abre o trecho original'), findsOneWidget);

      await tester.tap(find.text('Próximo'));
      await tester.pumpAndSettle();
      expect(find.text('Modo offline'), findsOneWidget);
      expect(find.text('Começar'), findsOneWidget);
      expect(find.text('Próximo'), findsNothing);

      await tester.tap(find.text('Começar'));
      await tester.pumpAndSettle();
      verify(marcar.call).called(1);
      expect(find.text('tela início'), findsOneWidget);
    });

    testWidgets('Pular está em todos os cartões e leva à consulta', (
      tester,
    ) async {
      await abrir(tester);
      expect(find.text('Pular'), findsOneWidget);
      await tester.tap(find.text('Próximo'));
      await tester.pumpAndSettle();
      expect(find.text('Pular'), findsOneWidget);

      await tester.tap(find.text('Pular'));
      await tester.pumpAndSettle();
      verify(marcar.call).called(1);
      expect(find.text('tela início'), findsOneWidget);
    });

    testWidgets('alvos de toque têm ao menos 48 dp', (tester) async {
      await abrir(tester);
      for (final botao in [
        find.widgetWithText(TextButton, 'Pular'),
        find.widgetWithText(FilledButton, 'Próximo'),
      ]) {
        final tamanho = tester.getSize(botao);
        expect(tamanho.height, greaterThanOrEqualTo(48));
        expect(tamanho.width, greaterThanOrEqualTo(48));
      }
    });

    testWidgets('já vista: não mostra nada e segue direto', (tester) async {
      when(consultar.call).thenAnswer((_) async => const Right(true));
      await abrir(tester);
      expect(find.text('Consulta'), findsNothing);
      expect(find.text('tela início'), findsOneWidget);
      verifyNever(marcar.call);
    });

    testWidgets('sem animação, troca de cartão na hora', (tester) async {
      await abrir(tester, semAnimacao: true);
      await tester.tap(find.text('Próximo'));
      await tester.pump();
      expect(find.text('Trilho de evidência'), findsOneWidget);
    });

    testWidgets('aguenta textScaleFactor 2.0 sem estourar', (tester) async {
      tester.platformDispatcher.textScaleFactorTestValue = 2;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      await abrir(tester);
      expect(tester.takeException(), isNull);
      await tester.tap(find.text('Próximo'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  });
}
