import 'package:app/core/error/failures.dart';
import 'package:app/features/termo/domain/repositories/termo_repository.dart';
import 'package:app/features/termo/domain/usecases/aceitar_termo.dart';
import 'package:app/features/termo/domain/usecases/consultar_aceite_termo.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mocktail/mocktail.dart';

class _MockTermoRepository extends Mock implements TermoRepository;

void main() {
  late _MockTermoRepository repo;
  final instante = DateTime(2026, 10, 2, 9);

  setUp(() {
    repo = _MockTermoRepository();
    registerFallbackValue(instante);
  });

  group('ConsultarAceiteTermo', () {
    test('devolve a data do aceite', () async {
      when(repo.aceitoEm).thenAnswer((_) async => Right(instante));
      expect(
        await ConsultarAceiteTermo(repo)(),
        Right<Failure, DateTime?>(instante),
      );
    });

    test('devolve Right(null) quando não aceito', () async {
      when(repo.aceitoEm).thenAnswer((_) async => const Right(null));
      expect(
        await ConsultarAceiteTermo(repo)(),
        const Right<Failure, DateTime?>(null),
      );
    });

    test('propaga a falha do repositório', () async {
      when(repo.aceitoEm).thenAnswer((_) async => const Left(FalhaCache('x')));
      expect(
        await ConsultarAceiteTermo(repo)(),
        const Left<Failure, DateTime?>(FalhaCache('x')),
      );
    });
  });

  group('AceitarTermo', () {
    test('grava e devolve o instante do relógio injetado', () async {
      when(() => repo.registrarAceite(any()))
          .thenAnswer((_) async => const Right(unit));
      final r = await AceitarTermo(repo, agora: () => instante)();
      expect(r, Right<Failure, DateTime>(instante));
      verify(() => repo.registrarAceite(instante)).called(1);
    });

    test('propaga a falha de gravação', () async {
      when(() => repo.registrarAceite(any()))
          .thenAnswer((_) async => const Left(FalhaCache('x')));
      final r = await AceitarTermo(repo, agora: () => instante)();
      expect(r, const Left<Failure, DateTime>(FalhaCache('x')));
    });
  });
}
