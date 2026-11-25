import 'package:app/core/error/failures.dart';
import 'package:app/features/ajustes/domain/endereco_backend.dart';
import 'package:app/features/ajustes/domain/repositories/ajustes_repository.dart';
import 'package:fpdart/fpdart.dart';

/// Valida e grava o endereço do back-end.
class SalvarEnderecoBackend {
  /// Cria o caso de uso.
  const new(this._repositorio);

  final AjustesRepository _repositorio;

  /// Devolve o endereço normalizado que foi gravado.
  Future<Either<Failure, String>> call(String entrada) async {
    final endereco = normalizarEndereco(entrada);
    return switch (endereco) {
      Left(:final value) => Left(value),
      Right(:final value) => (await _repositorio.salvarEndereco(
        value,
      )).map((_) => value),
    };
  }
}
