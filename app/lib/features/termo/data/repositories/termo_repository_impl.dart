import 'package:app/core/error/failures.dart';
import 'package:app/features/bootstrap/data/repositories/configuracao_repository_impl.dart';
import 'package:app/features/termo/domain/repositories/termo_repository.dart';
import 'package:fpdart/fpdart.dart';
import 'package:hive_ce/hive_ce.dart';
import 'package:injectable/injectable.dart';

/// Implementação de [TermoRepository] sobre a caixa de configuração.
///
/// Usa a mesma chave que `ConfiguracaoRepositoryImpl.termoAceitoEm` lê.
@LazySingleton(as: TermoRepository)
class TermoRepositoryImpl implements TermoRepository {
  /// Cria o repositório a partir da caixa `hive_ce` de configuração.
  const new(this._caixa);

  final Box<dynamic> _caixa;

  @override
  Future<Either<Failure, DateTime?>> aceitoEm() async {
    try {
      return Right(_caixa.get(chaveTermoAceitoEm) as DateTime?);
    } on Object {
      return const Left(FalhaCache('Não foi possível ler o aceite do termo.'));
    }
  }

  @override
  Future<Either<Failure, Unit>> registrarAceite(DateTime quando) async {
    try {
      await _caixa.put(chaveTermoAceitoEm, quando);
      return const Right(unit);
    } on Object {
      return const Left(FalhaCache('Não foi possível gravar o aceite.'));
    }
  }
}
