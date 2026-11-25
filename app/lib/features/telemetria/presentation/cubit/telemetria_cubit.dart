import 'package:app/features/telemetria/domain/usecases/exportar_telemetria.dart';
import 'package:app/features/telemetria/domain/usecases/listar_telemetria.dart';
import 'package:app/features/telemetria/presentation/cubit/telemetria_state.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:injectable/injectable.dart';

/// Controla `/telemetria`: contagem e exportação do CSV.
@injectable
class TelemetriaCubit extends Cubit<TelemetriaState> {
  /// Cria o cubit.
  new(this._listar, this._exportar) : super(const TelemetriaState());

  final ListarTelemetria _listar;
  final ExportarTelemetria _exportar;

  /// Conta os registros gravados.
  Future<void> carregar() async {
    emit(const TelemetriaState());
    final r = await _listar();
    r.match(
      (f) => emit(
        TelemetriaState(status: StatusTelemetria.falha, mensagem: f.mensagem),
      ),
      (lista) => emit(
        TelemetriaState(status: StatusTelemetria.pronta, total: lista.length),
      ),
    );
  }

  /// Gera o CSV e abre o compartilhamento.
  Future<void> exportar() async {
    final total = state.total;
    emit(TelemetriaState(status: StatusTelemetria.exportando, total: total));
    final r = await _exportar();
    r.match(
      (f) => emit(
        TelemetriaState(
          status: StatusTelemetria.falha,
          total: total,
          mensagem: f.mensagem,
        ),
      ),
      (_) =>
          emit(TelemetriaState(status: StatusTelemetria.pronta, total: total)),
    );
  }
}
