import 'package:app/core/error/failures.dart';
import 'package:app/features/ajustes/domain/endereco_backend.dart';
import 'package:app/features/ajustes/domain/repositories/ajustes_repository.dart';
import 'package:app/features/ajustes/domain/usecases/obter_endereco_backend.dart';
import 'package:app/features/ajustes/domain/usecases/salvar_endereco_backend.dart';
import 'package:app/features/ajustes/domain/usecases/testar_backend.dart';
import 'package:app/features/bootstrap/domain/repositories/configuracao_repository.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mocktail/mocktail.dart';

class _MockAjustes extends Mock implements AjustesRepository;

class _MockConfig extends Mock implements ConfiguracaoRepository;

void main() {
  group('normalizarEndereco', () {
    test('remove espaços e barras finais', () {
      expect(
        normalizarEndereco('  http://10.0.2.2:8000// '),
        const Right<Failure, String>('http://10.0.2.2:8000'),
      );
    });

    test('aceita https', () {
      expect(normalizarEndereco('https://api.exemplo.app').isRight(), isTrue);
    });

    for (final ruim in ['', 'abc', '10.0.2.2:8000', 'ftp://x.com', 'http://']) {
      test('rejeita "$ruim"', () {
        final r = normalizarEndereco(ruim);
        expect(r.getLeft().toNullable(), isA<FalhaValidacao>());
      });
    }
  });

  group('SalvarEnderecoBackend', () {
    late _MockAjustes repo;
    setUp(() => repo = _MockAjustes());

    test('grava o endereço normalizado e o devolve', () async {
      when(() => repo.salvarEndereco(any()))
          .thenAnswer((_) async => const Right(unit));
      final r = await SalvarEnderecoBackend(repo)(' http://x.com/ ');
      expect(r, const Right<Failure, String>('http://x.com'));
      verify(() => repo.salvarEndereco('http://x.com')).called(1);
    });

    test('endereço inválido não chega ao repositório', () async {
      final r = await SalvarEnderecoBackend(repo)('lixo');
      expect(r.isLeft(), isTrue);
      verifyNever(() => repo.salvarEndereco(any()));
    });

    test('propaga falha de gravação', () async {
      when(() => repo.salvarEndereco(any()))
          .thenAnswer((_) async => const Left(FalhaCache('x')));
      final r = await SalvarEnderecoBackend(repo)('http://x.com');
      expect(r, const Left<Failure, String>(FalhaCache('x')));
    });
  });

  group('TestarBackend', () {
    late _MockAjustes repo;
    setUp(() => repo = _MockAjustes());

    test('testa o endereço normalizado', () async {
      when(() => repo.testarBackend(any()))
          .thenAnswer((_) async => const Right(unit));
      final r = await TestarBackend(repo)('http://x.com/');
      expect(r.isRight(), isTrue);
      verify(() => repo.testarBackend('http://x.com')).called(1);
    });

    test('endereço inválido não chama o repositório', () async {
      final r = await TestarBackend(repo)('lixo');
      expect(r.getLeft().toNullable(), isA<FalhaValidacao>());
      verifyNever(() => repo.testarBackend(any()));
    });

    test('propaga falha de rede', () async {
      when(() => repo.testarBackend(any()))
          .thenAnswer((_) async => const Left(FalhaRede('x')));
      final r = await TestarBackend(repo)('http://x.com');
      expect(r, const Left<Failure, Unit>(FalhaRede('x')));
    });
  });

  test('ObterEnderecoBackend delega à configuração', () async {
    final config = _MockConfig();
    when(config.enderecoBackend).thenAnswer((_) async => 'http://x.com');
    expect(await ObterEnderecoBackend(config)(), 'http://x.com');
  });
}
