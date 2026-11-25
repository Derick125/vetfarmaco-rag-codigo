import 'package:app/core/error/failures.dart';
import 'package:app/features/historico/domain/repositories/resposta_cache_repository.dart';
import 'package:app/features/historico/domain/resposta_salva.dart';
import 'package:fpdart/fpdart.dart';

/// Guarda uma resposta no histórico.
class SalvarResposta {
  /// Cria o caso de uso.
  const new(this._repositorio);

  final RespostaCacheRepository _repositorio;

  /// Guarda [resposta].
  Future<Either<Failure, Unit>> call(RespostaSalva resposta) =>
      _repositorio.salvar(resposta);
}
