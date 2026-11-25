import 'package:app/core/error/failures.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/historico/domain/repositories/resposta_cache_repository.dart';
import 'package:app/features/historico/domain/resposta_salva.dart';
import 'package:fpdart/fpdart.dart';

/// Procura uma resposta guardada para a mesma consulta.
class BuscarRespostaSalva {
  /// Cria o caso de uso.
  const new(this._repositorio);

  final RespostaCacheRepository _repositorio;

  /// Resposta guardada para [corpo], ou `null`.
  Future<Either<Failure, RespostaSalva?>> call(CorpoConsulta corpo) =>
      _repositorio.buscar(chaveDaConsulta(corpo));
}
