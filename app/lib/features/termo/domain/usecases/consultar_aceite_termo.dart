import 'package:app/core/error/failures.dart';
import 'package:app/features/termo/domain/repositories/termo_repository.dart';
import 'package:fpdart/fpdart.dart';

/// Informa se (e quando) o termo de uso foi aceito neste dispositivo.
class ConsultarAceiteTermo {
  /// Cria o caso de uso.
  const new(this._repositorio);

  final TermoRepository _repositorio;

  /// `Right(null)` quando ainda não aceito.
  Future<Either<Failure, DateTime?>> call() => _repositorio.aceitoEm();
}
