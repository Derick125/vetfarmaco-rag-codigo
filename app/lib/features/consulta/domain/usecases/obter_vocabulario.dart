import 'package:app/core/error/failures.dart';
import 'package:app/features/consulta/domain/repositories/vocabulario_repository.dart';
import 'package:app/features/consulta/domain/vocabulario.dart';
import 'package:fpdart/fpdart.dart';

/// Obtém o vocabulário controlado para o formulário de consulta.
class ObterVocabulario {
  /// Cria o caso de uso.
  const new(this._repositorio);

  final VocabularioRepository _repositorio;

  /// Vocabulário do servidor ou, offline, da cópia local.
  Future<Either<Failure, Vocabulario>> call() => _repositorio.obter();
}
