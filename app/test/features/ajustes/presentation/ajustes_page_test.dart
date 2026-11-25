import 'package:app/core/error/failures.dart';
import 'package:app/features/ajustes/domain/usecases/obter_condicao_campanha.dart';
import 'package:app/features/ajustes/domain/usecases/obter_endereco_backend.dart';
import 'package:app/features/ajustes/domain/usecases/salvar_condicao_campanha.dart';
import 'package:app/features/ajustes/domain/usecases/salvar_endereco_backend.dart';
import 'package:app/features/ajustes/domain/usecases/testar_backend.dart';
import 'package:app/features/ajustes/presentation/cubit/ajustes_cubit.dart';
import 'package:app/features/ajustes/presentation/pages/ajustes_page.dart';
import 'package:app/features/telemetria/domain/condicao_campanha.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';

class _MockObter extends Mock implements ObterEnderecoBackend;

class _MockTestar extends Mock implements TestarBackend;

class _MockSalvar extends Mock implements SalvarEnderecoBackend;

class _MockObterCondicao extends Mock implements ObterCondicaoCampanha;

class _MockSalvarCondicao extends Mock implements SalvarCondicaoCampanha;

void main() {
  late _MockObter obter;
  late _MockTestar testar;
  late _MockSalvar salvar;
  late _MockSalvarCondicao salvarCondicao;
  late AjustesCubit cubit;

  setUpAll(() => registerFallbackValue(CondicaoCampanha.wifi));

  setUp(() {
    obter = _MockObter();
    testar = _MockTestar();
    salvar = _MockSalvar();
    when(obter.call).thenAnswer((_) async => 'http://10.0.2.2:8000');
    final obterCondicao = _MockObterCondicao();
    when(obterCondicao.call)
        .thenAnswer((_) async => CondicaoCampanha.naoInformada);
    salvarCondicao = _MockSalvarCondicao();
    when(() => salvarCondicao(any()))
        .thenAnswer((_) async => const Right(unit));
    cubit = AjustesCubit(obter, testar, salvar, obterCondicao, salvarCondicao);
  });

  tearDown(() => cubit.close());

  Widget app() => MaterialApp.router(
    routerConfig: GoRouter(
      initialLocation: '/ajustes',
      routes: [
        GoRoute(
          path: '/',
          builder: (_, _) => const Scaffold(body: Text('abertura')),
        ),
        GoRoute(
          path: '/ajustes',
          builder: (_, _) =>
              BlocProvider.value(value: cubit, child: const AjustesPage()),
        ),
        GoRoute(
          path: '/sobre',
          builder: (_, _) => const Scaffold(body: Text('tela sobre')),
        ),
      ],
    ),
  );

  testWidgets('preenche o campo com o endereço em vigor', (tester) async {
    await tester.pumpWidget(app());
    await tester.pumpAndSettle();
    final campo = tester.widget<TextField>(find.byType(TextField));
    expect(campo.controller!.text, 'http://10.0.2.2:8000');
  });

  testWidgets('Testar mostra "Back-end respondeu."', (tester) async {
    when(() => testar(any())).thenAnswer((_) async => const Right(unit));
    await tester.pumpWidget(app());
    await tester.pumpAndSettle();
    await tester.tap(find.text('Testar'));
    await tester.pumpAndSettle();
    expect(find.text('Back-end respondeu.'), findsOneWidget);
  });

  testWidgets('Testar com falha mostra a mensagem', (tester) async {
    when(() => testar(any()))
        .thenAnswer((_) async => const Left(FalhaRede('Sem conexão.')));
    await tester.pumpWidget(app());
    await tester.pumpAndSettle();
    await tester.tap(find.text('Testar'));
    await tester.pumpAndSettle();
    expect(find.text('Sem conexão.'), findsOneWidget);
  });

  testWidgets('Salvar grava o endereço digitado e volta à abertura', (
    tester,
  ) async {
    when(() => salvar(any()))
        .thenAnswer((_) async => const Right('http://novo:9000'));
    await tester.pumpWidget(app());
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'http://novo:9000');
    await tester.tap(find.text('Salvar'));
    await tester.pumpAndSettle();
    verify(() => salvar('http://novo:9000')).called(1);
    expect(find.text('abertura'), findsOneWidget);
  });

  testWidgets('seletor de condição de rede grava e permite desmarcar', (
    tester,
  ) async {
    await tester.pumpWidget(app());
    await tester.pumpAndSettle();
    expect(find.text('Condição de rede da campanha'), findsOneWidget);
    expect(find.text('Wi-Fi'), findsOneWidget);
    expect(find.text('4G'), findsOneWidget);
    expect(find.text('5G'), findsOneWidget);
    expect(find.text('Não informada'), findsNothing);

    await tester.ensureVisible(find.text('4G'));
    await tester.tap(find.text('4G'));
    await tester.pumpAndSettle();
    verify(() => salvarCondicao(CondicaoCampanha.g4)).called(1);
    expect(cubit.state.condicao, CondicaoCampanha.g4);

    await tester.tap(find.text('4G'));
    await tester.pumpAndSettle();
    verify(() => salvarCondicao(CondicaoCampanha.naoInformada)).called(1);
    expect(cubit.state.condicao, CondicaoCampanha.naoInformada);
  });

  testWidgets('Sobre o aplicativo abre a tela /sobre', (tester) async {
    await tester.pumpWidget(app());
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Sobre o aplicativo'));
    await tester.tap(find.text('Sobre o aplicativo'));
    await tester.pumpAndSettle();
    expect(find.text('tela sobre'), findsOneWidget);
  });
}
