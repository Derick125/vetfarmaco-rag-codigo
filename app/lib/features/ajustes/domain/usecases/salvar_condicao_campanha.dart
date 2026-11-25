import 'package:app/core/error/failures.dart';
import 'package:app/features/ajustes/domain/repositories/ajustes_repository.dart';
import 'package:app/features/telemetria/domain/condicao_campanha.dart';
import 'package:fpdart/fpdart.dart';

/// Grava a condição de rede da campanha.
class SalvarCondicaoCampanha {
  /// Cria o caso de uso.
  const new(this._repositorio);

  final AjustesRepository _repositorio;

  /// Grava [condicao].
  Future<Either<Failure, Unit>> call(CondicaoCampanha condicao) =>
      _repositorio.salvarCondicaoCampanha(condicao);
}
