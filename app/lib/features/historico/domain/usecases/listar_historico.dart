import 'package:app/core/error/failures.dart';
import 'package:app/features/historico/domain/repositories/resposta_cache_repository.dart';
import 'package:app/features/historico/domain/resposta_salva.dart';
import 'package:fpdart/fpdart.dart';

/// Lista as respostas guardadas, da mais recente para a mais antiga.
class ListarHistorico {
  /// Cria o caso de uso.
  const new(this._repositorio);

  final RespostaCacheRepository _repositorio;

  /// Respostas guardadas.
  Future<Either<Failure, List<RespostaSalva>>> call() =>
      _repositorio.historico();
}
