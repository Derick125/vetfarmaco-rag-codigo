import 'package:app/core/error/failures.dart';
import 'package:app/features/telemetria/domain/registro_telemetria.dart';
import 'package:app/features/telemetria/domain/repositories/telemetria_repository.dart';
import 'package:fpdart/fpdart.dart';

/// Grava as medições de uma consulta.
class RegistrarTelemetria {
  /// Cria o caso de uso.
  const new(this._repositorio);

  final TelemetriaRepository _repositorio;

  /// Grava [registro].
  Future<Either<Failure, Unit>> call(RegistroTelemetria registro) =>
      _repositorio.gravar(registro);
}
