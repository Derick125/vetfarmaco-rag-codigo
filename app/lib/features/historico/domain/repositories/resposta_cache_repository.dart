import 'package:app/core/error/failures.dart';
import 'package:app/features/historico/domain/resposta_salva.dart';
import 'package:fpdart/fpdart.dart';

/// Respostas guardadas no aparelho (`hive_ce`).
abstract interface class RespostaCacheRepository {
  /// Guarda [resposta], substituindo a anterior da mesma consulta.
  Future<Either<Failure, Unit>> salvar(RespostaSalva resposta);

  /// Resposta guardada para [chave], ou `null`.
  Future<Either<Failure, RespostaSalva?>> buscar(String chave);

  /// Todas as respostas, da mais recente para a mais antiga.
  Future<Either<Failure, List<RespostaSalva>>> historico();

  /// Remove a resposta de [chave].
  Future<Either<Failure, Unit>> remover(String chave);
}
