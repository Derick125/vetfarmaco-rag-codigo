import 'package:app/core/error/failures.dart';
import 'package:app/features/ajustes/domain/usecases/obter_condicao_campanha.dart';
import 'package:app/features/ajustes/domain/usecases/obter_endereco_backend.dart';
import 'package:app/features/ajustes/domain/usecases/salvar_condicao_campanha.dart';
import 'package:app/features/ajustes/domain/usecases/salvar_endereco_backend.dart';
import 'package:app/features/ajustes/domain/usecases/testar_backend.dart';
import 'package:app/features/ajustes/presentation/cubit/ajustes_cubit.dart';
import 'package:app/features/ajustes/presentation/cubit/ajustes_state.dart';
import 'package:app/features/telemetria/domain/condicao_campanha.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
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
  late _MockObterCondicao obterCondicao;
  late _MockSalvarCondicao salvarCondicao;

  setUpAll(() => registerFallbackValue(CondicaoCampanha.wifi));

  setUp(() {
    obter = _MockObter();
    testar = _MockTestar();
    salvar = _MockSalvar();
    obterCondicao = _MockObterCondicao();
    salvarCondicao = _MockSalvarCondicao();
    when(obterCondicao.call)
        .thenAnswer((_) async => CondicaoCampanha.naoInformada);
    when(() => salvarCondicao(any()))
        .thenAnswer((_) async => const Right(unit));
  });

  AjustesCubit build() =>
      AjustesCubit(obter, testar, salvar, obterCondicao, salvarCondicao);

  blocTest<AjustesCubit, AjustesState>(
    'carregar emite o endereço em vigor',
    setUp: () => when(obter.call).thenAnswer((_) async => 'http://x'),
    build: build,
    act: (c) => c.carregar(),
    expect: () => [const AjustesState(endereco: 'http://x')],
  );

  blocTest<AjustesCubit, AjustesState>(
    'carregar sem endereço emite vazio',
    setUp: () => when(obter.call).thenAnswer((_) async => null),
    build: build,
    act: (c) => c.carregar(),
    expect: () => [const AjustesState()],
  );

  blocTest<AjustesCubit, AjustesState>(
    'testar com sucesso emite testando e ok',
    setUp: () =>
        when(() => testar('http://x'))
            .thenAnswer((_) async => const Right(unit)),
    build: build,
    act: (c) => c.testar('http://x'),
    expect: () => [
      const AjustesState(status: StatusTeste.testando),
      const AjustesState(status: StatusTeste.ok),
    ],
  );

  blocTest<AjustesCubit, AjustesState>(
    'testar com falha emite testando e falha com a mensagem',
    setUp: () =>
        when(() => testar('http://x'))
            .thenAnswer((_) async => const Left(FalhaRede('sem rede'))),
    build: build,
    act: (c) => c.testar('http://x'),
    expect: () => [
      const AjustesState(status: StatusTeste.testando),
      const AjustesState(status: StatusTeste.falha, mensagem: 'sem rede'),
    ],
  );

  blocTest<AjustesCubit, AjustesState>(
    'salvar com sucesso emite salvo com o endereço normalizado',
    setUp: () =>
        when(() => salvar(' http://x/ '))
            .thenAnswer((_) async => const Right('http://x')),
    build: build,
    act: (c) => c.salvar(' http://x/ '),
    expect: () => [const AjustesState(endereco: 'http://x', salvo: true)],
  );

  blocTest<AjustesCubit, AjustesState>(
    'salvar endereço inválido emite falha',
    setUp: () =>
        when(() => salvar('lixo'))
            .thenAnswer((_) async => const Left(FalhaValidacao('inválido'))),
    build: build,
    act: (c) => c.salvar('lixo'),
    expect: () => [
      const AjustesState(status: StatusTeste.falha, mensagem: 'inválido'),
    ],
  );

  blocTest<AjustesCubit, AjustesState>(
    'carregar traz a condição de rede salva',
    setUp: () {
      when(obter.call).thenAnswer((_) async => 'http://x');
      when(obterCondicao.call).thenAnswer((_) async => CondicaoCampanha.g4);
    },
    build: build,
    act: (c) => c.carregar(),
    expect: () => [
      const AjustesState(endereco: 'http://x', condicao: CondicaoCampanha.g4),
    ],
  );

  blocTest<AjustesCubit, AjustesState>(
    'alterarCondicao grava e emite a nova condição',
    build: build,
    act: (c) => c.alterarCondicao(CondicaoCampanha.g5),
    expect: () => [const AjustesState(condicao: CondicaoCampanha.g5)],
    verify: (_) => verify(() => salvarCondicao(CondicaoCampanha.g5)).called(1),
  );

  blocTest<AjustesCubit, AjustesState>(
    'escolher a condição já marcada a desmarca',
    build: build,
    seed: () => const AjustesState(condicao: CondicaoCampanha.wifi),
    act: (c) => c.alterarCondicao(CondicaoCampanha.wifi),
    expect: () => [const AjustesState()],
    verify: (_) =>
        verify(() => salvarCondicao(CondicaoCampanha.naoInformada)).called(1),
  );

  blocTest<AjustesCubit, AjustesState>(
    'falha ao gravar a condição mostra a mensagem e mantém a anterior',
    setUp: () =>
        when(() => salvarCondicao(any()))
            .thenAnswer((_) async => const Left(FalhaCache('sem disco'))),
    build: build,
    seed: () => const AjustesState(condicao: CondicaoCampanha.wifi),
    act: (c) => c.alterarCondicao(CondicaoCampanha.g4),
    expect: () => [
      const AjustesState(
        condicao: CondicaoCampanha.wifi,
        status: StatusTeste.falha,
        mensagem: 'sem disco',
      ),
    ],
  );
}
