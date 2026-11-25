import 'package:app/core/error/failures.dart';
import 'package:app/features/historico/domain/repositories/resposta_cache_repository.dart';
import 'package:fpdart/fpdart.dart';

/// Remove uma resposta do histórico.
class RemoverRespostaSalva {
  /// Cria o caso de uso.
  const new(this._repositorio);

  final RespostaCacheRepository _repositorio;

  /// Remove a resposta de [chave].
  Future<Either<Failure, Unit>> call(String chave) =>
      _repositorio.remover(chave);
}
