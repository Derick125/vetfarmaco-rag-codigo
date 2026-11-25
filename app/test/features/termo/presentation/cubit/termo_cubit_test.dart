import 'package:app/core/error/failures.dart';
import 'package:app/features/termo/domain/usecases/aceitar_termo.dart';
import 'package:app/features/termo/domain/usecases/consultar_aceite_termo.dart';
import 'package:app/features/termo/presentation/cubit/termo_cubit.dart';
import 'package:app/features/termo/presentation/cubit/termo_state.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mocktail/mocktail.dart';

class _MockConsultar extends Mock implements ConsultarAceiteTermo;

class _MockAceitar extends Mock implements AceitarTermo;

void main() {
  late _MockConsultar consultar;
  late _MockAceitar aceitar;
  final instante = DateTime(2026, 10, 2, 9);

  setUp(() {
    consultar = _MockConsultar();
    aceitar = _MockAceitar();
  });

  blocTest<TermoCubit, TermoState>(
    'carregar com aceite persistido emite Aceito',
    setUp: () => when(consultar.call).thenAnswer((_) async => Right(instante)),
    build: () => TermoCubit(consultar, aceitar),
    act: (c) => c.carregar(),
    expect: () => [Aceito(instante)],
  );

  blocTest<TermoCubit, TermoState>(
    'carregar sem aceite emite NaoAceito',
    setUp: () =>
        when(consultar.call).thenAnswer((_) async => const Right(null)),
    build: () => TermoCubit(consultar, aceitar),
    act: (c) => c.carregar(),
    expect: () => [const NaoAceito()],
  );

  blocTest<TermoCubit, TermoState>(
    'carregar com falha emite NaoAceito com a falha',
    setUp: () =>
        when(consultar.call)
            .thenAnswer((_) async => const Left(FalhaCache('x'))),
    build: () => TermoCubit(consultar, aceitar),
    act: (c) => c.carregar(),
    expect: () => [const NaoAceito(falha: FalhaCache('x'))],
  );

  blocTest<TermoCubit, TermoState>(
    'aceitar emite Aceito com o instante gravado',
    setUp: () => when(aceitar.call).thenAnswer((_) async => Right(instante)),
    build: () => TermoCubit(consultar, aceitar),
    act: (c) => c.aceitar(),
    expect: () => [Aceito(instante)],
  );

  blocTest<TermoCubit, TermoState>(
    'aceitar com falha de gravação emite NaoAceito com a falha',
    setUp: () =>
        when(aceitar.call).thenAnswer((_) async => const Left(FalhaCache('y'))),
    build: () => TermoCubit(consultar, aceitar),
    act: (c) => c.aceitar(),
    expect: () => [const NaoAceito(falha: FalhaCache('y'))],
  );
}
