import 'package:app/features/bootstrap/domain/usecases/decidir_destino_inicial.dart';
import 'package:app/features/bootstrap/presentation/cubit/bootstrap_state.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:injectable/injectable.dart';

/// Decide o destino da tela de abertura (`docs/FRONTEND_SPEC.md` §7).
@injectable
class BootstrapCubit extends Cubit<BootstrapState> {
  /// Cria o cubit a partir do caso de uso de decisão de destino.
  new(this._decidirDestinoInicial) : super(const Carregando());

  final DecidirDestinoInicial _decidirDestinoInicial;

  /// Lê a configuração local e emite o estado terminal correspondente.
  Future<void> iniciar() async {
    final destino = await _decidirDestinoInicial();
    switch (destino) {
      case DestinoInicial.termo:
        emit(const ParaTermo());
      case DestinoInicial.consulta:
        emit(const ParaConsulta());
      case DestinoInicial.falhaConfig:
        emit(const FalhaConfig());
    }
  }
}
