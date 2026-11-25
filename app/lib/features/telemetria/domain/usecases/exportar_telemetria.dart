import 'package:app/core/error/failures.dart';
import 'package:app/features/telemetria/domain/csv_telemetria.dart';
import 'package:app/features/telemetria/domain/repositories/telemetria_repository.dart';
import 'package:fpdart/fpdart.dart';

/// Gera o CSV das medições e o entrega pela folha de compartilhamento.
class ExportarTelemetria {
  /// Cria o caso de uso.
  const new(this._repositorio, this._compartilhador);

  final TelemetriaRepository _repositorio;
  final CompartilhadorCsv _compartilhador;

  /// Exporta; devolve quantas consultas foram incluídas.
  Future<Either<Failure, int>> call() async {
    final lista = await _repositorio.listar();
    return switch (lista) {
      Left(:final value) => Left(value),
      Right(:final value) when value.isEmpty => const Left(
        FalhaValidacao('Ainda não há consultas registradas.'),
      ),
      Right(:final value) => (await _compartilhador.compartilhar(
        'telemetria_vetfarmaco.csv',
        gerarCsv(value),
      )).map((_) => value.length),
    };
  }
}
