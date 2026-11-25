import 'package:app/core/error/failures.dart';
import 'package:app/features/ajustes/domain/endereco_backend.dart';
import 'package:app/features/ajustes/domain/repositories/ajustes_repository.dart';
import 'package:fpdart/fpdart.dart';

/// Verifica se o back-end responde em `/health`.
class TestarBackend {
  /// Cria o caso de uso.
  const new(this._repositorio);

  final AjustesRepository _repositorio;

  /// `Right(unit)` quando o back-end respondeu.
  Future<Either<Failure, Unit>> call(String entrada) {
    final endereco = normalizarEndereco(entrada);
    return switch (endereco) {
      Left(:final value) => Future.value(Left(value)),
      Right(:final value) => _repositorio.testarBackend(value),
    };
  }
}
