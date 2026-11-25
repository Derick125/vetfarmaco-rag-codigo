import 'package:app/core/error/failures.dart';
import 'package:app/features/telemetria/domain/registro_telemetria.dart';
import 'package:app/features/telemetria/domain/repositories/telemetria_repository.dart';
import 'package:fpdart/fpdart.dart';

/// Lista as medições gravadas.
class ListarTelemetria {
  /// Cria o caso de uso.
  const new(this._repositorio);

  final TelemetriaRepository _repositorio;

  /// Registros gravados.
  Future<Either<Failure, List<RegistroTelemetria>>> call() =>
      _repositorio.listar();
}
